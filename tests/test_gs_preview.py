import sys
from pathlib import Path


sys.path.insert(0, str(Path("apple2gs").resolve()))
import preview


def test_preview_parses_named_interrupt_palette():
    assets = """shr_palette_interrupt:
    .word $0000
    .word $0999
    .word $0D33
    .word $0FFF
"""
    assert preview.parse_palette(assets, "shr_palette_interrupt")[:4] == [
        (0, 0, 0),
        (153, 153, 153),
        (221, 51, 51),
        (255, 255, 255),
    ]


def test_interrupt_marker_is_fourteen_pixels_wide_for_shr_aspect_ratio():
    filled_rows = [row for row in preview._INTERRUPT if "#" in row]
    assert len(filled_rows) == 6
    assert all(row.count("#") == 14 for row in filled_rows)
