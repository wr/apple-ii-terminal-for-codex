import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import backends


pytestmark = pytest.mark.codex_live


def _backend(repo: Path, sandbox: str = "workspace-write") -> backends.CodexBackend:
    return backends.CodexBackend(
        cols=80,
        model=None,
        codex_bin=shutil.which("codex") or "codex",
        cwd=str(repo),
        sandbox=sandbox,
        show_tools=False,
    )


def _turn(be: backends.CodexBackend, prompt: str) -> str:
    be.begin_turn()
    return "".join(be.stream(prompt))


def _git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _live_cancel_probe(repo: Path) -> dict:
    script = r'''
import json
import sys
import threading
import time
import backends

repo, codex_bin = sys.argv[1:]
be = backends.CodexBackend(80, None, codex_bin, repo, "workspace-write", False)
be.begin_turn()
list(be.stream("Reply with only READY."))
original = be._thread_id
assert original

def consume():
    be.begin_turn()
    list(be.stream("Run a shell command that sleeps for 60 seconds, wait for it, then reply done."))

worker = threading.Thread(target=consume, daemon=True)
worker.start()
deadline = time.monotonic() + 20
while be._proc is None and time.monotonic() < deadline:
    time.sleep(0.05)
proc = be._proc
assert proc is not None
pgid = proc.pid
time.sleep(1)
be.cancel()
worker.join(10)
assert not worker.is_alive()
assert not backends._process_group_exists(pgid)
be.begin_turn()
resume_output = "".join(be.stream("Reply with only READY."))
print(json.dumps({"original": original, "thread": be._thread_id, "output": resume_output}))
'''
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(repo),
            shutil.which("codex") or "codex",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
        start_new_session=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(
    os.environ.get("RUN_CODEX_LIVE") != "1",
    reason="set RUN_CODEX_LIVE=1 to use the authenticated Codex CLI",
)
def test_authenticated_first_turn_and_resume(tmp_path):
    repo = _git_repo(tmp_path / "write-repo")
    be = _backend(repo)

    first = _turn(
        be,
        "Create inside.txt containing exactly APPLEII_CODEX, then reply with its name.",
    )
    assert (repo / "inside.txt").read_text().strip() == "APPLEII_CODEX"
    assert "inside.txt" in first
    original_thread = be._thread_id
    assert original_thread

    resumed = _turn(be, "Reply with the filename you created in the previous turn.")
    assert "inside.txt" in resumed
    assert be._thread_id == original_thread



@pytest.mark.skipif(
    os.environ.get("RUN_CODEX_LIVE") != "1",
    reason="set RUN_CODEX_LIVE=1 to use the authenticated Codex CLI",
)
def test_authenticated_read_only_denies_write(tmp_path):
    read_only_repo = _git_repo(tmp_path / "read-only-repo")
    read_only = _backend(read_only_repo, sandbox="read-only")
    _turn(read_only, "Create forbidden.txt containing NO, then reply when finished.")
    assert not (read_only_repo / "forbidden.txt").exists()


@pytest.mark.skipif(
    os.environ.get("RUN_CODEX_LIVE") != "1",
    reason="set RUN_CODEX_LIVE=1 to use the authenticated Codex CLI",
)
@pytest.mark.skipif(
    bool(os.environ.get("CODEX_THREAD_ID"))
    or os.environ.get("SKIP_CODEX_LIVE_CANCEL") == "1",
    reason="cancellation probe disabled in a nested Codex task",
)
def test_authenticated_cancel_and_recover(tmp_path):
    repo = _git_repo(tmp_path / "cancel-repo")
    cancel_result = _live_cancel_probe(repo)
    resume_output = cancel_result["output"]
    assert "READY" in resume_output or "next prompt starts a fresh thread" in resume_output
    assert (
        cancel_result["thread"] == cancel_result["original"]
        or (
            cancel_result["thread"] is None
            and "next prompt starts a fresh thread" in resume_output
        )
    )
