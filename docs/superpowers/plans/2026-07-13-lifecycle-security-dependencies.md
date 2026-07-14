# Bridge Lifecycle, Security, and Dependency Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Ctrl-C and shutdown reliably stop all active work, correct the security documentation, and make each Python dependency installable from the setup path that needs it.

**Architecture:** Keep the current backend and transport interfaces. Add cancellation state around resource publication, make process-group teardown verify the whole group is gone, make session loops own and clean up their workers, then separate optional runtime dependencies from pinned repository tooling.

**Tech Stack:** Python 3.10+, pytest, POSIX process groups, GitHub Actions, Markdown

## Global Constraints

- Keep the Apple II UI, serial protocol bytes, token format, and normal Ctrl-C behavior unchanged.
- Keep Python 3.10 as the minimum and test Python 3.10 plus 3.14.
- Keep code-mode process cancellation POSIX-only; do not add Windows support.
- Keep runtime dependency ranges updateable; pin build and test tools exactly.
- Do not change dos33fsprogs, GitHub Action revisions, release version `1.1.0`, or the trusted-LAN model.
- Use TDD for every behavior change and preserve the master-based release disk workflow.

---

### Task 1: Make backend cancellation race-safe and kill the whole process group

**Files:**
- Modify: `bridge/backends.py:154-256,262-462`
- Modify: `bridge/test_cancel.py:1-145`

**Interfaces:**
- Produces: `_process_group_exists(pgid: int) -> bool`
- Produces: `_kill_process_group(proc: subprocess.Popen, grace: float = 2.0) -> None`
- Produces: race-safe `ChatBackend.cancel()` and `CodeBackend.cancel()`
- Preserves: `ChatBackend._cancel` and `CodeBackend._cancelled` for existing behavior and tests

- [ ] **Step 1: Add failing process-group and publication-race tests**

Append these tests to `bridge/test_cancel.py` before changing production code:

```python
def test_kill_group_when_leader_exits_but_child_ignores_term() -> None:
    child_src = (
        "import signal,time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "print('ready', flush=True);"
        "time.sleep(999)"
    )
    parent_src = (
        "import subprocess,sys,time;"
        "c=subprocess.Popen([sys.executable,'-c',sys.argv[1]]);"
        "print(c.pid, flush=True);"
        "time.sleep(999)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", parent_src, child_src],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    assert proc.stdout is not None
    child_pid = int(proc.stdout.readline())
    time.sleep(0.3)
    backends._kill_process_group(proc, grace=0.2)
    assert _wait_dead(proc.pid), "group leader survived"
    assert _wait_dead(child_pid), "SIGTERM-ignoring child survived leader exit"


def test_codebackend_cancel_during_process_publication(monkeypatch) -> None:
    real_popen = backends.subprocess.Popen
    spawned = threading.Event()
    publish = threading.Event()
    holder = {}

    def delayed_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        holder["proc"] = proc
        spawned.set()
        assert publish.wait(2)
        return proc

    be = backends.CodeBackend(cols=80, claude_bin=sys.executable)
    be._build_cmd = lambda _text: [
        sys.executable, "-c", "import time; time.sleep(999)"
    ]
    monkeypatch.setattr(backends.subprocess, "Popen", delayed_popen)
    worker = threading.Thread(target=lambda: list(be.stream("hello")), daemon=True)
    worker.start()
    assert spawned.wait(2)
    be.cancel()
    publish.set()
    worker.join(3)
    proc = holder["proc"]
    assert not worker.is_alive(), "stream stayed blocked after startup cancel"
    assert _wait_dead(proc.pid), "process published after cancel survived"


def test_chatbackend_cancel_during_stream_publication() -> None:
    entered = threading.Event()
    publish = threading.Event()
    closed = threading.Event()

    class BlockingText:
        def __iter__(self):
            closed.wait(3)
            return iter(())

    class FakeStream:
        text_stream = BlockingText()
        def close(self):
            closed.set()
        def get_final_message(self):
            raise AssertionError("cancelled stream must not request a final message")

    class StreamContext:
        def __enter__(self):
            entered.set()
            assert publish.wait(2)
            return FakeStream()
        def __exit__(self, *_args):
            return False

    class Messages:
        def stream(self, **_kwargs):
            return StreamContext()

    be = backends.ChatBackend.__new__(backends.ChatBackend)
    be._client = type("Client", (), {"messages": Messages()})()
    be._model = "test"
    be._effort = "low"
    be._max_tokens = 32
    be._system = "test"
    be._messages = []
    be._cancel = False
    be._stream = None
    be._state_lock = threading.Lock()
    be._cancel_event = threading.Event()

    worker = threading.Thread(target=lambda: list(be.stream("hello")), daemon=True)
    worker.start()
    assert entered.wait(2)
    be.cancel()
    publish.set()
    worker.join(3)
    assert closed.is_set(), "stream published after cancel was not closed"
    assert not worker.is_alive(), "chat stream stayed blocked after startup cancel"
```

