"""Codex CLI backend for the Apple II terminal bridge."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: omit the optional effort label
    tomllib = None


MIN_CODEX_VERSION = (0, 144, 1)


def _parse_codex_version(raw: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
    return tuple(map(int, match.groups())) if match else None


def codex_version(codex_bin: str = "codex") -> tuple[int, int, int] | None:
    """Return the installed Codex CLI version, or None when unavailable."""
    try:
        result = subprocess.run(
            [codex_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    return _parse_codex_version(result.stdout)


def _redact_stderr(value: str) -> str:
    value = re.sub(r"(?i)(bearer\s+)[^\s]+", r"\1[redacted]", value)
    value = re.sub(r"(?i)(token\s*[=:]\s*)[^\s]+", r"\1[redacted]", value)
    return value

def abbrev_cwd(path: str | None) -> str:
    home = os.path.expanduser("~")
    if path and path.startswith(home):
        return "~" + path[len(home):]
    return path or ""


def _doctor_model(codex_bin: str, sandbox: str) -> str | None:
    """Read Codex's resolved model from its redacted diagnostic report."""
    result = subprocess.run(
        [
            codex_bin,
            "doctor",
            "--json",
            "-c",
            f'sandbox_mode="{sandbox}"',
            "-c",
            'approval_policy="never"',
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        return None
    report = json.loads(result.stdout)
    value = (
        report.get("checks", {})
        .get("config.load", {})
        .get("details", {})
        .get("model")
    )
    return value if isinstance(value, str) and value.strip() else None


def _configured_effort() -> str | None:
    """Read only the optional top-level reasoning-effort setting."""
    if tomllib is None:
        return None
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    with (home / "config.toml").open("rb") as stream:
        value = tomllib.load(stream).get("model_reasoning_effort")
    return value if isinstance(value, str) and value.strip() else None

class Backend:
    name = "backend"

    def stream(self, user_text: str) -> Iterator[str]:
        raise NotImplementedError

    def reset(self) -> None:
        pass

    def begin_turn(self) -> None:
        """Synchronously establish a new cancellation boundary.

        Callers invoke this before handing stream() to a worker, so a cancel
        arriving before the generator's first iteration cannot be erased.
        """
        pass

    def footer(self) -> str | None:
        """Optional one-line status shown after a reply (e.g. 'Worked for 4m 41s').
        Returns None when there's nothing to show."""
        return None

    def header(self) -> tuple[str, ...] | None:
        """Optional header lines for the client. None to leave it."""
        return None

    def prime(self) -> None:
        """Optional: fetch header/model info before the first user message."""
        pass

    def cancel(self) -> None:
        """Stop an in-flight stream() early (the client sent Ctrl-C). Safe to
        call from another thread; a backend that can't cancel just ignores it."""
        pass


class CodexBackend(Backend):
    """Map non-interactive Codex JSONL events onto the terminal backend API."""

    name = "codex"

    def __init__(self, cols: int, model: str | None, codex_bin: str,
                 cwd: str, sandbox: str, show_tools: bool) -> None:
        self._cols = cols
        self._model = model
        self._resolved_model: str | None = None
        self._reasoning_effort: str | None = None
        self._bin = codex_bin
        self._cwd = cwd
        self._sandbox = sandbox
        self._show_tools = show_tools
        self._thread_id: str | None = None
        self._proc: subprocess.Popen | None = None
        self._state_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._cancelled = False
        self._last_duration_ms: int | None = None
        self._last_output_tokens: int | None = None
        self._turn_started: float | None = None

    def prime(self) -> None:
        """Resolve display-only Codex settings without delaying startup on error."""
        if not self._model:
            try:
                self._resolved_model = _doctor_model(self._bin, self._sandbox)
            except (OSError, subprocess.SubprocessError, ValueError, TypeError):
                self._resolved_model = None
        try:
            self._reasoning_effort = _configured_effort()
        except (OSError, ValueError, TypeError):
            self._reasoning_effort = None

    def _build_cmd(self) -> list[str]:
        cmd = [self._bin, "exec"]
        if self._thread_id:
            cmd.append("resume")
        cmd += ["--json"]
        if not self._thread_id:
            # `codex exec resume` supports JSONL but not the parent command's
            # --color option (Codex CLI 0.144.1).
            cmd += ["--color", "never"]
        cmd += [
            "-c",
            f'sandbox_mode="{self._sandbox}"',
            "-c",
            'approval_policy="never"',
        ]
        if self._model:
            cmd += ["--model", self._model]
        if self._thread_id:
            cmd.append(self._thread_id)
        cmd.append("-")
        return cmd

    def reset(self) -> None:
        self._thread_id = None

    def begin_turn(self) -> None:
        with self._state_lock:
            self._cancelled = False
            self._cancel_event.clear()

    def cancel(self) -> None:
        with self._state_lock:
            self._cancelled = True
            self._cancel_event.set()
            proc = self._proc
        if proc is not None:
            _kill_process_group(proc)

    def stream(self, user_text: str) -> Iterator[str]:
        resumed = self._thread_id is not None
        self._last_duration_ms = None
        self._last_output_tokens = None
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                self._build_cmd(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self._cwd,
                start_new_session=True,
            )
        except FileNotFoundError:
            print(
                f"[bridge] codex binary not found: {self._bin!r}",
                file=sys.stderr,
                flush=True,
            )
            yield "\n[Codex CLI not found on the host]"
            return

        with self._state_lock:
            self._proc = proc
            cancelled_during_start = self._cancel_event.is_set()
        if cancelled_during_start:
            _kill_process_group(proc)

        err_parts: list[str] = []

        def _drain_err(p=proc) -> None:
            try:
                if p.stderr is not None:
                    for chunk in iter(lambda: p.stderr.read(4096), ""):
                        err_parts.append(chunk)
            except Exception:
                pass

        err_thread = threading.Thread(target=_drain_err, daemon=True)
        err_thread.start()

        try:
            if proc.stdin is not None:
                try:
                    proc.stdin.write(user_text)
                    proc.stdin.close()
                except BrokenPipeError:
                    pass

            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        "[bridge] ignored malformed Codex JSONL event",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue
                yield from self._render_event(event)

            proc.wait()
            err_thread.join(timeout=1.0)
            stderr = "".join(err_parts).strip()
            if self._cancelled:
                return
            if proc.returncode not in (0, None):
                if stderr:
                    print(
                        f"[bridge] codex stderr: {_redact_stderr(stderr)}",
                        file=sys.stderr,
                        flush=True,
                    )
                if resumed:
                    self._thread_id = None
                    yield (
                        "\n[Codex could not resume this thread; "
                        "next prompt starts a fresh thread]"
                    )
                elif re.search(
                    r"not authenticated|codex login|authentication", stderr, re.I
                ):
                    yield "\n[Codex is not logged in; run codex login on the host]"
                else:
                    yield f"\n[Codex exited {proc.returncode}; see the bridge console]"
        finally:
            self._last_duration_ms = round((time.monotonic() - started) * 1000)
            with self._state_lock:
                if self._proc is proc:
                    self._proc = None

    def header(self) -> tuple[str, ...]:
        version = codex_version(self._bin)
        label = ".".join(map(str, version)) if version else "?"
        model = self._model or self._resolved_model or "default model"
        if self._reasoning_effort:
            model += f" {self._reasoning_effort}"
        model_line = f"model: {model}"
        if self._cols >= 80:
            model_line += "   /model to change"
        permissions = (
            "YOLO mode"
            if self._sandbox == "danger-full-access"
            else f"{self._sandbox} / never"
        )
        return (
            f">_ OpenAI Codex (v{label})",
            model_line,
            f"directory: {abbrev_cwd(self._cwd)}",
            f"permissions: {permissions}",
        )

    def footer(self) -> str | None:
        if self._last_duration_ms is None:
            return None
        seconds = round(self._last_duration_ms / 1000)
        elapsed = (
            f"{seconds // 60}m {seconds % 60}s"
            if seconds >= 60
            else f"{seconds}s"
        )
        footer = f"Worked for {elapsed}"
        if self._last_output_tokens:
            if self._last_output_tokens >= 1000:
                tokens = (
                    f"{self._last_output_tokens / 1000:.1f}".rstrip("0").rstrip(".")
                    + "k"
                )
            else:
                tokens = str(self._last_output_tokens)
            footer += f" - {tokens} tokens"
        return footer

    def _render_event(self, event: dict) -> Iterator[str]:
        etype = event.get("type")
        if etype == "thread.started":
            self._thread_id = event.get("thread_id") or self._thread_id
        elif etype == "turn.started":
            self._turn_started = time.monotonic()
        elif etype == "turn.completed":
            usage = event.get("usage") or {}
            self._last_output_tokens = usage.get("output_tokens")
        elif etype in ("turn.failed", "error"):
            error = event.get("error") or {}
            detail = error.get("message") if isinstance(error, dict) else error
            if detail:
                print(
                    f"[bridge] Codex {etype}: {_redact_stderr(str(detail))}",
                    file=sys.stderr,
                    flush=True,
                )
            yield "\n[Codex request failed; see the bridge console]"
        elif etype in ("item.started", "item.completed"):
            item = event.get("item") or {}
            kind = item.get("type")
            if etype == "item.completed" and kind == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    yield text
            elif self._show_tools:
                summary = self._tool_summary(item)
                if summary:
                    yield f"[{summary}]\n"
            if kind not in {
                "agent_message",
                "reasoning",
                "command_execution",
                "file_change",
                "web_search",
                "mcp_tool_call",
                "todo_list",
            }:
                print(
                    f"[bridge] ignored unknown Codex item: {kind!r}",
                    file=sys.stderr,
                    flush=True,
                )
        else:
            print(
                f"[bridge] ignored unknown Codex event: {etype!r}",
                file=sys.stderr,
                flush=True,
            )

    def _tool_summary(self, item: dict) -> str | None:
        kind = item.get("type")
        if kind == "command_execution":
            value = item.get("command") or "command"
        elif kind == "file_change":
            changes = item.get("changes") or []
            value = (
                f"changed {changes[0].get('path', 'file')}"
                if changes
                else "changed file"
            )
        elif kind == "web_search":
            value = f"searched {item.get('query', 'web')}"
        elif kind == "mcp_tool_call":
            value = f"{item.get('server', 'MCP')}/{item.get('tool', 'tool')}"
        elif kind == "todo_list":
            entries = item.get("items") or []
            complete = sum(bool(entry.get("completed")) for entry in entries)
            value = f"plan {complete}/{len(entries)}"
        else:
            return None
        limit = max(8, self._cols - 4)
        return value if len(value) <= limit else value[:limit - 3] + "..."



def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _kill_process_group(proc: subprocess.Popen, grace: float = 2.0) -> None:
    pgid = proc.pid  # start_new_session=True makes the leader PID the PGID

    def _signal_group(sig) -> None:
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _wait_group(timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            proc.poll()  # reap an exited leader; surviving children keep the PGID live
            if not _process_group_exists(pgid):
                return True
            time.sleep(0.02)
        proc.poll()
        return not _process_group_exists(pgid)

    _signal_group(signal.SIGTERM)
    if not _wait_group(grace):
        _signal_group(signal.SIGKILL)
        _wait_group(grace)
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
