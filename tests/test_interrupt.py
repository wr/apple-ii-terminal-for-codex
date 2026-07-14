"""Integration tests for Ctrl-C and reply-worker lifecycle handling."""
import os
import queue
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "bridge"))

import bridge
from terminal import Terminal, TermConfig


class FakeChannel:
    is_network = False
    peer = None

    def __init__(self):
        self.rx = queue.Queue()   # bytes the "Apple II" sends us
        self.tx = bytearray()     # bytes we send the "Apple II"
        self.tx_changed = threading.Condition()
        self.closed = False

    def feed(self, data: bytes):
        for byte in data:
            self.rx.put(byte)

    def read_byte(self):
        if self.closed:
            return None
        try:
            return self.rx.get(timeout=0.05)
        except queue.Empty:
            return -1

    def write(self, data: bytes):
        with self.tx_changed:
            self.tx.extend(data)
            self.tx_changed.notify_all()

    def snapshot(self) -> bytes:
        with self.tx_changed:
            return bytes(self.tx)

    def wait_for_tx(self, needle: bytes, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self.tx_changed:
            while needle not in self.tx:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.tx_changed.wait(remaining)
            return True

    def close(self):
        self.closed = True


class SlowBackend:
    """Streams until cancelled - a stand-in for a long Codex turn."""
    name = "codex"

    def __init__(self):
        self.cancelled = False
        self.started_event = threading.Event()
        self.cancel_event = threading.Event()
        self.done_event = threading.Event()

    def prime(self): pass
    def header(self): return ("Codex CLI vTEST", "default model", "~/x")
    def footer(self): return None if self.cancelled else "Worked for 1s"
    def reset(self): pass

    def cancel(self):
        self.cancelled = True
        self.cancel_event.set()

    def stream(self, _user):
        self.started_event.set()
        try:
            yield "partial text before the interrupt. "
            assert self.cancel_event.wait(20), "test backend was never cancelled"
        finally:
            self.done_event.set()


class BusyBackend(SlowBackend):
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()

    def stream(self, _user):
        self.started_event.set()
        try:
            while not self.cancel_event.is_set() and not self.stop_event.is_set():
                yield "x"
                time.sleep(0.01)
        finally:
            self.done_event.set()


class BurstBackend(SlowBackend):
    def stream(self, _user):
        self.started_event.set()
        try:
            for _ in range(128):
                yield "x"
        finally:
            self.done_event.set()


class NonCooperativeBackend(SlowBackend):
    def __init__(self):
        super().__init__()
        self.release_event = threading.Event()

    def stream(self, _user):
        self.started_event.set()
        try:
            yield "partial from stuck backend"
            self.release_event.wait()
        finally:
            self.done_event.set()


class Args:
    cols = 80
    app = True


def start_session(ch, backend):
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    session = threading.Thread(
        target=bridge.run_app_session,
        args=(term, Args(), backend, None, "code"),
        daemon=True,
    )
    session.start()
    ch.feed(b"hello\r")
    assert backend.started_event.wait(1), "backend stream did not start"
    return term, session


def stop_session(ch, session, backend):
    if hasattr(backend, "stop_event"):
        backend.stop_event.set()
    if hasattr(backend, "release_event"):
        backend.release_event.set()
    if ch.wait_for_tx(bridge.EOT, 5):
        ch.feed(b"/exit\r")
    else:
        ch.close()
    session.join(5)
    assert not session.is_alive(), "session thread did not end"
    assert backend.done_event.wait(1), "reply worker did not end"


def test_ctrl_c_is_polled_while_chunks_are_continuous():
    ch = FakeChannel()
    backend = BusyBackend()
    _term, session = start_session(ch, backend)
    ch.feed(b"\x03")
    try:
        assert backend.cancel_event.wait(1), (
            "continuous chunks starved Ctrl-C polling")
    finally:
        stop_session(ch, session, backend)


def test_busy_producer_is_drained_between_post_poll_deadlines():
    ch = FakeChannel()
    backend = BurstBackend()
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    real_poll = term.poll_ctrl_c
    slow_polls = threading.Event()
    slow_polls.set()

    def slow_poll():
        if slow_polls.is_set():
            time.sleep(0.06)
        return real_poll()

    term.poll_ctrl_c = slow_poll
    session = threading.Thread(
        target=bridge.run_app_session,
        args=(term, Args(), backend, None, "code"),
        daemon=True,
    )
    session.start()
    ch.feed(b"hello\r")
    try:
        assert backend.started_event.wait(1)
        assert ch.wait_for_tx(b"Worked for 1s", 2), (
            "producer backlog prevented a bounded drain between channel polls")
    finally:
        slow_polls.clear()
        stop_session(ch, session, backend)


def test_disconnect_cancels_and_joins_reply_worker():
    ch = FakeChannel()
    backend = BusyBackend()
    _term, session = start_session(ch, backend)
    ch.close()
    session.join(3)
    assert not session.is_alive(), "session survived channel close"
    assert backend.cancel_event.is_set(), "disconnect did not cancel backend"
    assert backend.done_event.wait(1), "disconnect did not join reply worker"


def test_host_interrupt_cancels_and_joins_reply_worker():
    ch = FakeChannel()
    ch.feed(b"hello\r")
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = SlowBackend()

    def host_interrupt():
        raise KeyboardInterrupt

    term.poll_ctrl_c = host_interrupt
    with pytest.raises(KeyboardInterrupt):
        bridge.run_app_session(term, Args(), backend, None, "code")
    assert backend.cancelled, "host Ctrl-C left backend work running"
    assert backend.done_event.is_set(), "host Ctrl-C did not join reply worker"


def test_partial_thread_start_failure_cancels_and_joins_worker(monkeypatch):
    ch = FakeChannel()
    ch.feed(b"hello\r")
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = SlowBackend()
    real_start = threading.Thread.start

    def start_then_raise(thread):
        real_start(thread)
        raise RuntimeError("start failed after worker launch")

    monkeypatch.setattr(bridge.threading.Thread, "start", start_then_raise)
    with pytest.raises(RuntimeError, match="start failed after worker launch"):
        bridge.run_app_session(term, Args(), backend, None, "code")

    assert backend.cancelled, "partial start left backend work running"
    assert backend.done_event.wait(1), "partial start skipped worker join"


def test_cancel_error_still_joins_reply_worker():
    class RaisingCancelBackend(NonCooperativeBackend):
        def cancel(self):
            self.cancel_event.set()
            raise RuntimeError("cancel exploded")

    ch = FakeChannel()
    ch.feed(b"hello\r")
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = RaisingCancelBackend()

    def host_interrupt():
        raise KeyboardInterrupt

    term.poll_ctrl_c = host_interrupt

    def release_after_cancel():
        assert backend.cancel_event.wait(1)
        backend.release_event.set()

    releaser = threading.Thread(target=release_after_cancel)
    releaser.start()
    try:
        with pytest.raises(RuntimeError, match="cancel exploded"):
            bridge.run_app_session(term, Args(), backend, None, "code")
        assert backend.done_event.is_set(), "cancel error skipped worker join"
    finally:
        backend.release_event.set()
        releaser.join(2)


def test_noncooperative_backend_has_bounded_interrupt_cleanup(capsys):
    ch = FakeChannel()
    backend = NonCooperativeBackend()
    _term, session = start_session(ch, backend)
    ch.feed(b"\x03")
    try:
        assert backend.cancel_event.wait(1), "Ctrl-C did not request cancellation"
        assert ch.wait_for_tx(b"Interrupted by user", 5), (
            "session waited indefinitely for a noncooperative backend")
        assert ch.wait_for_tx(bridge.EOT, 1), "interrupted reply omitted EOT"
        out = ch.snapshot()
        marker = out.index(bridge.CMD_INTERRUPT)
        message = out.index(b"Interrupted by user")
        assert marker < message < out.index(bridge.EOT, message)
        assert b"* Interrupted by user" not in out
        assert "reply worker did not stop after cancellation" in capsys.readouterr().out
    finally:
        stop_session(ch, session, backend)


def test_final_poll_can_interrupt_as_worker_finishes():
    class FinishingBackend(NonCooperativeBackend):
        pass

    ch = FakeChannel()
    ch.feed(b"hello\r")
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = FinishingBackend()
    poll_count = 0

    def poll_at_finish():
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            backend.release_event.set()
            return False
        return backend.done_event.is_set()

    term.poll_ctrl_c = poll_at_finish
    session = threading.Thread(
        target=bridge.run_app_session,
        args=(term, Args(), backend, None, "code"),
        daemon=True,
    )
    session.start()
    try:
        assert ch.wait_for_tx(b"Interrupted by user", 2), (
            "worker sentinel was accepted without a final channel poll")
        out = ch.snapshot()
        assert b"Worked for" not in out
    finally:
        stop_session(ch, session, backend)


def test_worker_base_exception_renders_failure_not_footer(capsys):
    class CrashingBackend(SlowBackend):
        def stream(self, _user):
            self.started_event.set()
            try:
                yield "partial before crash"
                raise KeyboardInterrupt("worker crash")
            finally:
                self.done_event.set()

    ch = FakeChannel()
    backend = CrashingBackend()
    _term, session = start_session(ch, backend)
    try:
        assert ch.wait_for_tx(b"[bridge error: reply failed]", 2)
        out = ch.snapshot()
        assert b"Worked for" not in out
        assert "stream error: KeyboardInterrupt: worker crash" in capsys.readouterr().out
    finally:
        stop_session(ch, session, backend)


def test_non_app_interrupt_cancels_synchronous_stream(monkeypatch):
    class InterruptingBackend(SlowBackend):
        def stream(self, _user):
            yield "partial text"
            raise KeyboardInterrupt

    class PlainArgs:
        telnet = False
        idle_timeout = 0
        backend = "code"
        app = False
        cols = 80

    ch = FakeChannel()
    ch.feed(b"hello\r")
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = InterruptingBackend()
    monkeypatch.setattr(bridge, "make_backend", lambda *_args: backend)

    with pytest.raises(KeyboardInterrupt):
        bridge.run_session(term, PlainArgs())
    assert backend.cancelled, "non-app unwind left backend work running"


def run():
    ch = FakeChannel()
    backend = SlowBackend()
    _term, session = start_session(ch, backend)

    # Turn 1: a prompt, then Ctrl-C mid-generation.
    ch.feed(b"\x03")
    assert backend.cancel_event.wait(1), "backend.cancel() was never called"
    assert ch.wait_for_tx(b"Interrupted by user", 2), "no interrupt marker"
    out = ch.snapshot()
    assert b"partial text before the interrupt" in out, "partial reply lost"
    assert b"Worked for" not in out, "footer should be skipped on interrupt"
    eot_at = out.rindex(bridge.EOT)
    assert eot_at > out.index(b"Interrupted"), "EOT must close the reply"
    print("PASS: Ctrl-C mid-generation -> cancel + partial + marker + EOT")

    # Turn 2: /exit behaves exactly like /quit.
    before = len(out)
    ch.feed(b"/exit\r")
    session.join(timeout=5)
    assert not session.is_alive(), "session did not end on /exit"
    tail = ch.snapshot()[before:]
    assert b"Goodbye." in tail, f"no goodbye: {tail!r}"
    assert b"\x03" in tail, "no CMD_QUIT byte"
    assert tail.rindex(bridge.EOT) > tail.index(b"\x03"), "CMD_QUIT then EOT"
    assert backend.done_event.is_set(), "reply worker survived direct protocol test"
    print("PASS: /exit -> Goodbye + CMD_QUIT + EOT, session closed")


if __name__ == "__main__":
    test_ctrl_c_is_polled_while_chunks_are_continuous()
    test_disconnect_cancels_and_joins_reply_worker()
    test_host_interrupt_cancels_and_joins_reply_worker()
    run()
    print("ALL PASS")
