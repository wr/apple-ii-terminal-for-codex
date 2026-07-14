from pathlib import Path

from patch_art import PATCH_FRAMES, PATCH_HOLD, PATCH_SEQUENCE, PATCH_SESSION


def test_patch_frames_have_one_640_packable_geometry():
    shapes = {(len(frame), len(frame[0])) for frame in PATCH_FRAMES.values()}
    assert shapes == {(16, 28)}
    assert all(
        len(row) == 28 for frame in PATCH_FRAMES.values() for row in frame
    )
    assert all(
        set(row) <= set(".SCGK") for frame in PATCH_FRAMES.values() for row in frame
    )


def test_storyboard_references_real_frames_and_has_typing_motion():
    assert PATCH_HOLD in PATCH_FRAMES
    assert PATCH_SESSION in PATCH_FRAMES
    assert {name for name, _duration in PATCH_SEQUENCE} <= PATCH_FRAMES.keys()
    assert {
        name for name, _duration in PATCH_SEQUENCE if name.startswith("typing_")
    } == {"typing_a", "typing_b"}


def test_asset_build_has_no_clawd_or_pillow_dependency():
    assert not Path("apple2gs/clawd.gif").exists()
    assert "PIL" not in Path("apple2gs/gen_assets.py").read_text()
    assert "Pillow" not in Path("requirements-build.txt").read_text()
