#!/bin/bash
# Install or update the Claude Code ][ disk image on a FloppyEmu SD card.
#
# FloppyEmu requires each image file to be CONTIGUOUS on the card's FAT
# filesystem. A plain copy is fine on a healthy card, but once the card's
# free space fragments, freshly copied files get split and the Emu refuses
# them ("file not contiguous"). This installer avoids that:
#   - update:  if the image already exists on the card at the same size, it
#              is overwritten IN PLACE (same clusters, new bytes) - this can
#              never fragment, so updates always work.
#   - install: plain copy + cleanup of macOS "._*" droppings; if the Emu
#              still complains, run with --repair once.
#   - repair:  repacks every file on the card (copy off, wipe, copy back),
#              which defragments it; plain copies work again afterwards.
#
# Usage:
#   tools/install-sd.sh [image.dsk] [/Volumes/CARD]
#   tools/install-sd.sh --repair [/Volumes/CARD]
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

find_card() {
    local cards=()
    while IFS= read -r line; do
        cards+=("$line")
    done < <(mount | awk '/msdos|exfat/ {sub(/^.* on /,""); sub(/ \(.*/,""); print}')
    [ ${#cards[@]} -gt 0 ] || die "no FAT-formatted volume mounted - insert the SD card"
    [ ${#cards[@]} -eq 1 ] || die "several FAT volumes mounted (${cards[*]}) - pass the card path explicitly"
    echo "${cards[0]}"
}

repair=false
if [ "${1:-}" = "--repair" ]; then
    repair=true
    shift
fi

if $repair; then
    card="${1:-$(find_card)}"
    [ -d "$card" ] || die "no such volume: $card"
    echo "This repacks EVERY file on $card (copy off, wipe, copy back)."
    read -r -p "Continue? [y/N] " a
    [ "$a" = "y" ] || [ "$a" = "Y" ] || exit 1
    tmp=$(mktemp -d)
    echo "copying card contents to $tmp ..."
    rsync -a --exclude='._*' --exclude='.Spotlight-V100' --exclude='.fseventsd' \
          --exclude='.Trashes' --exclude='.DS_Store' "$card/" "$tmp/"
    echo "wiping card ..."
    find "$card" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    echo "copying back in one pass ..."
    rsync -a "$tmp/" "$card/"
    dot_clean -m "$card" 2>/dev/null || true
    sync
    rm -rf "$tmp"
    echo "done - files are repacked contiguously; plain copies will work again"
    exit 0
fi

script_dir=$(cd "$(dirname "$0")" && pwd)
image="${1:-$script_dir/../apple2gs/CLAUDEG.dsk}"
[ -f "$image" ] || die "image not found: $image (run apple2gs/build.sh first?)"
card="${2:-$(find_card)}"
[ -d "$card" ] || die "no such volume: $card"

dest="$card/$(basename "$image")"
if [ -f "$dest" ] && [ "$(stat -f%z "$image")" -eq "$(stat -f%z "$dest")" ]; then
    dd if="$image" of="$dest" conv=notrunc status=none
    sync
    echo "updated in place: $dest (clusters reused - cannot fragment)"
else
    cp "$image" "$dest"
    dot_clean -m "$card" 2>/dev/null || true
    rm -f "$card/._$(basename "$image")"
    sync
    echo "installed: $dest"
    echo "if FloppyEmu says 'file not contiguous', run: $0 --repair"
fi
