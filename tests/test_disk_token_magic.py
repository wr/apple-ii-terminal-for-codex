from pathlib import Path


TRACK, SECTOR, SIZE = 0x12, 0x0F, 256


def test_release_disk_token_sector_is_blank_and_reserved():
    image = Path("apple2gs/CODEX.dsk").read_bytes()
    assert len(image) == 143360
    offset = (TRACK * 16 + SECTOR) * SIZE
    assert image[offset:offset + 6] == b"\x00" * 6
    vtoc = (0x11 * 16) * SIZE
    bitmap = vtoc + 0x38 + TRACK * 4
    assert image[bitmap] & 0x80 == 0