Also initialize the new state fields in the existing
`test_chatbackend_cancel_closes_stream` fixture:

```python
be._state_lock = threading.Lock()
be._cancel_event = threading.Event()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
bridge/.venv/bin/python -m pytest -q \
  bridge/test_cancel.py::test_kill_group_when_leader_exits_but_child_ignores_term \
  bridge/test_cancel.py::test_codebackend_cancel_during_process_publication \
  bridge/test_cancel.py::test_chatbackend_cancel_during_stream_publication
```

Expected: all three fail against the current code; the child survives, CodeBackend misses the unpublished process, and ChatBackend misses the unpublished stream.

- [ ] **Step 3: Replace leader-only teardown with group-existence teardown**

Replace `_kill_process_group` in `bridge/backends.py` with:

```python
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
            if not _process_group_exists(pgid):
                return True
            time.sleep(0.02)
        return not _process_group_exists(pgid)

    _signal_group(signal.SIGTERM)
    if not _wait_group(grace):
        _signal_group(signal.SIGKILL)
        _wait_group(grace)
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
```

Add `import time` if it is not already present.

- [ ] **Step 4: Make ChatBackend publication atomic**

In `ChatBackend.__init__`, add:

```python
self._state_lock = threading.Lock()
self._cancel_event = threading.Event()
```

Replace `cancel()` with:

```python
def cancel(self) -> None:
    self._cancel = True
    self._cancel_event.set()
    with self._state_lock:
        stream = self._stream
    if stream is not None:
        try:
            stream.close()
        except Exception:
            pass
```

At the start of `stream()`, clear both cancellation indicators:

```python
self._cancel = False
self._cancel_event.clear()
```

Initialize `stream = None` before the outer `try`, so cleanup remains valid if
the SDK context manager fails before `__enter__` returns.

Immediately after entering the SDK stream context, publish and honor a racing cancellation:

```python
with self._state_lock:
    self._stream = stream
    cancelled_during_start = self._cancel_event.is_set()
if cancelled_during_start:
    stream.close()
```

Replace chunk-loop checks with `self._cancel_event.is_set()`. In `finally`, clear only the current stream:

```python
with self._state_lock:
    if self._stream is stream:
        self._stream = None
```

- [ ] **Step 5: Make CodeBackend publication atomic and clean probes as groups**

In `CodeBackend.__init__`, add:

```python
self._state_lock = threading.Lock()
self._cancel_event = threading.Event()
```

Replace `cancel()` with:

```python
def cancel(self) -> None:
    self._cancelled = True
    self._cancel_event.set()
    with self._state_lock:
        proc = self._proc
    if proc is not None:
        _kill_process_group(proc)
```

At the start of `stream()`, clear the event and `_cancelled`. After `Popen`, publish under the lock and immediately kill when the event is already set:

