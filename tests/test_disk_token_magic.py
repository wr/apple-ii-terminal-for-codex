import shutil
import sys
from pathlib import Path


sys.path.insert(0, str(Path("apple2gs").resolve()))
import reserve_token_sector


TRACK, SECTOR, SIZE = 0x12, 0x0F, 256


def test_token_sector_reservation_is_blank_and_allocated(tmp_path):
    disk = tmp_path / "reserved.dsk"
    shutil.copyfile("apple2gs/dos33-master-jan83.dsk", disk)

    assert reserve_token_sector.main(str(disk)) == 0

    image = disk.read_bytes()
    assert len(image) == 143360
    offset = (TRACK * 16 + SECTOR) * SIZE
    assert image[offset:offset + 6] == b"\x00" * 6
    vtoc = (0x11 * 16) * SIZE
    bitmap = vtoc + 0x38 + TRACK * 4
    assert image[bitmap] & 0x80 == 0
