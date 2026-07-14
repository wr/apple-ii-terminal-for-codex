from pathlib import Path

from gen_assets import (
    COLORS,
    COLORS_SPLASH,
    LOGO_FRAMES,
    LOGO_ON,
    SND_WAKE0,
    SND_WAKE1,
)


HERE = Path(__file__).parent


def test_logo_frames_have_one_packable_geometry_and_blink_underscore():
    shapes = {(len(frame), len(frame[0])) for frame in LOGO_FRAMES.values()}
    assert shapes == {(7, 16)}
    assert all(set(row) <= {".", "W"} for frame in LOGO_FRAMES.values() for row in frame)
    off = LOGO_FRAMES["off"]
    on = LOGO_FRAMES[LOGO_ON]
    assert off[:-1] == on[:-1]
    assert off[-1] == "..WW............"
    assert on[-1] == "..WW..WWWWWW...."


def test_all_generated_palettes_are_neutral():
    for palette in (COLORS, COLORS_SPLASH):
        assert all(r == g == b for r, g, b in palette.values())


def test_asset_build_has_no_patch_coral_or_pillow_dependency():
    source = (HERE / "gen_assets.py").read_text()
    assert "patch_art" not in source
    assert "Patch" not in source
    assert "coral" not in source.lower()
    assert "PIL" not in source
    assert "Pillow" not in (HERE.parent / "requirements-build.txt").read_text()


def test_codex_wake_is_four_notes_a_rest_and_a_fifth():
    assert SND_WAKE0 == [
        (329.6, 4),
        (392.0, 4),
        (493.9, 4),
        (659.3, 4),
        (0, 3),
        (659.3, 28),
    ]
    assert SND_WAKE1 == [(0, 19), (440.0, 28)]
    assert sum(duration for _, duration in SND_WAKE0) == sum(
        duration for _, duration in SND_WAKE1
    )


def test_8bit_wake_uses_the_codex_prompt_cadence():
    source = (HERE.parent / "apple2" / "codex2.s").read_text()
    assert "jtab_d: .byte 76,64,51,38,$FE,57,38,57,38,57,0" in source
    assert "jtab_w: .byte 60,71,89,120,18,105,157,105,157,254" in source