```python
self._cancelled = False
self._cancel_event.clear()
# existing Popen call
with self._state_lock:
    self._proc = proc
    cancelled_during_start = self._cancel_event.is_set()
if cancelled_during_start:
    _kill_process_group(proc)
```

Wrap stdout parsing, `wait()`, and stderr joining in `try/finally`. In the finalizer:

```python
with self._state_lock:
    if self._proc is proc:
        self._proc = None
```

In `probe_model()`, add `start_new_session=True` to `Popen`. Keep the timeout,
but make it terminate the whole group instead of only the leader:

```python
killer = threading.Timer(timeout, _kill_process_group, args=(proc, 0.5))
killer.start()
```

Use this finalizer:

```python
finally:
    killer.cancel()
    _kill_process_group(proc, grace=2.0)
```

- [ ] **Step 6: Run focused and full backend tests**

```bash
bridge/.venv/bin/python -m pytest -q bridge/test_cancel.py
bridge/.venv/bin/python -m pytest -q bridge tests/test_interrupt.py
```

Expected: all focused tests pass and the full suite has zero failures.

- [ ] **Step 7: Commit Task 1**

```bash
git add bridge/backends.py bridge/test_cancel.py
git commit -m "Make backend cancellation race-safe"
```

---

### Task 2: Poll Ctrl-C under continuous output and clean every session unwind

**Files:**
- Modify: `bridge/bridge.py:221-360,730-789`
- Modify: `tests/test_interrupt.py:1-112`

**Interfaces:**
- Consumes: race-safe `Backend.cancel()` from Task 1
- Produces: fixed-cadence channel polling during native-client generation
- Produces: bounded reply-worker join on completion, cancel, disconnect, exception, and host Ctrl-C
- Preserves: partial reply plus `* Interrupted by user` and EOT for native-client Ctrl-C

- [ ] **Step 1: Add a continuous-output Ctrl-C regression**

Add this backend and test to `tests/test_interrupt.py`:

```python
class BusyBackend(SlowBackend):
    def __init__(self):
        super().__init__()
        self.cancel_event = threading.Event()
        self.stop_event = threading.Event()

    def cancel(self):
        self.cancelled = True
        self.cancel_event.set()

    def stream(self, _user):
        while not self.cancel_event.is_set() and not self.stop_event.is_set():
            yield "x"
            time.sleep(0.01)


def test_ctrl_c_is_polled_while_chunks_are_continuous():
    ch = FakeChannel()
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = BusyBackend()
    worker = threading.Thread(
        target=bridge.run_app_session,
        args=(term, Args(), backend, None, "code"),
        daemon=True,
    )
    worker.start()
    time.sleep(0.2)
    ch.feed(b"hello\r")
    time.sleep(0.2)
    ch.feed(b"\x03")
    try:
        assert backend.cancel_event.wait(1), (
            "continuous chunks starved Ctrl-C polling")
    finally:
        backend.stop_event.set()
        ch.feed(b"/exit\r")
        worker.join(3)
```

Call the new test from the file's `__main__` block.

- [ ] **Step 2: Add disconnect cleanup coverage**

Extend `FakeChannel` with a closed state:

```python
self.closed = False

def read_byte(self):
    if self.closed:
        return None
    try:
        return self.rx.get(timeout=0.05)
    except queue.Empty:
        return -1

def close(self):
    self.closed = True
```

Add:

```python
def test_disconnect_cancels_and_joins_reply_worker():
    ch = FakeChannel()
    term = Terminal(ch, TermConfig(width=80, echo=False, telnet=False))
    backend = BusyBackend()
    session = threading.Thread(
        target=bridge.run_app_session,
        args=(term, Args(), backend, None, "code"),
        daemon=True,
    )
    session.start()
    ch.feed(b"hello\r")
    time.sleep(0.2)
    ch.close()
    session.join(3)
    assert not session.is_alive(), "session survived channel close"
    assert backend.cancel_event.is_set(), "disconnect did not cancel backend"
```

