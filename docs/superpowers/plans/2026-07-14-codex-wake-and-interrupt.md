# Codex Wake and Interrupt Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Codex a distinct restrained wake phrase and render interrupted turns as a red square and red text on the IIgs, with an inverse-video fallback on 8-bit Apples.

**Architecture:** The bridge emits a new `CMD_INTERRUPT` control byte before the interruption text. The IIgs uses SHR palette 1 on that text row and stores semantic red as color 6 (hardware color 2 after masking); the 8-bit client translates the same marker into inverse video. Generated sound streams keep the existing playback engines and replace only the wake note data.

**Tech Stack:** Python, pytest, ca65 6502/65816 assembly, Apple IIgs Super Hi-Res SCBs and palettes, DOS 3.3 disk tooling.

## Global Constraints

- Keep the dial theater, reply bell, `Working` shimmer, cancellation timing, partial replies, and normal colors unchanged.
- Preserve red during live scrolling and scrollback redraws.
- Keep the wake quiet, once per boot, skippable, and approximately the current duration.
- Use `CMD_INTERRUPT = $06` in both clients and `CMD_INTERRUPT = b"\x06"` in the bridge.

---

### Task 1: Distinct Codex wake phrase

**Files:**
- Modify: `apple2gs/gen_assets.py`
- Modify: `apple2/codex2.s`
- Modify: `apple2gs/test_codex_assets.py`

**Interfaces:**
- Produces: `SND_WAKE0` and `SND_WAKE1`, equal-duration GS note streams.
- Produces: `jtab_d` and `jtab_w`, the 8-bit approximation consumed by `jingle`.

- [ ] Add failing asset tests that require four initial GS notes, an explicit rest, equal voice duration, and a wake sequence different from the Claude sequence.
- [ ] Run `PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q apple2gs/test_codex_assets.py` and confirm the new assertions fail.
- [ ] Replace the GS seven-step sweep with four short rising notes, a three-vblank rest, and a sustained E5/A4 fifth:

```python
SND_WAKE0 = [(329.6, 4), (392.0, 4), (493.9, 4), (659.3, 4),
             (0, 3), (659.3, 28)]
SND_WAKE1 = [(0, 19), (440.0, 28)]
```

- [ ] Replace the 8-bit seven-step table with the octave-up four-step approximation, flagged rest, and alternating A/E landing below. The opening note products stay near 4,560 and the landing stays near the current total duration.

```asm
jtab_d: .byte 76,64,51,38,$FE,57,38,57,38,57,0
jtab_w: .byte 60,71,89,120,18,105,157,105,157,254
```
- [ ] Re-run the asset tests and assemble both clients.
- [ ] Commit with `git commit -m "feat: give Codex a distinct wake sound"`.

### Task 2: Bridge interrupt marker

**Files:**
- Modify: `bridge/bridge.py`
- Modify: `tests/test_interrupt.py`

**Interfaces:**
- Produces: `CMD_INTERRUPT = b"\x06"`.
- Sends: blank line, `CMD_INTERRUPT`, `Interrupted by user`, then `EOT`.

- [ ] Extend an existing app-mode interrupt test to assert:

```python
marker = out.index(bridge.CMD_INTERRUPT)
message = out.index(b"Interrupted by user")
assert marker < message < out.index(bridge.EOT, message)
assert b"* Interrupted by user" not in out
```

- [ ] Run the focused interrupt test and confirm it fails because `CMD_INTERRUPT` is absent.
- [ ] Define the marker beside `EOT` and replace the gray ASCII-star prefix with:

```python
term.write(CMD_INTERRUPT)
term.write_line("Interrupted by user")
```

- [ ] Run all interrupt tests and commit with `git commit -m "feat: mark interrupted native replies"`.

### Task 3: IIgs red interrupt rows

**Files:**
- Modify: `apple2gs/gen_assets.py`
- Modify: `apple2gs/codex.s`
- Modify: `tests/test_native_ui_contract.py`
- Modify: `tests/test_gs_shimmer.py`

**Interfaces:**
- Produces: `shr_palette_interrupt`, matching `shr_palette` except color 2 is `$0D33`.
- Consumes: `CMD_INTERRUPT` and stores semantic red as `COLOR_RED = $06`.
- Produces: `set_interrupt_row`, which writes `$81` to the current row's eight SCBs.

- [ ] Add failing tests for the interrupt palette, marker dispatch, semantic red constant, square glyph, color masking, SCB row selection, SCB copying in `scroll_up`, and palette restoration in `clear_rowA`.
- [ ] Run the focused GS tests and confirm the new assertions fail.
- [ ] Generate palette 1 and load its 32 bytes into `$E19E20` during initialization.
- [ ] Add `interrupt_data` as a filled 6x6 square and `CELL_INTERRUPT = $02` for scrollback replay.
- [ ] Handle `CMD_INTERRUPT` in `recv_reply`: set the current row's SCBs to palette 1, draw/record the square and a space, then select semantic red.
- [ ] Mask `txtcolor` with `#$03` before calculating `coloff`, allowing stored color 6 to render as hardware color 2.
- [ ] Copy the eight relevant SCBs when `scroll_up` moves a text row, reset cleared rows to `$80`, and make `draw_buf_line` select palette 1 when it sees color 6.
- [ ] Re-run focused tests and assemble the GS client.
- [ ] Commit with `git commit -m "feat: render GS interrupts in red"`.

### Task 4: 8-bit inverse interrupt rows

**Files:**
- Modify: `apple2/codex2.s`
- Modify: `tests/test_native_ui_contract.py`

**Interfaces:**
- Consumes: `CMD_INTERRUPT = $06`.
- Produces: an inverse-space block, a normal separating space, and inverse interruption text.

- [ ] Add a failing source-contract test requiring `CMD_INTERRUPT`, an interrupt dispatch branch in `recv_reply`, and a `draw_interrupt` routine that calls `putscr` with an inverse space before setting `invflag` for the message.
- [ ] Run the focused native UI test and confirm it fails.
- [ ] Add the marker dispatch and minimal renderer without changing ordinary `CMD_COLOR` handling.
- [ ] Re-run the native UI tests and assemble the 8-bit client.
- [ ] Commit with `git commit -m "feat: style 8-bit interrupt messages"`.

### Task 5: Preview, disk build, and release verification

**Files:**
- Modify: `apple2gs/preview.py`
- Generated: `apple2gs/assets.inc`
- Generated: `apple2gs/CODEX.dsk`

**Interfaces:**
- Produces: a preview containing a red interrupt line.
- Produces: the bootable `CODEX.dsk` release artifact.

- [ ] Extend the preview parser to read `shr_palette_interrupt` and draw `Interrupted by user` with its square in red.
- [ ] Generate and inspect `/tmp/codex-interrupt-preview.png`.
- [ ] Run the complete pytest suite.
- [ ] Run `cd apple2gs && ./build.sh`.
- [ ] Run `./tests/test_release_gate.sh "$PWD/apple2gs/CODEX.dsk"`.
- [ ] Record the SHA-256, `git diff --check`, and clean repository status.
- [ ] Commit preview changes with `git commit -m "test: preview Codex interrupt styling"` before the final build if they are tracked.
