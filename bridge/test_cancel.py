"""Tests for W-528: real Ctrl-C cancellation + idle-connection timeout.

Plain assert-script (not pytest). Covers what's exercisable without a live
Codex process or a real Apple II:

  * _kill_process_group takes down a whole process group (no orphaned child),
  * and escalates SIGTERM -> SIGKILL when the leader ignores SIGTERM,
  * CodexBackend.cancel routes through the group kill,
  * _IdleGuard drops a silent peer, resets on bytes, and stops on disarm.
"""
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backends
import bridge


def _backend(codex_bin=sys.executable):
    return backends.CodexBackend(
        cols=80,
        model=None,
        codex_bin=codex_bin,
        cwd=os.getcwd(),
        sandbox="workspace-write",
        show_tools=False,
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal


def _wait_dead(pid: int, timeout: float = 3.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if not _alive(pid):
            return True
        time.sleep(0.02)
    return not _alive(pid)


# --------------------------------------------------------------------------- #
# _kill_process_group: whole-group kill, no orphans
# --------------------------------------------------------------------------- #
def test_kill_group_no_orphans() -> None:
    # A parent that forks a child, prints the child's PID, then sleeps. Both
    # live in the parent's process group (start_new_session gives the parent a
    # fresh one). Killing the group must take out the child too.
    parent_src = (
        "import subprocess, sys, time;"
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(999)']);"
        "print(c.pid, flush=True);"
        "time.sleep(999)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_src],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    child_pid = int(proc.stdout.readline())
    assert _alive(proc.pid) and _alive(child_pid), "parent+child should be up"

    backends._kill_process_group(proc, grace=2.0)

    assert _wait_dead(proc.pid), "parent (Codex stand-in) survived the kill"
    assert _wait_dead(child_pid), "CHILD orphaned - group kill missed it"
    print("PASS: _kill_process_group takes down the whole group (no orphans)")


def test_kill_group_escalates_to_sigkill() -> None:
    # A process that ignores SIGTERM and has no children: SIGTERM alone can't
    # stop it, so the helper must wait the grace and then SIGKILL.
    ign_src = (
        "import signal, time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "time.sleep(999)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", ign_src], start_new_session=True,
    )
    time.sleep(0.3)  # let it install the SIG_IGN handler
    assert _alive(proc.pid)

    grace = 0.5
    t0 = time.monotonic()
    backends._kill_process_group(proc, grace=grace)
    elapsed = time.monotonic() - t0

    assert _wait_dead(proc.pid), "SIGTERM-ignoring process was never SIGKILLed"
    assert elapsed >= grace, (
        f"returned in {elapsed:.2f}s (< grace {grace}s) - it did not wait out "
        "SIGTERM before escalating")
    print(f"PASS: SIGTERM ignored -> SIGKILL after {elapsed:.2f}s grace")


def test_kill_group_already_dead() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    backends._kill_process_group(proc)  # must not raise
    print("PASS: _kill_process_group no-ops on an already-dead process")


def test_codexbackend_cancel_uses_group_kill() -> None:
    # Point a CodexBackend at a long-lived process-group leader and confirm its
    # cancel() tears the group down (proving cancel routes through the group
    # kill, not a lone terminate()).
    be = _backend()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(999)"],
        start_new_session=True,
    )
    be._proc = proc
    be.cancel()
    assert be._cancelled is True
    assert _wait_dead(proc.pid), "CodexBackend.cancel did not kill the turn"
    print("PASS: CodexBackend.cancel kills the process group")


def test_kill_group_when_leader_exits_but_child_ignores_term() -> None:
    child_src = (
        "import signal,time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "print('ready', flush=True);"
        "time.sleep(999)"
    )
    parent_src = (
        "import subprocess,sys,time;"
        "c=subprocess.Popen([sys.executable,'-c',sys.argv[1]],"
        "stdout=subprocess.PIPE,text=True);"
        "assert c.stdout.readline().strip()=='ready';"
        "print(c.pid, flush=True);"
        "time.sleep(999)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_src, child_src],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    assert proc.stdout is not None
    child_pid = int(proc.stdout.readline())
    backends._kill_process_group(proc, grace=0.2)
    assert _wait_dead(proc.pid), "group leader survived"
    assert _wait_dead(child_pid), "SIGTERM-ignoring child survived leader exit"


def test_codexbackend_cancel_during_process_publication(monkeypatch) -> None:
    real_popen = backends.subprocess.Popen
    spawned = threading.Event()
    publish = threading.Event()
    holder = {}
    errors = []

    def delayed_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        holder["proc"] = proc
        spawned.set()
        assert publish.wait(2)
        return proc

    be = _backend()
    be._build_cmd = lambda: [
        sys.executable, "-c", "import time; time.sleep(999)"
    ]
    monkeypatch.setattr(backends.subprocess, "Popen", delayed_popen)
    def consume():
        try:
            be.begin_turn()
            list(be.stream("hello"))
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert spawned.wait(2)
    be.cancel()
    publish.set()
    worker.join(3)
    proc = holder["proc"]
    assert not worker.is_alive(), "stream stayed blocked after startup cancel"
    assert _wait_dead(proc.pid), "process published after cancel survived"
    assert errors == [], f"worker raised: {errors!r}"


def test_codexbackend_cancel_after_generator_creation_is_not_cleared() -> None:
    be = _backend()
    be._build_cmd = lambda: [
        sys.executable, "-c", "import time; time.sleep(999)"
    ]
    be.begin_turn()
    stream = be.stream("hello")
    be.cancel()

    list(stream)

    assert be._cancel_event.is_set()
    assert be._proc is None


class _GatedClearEvent(threading.Event):
    """Pause clear() so a cancel can contend exactly at the turn boundary."""

    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def clear(self):
        self.entered.set()
        assert self.release.wait(2), "test never released turn start"
        super().clear()


def test_codexbackend_cancel_at_turn_start_is_not_cleared() -> None:
    be = _backend()
    be._build_cmd = lambda: [
        sys.executable, "-c", "import time; time.sleep(999)"
    ]
    gate = _GatedClearEvent()
    be._cancel_event = gate
    worker_errors = []
    cancel_errors = []

    def consume():
        try:
            be.begin_turn()
            list(be.stream("hello"))
        except Exception as exc:
            worker_errors.append(exc)

    def cancel():
        try:
            be.cancel()
        except Exception as exc:
            cancel_errors.append(exc)

    worker = threading.Thread(target=consume, daemon=True)
    worker.start()
    assert gate.entered.wait(2)
    canceller = threading.Thread(target=cancel, daemon=True)
    canceller.start()
    gate.release.set()
    canceller.join(2)
    worker.join(2)
    finished_after_first_cancel = not worker.is_alive()
    if worker.is_alive():
        be.cancel()
        worker.join(3)

    assert not canceller.is_alive(), "cancel stayed blocked at turn start"
    assert finished_after_first_cancel, "turn-start cancel was cleared"
    assert not worker.is_alive(), "stream survived cleanup cancel"
    assert worker_errors == [], f"worker raised: {worker_errors!r}"
    assert cancel_errors == [], f"cancel worker raised: {cancel_errors!r}"


# _IdleGuard: drop a silent peer, but never a slow-typing one
# --------------------------------------------------------------------------- #
class _FakeChannel:
    is_network = True
    peer = "test-peer"

    def __init__(self):
        self.closed = False
        self._feed = []  # queued real bytes to hand back

    def feed(self, b: int):
        self._feed.append(b)

    def read_byte(self):
        if self.closed:
            return None
        if self._feed:
            return self._feed.pop(0)
        time.sleep(0.05)
        return -1  # nothing available (a read timeout)

    def write(self, data):
        pass

    def close(self):
        self.closed = True


def test_idle_guard_drops_silent_peer() -> None:
    ch = _FakeChannel()
    guard = bridge._IdleGuard(ch, timeout=0.3)
    # A reader that just keeps polling, like Terminal.read_line does.
    end = time.time() + 2.0
    while time.time() < end and not ch.closed:
        if guard.read_byte() is None:
            break
    assert ch.closed, "idle peer was not dropped"
    guard.disarm()
    print("PASS: _IdleGuard drops a peer that stays silent past the timeout")


def test_idle_guard_resets_on_bytes() -> None:
    ch = _FakeChannel()
    guard = bridge._IdleGuard(ch, timeout=0.5)
    # Deliver a byte every 0.2s for ~1.2s (each shorter than the 0.5s timeout).
    t0 = time.time()
    while time.time() - t0 < 1.2:
        ch.feed(ord("A"))
        assert guard.read_byte() == ord("A")
        time.sleep(0.2)
    assert not ch.closed, "steady slow typing was wrongly dropped"
    guard.disarm()
    print("PASS: _IdleGuard resets on every byte (slow typing survives)")


def test_idle_guard_disarm_stops_watchdog() -> None:
    ch = _FakeChannel()
    guard = bridge._IdleGuard(ch, timeout=0.3)
    guard.disarm()
    time.sleep(0.8)  # well past the timeout
    assert not ch.closed, "disarmed guard still dropped the peer"
    print("PASS: _IdleGuard.disarm stops the watchdog (live session kept)")


if __name__ == "__main__":
    test_kill_group_no_orphans()
    test_kill_group_escalates_to_sigkill()
    test_kill_group_already_dead()
    test_codexbackend_cancel_uses_group_kill()
    test_idle_guard_drops_silent_peer()
    test_idle_guard_resets_on_bytes()
    test_idle_guard_disarm_stops_watchdog()
    print("ALL PASS")