Import `pytest`, then add a host-interrupt unwind test using a backend that
produces one chunk and waits for cancellation:

```python
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
```

- [ ] **Step 3: Run the new tests and verify RED**

```bash
bridge/.venv/bin/python -m pytest -q \
  tests/test_interrupt.py::test_ctrl_c_is_polled_while_chunks_are_continuous \
  tests/test_interrupt.py::test_disconnect_cancels_and_joins_reply_worker \
  tests/test_interrupt.py::test_host_interrupt_cancels_and_joins_reply_worker
```

Expected: continuous output prevents cancellation, disconnect does not reliably
unwind the worker, and host interruption leaves the backend uncancelled.

- [ ] **Step 4: Own the native-client reply worker and poll on a fixed cadence**

Replace the anonymous thread and queue loop in `run_app_session` with this structure:

```python
worker = threading.Thread(target=_pump, daemon=True)
worker.start()
interrupted = False
finished = False
next_poll = time.monotonic()
try:
    while True:
        now = time.monotonic()
        if now >= next_poll:
            next_poll = now + 0.05
            if not interrupted and term.poll_ctrl_c():
                interrupted = True
                backend.cancel()
            if term.closed:
                backend.cancel()
                return
        wait = max(0.0, min(0.05, next_poll - time.monotonic()))
        try:
            chunk = chunks.get(timeout=wait)
        except queue.Empty:
            continue
        if chunk is None:
            finished = True
            break
        lines.extend(fmt.feed(chunk))
finally:
    if not finished:
        backend.cancel()
    worker.join(timeout=3.0)
    if worker.is_alive():
        log("reply worker did not stop after cancellation", peer=peer)
```

Keep the existing reply rendering after this block unchanged.

- [ ] **Step 5: Cancel synchronous non-app streams when the session unwinds**

Wrap the non-app `for chunk in backend.stream(user)` block in:

```python
turn_finished = False
try:
    for chunk in backend.stream(user):
        for out_line in fmt.feed(chunk):
            term.write_line(out_line)
            nlines += 1
        if term.closed:
            return
    turn_finished = True
finally:
    if not turn_finished:
        backend.cancel()
```

This finalizer also runs when host-side `KeyboardInterrupt` unwinds through `run_session`.

- [ ] **Step 6: Verify session behavior**

```bash
bridge/.venv/bin/python -m pytest -q tests/test_interrupt.py bridge/test_cancel.py
bridge/.venv/bin/python -m pytest -q bridge tests/test_interrupt.py
```

Expected: continuous-output Ctrl-C cancels within one second, disconnect exits within three seconds, existing partial-reply behavior passes, and the full suite has zero failures.

- [ ] **Step 7: Commit Task 2**

```bash
git add bridge/bridge.py tests/test_interrupt.py
git commit -m "Clean up interrupted bridge turns"
```

---

### Task 3: Normalize pinned pairing codes and correct security claims

**Files:**
- Modify: `bridge/bridge.py:861-936`
- Modify: `bridge/test_pairing.py`
- Modify: `README.md:30-45,83-123`
- Modify: `SECURITY.md:5-50`
- Modify: `CHANGELOG.md:18-31`
- Modify: `AGENTS.md:47`
- Modify: `apple2/TERMINAL-SETUP.md:106-134`
- Modify: `docs/superpowers/specs/2026-07-13-token-device-pairing-design.md`

**Interfaces:**
- Produces: `parse_args(...).pair_code` normalized to uppercase
- Documents: on-demand per-source-IP codes, plaintext replay risk, token metadata, XDG storage, raw-telnet limitation, actual delay cap
- Preserves: token format, pairing protocol, attempt cap, and trusted-LAN model

- [ ] **Step 1: Add a failing lowercase-code test**

Add to `bridge/test_pairing.py`:

