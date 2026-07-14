# IIgs header row and prompt glyph fix

## Problem

The buffered IIgs header renderer displays the slot length as a stray first
glyph and omits the final character. `hdr_readline` increments `hdr_pos` in
memory but transfers the accumulator's pre-increment value into Y, so it reads
slot offsets 0 through N-1 instead of 1 through N.

The bundled UNSCII `>` is brace-like at the IIgs display aspect ratio, while
its `_` occupies the lowest scanline and does not read clearly as the Codex
`>_` mark.

## Design

- Keep the header box at its current full 80-column width. KEGS shows that the
  edges render correctly, so no inset or layout change is needed.
- In `hdr_readline`, reload `hdr_pos` after incrementing it and before `tay`.
  This makes the reader consume captured bytes 1 through N exactly once.
- Add explicit 8x8 bitmap overrides for ASCII `>` and `_` in
  `apple2gs/gen_assets.py`. Use a clean single-stroke chevron and raise the
  underscore one scanline so the pair remains legible on a CRT.
- Regenerate `assets.inc` through the normal build.

## Verification

- Add a source contract test for the corrected increment, reload, and index
  order.
- Add an asset-generation test for the exact custom glyph rows.
- Render the preview, assemble both clients, run the full Python suite and disk
  release gate, then rebuild `CODEX.dsk` for KEGS and real-IIgs confirmation.

No bridge protocol, pairing, chat, or header-field content changes are in scope.
