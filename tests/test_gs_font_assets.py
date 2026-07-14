import sys
from pathlib import Path

sys.path.insert(0, str(Path("apple2gs").resolve()))
import gen_assets


def _glyph_rows(font: str, char: str) -> str:
    return font.split(f"    ; '{char}'\n", 1)[1].splitlines()[0]


def test_terminal_prompt_glyphs_are_crt_legible(monkeypatch):
    monkeypatch.chdir(Path("apple2gs"))
    font = gen_assets.emit_font()
    assert _glyph_rows(font, ">") == (
        "    .byte $C0,$30,$0C,$03,$0C,$30,$C0,$00"
    )
    assert _glyph_rows(font, "_") == (
        "    .byte $00,$00,$00,$00,$00,$00,$7E,$00"
    )