```python
def test_parse_args_normalizes_pinned_pair_code():
    args = bridge.parse_args(["--telnet", "--pair-code", "abc234"])
    assert args.pair_code == "ABC234"
```

Run:

```bash
bridge/.venv/bin/python -m pytest -q \
  bridge/test_pairing.py::test_parse_args_normalizes_pinned_pair_code
```

Expected: FAIL because the current parser returns `abc234`.

- [ ] **Step 2: Normalize the parsed option and correct CLI wording**

After `args = p.parse_args(argv)` in `parse_args`, add:

```python
args.pair_code = args.pair_code.upper()
```

Replace “per-device” in the parser epilog and pairing help with “per-source-IP”. Use this exact help text:

```python
p.add_argument("--pair-code", default="",
               help="fix one shared pairing code for every caller; letters "
                    "are case-insensitive (telnet default: a per-source-IP "
                    "code shown when an unpaired caller needs it)")
```

- [ ] **Step 3: Correct README and terminal setup**

Update the pairing/privacy paragraphs and pairing table so they state:

```text
The bridge creates a six-character code when an unpaired source IP first needs
pairing and prints it only on the bridge console. Native clients exchange that
code for a disk-stored token. A valid-token reconnect does not print a code.

Telnet is plaintext. Anyone who can capture traffic on the LAN may be able to
replay a pairing code or device token, so the listener belongs only on a trusted
home network and must never be port-forwarded.

The pairing store contains the token SHA-256, first-seen IP, and pairing time at
$XDG_CONFIG_HOME/claude-ii-terminal/paired.json, or ~/.config/... when XDG is
unset. The plaintext token remains on the Apple II disk.
```

In `apple2/TERMINAL-SETUP.md`, add after the raw telnet steps:

```text
Raw terminal programs do not store the native client's device token, so they
must enter the code shown on the bridge console for each new session.
```

- [ ] **Step 4: Correct SECURITY.md and historical notes**

Make these exact factual corrections:

- support table: `1.1.x | Yes`, `1.0.x | No`, `< 1.0 | No`;
- default code: six characters, on-demand, keyed by source IP;
- pinned code: shared and case-insensitive for letters;
- effective delays: three free tries, delays capped at eight seconds, ten attempts maximum per source IP per run;
- confidentiality: telnet does not encrypt codes, tokens, prompts, or replies;
- native client: token persistence; raw telnet: code each session;
- stored fields: token hash, first IP, pairing time;
- path: XDG path with `~/.config` fallback;
- permissions: newly created directory/file request `0700`/`0600`; existing path modes are not repaired;
- remove “Nothing else is persisted.”

Change `CHANGELOG.md` from “per-device” to “per-source-IP” and remove the claim that one code cannot enroll another device. Remove “expiry” from `AGENTS.md`. Mark the token-pairing design implemented and append an amendment stating that later changes introduced per-source-IP on-demand codes and exempt stale token-shaped values from guess strikes.

- [ ] **Step 5: Verify code and documentation consistency**

```bash
bridge/.venv/bin/python -m pytest -q bridge/test_pairing.py bridge/test_pairing_flow.py
rg -n "per-device|printed at startup|Nothing else is persisted|1\.0\.x \| Yes|expiry" \
  README.md SECURITY.md CHANGELOG.md AGENTS.md apple2/TERMINAL-SETUP.md \
  docs/superpowers/specs/2026-07-13-token-device-pairing-design.md bridge/bridge.py
```

Expected: pairing tests pass. Any remaining search hit must be historical context that explicitly identifies the old behavior, not a current claim.

- [ ] **Step 6: Commit Task 3**

```bash
git add bridge/bridge.py bridge/test_pairing.py README.md SECURITY.md CHANGELOG.md \
  AGENTS.md apple2/TERMINAL-SETUP.md \
  docs/superpowers/specs/2026-07-13-token-device-pairing-design.md
git commit -m "Correct pairing security documentation"
```

