# Codex-native UI and Modem Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fork's Claude-derived presentation with a Codex-native `>_` UI and make WiModem entry-1 failures actionable on the Apple II.

**Architecture:** The bridge resolves and frames four header values, while each native client owns its width-specific box, working indicator, and modem verdict display. Generated IIgs assets become deterministic monochrome `>_` frames; the serial protocol remains printable ASCII plus its existing control bytes.

**Tech Stack:** Python 3.10+, pytest, ca65/ld65, 6502 assembly, 65816 assembly, DOS 3.3 image tooling, Pillow preview renderer

## Global Constraints

- Keep Codex CLI 0.144.1 as the minimum supported version.
- Keep phonebook entry 1, TCP port 6401, and `ATDS=1` for Codex.
- Keep approval policy `never`; label permissions truthfully and use `YOLO mode` only with unrestricted sandboxing.
- Do not inspect Codex auth data; read only redacted doctor output and the `model_reasoning_effort` TOML key.
- Every slow Apple II loop must continue polling the receive ring.
- Preserve both `CODEX` and `CODEX8` on the DOS 3.3 master-based disk.
- Do not copy entry 1 into the Claude sister repo; only propose portable verdict handling there.

---

### Task 1: Resolve and frame the Codex header

**Files:**
- Modify: `bridge/backends.py`
- Modify: `bridge/bridge.py`
- Modify: `bridge/test_codex_backend.py`
- Modify: `bridge/test_pairing_flow.py`

**Interfaces:**
- Produces: `CodexBackend.prime() -> None`, which populates `_resolved_model` and `_reasoning_effort` without raising.
- Produces: `CodexBackend.header() -> tuple[str, str, str, str]` in title/model/directory/permissions order.
- Consumes: existing `send_header(term, backend)` and `CMD_HEADER = 0x0E` framing.

- [ ] **Step 1: Write failing header-resolution tests**

Add tests that monkeypatch `subprocess.run` and assert explicit-model precedence, doctor JSON parsing, TOML effort parsing, timeout fallback, directory abbreviation, and exact permission labels:

```python
def test_prime_resolves_model_and_effort_without_auth(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('model_reasoning_effort = "high"\n')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(backends, "codex_version", lambda _bin: (0, 144, 4))
    monkeypatch.setattr(backends.subprocess, "run", fake_doctor("gpt-5.6-sol"))
    be = backend(cwd=os.path.expanduser("~/Projects/demo"))
    be.prime()
    assert be.header() == (
        ">_ OpenAI Codex (v0.144.4)",
        "model: gpt-5.6-sol high   /model to change",
        "directory: ~/Projects/demo",
        "permissions: workspace-write / never",
    )

def test_header_falls_back_when_doctor_times_out(monkeypatch):
    monkeypatch.setattr(backends.subprocess, "run", raise_timeout)
    be = backend()
    be.prime()
    assert be.header()[1].startswith("model: default model")
```

Update the pairing fixture backend to return four lines and assert four CRs occur between `CMD_HEADER` and EOT.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `cd bridge && python3 -m pytest test_codex_backend.py test_pairing_flow.py -q`

Expected: FAIL because `prime()` does not resolve settings and `header()` returns three legacy lines.

- [ ] **Step 3: Implement bounded, redacted header discovery**

In `backends.py`, import `Path` from `pathlib` and import `tomllib` with a
Python 3.10 fallback that simply omits effort. Add helpers that:

```python
def _doctor_model(codex_bin: str, sandbox: str) -> str | None:
    result = subprocess.run(
        [codex_bin, "doctor", "--json", "-c", f'sandbox_mode="{sandbox}"',
         "-c", 'approval_policy="never"'],
        capture_output=True, text=True, timeout=10, check=False,
    )
    report = json.loads(result.stdout)
    return report.get("checks.config.load", {}).get("details", {}).get("model")

def _configured_effort() -> str | None:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    with (home / "config.toml").open("rb") as stream:
        value = tomllib.load(stream).get("model_reasoning_effort")
    return value if isinstance(value, str) else None
```

