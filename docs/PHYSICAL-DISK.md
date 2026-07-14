# Put Codex on side B of a physical disk

This is a manual preservation-minded procedure. No project script writes a real floppy automatically.

1. Use media certified for double-sided recording. Do not assume a single-sided disk is safe to record on its reverse.
2. Back up both surfaces before changing either one.
3. Put `CLAUDE.dsk` and `CODEX.dsk` on FloppyEmu as separate files.
4. Keep Claude on side A. Flip the physical disk and use a trusted Apple II disk utility to copy `CODEX.dsk` from FloppyEmu to side B.
5. Before writing, confirm the source is FloppyEmu and the destination is the real disk.
6. Add a reverse-side write-enable notch only if the drive requires one and the media is safe for it.
7. Cold-boot each side. Confirm side A uses phonebook entry 0 and port 6400, while side B sends `ATDS=1` to port 6401.
8. Pair both clients and confirm the token stored on one side does not unlock the other bridge.

Keep the backups. Label both surfaces so the source and destination cannot be confused during a later copy.
