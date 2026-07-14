import json
import os
from pathlib import Path
import threading
import time

import pytest

import backends


FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def backend(**overrides):
    values = dict(
        cols=80,
        model=None,
        codex_bin="codex",
        cwd="/tmp/repo",
        sandbox="workspace-write",
        show_tools=False,
    )
    values.update(overrides)
    return backends.CodexBackend(**values)


def test_first_turn_argv_uses_stdin_and_fail_closed_config():
    assert backend()._build_cmd() == [
        "codex",
        "exec",
        "--json",
        "--color",
        "never",
        "-c",
        'sandbox_mode="workspace-write"',
        "-c",
        'approval_policy="never"',
        "-",
    ]


def test_resume_argv_repeats_model_and_permissions():
    be = backend(model="gpt-5.4", sandbox="read-only")
    be._thread_id = "019-test-thread"
    assert be._build_cmd() == [
        "codex",
        "exec",
        "resume",
        "--json",
        "--color",
        "never",
        "-c",
        'sandbox_mode="read-only"',
        "-c",
        'approval_policy="never"',
        "--model",
        "gpt-5.4",
        "019-test-thread",
        "-",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("codex-cli 0.144.1", (0, 144, 1)),
        ("codex-cli 1.2.3\n", (1, 2, 3)),
        ("garbage", None),
    ],
)
def test_parse_codex_version(raw, expected):
    assert backends._parse_codex_version(raw) == expected


def test_first_turn_fixture_emits_only_agent_message_and_saves_metadata():
    be = backend()
    output = []
    for raw in (FIXTURES / "first-turn.jsonl").read_text().splitlines():
        output.extend(be._render_event(json.loads(raw)))
    assert "".join(output) == "Done. I changed one file."
    assert be._thread_id == "019-test-thread"
    assert be._last_output_tokens == 9
    assert "private" not in "".join(output)


def test_tool_fixture_is_quiet_in_app_and_summarized_in_raw_mode():
    events = [
        json.loads(line)
        for line in (FIXTURES / "tool-turn.jsonl").read_text().splitlines()
    ]
    quiet = backend(show_tools=False)
    loud = backend(show_tools=True)
    assert "".join(x for event in events for x in quiet._render_event(event)) == (
        "All tests pass."
    )
    rendered = "".join(x for event in events for x in loud._render_event(event))
    assert "pytest -q" in rendered
    assert "bridge.py" in rendered
    assert "All tests pass." in rendered


def test_header_and_footer_are_codex_specific(monkeypatch):
    monkeypatch.setattr(backends, "codex_version", lambda _bin: (0, 144, 1))
    be = backend(model="gpt-5.4", cwd="/tmp/repo")
    be._last_duration_ms = 2300
    be._last_output_tokens = 1200
    assert be.header() == ("Codex CLI v0.144.1", "gpt-5.4", "/tmp/repo")
    assert be.footer() == "Worked for 2s - 1.2k tokens"


def fake_backend(tmp_path, **overrides):
    return backend(
        codex_bin=str(Path(__file__).parent / "fixtures" / "fake_codex.py"),
        cwd=str(tmp_path),
        **overrides,
    )


def test_stream_sends_prompt_only_on_stdin(tmp_path, monkeypatch):
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    be = fake_backend(tmp_path)
    be.begin_turn()
    assert "".join(be.stream("secret prompt")) == "received:secret prompt"
    saved = json.loads(record.read_text())
    assert saved["stdin"] == "secret prompt"
    assert "secret prompt" not in saved["argv"]


def test_auth_error_is_short_and_secret_free(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_CODEX_MODE", "auth")
    be = fake_backend(tmp_path)
    output = "".join(be.stream("hello"))
    assert output == "\n[Codex is not logged in; run codex login on the host]"
    assert "secret" not in output
    host_error = capsys.readouterr().err
    assert "Not authenticated" in host_error
    assert "token=secret" not in host_error


def test_failed_resume_clears_thread_and_explains_next_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_MODE", "resume-fail")
    be = fake_backend(tmp_path)
    be._thread_id = "fake-thread"
    output = "".join(be.stream("continue"))
    assert "next prompt starts a fresh thread" in output
    assert be._thread_id is None


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _wait_dead(pid, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.02)
    return not _alive(pid)


def test_cancel_kills_codex_and_child_process(tmp_path, monkeypatch):
    child_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CODEX_MODE", "child")
    monkeypatch.setenv("FAKE_CODEX_CHILD_PID", str(child_file))
    be = fake_backend(tmp_path)
    be.begin_turn()
    output = []
    worker = threading.Thread(target=lambda: output.extend(be.stream("wait")))
    worker.start()
    deadline = time.monotonic() + 3
    while not child_file.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert child_file.exists(), "fake Codex child never started"
    child_pid = int(child_file.read_text())
    assert be._proc is not None
    leader_pid = be._proc.pid
    be.cancel()
    worker.join(5)
    assert not worker.is_alive()
    assert _wait_dead(leader_pid)
    assert _wait_dead(child_pid)
    assert output == []


def test_unknown_event_is_client_silent_and_host_visible(capsys):
    be = backend()
    assert list(be._render_event({"type": "future.event", "payload": {}})) == []
    assert "future.event" in capsys.readouterr().err


def test_failed_turn_detail_is_redacted_on_host(capsys):
    be = backend()
    event = {
        "type": "turn.failed",
        "error": {"message": "request failed with bearer sk-secret-value"},
    }
    output = "".join(be._render_event(event))
    assert output == "\n[Codex request failed; see the bridge console]"
    host_error = capsys.readouterr().err
    assert "request failed" in host_error
    assert "sk-secret-value" not in host_error
    assert "[redacted]" in host_error