Catch missing binary, timeout, JSON/TOML parse, and filesystem errors inside `prime()`. Store the explicit constructor model separately so it always wins. Format unrestricted plus never as `YOLO mode`; otherwise format `<sandbox> / never`. Make `header()` return exactly four lines and keep `/model to change` only when it fits the backend's selected column count.

- [ ] **Step 4: Normalize locked headers to four data lines**

Add `_header4(lines)` in `bridge.py` to pad/truncate header payloads to four strings. Use it from both `send_header()` and `_lock_header()`. Change pairing prompts to title/model-like/directory-like/permissions-like rows without adding a fifth line.

- [ ] **Step 5: Run tests and commit**

Run: `cd bridge && python3 -m pytest test_codex_backend.py test_pairing_flow.py -q`

Expected: PASS.

Commit: `git commit -am "feat: report resolved Codex session settings"`

### Task 2: Correct WiModem setup and classify dial failures

**Files:**
- Modify: `bridge/bridge.py`
- Modify: `apple2gs/codex.s`
- Modify: `apple2/codex2.s`
- Modify: `tests/test_codex_identity.py`
- Create: `tests/test_modem_verdicts.py`

**Interfaces:**
- Produces: native `dialres` values `0=timeout`, `1=CONNECT`, `2=ERROR`, `3=BUSY`, `4=NO CARRIER`, `5=NO ANSWER`.
- Consumes: the existing incremental `dial_byte` entry point in both clients.

- [ ] **Step 1: Write failing setup-copy and verdict tests**

Extend `test_codex_identity.py` to assert `AT&Z1=` appears in the bridge and both clients and that `AT&Z0=` is absent from all three. Add a source-contract test with representative result lines:

```python
@pytest.mark.parametrize("line,value", [
    ("CONNECT 9600", 1), ("ERROR", 2), ("BUSY", 3),
    ("NO CARRIER", 4), ("NO ANSWER", 5),
])
def test_both_clients_define_distinct_modem_verdict(line, value):
    for source in SOURCES:
        text = source.read_text()
        assert f"DIAL_{line.split()[0]}" in text or f"DIAL_{line.replace(' ', '_')}" in text
        assert f"= {value}" in text
```

Also assert each user-facing diagnosis string and the 9600 8N1 timeout guidance exist in both clients.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python3 -m pytest tests/test_codex_identity.py tests/test_modem_verdicts.py -q`

Expected: FAIL on `AT&Z0=` and generic failure state.

- [ ] **Step 3: Fix all entry-1 setup copy**

Change the host banner and native instructions from `AT&Z0=` to `AT&Z1=`. Keep `AT&W` and `ATDS=1` unchanged. Update the banner comment so it describes `&Z1=`.

- [ ] **Step 4: Implement bounded line-buffer verdict matching**

Replace the first-two-letter classifier in both clients with a small upper-case line buffer or incremental state machine that distinguishes the five complete result phrases at CR. Define named constants for the six states, latch `CONNECT`, and return immediately on failures. Keep `rb_poll` in every wait/display loop.

At dial exit, select a short message by `dialres`. Use these meanings:

```text
ERROR: ENTRY 1 NOT SAVED - USE AT&Z1=HOST:6401
BUSY: BRIDGE IS BUSY
NO CARRIER: CHECK ENTRY 1, BRIDGE, AND NETWORK
NO ANSWER: CHECK THAT THE BRIDGE IS LISTENING
NO MODEM RESPONSE: CHECK 9600 8N1
```

The GS strings may use mixed case; the 8-bit strings stay uppercase-compatible and clip safely at the current width.

- [ ] **Step 5: Assemble both clients and run focused tests**

Run: `python3 -m pytest tests/test_codex_identity.py tests/test_modem_verdicts.py -q`

Run: `cd apple2gs && ca65 codex.s -o codex.o && ld65 -C codex.cfg codex.o -o CODEX && ca65 ../apple2/codex2.s -o ../apple2/codex2.o && ld65 -C ../apple2/codex2.cfg ../apple2/codex2.o -o CODEX8`

Expected: tests PASS and both assemblers exit 0.

- [ ] **Step 6: Commit**

Commit: `git commit -am "fix: explain WiModem dial failures"`

### Task 3: Replace Patch and coral with the `>_` identity

**Files:**
- Delete: `apple2gs/patch_art.py`
- Rename: `apple2gs/test_patch_assets.py` to `apple2gs/test_codex_assets.py`
- Modify: `apple2gs/gen_assets.py`
- Modify: `apple2gs/preview.py`
- Modify: `apple2gs/codex.s`
- Modify: `apple2/codex2.s`
- Modify: `tests/test_codex_identity.py`
- Regenerate: `apple2gs/assets.inc`

**Interfaces:**
- Produces: deterministic `LOGO_FRAMES`, `LOGO_SEQUENCE`, and generated `mascot_data`/`splash_data` symbols consumed by existing GS draw routines.
- Consumes: the existing 2-bit 640-mode packing and session color control values.

- [ ] **Step 1: Replace Patch tests with logo and palette tests**

Test that the asset generator has no `patch_art` import, no Patch/coral strings, all non-black palette entries are neutral (`r == g == b`), and the two logo frames differ only by the underscore. Update the identity test to reject `Patch`, `Cogitating`, and `coral` across source and generated assets.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python3 -m pytest apple2gs/test_codex_assets.py tests/test_codex_identity.py -q`