---

### Task 4: Split optional dependencies and test supported Python versions

**Files:**
- Create: `bridge/requirements-chat.txt`
- Create: `bridge/requirements-serial.txt`
- Modify: `bridge/requirements.txt`
- Create: `requirements-build.txt`
- Create: `requirements-test.txt`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `apple2/TERMINAL-SETUP.md:53-71`
- Modify: `tests/README.md:1-16`

**Interfaces:**
- Produces: feature-specific pip install paths for serial and chat
- Produces: reproducible build/test requirements
- Produces: CI Python tests on 3.10 and 3.14 plus one disk-build job
- Preserves: `bridge/requirements.txt` as the all-features convenience install

- [ ] **Step 1: Create exact dependency files**

Create `bridge/requirements-chat.txt`:

```text
# Messages API backend (--backend chat). Requires ANTHROPIC_API_KEY.
anthropic>=0.77.0,<1
```

Create `bridge/requirements-serial.txt`:

```text
# Direct serial transport (--serial).
pyserial==3.5
```

Replace `bridge/requirements.txt` with:

```text
# All optional bridge features. TCP + --backend code needs no Python package.
-r requirements-chat.txt
-r requirements-serial.txt
```

Create `requirements-build.txt`:

```text
Pillow==12.3.0
```

Create `requirements-test.txt`:

```text
pytest==9.1.1
```

- [ ] **Step 2: Verify dependency resolution in clean environments**

```bash
python3.14 -m venv /tmp/appleii-py314
/tmp/appleii-py314/bin/pip install -r requirements-test.txt -r bridge/requirements.txt
/tmp/appleii-py314/bin/python -m pytest -q bridge tests/test_interrupt.py

python3 -m venv /tmp/appleii-build-deps
/tmp/appleii-build-deps/bin/pip install -r requirements-build.txt
/tmp/appleii-build-deps/bin/python -c "from PIL import Image; print(Image.__version__)"
```

Expected: Python 3.14 installs and passes the full suite; Pillow prints `12.3.0`.
Python 3.10 is verified by the CI matrix because no local 3.10 interpreter is
installed on this host.

- [ ] **Step 3: Split CI into Python compatibility and disk-build jobs**

Add this job before the existing build job, reusing the already-pinned action revisions:

```yaml
  python-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.10", "3.14"]
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: ${{ matrix.python }}
      - name: Install test and bridge dependencies
        run: |
          python3 -m pip install --upgrade pip
          python3 -m pip install -r requirements-test.txt -r bridge/requirements.txt
          python3 -m pip check
      - name: Bridge / renderer tests
        run: python3 -m pytest -q bridge tests/test_interrupt.py
```

In the existing build job, replace the Python dependency step with:

```yaml
      - name: Install build dependencies
        run: |
          python3 -m pip install --upgrade pip
          python3 -m pip install -r requirements-build.txt
          python3 -m pip check
```

Remove the duplicate bridge-test step from the build job. Keep ShellCheck, assembly, disk build, release gate, action SHAs, and dos33fsprogs steps unchanged.

- [ ] **Step 4: Document the install choices**

Add this table near the README bridge setup:

```markdown
| Setup | Python install |
|---|---|
| TCP/emulator + `--backend code` | None; install and log in to the external `claude` CLI |
| Serial + `--backend code` | `python3 -m pip install -r bridge/requirements-serial.txt` |
| Any transport + `--backend chat` | `python3 -m pip install -r bridge/requirements-chat.txt` and set `ANTHROPIC_API_KEY` |
| Every optional bridge feature | `python3 -m pip install -r bridge/requirements.txt` |
```

In `apple2/TERMINAL-SETUP.md`, add the serial install command and change the basic command to:

```sh
python3 -m pip install -r bridge/requirements-serial.txt
python3 bridge/bridge.py --serial /dev/tty.usbserial-XXXX --baud 9600 \
  --cols 80 --backend code
```

