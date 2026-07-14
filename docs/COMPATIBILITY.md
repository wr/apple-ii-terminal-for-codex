# Compatibility

`CODEX.dsk` carries two clients. Its DOS `HELLO` program reads the machine ROM and starts the right one:

- `CODEX`: 65816 Super Hi-Res client for the IIgs.
- `CODEX8`: plain-6502 text client for all other supported models.

| Machine | Client | Emulator-tested | Metal-tested | Notes |
|---|---|---|---|---|
| IIgs | Super Hi-Res | Yes, KEGS | Yes | Uses modem port and initializes the SCC itself. |
| IIe, 80 column | Text | Yes, MAME enhanced IIe | Not yet | Needs an auxiliary card and Super Serial Card in slot 2. |
| IIe, 40 column | Text | Not yet | Not yet | Detects the missing auxiliary card and falls back to 40 columns. Needs an SSC. |
| IIc | Text | Yes, MAME | Yes | Uses the built-in modem port. |
| IIc Plus | Text | Not yet | Not yet | Scales timing for the 4 MHz CPU. |
| II / II+ | Text | Not yet | Not yet | Plain 6502 and 40-column text. Needs an SSC in slot 2. |

Emulator-tested means the logic ran through the scripted path. It does not prove the electrical and timing behavior of the matching physical machine. Real IIgs and IIc hardware are the current metal coverage.

KEGS needs a user-supplied IIgs ROM. The 8-bit MAME harness also needs ROM files that this repository cannot distribute.