Expected: FAIL because Patch assets and coral remain.

- [ ] **Step 3: Define code-native `>_` frames and neutral palettes**

Move the art into `gen_assets.py` as these two equal-size frames using only `.`
and `W`:

```python
LOGO_OFF = (
    "..WW............", "...WW...........", "....WW..........",
    ".....WW.........", "....WW..........", "...WW...........",
    "..WW............",
)
LOGO_ON = LOGO_OFF[:-1] + ("..WW..WWWWWW....",)
```

Set session and splash palettes to black, dark gray, light gray, and white.
Keep palette slot numbers stable so assembly color controls do not change
protocol meaning.

Generate a short wake sequence that alternates underscore-off/on frames and ends on the on frame. Keep the existing expansion tables and DOC sound data. Remove the generated rotating word table.

- [ ] **Step 4: Adapt native drawing and preview**

Keep the GS splash/session drawing entry points but rename Patch-specific comments and state. Replace the 8-bit 16-by-5 block mascot with a compact `>_` renderer and make its underscore blink through the existing menu frame loop. Update `preview.py` to draw the boxed four-field header, monochrome bullet, fixed Working line, and no Patch crop assumptions.

- [ ] **Step 5: Regenerate, test, preview, and commit**

Run: `cd apple2gs && python3 gen_assets.py && python3 preview.py assets.inc codex-preview.png`

Run: `python3 -m pytest apple2gs/test_codex_assets.py tests/test_codex_identity.py -q`

Expected: assets regenerate, preview files are written, and tests PASS.

Commit: `git add apple2 apple2gs tests && git commit -m "feat: adopt monochrome Codex terminal identity"`

### Task 4: Draw the boxed header and Codex Working state

**Files:**
- Modify: `apple2gs/codex.s`
- Modify: `apple2/codex2.s`
- Modify: `tests/test_codex_identity.py`
- Create: `tests/test_native_ui_contract.py`

**Interfaces:**
- Consumes: Task 1's four header strings and existing `CMD_HEADER` marker.
- Produces: six-row local header box and Escape/Ctrl-C interrupt aliases.

- [ ] **Step 1: Write failing native UI contract tests**

