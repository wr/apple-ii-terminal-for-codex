# Apple II Terminal for Codex

Run the authenticated Codex CLI from a real Apple II.

`CODEX.dsk` boots every Apple II from the IIgs through the II+. The IIgs gets a monochrome Super Hi-Res client with an animated `>_` mark, a Codex-style session header, transcript, Working status, and scrollback. The IIe, IIc, IIc Plus, and II/II+ use a plain-6502 text client from the same disk.

The Apple II handles the interface. A small Python bridge on your modern computer carries prompts to the installed Codex CLI and streams printable 7-bit text back over serial or a trusted LAN.

The source lives at [wr/apple-ii-terminal-for-codex](https://github.com/wr/apple-ii-terminal-for-codex). This project is derived from [Apple II Terminal for Claude Code](https://github.com/wr/apple-ii-terminal-for-claude-code). It is not affiliated with or endorsed by OpenAI.

## Quick start

You need Codex installed and authenticated on the host, Python 3.10 or newer, `CODEX.dsk`, and either a Hayes-compatible WiFi modem or a serial/emulator connection.

```sh
codex --version                 # must be 0.144.1 or newer
codex login                     # only if the host is not already authenticated
python3 -m pip install -r bridge/requirements.txt
python3 bridge/bridge.py --telnet --app --workdir /absolute/path/to/git/repo
```

The bridge never receives an API key. It starts the local `codex` executable, which owns authentication and its own session data. `--workdir` is required and must point to an existing Git repository.

The default sandbox is `workspace-write`. Use `--sandbox read-only` when the Apple II should inspect a repository without changing it:

```sh
python3 bridge/bridge.py --telnet --app --sandbox read-only \
  --workdir /absolute/path/to/git/repo
```

Codex runs with `approval_policy=never` because an Apple II cannot answer an invisible host approval dialog. Work that needs broader permission fails closed.

## Modem and disk

The bridge listens on TCP port 6401. Store it as phonebook entry 1 on a WiModem 232:

```text
AT&Z1=192.168.1.50:6401
AT&W
```

The native client dials `ATDS=1`. Other modem firmware may use different store or dial syntax; see [docs/MODEM-SETUP.md](docs/MODEM-SETUP.md).

Copy `CODEX.dsk` from Releases to a FloppyEmu SD card in 5.25-inch mode. On macOS, `tools/install-sd.sh` pushes the built image without replacing the existing FAT directory entry, which avoids FloppyEmu fragmentation failures. Back up the card first.

Power on and choose **Connect**. The bridge prints a six-character pairing code on its console the first time a client connects. Enter it on the Apple II. The 8-bit client stores the resulting bearer token on its boot disk. The IIgs client keeps it in RAM for reconnects during that boot and asks for a new code after reboot. Run with `--clear-paired` to revoke issued tokens.

If you want Codex on the reverse of an existing physical disk while keeping the other client on side A, follow [docs/PHYSICAL-DISK.md](docs/PHYSICAL-DISK.md). There is deliberately no automatic real-disk writer.

## Emulator

For KEGS, mount `CODEX.dsk`, set Serial Slot 2 to **Incoming**, and start:

```sh
python3 bridge/bridge.py --connect 127.0.0.1:6502 --app \
  --workdir /absolute/path/to/git/repo
```

For an emulator-only listener, bind it locally:

```sh
python3 bridge/bridge.py --telnet --host 127.0.0.1 --app \
  --workdir /absolute/path/to/git/repo
```

## Bridge options

Choose one transport:

| Flag | Use |
|---|---|
| `--telnet` | Listen for a WiFi modem on TCP port 6401 |
| `--connect HOST:PORT` | Connect to an emulator listener, such as KEGS on port 6502 |
| `--serial PORT` | Use a direct serial cable; default is 9600 baud |

Useful controls:

| Flag | Use |
|---|---|
| `--app` | Required for the clients on `CODEX.dsk` |
| `--workdir DIR` | Existing Git repository exposed to Codex |
| `--sandbox workspace-write\|read-only` | Set Codex's filesystem boundary |
| `--model ID` | Override the Codex model |
| `--clear-paired` | Revoke every stored device token |
| `--no-pair` | Remove the gate; isolated networks only |
| `--host 127.0.0.1` | Keep a TCP listener on the host only |

The local slash commands are `/help`, `/new`, `/model`, and `/quit`. Esc or Ctrl-C during `Working` cancels the Codex subprocess and returns any partial reply. Ctrl-C at an idle prompt returns to the menu.

## Security boundary

`--telnet` is for a trusted home LAN. Traffic, pairing codes, tokens, prompts, and replies are plaintext. Never port-forward it or expose it to the public internet. Possession of an 8-bit client's disk token grants access to the configured Codex bridge, so treat that disk image like a key. Read [SECURITY.md](SECURITY.md) before enabling `workspace-write`.

## Compatibility

The disk selects the right client at boot:

- IIgs: 65816 Super Hi-Res client.
- IIe with or without an auxiliary card: 80 or 40 columns; Super Serial Card in slot 2.
- IIc and IIc Plus: built-in modem port.
- II and II+: 40 columns; Super Serial Card in slot 2.

Current emulator and real-hardware coverage is listed in [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Plain terminal mode

Run without `--app` to use a normal Apple II terminal program or the IIc firmware terminal. Wiring, serial settings, and first-contact steps are in [apple2/TERMINAL-SETUP.md](apple2/TERMINAL-SETUP.md).

## Build from source

Install cc65 and build [dos33fsprogs](https://github.com/deater/dos33fsprogs), then point `DOS33FSPROGS` at that checkout:

```sh
DOS33FSPROGS=/path/to/dos33fsprogs ./apple2gs/build.sh
DOS33FSPROGS=/path/to/dos33fsprogs ./tools/check-release-disk.sh
```

The build uses only the Python standard library for generated assets. The optional screen preview needs Pillow:

```sh
python3 -m pip install Pillow
cd apple2gs
python3 preview.py assets.inc preview.png
```

The result is a reproducible 143,360-byte `apple2gs/CODEX.dsk` containing `CODEX` for the IIgs and `CODEX8` for 8-bit models. It starts from the vendored January 1983 DOS 3.3 System Master; legal and provenance details are in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Credits

- The pixel `>_` artwork and the Codex conversion are original project work.
- [UNSCII](http://viznut.fi/unscii/) by Viljami Salminen supplies the IIgs font under CC0.
- [dos33fsprogs](https://github.com/deater/dos33fsprogs) by Vince Weaver builds the disk.
- [KEGS](https://kegs.sourceforge.net/) and MAME support emulator testing.

The MIT license covers this project's code, not every byte of the derived disk image. See [NOTICE.md](NOTICE.md) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
