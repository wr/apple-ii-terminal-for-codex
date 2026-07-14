# IIgs Header Row and Prompt Glyph Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render every buffered IIgs header character exactly once and make the `>_` Codex mark legible in KEGS and on a real IIgs CRT.

**Architecture:** Correct the off-by-one read in the existing fixed-slot header buffer without changing its protocol or layout. Override only ASCII `>` and `_` during generated-font assembly, leaving the rest of UNSCII untouched.

**Tech Stack:** ca65/ld65 65816 assembly, Python 3 asset generator, pytest, DOS 3.3 disk tools.

## Global Constraints

- Keep the full-width 80-column header box.
- Do not change bridge framing, pairing, chat, or header-field content.
- Preserve capture-before-render for the IIgs SCC's three-byte FIFO.
- Generate `apple2gs/assets.inc` through `apple2gs/gen_assets.py`.

---

### Task 1: Correct buffered header indexing

**Files:**
- Modify: `apple2gs/codex.s` in `hdr_readline`
- Test: `tests/test_native_ui_contract.py`

**Interfaces:**
- Consumes: `HDRBUF` slots with length at offset 0 and text at offsets 1 through N.
- Produces: `hdr_readline` draws offsets 1 through N once.

- [ ] **Step 1: Write the failing source-contract test**

Add to `test_gs_buffers_the_complete_header_before_drawing_it`:

```python
assert "inc     hdr_pos\n        lda     hdr_pos\n        tay" in reader
```

- [ ] **Step 2: Verify the test fails**

```bash
PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q tests/test_native_ui_contract.py::test_gs_buffers_the_complete_header_before_drawing_it
```

Expected: FAIL because `tay` receives the pre-increment accumulator value.

- [ ] **Step 3: Implement the corrected read order**

```asm
        inc     hdr_pos
        lda     hdr_pos
        tay
        lda     (tmp2),y
        jsr     putchar
```

- [ ] **Step 4: Re-run the focused test**

Run the Step 2 command. Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add apple2gs/codex.s tests/test_native_ui_contract.py
git commit -m "fix: read complete GS header rows"
```

### Task 2: Replace the ambiguous prompt glyphs

**Files:**
- Modify: `apple2gs/gen_assets.py` in `emit_font`
- Create: `tests/test_gs_font_assets.py`
- Generated: `apple2gs/assets.inc`

**Interfaces:**
- Consumes: the glyph dictionary returned by `load_unscii`.
- Produces: `emit_font()` with explicit 8x8 rows for `>` and `_`.

- [ ] **Step 1: Write the failing glyph test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("apple2gs").resolve()))
import gen_assets


def _glyph_rows(font: str, char: str) -> str:
    return font.split(f"    ; '{char}'\n", 1)[1].splitlines()[0]


def test_terminal_prompt_glyphs_are_crt_legible():
    font = gen_assets.emit_font()
    assert _glyph_rows(font, ">") == "    .byte $00,$40,$20,$10,$20,$40,$00,$00"
    assert _glyph_rows(font, "_") == "    .byte $00,$00,$00,$00,$00,$00,$7E,$00"
```

- [ ] **Step 2: Verify the stock glyphs fail**

```bash
PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q tests/test_gs_font_assets.py
```

Expected: FAIL showing the current UNSCII rows.

- [ ] **Step 3: Add two explicit overrides**

```python
FONT_OVERRIDES = {
    ord(">"): [0x00, 0x40, 0x20, 0x10, 0x20, 0x40, 0x00, 0x00],
    ord("_"): [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7E, 0x00],
}
```

Inside `emit_font()`:

```python
rowbytes = FONT_OVERRIDES.get(code, glyphs.get(code, blank))
```

- [ ] **Step 4: Run the glyph test and regenerate assets**

```bash
PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q tests/test_gs_font_assets.py
cd apple2gs && ../.venv/bin/python gen_assets.py
```

Expected: `1 passed`, then `wrote assets.inc`.

- [ ] **Step 5: Render the preview**

```bash
cd apple2gs && ../.venv/bin/python preview.py assets.inc /tmp/codex-preview.png
```

Expected: the header preview shows a clean chevron and raised underscore.

- [ ] **Step 6: Commit**

```bash
git add apple2gs/gen_assets.py apple2gs/assets.inc tests/test_gs_font_assets.py
git commit -m "fix: sharpen GS terminal prompt glyphs"
```

### Task 3: Build and verify the release disk

**Files:**
- Generated: `apple2gs/CODEX.dsk`

**Interfaces:**
- Consumes: corrected GS source and regenerated assets.
- Produces: a bootable DOS 3.3 disk containing `CODEX` and `CODEX8`.

- [ ] **Step 1: Run the complete suite**

```bash
PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest -q
```

Expected: all non-hardware tests pass; hardware/live skips remain explicit.

- [ ] **Step 2: Build both clients and the disk**

```bash
cd apple2gs && ./build.sh
```

Expected: the catalog contains `CODEX` and `CODEX8`.

- [ ] **Step 3: Run the disk release gate**

```bash
./tests/test_release_gate.sh "$PWD/apple2gs/CODEX.dsk"
```

Expected: `release gate test: valid disk accepted; missing CODEX8 rejected`.

- [ ] **Step 4: Record checksum and repository evidence**

```bash
shasum -a 256 apple2gs/CODEX.dsk
git diff --check
git status --short --branch
```

Expected: a SHA-256 checksum, no whitespace errors, and only intentional changes.

- [ ] **Step 5: Hand off for hardware verification**

Provide the disk path and checksum. Confirm in KEGS and ask the user to verify on the IIgs that all four fields retain their first and last characters and the title begins with a recognizable `>_`.