Assert both sources define four header rows, consume four CR-terminated payloads, start transcripts at row 6, contain `Working (` and `esc to interrupt`, and transmit `$03` for both Esc and Ctrl-C during `spinner`. Assert no Esc branch sets `quitflag` inside the spinner block.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python3 -m pytest tests/test_native_ui_contract.py tests/test_codex_identity.py -q`

Expected: FAIL on three-line headers, legacy spinner copy, and Esc-to-menu.

- [ ] **Step 3: Render a width-aware six-row header**

In each `do_header`, preserve the transcript cursor, draw `+` plus `width-2` hyphens plus `+` on rows 0 and 5, then draw four rows with `| `, clipped payload, padding, and trailing `|`. Consume all four CR-terminated lines even after the visible width fills. Set GS `START_ROW = 6`; keep 8-bit `TOPROW = 6`.

- [ ] **Step 4: Replace both working indicators and Esc behavior**

Render a blinking leading bullet, ` Working (`, elapsed decimal seconds, `s * esc to interrupt)`, and clear the previous tail. Preserve GS VBL timing and 8-bit frame counting. On either key code `$1B` or `$03`, send one bare `$03` through `sccput`/`aciaput`, debounce repeated sends with an interrupt flag, and continue draining until EOT. Do not set `quitflag` for in-flight Escape.

- [ ] **Step 5: Run focused tests and assemble**

Run: `python3 -m pytest tests/test_native_ui_contract.py tests/test_codex_identity.py -q`

Run: `cd apple2gs && ca65 codex.s -o codex.o && ld65 -C codex.cfg codex.o -o CODEX && ca65 ../apple2/codex2.s -o ../apple2/codex2.o && ld65 -C ../apple2/codex2.cfg ../apple2/codex2.o -o CODEX8`

Expected: tests PASS; both binaries link.

- [ ] **Step 6: Commit**

Commit: `git add apple2 apple2gs tests && git commit -m "feat: match Codex header and working state"`

### Task 5: Full verification, disk build, docs, and sister issue

**Files:**
- Modify: `README.md`
- Modify: `docs/MODEM-SETUP.md`
- Modify: `apple2/TERMINAL-SETUP.md`
- Modify: other tracked docs found by the identity scan
- Generate: `apple2gs/CODEX.dsk`

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: release-candidate disk and one GitHub issue in `wr/apple-ii-terminal-for-claude-code`.

- [ ] **Step 1: Update public copy**

Replace Patch/spinner descriptions with `>_`, the boxed Codex header, and Working state. Ensure setup consistently says `AT&Z1=<host>:6401`, `AT&W`, then client-side `ATDS=1`. Add the verdict guidance table to modem setup docs.

- [ ] **Step 2: Run the complete automated suite**

Run: `python3 -m pytest -q`

Run: `bash tests/test_release_gate.sh`

Expected: all tests PASS and the release gate confirms both client catalog entries.

- [ ] **Step 3: Build and inspect the disk**

Run: `cd apple2gs && ./build.sh`

Expected: `CODEX.dsk` is 143,360 bytes and the DOS catalog includes both `CODEX` and `CODEX8`.

- [ ] **Step 4: Inspect generated visuals**

Open `apple2gs/codex-preview.png` and its crop, checking that `>_` is recognizable at KEGS geometry, the box is not clipped, the palette is neutral, and the Working line fits. If MAME and ROMs are available, boot `CODEX.dsk` in 40-column mode and capture the header; otherwise report that emulator check as unavailable.

- [ ] **Step 5: Run release residue scans**

Run: `rg -ni "Patch|Cogitating|Pondering|coral|AT&Z0|Claude Code|CLDTK1|ATDS=0" --glob '!docs/superpowers/**' --glob '!*.o' --glob '!CODEX' --glob '!CODEX8' .`

Expected: no unintended matches. Historical third-party/upstream attribution is reviewed manually rather than deleted blindly.

- [ ] **Step 6: Create the sister-repository issue**

Create an issue in `wr/apple-ii-terminal-for-claude-code` titled `Surface distinct modem dial failures in native clients`. The body must propose portable `ERROR`, `BUSY`, `NO CARRIER`, `NO ANSWER`, and timeout handling, retain raw modem echo and serial polling, and explicitly leave Claude on entry 0.

- [ ] **Step 7: Commit the release candidate**

Commit: `git add README.md docs apple2 apple2gs bridge tests && git commit -m "docs: prepare Codex disk for modem setup"`

- [ ] **Step 8: Report hardware limits**

State whether real WiModem 232 Pro dialing was exercised. If no hardware was attached, list that single check as outstanding and do not claim it passed.
