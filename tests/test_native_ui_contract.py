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
    gs = SOURCES[0].read_text()
    eight_bit = SOURCES[1].read_text()

    assert '"Working"' in gs
    assert '" ("' in gs
    assert '" Working ("' in eight_bit
    for text in (gs, eight_bit):
        assert '" * esc to interrupt)"' in text


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
    assert "inc     hdr_pos\n        lda     hdr_pos\n        tay" in reader


def test_gs_glyph_drawing_keeps_draining_the_scc():
    source = Path("apple2gs/codex.s").read_text()
    putchar = source.split("putchar:", 1)[1].split("draw_bullet:", 1)[0]

    assert "pc_row:\n        jsr     rb_poll" in putchar


def test_escape_and_ctrl_c_share_one_inflight_remote_interrupt_path():
    for source, sender in zip(SOURCES, ("sccput", "aciaput")):
        text = source.read_text()
        spinner = text[text.index("spinner:"):text.index("recv_reply:")]
        assert "spin_cancel" in spinner
        assert "#$1B" in spinner
        assert "#$03" in spinner
        assert "inc     spin_cancel" in spinner
        assert f"jsr     {sender}" in spinner


def test_8bit_spinner_can_force_local_recovery_after_remote_cancel():
    source = Path("apple2/codex2.s").read_text()
    spinner = source.split("spinner:", 1)[1].split("recv_reply:", 1)[0]

    assert "second Esc/Ctrl-C forces a local return" in spinner
    assert "jsr     check_carrier" in spinner
    assert "spin_wait" in spinner
    assert "lda     #EOT" in spinner
    assert "sta     quitflag" in spinner


def test_8bit_spinner_drawing_never_starves_the_single_byte_acia():
    source = Path("apple2/codex2.s").read_text()
    draw_str = source.split("draw_str:", 1)[1].split("; setstr", 1)[0]
    spinner = source.split("spinner:", 1)[1].split("recv_reply:", 1)[0]
    put_digit = spinner.split("sp_put_digit:", 1)[1]

    assert "@l:     jsr     rb_poll" in draw_str
    assert "jsr     rb_poll" in put_digit


def _format_native_elapsed(total_seconds):
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def test_native_elapsed_timer_rollovers():
    assert _format_native_elapsed(59) == "59s"
    assert _format_native_elapsed(60) == "1m 00s"
    assert _format_native_elapsed(999) == "16m 39s"
    assert _format_native_elapsed(1000) == "16m 40s"
    assert _format_native_elapsed(3600) == "1h 00m"


def test_native_timers_use_bounded_seconds_minutes_hours_digits():
    for source_path in SOURCES:
        source = source_path.read_text()
        spinner = source.split("spinner:", 1)[1].split("recv_reply:", 1)[0]
        for counter in ("sp_s1", "sp_s10", "sp_m1", "sp_m10", "sp_h"):
            assert counter in spinner
        assert "60 seconds -> carry into minutes" in spinner
        assert "60 minutes -> carry into hours" in spinner
        assert "#'h'" in spinner
        assert "#'m'" in spinner
        assert "#'s'" in spinner


def test_8bit_spinner_redraws_the_status_line_only_when_the_second_changes():
    source = Path("apple2/codex2.s").read_text()
    spinner = source.split("spinner:", 1)[1].split("recv_reply:", 1)[0]

    assert "sp_draw_line:" in spinner
    assert "sp_draw_pulse:" in spinner
    assert "jsr     sp_draw_line" in spinner
    assert "jsr     sp_draw_pulse" in spinner


def test_legacy_three_line_header_contract_is_absent():
    for source in SOURCES:
        text = source.read_text()
        assert "3 CR-terminated lines" not in text
        assert "rows 1-3" not in text


def test_8bit_interrupt_marker_draws_an_inverse_block_and_text():
    source = Path("apple2/codex2.s").read_text()
    spinner = source.split("spinner:", 1)[1].split("recv_reply:", 1)[0]
    receiver = source.split("recv_reply:", 1)[1].split("do_header:", 1)[0]
    assert "draw_interrupt:" in source
    renderer = source.split("draw_interrupt:", 1)[1].split("do_header:", 1)[0]

    assert "CMD_INTERRUPT = $06" in source
    assert "cmp     #CMD_INTERRUPT" in spinner
    assert "cmp     #CMD_INTERRUPT" in receiver
    assert "jsr     draw_interrupt" in receiver
    assert "lda     #1\n        sta     invflag" in renderer
    assert "lda     #' '\n        jsr     cout" in renderer
    assert "inverse-space block" in source