Replace the bridge section of `tests/README.md` with:

````markdown
## Bridge (no emulator)

```sh
python3 -m pip install -r requirements-test.txt
python3 -m pytest -q bridge tests/test_interrupt.py
```

This runs the renderer, pairing, cancellation, terminal-protocol, error-hygiene,
and native-client interrupt tests without an emulator or Claude account.
````

- [ ] **Step 5: Verify workflow syntax and local dependency tests**

```bash
git diff --check
rg -n "pip install (pillow|pytest|anthropic|pyserial)" .github README.md apple2 bridge tests
/tmp/appleii-py314/bin/python -m pytest -q bridge tests/test_interrupt.py
```

Expected: no unconstrained direct installs remain in project instructions or CI;
the local Python 3.14 suite passes, and the pushed CI matrix supplies the Python
3.10 result.

- [ ] **Step 6: Commit Task 4**

```bash
git add bridge/requirements-chat.txt bridge/requirements-serial.txt \
  bridge/requirements.txt requirements-build.txt requirements-test.txt \
  .github/workflows/ci.yml README.md apple2/TERMINAL-SETUP.md tests/README.md
git commit -m "Clarify Python dependency boundaries"
```

---

### Task 5: Run the complete release gate and verify live CI

**Files:**
- Verify only; modify code only if a preceding requirement is not met

**Interfaces:**
- Consumes: Tasks 1-4
- Produces: local and live evidence that the release remains buildable and cancellation-safe

- [ ] **Step 1: Run the full Python suites at both supported endpoints**

```bash
/tmp/appleii-py314/bin/python -m pytest -q bridge tests/test_interrupt.py
```

Expected: the local Python 3.14 suite completes with zero failures. The live CI
matrix in Step 4 must provide the Python 3.10 completion evidence.

- [ ] **Step 2: Run static checks and the release build**

```bash
shellcheck apple2gs/build.sh tools/install-sd.sh tools/check-release-disk.sh \
  tests/test_release_gate.sh
DOS33FSPROGS=/tmp/dos33fsprogs ./apple2gs/build.sh
DOS33FSPROGS=/tmp/dos33fsprogs ./tools/check-release-disk.sh apple2gs/CLAUDE.dsk
DOS33FSPROGS=/tmp/dos33fsprogs ./tests/test_release_gate.sh apple2gs/CLAUDE.dsk
shasum -a 256 apple2gs/CLAUDE.dsk
```

Expected: ShellCheck is clean, both clients assemble, the valid disk passes, the deleted-`COBJ8` disk fails, and a SHA-256 is printed.

- [ ] **Step 3: Audit scope and documentation claims**

```bash
git diff --check
git status --short
git log --oneline 0491b10..HEAD
rg -n "per-device|printed at startup|Nothing else is persisted|pip install anthropic|pip install pyserial" \
  README.md SECURITY.md CHANGELOG.md AGENTS.md apple2/TERMINAL-SETUP.md bridge tests
```

Expected: only planned files changed; no inaccurate current claims or obsolete install commands remain.

- [ ] **Step 4: Push `main` and watch GitHub Actions**

```bash
git push origin main
HEAD_SHA=$(git rev-parse HEAD)
RUN_ID=$(gh run list --workflow ci.yml --branch main --limit 10 \
  --json databaseId,headSha --jq ".[] | select(.headSha == \"$HEAD_SHA\") | .databaseId" \
  | head -1)
test -n "$RUN_ID"
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --json headSha,status,conclusion,jobs,url
```

Expected: the run for the pushed HEAD completes successfully, both Python matrix jobs pass, and the disk-build job passes.

- [ ] **Step 5: Record final evidence**

Report the two Python test counts, focused cancellation regression results, dependency install checks, disk SHA-256, effective security-doc corrections, latest commit, and successful Actions URL. Mention any non-failing upstream warnings separately.
