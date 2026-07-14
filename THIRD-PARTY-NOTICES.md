# Third-party notices

The MIT license in [LICENSE](LICENSE) covers this project's code and original `>_` artwork. It does not relicense the Apple DOS material in the repository or the derived release disk.

## Apple DOS 3.3 System Master, January 1983

- File: `apple2gs/dos33-master-jan83.dsk`
- Size: 143,360 bytes
- SHA-256: `70986935d95c4a918852700364ac107607eb861a7d93a69c2b5caf44a696b17a`
- Copyright: Apple Computer, Inc.

Apple has not placed DOS 3.3 in the public domain or supplied this project with a redistribution license. The image is widely preserved by the retrocomputing community and is included here in good faith for interoperability. It will be removed on a rights holder's request.

`apple2gs/build.sh` copies this master, replaces `HELLO`, adds the `CODEX` and `CODEX8` client binaries, and reserves one token sector. The distributed derivative artifact is `CODEX.dsk`. Its DOS boot code and filesystem remain Apple's material. The project's MIT license does not cover the whole disk.

## UNSCII bitmap font

- File: `apple2gs/unscii-8.hex`
- SHA-256: `03094f7fbab7085cf6a6b624cee61e47e71ce5d0c2f308c2f4436afdc17f776c`
- Author: Viljami Salminen, [UNSCII](http://viznut.fi/unscii/)
- License: CC0 / public domain

Selected glyphs are packed into the IIgs client at build time.

## dos33fsprogs

[dos33fsprogs](https://github.com/deater/dos33fsprogs), by Vince Weaver, is a GPL-licensed host build tool. It is installed separately and does not ship inside `CODEX.dsk`.

## Tools referenced but not bundled

- cc65 (`ca65` and `ld65`), under its own zlib license.
- Codex CLI, installed and authenticated separately by the user.
- KEGS and MAME, used for emulator testing under their own licenses.

See [NOTICE.md](NOTICE.md) for the upstream modification notice and non-affiliation statement.
