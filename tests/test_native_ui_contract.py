from pathlib import Path


SOURCES = (Path("apple2gs/codex.s"), Path("apple2/codex2.s"))


def test_native_clients_expect_four_header_lines_and_six_header_rows():
    for source in SOURCES:
        text = source.read_text()
        assert "HEADER_LINES = 4" in text
        assert "HEADER_ROWS = 6" in text
        assert "hdr_border" in text
    assert "START_ROW = 6" in SOURCES[0].read_text()
    assert "TOPROW  = 6" in SOURCES[1].read_text()


def test_native_clients_show_codex_working_copy():
    for source in SOURCES:
        text = source.read_text()
        assert '" Working ("' in text
        assert '"s * esc to interrupt)"' in text


def test_menu_title_is_centered_for_its_29_character_width():
    gs = Path("apple2gs/codex.s").read_text()
    eight_bit = Path("apple2/codex2.s").read_text()

    assert gs.count("TEXT    str_welcome, 25, 16, 2") == 2
    assert "sbc     #29" in eight_bit


def test_gs_buffers_the_complete_header_before_drawing_it():
    source = Path("apple2gs/codex.s").read_text()
    header = source.split("do_header:", 1)[1].split("check_incoming:", 1)[0]
    reader = header.split("hdr_readline:", 1)[1].split("check_incoming:", 1)[0]

    assert "HDRBUF" in source
    assert header.index("jsr     hdr_capture") < header.index("TEXT    hdr_border")
    assert "getbyte" not in reader


def test_escape_and_ctrl_c_share_one_inflight_interrupt_path():
    for source in SOURCES:
        text = source.read_text()
        spinner = text[text.index("spinner:"):text.index("recv_reply:")]
        assert "spin_cancel" in spinner
        assert "#$1B" in spinner
        assert "#$03" in spinner
        assert "sp_esc" not in spinner
        assert "fake end-of-reply" not in spinner


def test_legacy_three_line_header_contract_is_absent():
    for source in SOURCES:
        text = source.read_text()
        assert "3 CR-terminated lines" not in text
        assert "rows 1-3" not in text
