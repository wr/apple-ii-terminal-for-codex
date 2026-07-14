from pathlib import Path


def test_gs_enters_6502_emulation_mode_around_dos_rwts():
    source = Path("apple2gs/codex.s").read_text()
    wrapper = source.split("rwts_call:", 1)[1].split("; tok_valid", 1)[0]

    enter = wrapper.index("sec")
    enter_xce = wrapper.index("xce", enter)
    call = wrapper.index("jsr     RWTS", enter_xce)
    leave = wrapper.index("clc", call)
    leave_xce = wrapper.index("xce", leave)
    restore_width = wrapper.index("rep     #$30", leave_xce)

    assert enter < enter_xce < call < leave < leave_xce < restore_width
