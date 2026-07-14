#!/bin/bash
# Build the SHR graphics client disk. Run from apple2gs/.
set -e
cd "$(dirname "$0")"
# dos33fsprogs checkout (https://github.com/deater/dos33fsprogs, `make` in
# utils/dos33fs-utils and utils/asoft_basic-utils). Override with DOS33FSPROGS.
DOS33FSPROGS="${DOS33FSPROGS:-/tmp/dos33fsprogs}"
DOS33="$DOS33FSPROGS/utils/dos33fs-utils/dos33"
TOK="$DOS33FSPROGS/utils/asoft_basic-utils/tokenize_asoft"
[ -x "$DOS33" ] || { echo "dos33fsprogs not found at $DOS33FSPROGS - clone+make it or set DOS33FSPROGS" >&2; exit 1; }
# Base image: pristine Apple DOS 3.3 System Master (Jan 1983). We inject our
# files into it instead of generating a disk from scratch - a master-based
# image is proven to boot on both KEGS and real hardware via FloppyEmu.
# (FloppyEmu gotcha: update the SD card with `dd conv=notrunc` over the
# existing image file - a fresh copy can land fragmented and the Emu
# refuses non-contiguous files.)
BASE=dos33-master-jan83.dsk

python3 gen_assets.py
ca65 --cpu 65816 -o codex.o codex.s
ld65 -C codex.cfg -o codex.obj codex.o

# 8-bit client (IIe/IIc/IIc+/II+) shares the disk
ca65 --cpu 6502 -o ../apple2/codex2.o ../apple2/codex2.s
ld65 -C ../apple2/codex2.cfg -o CODEX8 ../apple2/codex2.o

# HELLO picks the client for the machine: IIgs -> CODEX (SHR), everything
# else -> CODEX8 (text). GS vs enhanced IIe ($FBB3=6, $FBC0=$E0 on both)
# is split by the GS id hook: SEC / JSR $FE1F / carry clear = GS. The
# stub POKEd at $300 stores the carry at 783.
# dos33 (BSD getopt) needs flags BEFORE the disk, and no '.' in filenames.
$TOK < hello.bas > HH
cp codex.obj CODEX

cp "$BASE" CODEX.dsk
$DOS33 CODEX.dsk UNLOCK HELLO
$DOS33 -y CODEX.dsk DELETE HELLO
$DOS33 -y CODEX.dsk SAVE A HH HELLO
$DOS33 -a 0x4000 CODEX.dsk BSAVE CODEX CODEX
$DOS33 -a 0x2000 CODEX.dsk BSAVE CODEX8 CODEX8
python3 reserve_token_sector.py CODEX.dsk
test "$(wc -c < CODEX.dsk | tr -d ' ')" = 143360
$DOS33 CODEX.dsk CATALOG
# Opt-in convenience deploy for KEGS (~/config.kegs boots ~/Downloads/CODEX.dsk).
# Off by default so a plain build never writes outside the repo; enable with
# COPY_TO_DOWNLOADS=1 ./build.sh. Harmless if ~/Downloads doesn't exist.
if [ -n "${COPY_TO_DOWNLOADS:-}" ]; then
  if cp CODEX.dsk "$HOME/Downloads/CODEX.dsk" 2>/dev/null; then
    echo "=== copied CODEX.dsk to ~/Downloads (COPY_TO_DOWNLOADS) ==="
  else
    echo "=== COPY_TO_DOWNLOADS set but ~/Downloads copy failed (dir missing?) ===" >&2
  fi
fi
echo "=== built CODEX.dsk (master-based, boots KEGS + FloppyEmu + real drives) ==="
echo "    (set COPY_TO_DOWNLOADS=1 to also copy it to ~/Downloads for KEGS)"
