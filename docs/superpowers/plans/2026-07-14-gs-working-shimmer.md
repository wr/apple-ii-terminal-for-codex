# IIgs Working Shimmer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a three-tone shimmer to `Working` and a matching non-blinking star pulse on the IIgs.

**Architecture:** Turn session color 2 into light gray while preserving color 3 as white. Replace the monolithic Working string draw with a table-driven seven-character renderer and use a four-entry table for the star pulse.

**Tech Stack:** Python asset generator, ca65 65816 assembly, pytest, Pillow preview, DOS 3.3 build tools.

## Global Constraints

- Animate only `Working` and the leading `*`.
- Keep elapsed time, interrupt copy, serial polling, and reply detection unchanged.
- Keep the splash palette unchanged.
- Keep the real Codex header title white.

---

### Task 1: Add the third session tone

**Files:**
- Modify: `apple2gs/gen_assets.py`
- Create: `tests/test_gs_shimmer.py`

**Interfaces:**
- Produces session colors 1=`$0999`, 2=`$0CCC`, 3=`$0FFF` through `emit_palette()`.

- [ ] Write a failing test that parses the first four words from `emit_palette()` and expects `$0000,$0999,$0CCC,$0FFF`.
- [ ] Run `PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q tests/test_gs_shimmer.py` and confirm failure.
- [ ] Change `COLORS[2]` to `(0xC, 0xC, 0xC)` and update the palette documentation.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Implement the shimmer and star pulse

**Files:**
- Modify: `apple2gs/codex.s` in `spinner`, strings, tables, and BSS
- Test: `tests/test_gs_shimmer.py`

**Interfaces:**
- Consumes `frame` as the animation counter.
- Produces `draw_working`, which draws seven letters using `shimmer_colors`; `star_colors` always supplies a visible color.

- [ ] Add failing source-contract tests requiring `star_colors: .byte 1,2,3,2`, a 56-byte `shimmer_colors` table, `jsr draw_working`, and no `sp_boff` blank-star branch.
- [ ] Run the focused test and confirm failure.
- [ ] Split the status strings into `str_working: "Working"`, `str_worktail: " ("`, and the unchanged suffix.
- [ ] Draw the star every frame using `star_colors[frame & 3]`.
- [ ] Add `draw_working`: calculate `(frame & 7) * 7`, then draw each letter with its table-selected color. Use eight table rows with a white center and light-gray neighbor moving across the word and past its final letter.
- [ ] Restore color 1 before drawing `str_worktail`, seconds, and `str_interrupt`.
- [ ] Change the real header title color from 2 to 3 so it stays white.
- [ ] Re-run the focused shimmer test and the native UI contract tests.
- [ ] Commit the implementation with `git commit -m "feat: shimmer GS Working status"`.

### Task 3: Regenerate, preview, and verify

**Files:**
- Generated: `apple2gs/assets.inc`, `apple2gs/CODEX.dsk`

**Interfaces:**
- Produces the final boot disk for KEGS, FloppyEmu, and real hardware.

- [ ] Run `cd apple2gs && ../.venv/bin/python gen_assets.py`.
- [ ] Run `cd apple2gs && ../.venv/bin/python preview.py assets.inc /tmp/codex-preview.png` and inspect the grayscale hierarchy.
- [ ] Run the full pytest suite.
- [ ] Run `cd apple2gs && ./build.sh`.
- [ ] Run `./tests/test_release_gate.sh "$PWD/apple2gs/CODEX.dsk"`.
- [ ] Record `shasum -a 256 apple2gs/CODEX.dsk`, `git diff --check`, and `git status --short --branch`.
- [ ] Hand the disk to the user for live animation verification.
