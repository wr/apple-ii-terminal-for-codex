import sys
from pathlib import Path


sys.path.insert(0, str(Path("apple2gs").resolve()))
import gen_assets


def test_session_palette_has_three_visible_tones():
    palette = gen_assets.emit_palette().splitlines()
    assert [line.strip() for line in palette[1:5]] == [
        ".word $0000",
        ".word $0999",
        ".word $0CCC",
        ".word $0FFF",
    ]


def test_interrupt_palette_only_replaces_light_gray_with_red():
    palette = gen_assets.emit_palette().splitlines()
    start = palette.index("shr_palette_interrupt:")
    assert [line.strip() for line in palette[start + 1:start + 5]] == [
        ".word $0000",
        ".word $0999",
        ".word $0D33",
        ".word $0FFF",
    ]


def test_interrupt_asset_is_a_filled_square():
    assert gen_assets.emit_interrupt() == (
        "interrupt_data:\n    .byte $00,$7E,$7E,$7E,$7E,$7E,$7E,$00"
    )


def _source() -> str:
    return Path("apple2gs/codex.s").read_text()


def _byte_table(source: str, label: str, rows: int) -> list[int]:
    tail = source.split(f"{label}:", 1)[1]
    lines = [line for line in tail.splitlines() if ".byte" in line][:rows]
    return [
        int(value.strip())
        for line in lines
        for value in line.split(".byte", 1)[1].split(";", 1)[0].split(",")
    ]


def test_working_shimmer_has_eight_seven_character_frames():
    source = _source()
    colors = _byte_table(source, "shimmer_colors", 8)
    assert len(colors) == 56
    assert colors == [
        3, 2, 1, 1, 1, 1, 1,
        2, 3, 2, 1, 1, 1, 1,
        1, 2, 3, 2, 1, 1, 1,
        1, 1, 2, 3, 2, 1, 1,
        1, 1, 1, 2, 3, 2, 1,
        1, 1, 1, 1, 2, 3, 2,
        1, 1, 1, 1, 1, 2, 3,
        1, 1, 1, 1, 1, 1, 2,
    ]


def test_spinner_pulses_visible_star_and_draws_only_working_in_shimmer():
    source = _source()
    spinner = source.split("spinner:", 1)[1].split("spin_pace:", 1)[0]
    assert _byte_table(source, "star_colors", 1) == [1, 2, 3, 2]
    assert "jsr     draw_working" in spinner
    assert "sp_boff" not in spinner
    assert 'str_working:.byte "Working",0' in source
    assert 'str_worktail:.byte " (",0' in source


def test_header_title_uses_white_color_three():
    source = _source()
    header = source.split("do_header:", 1)[1].split("hdr_capture:", 1)[0]
    assert "lda     #3\n        sta     txtcolor        ; title row is white" in header


def test_gs_interrupt_rows_use_palette_one_and_semantic_red():
    source = _source()
    receiver = source.split("recv_reply:", 1)[1].split("do_header:", 1)[0]
    renderer = source.split("put_common:", 1)[1].split("draw_bullet:", 1)[0]
    scroller = source.split("scroll_up:", 1)[1].split("clear_rowA:", 1)[0]
    clearer = source.split("clear_rowA:", 1)[1].split("draw_mascot:", 1)[0]

    assert "CMD_INTERRUPT = $06" in source
    assert "COLOR_RED = $06" in source
    assert "CELL_INTERRUPT = $02" in source
    assert "cmp     #CMD_INTERRUPT" in receiver
    assert "jsr     draw_interrupt" in receiver
    assert "and     #$03" in renderer
    assert "$9D00" in scroller and "SCBs follow their text rows" in scroller
    assert "#$80" in clearer and "restore palette 0" in clearer
    assert "set_interrupt_row:" in source
    assert "interrupt_data" in source
