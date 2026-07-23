<h1 align="center">Apple II Terminal for Codex</h1>

<p align="center">
  <strong>A real Apple II, as a terminal for the actual <code>codex</code> CLI.</strong>
</p>

<p align="center">
  <a href="#what-is-it">What is it?</a> ⬪
  <a href="#apple-ii-instructions">Install (real hardware)</a> ⬪
  <a href="#emulator-instructions">Install (emulator)</a> ⬪
  <a href="#advanced-bridge-options">Bridge options</a> ⬪
  <a href="#donate">Donate</a>
</p>

<p align="center">
  <sub>I recorded a full build video that you can <a href="https://www.youtube.com/watch?v=6VsCheEJMIk">watch here</a>.</sub>
</p>

---

## What is it?

Boot a 140K floppy, dial a WiFi modem, and your Apple II becomes a terminal for the real `codex` CLI, bridged from a modern machine. The disk image boots every model from the IIgs down to the II+ — or an emulator.

The backend is the actual agentic Codex CLI. The clients are bare-metal 65816 and 6502 programs that draw the whole interface themselves from a tiny 7-bit ASCII protocol. A IIgs gets a monochrome Super Hi-Res client with an animated `>_` splash, scrolling transcript, Codex-style header, and Working shimmer; a IIe, IIc, IIc Plus, or II+ gets a text-mode client from the same disk.

Press **Connect** and it plays the 1986 dial-up soundscape: dial tone, touch-tones that spell `C-O-D-E-X` on the keypad, ring, answer tone, and carrier buzz.

## Apple II instructions

### Prerequisites:

1. An Apple II (IIgs down to the II+ -- see [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for the tested-model matrix)
2. A Hayes-compatible modem such as the [WiModem 232 Pro](https://www.cbmstuff.com/index.php?route=product/product&path=59_66&product_id=113), or a serial connection to your modern computer
3. [FloppyEmu](https://www.bigmessowires.com/floppy-emu/) or another way to write a `.dsk` image to a floppy
4. [Codex CLI](https://github.com/openai/codex) 0.144.1 or newer, installed and logged in on your modern computer
5. **CODEX.dsk**, from [Releases](https://github.com/wr/apple-ii-terminal-for-codex/releases) (or built from source below)

### Setup:

1. **Bridge**, on the computer with the `codex` CLI:

   ```sh
   git clone https://github.com/wr/apple-ii-terminal-for-codex
   cd apple-ii-terminal-for-codex
   python3 -m pip install -r bridge/requirements.txt
   python3 bridge/bridge.py --telnet --app --workdir /absolute/path/to/your-project
   ```

   `--workdir` is the existing Git repository Codex works in. The default sandbox is `workspace-write`; use `--sandbox read-only` when the Apple II should inspect the repository without changing it. Codex runs with `approval_policy=never` because the Apple II cannot answer an invisible host approval dialog. Work outside the selected sandbox fails closed.

   The bridge listens on TCP port 6401. When an unpaired source IP first connects, the bridge creates a six-character code and prints it only on its own console. The native client exchanges that code for a bearer token. The 8-bit client stores the token on its boot disk; the IIgs keeps it in RAM for the current boot. The host stores only the token's SHA-256 hash, first-seen IP, and pairing time. Run with `--clear-paired` to revoke every issued token.

   > **Trusted LAN only.** `--telnet` exposes a shell-capable Codex session to your network. Telnet is plaintext: pairing codes, tokens, prompts, and replies can be captured. Run it only on a home LAN you trust, and never port-forward it or expose it to the public internet. Read [SECURITY.md](SECURITY.md) before enabling `workspace-write`.

   > **What the bridge records.** Every prompt you type from the Apple II prints to the bridge console. Codex owns authentication and may retain its normal local session data. The bridge never receives an API key or your Codex credentials.

2. **Modem**: store the bridge address as phonebook entry 1, then save:

   ```text
   AT&Z1=192.168.1.50:6401      (your host's LAN IP)
   AT&W
   ```

   Connect sends `ATDS=1`. Firmware differs, so another modem may use different store or dial syntax. The boot menu also has a live Hayes AT console for manual setup. A fresh WiModem ships at 300 baud and needs `AT*B9600` once; cables, per-device commands, and the dead-modem checklist are in [docs/MODEM-SETUP.md](docs/MODEM-SETUP.md).

3. **Disk**: copy `CODEX.dsk` to a FloppyEmu SD card in 5.25-inch mode (it boots from slot 6). On macOS, `tools/install-sd.sh` updates an existing image safely; FloppyEmu is sensitive to FAT32 fragmentation. Create a backup before using it.

4. Power on and choose **Connect** from the menu. Enter the pairing code shown on the bridge console when asked, then type.

To update later, download the new release image and run `tools/install-sd.sh` again. If you want Codex on the reverse of an existing physical disk, follow [docs/PHYSICAL-DISK.md](docs/PHYSICAL-DISK.md).

## Emulator instructions

[KEGS](https://kegs.sourceforge.net/) works well, but any Apple II emulator with serial emulation should work. KEGS needs an Apple IIgs ROM file that you supply.

1. Download **CODEX.dsk** from [Releases](https://github.com/wr/apple-ii-terminal-for-codex/releases).
2. In KEGS, press **F4**: set **s6d1** to `CODEX.dsk`, then set Serial Port **Slot 2** to **Incoming**. KEGS listens on TCP 6502.
3. Start the bridge, then reboot the emulator with Ctrl-Command-Reset:

   ```sh
   git clone https://github.com/wr/apple-ii-terminal-for-codex
   cd apple-ii-terminal-for-codex
   python3 -m pip install -r bridge/requirements.txt
   python3 bridge/bridge.py --connect 127.0.0.1:6502 --app \
     --workdir /absolute/path/to/your-project
   ```

4. Choose **1. Connect** on the boot menu, then type.

For an emulator that connects to a local listener instead, keep it off the LAN:

```sh
python3 bridge/bridge.py --telnet --host 127.0.0.1 --app \
  --workdir /absolute/path/to/your-project
```

## Advanced bridge options

The bridge is one Python script. Pick a transport and, for the native clients, add `--app`. Two commands cover almost everything:

```sh
# Emulator (KEGS in Incoming mode):
python3 bridge/bridge.py --connect 127.0.0.1:6502 --app \
  --workdir /absolute/path/to/your-project

# Real hardware (WiFi modem listening):
python3 bridge/bridge.py --telnet --app \
  --workdir /absolute/path/to/your-project
```

**Transport** (choose one):

| Flag | Use |
|---|---|
| `--connect HOST:PORT` | Dial out to a listening emulator (KEGS Incoming uses port 6502) |
| `--telnet` | Listen for a WiFi modem (port 6401) |
| `--serial PORT` | Use a direct serial cable, such as `/dev/tty.usbserial-1420` |

**Codex:**

| Flag | Use |
|---|---|
| `--workdir DIR` | Existing Git repository Codex may work in; required |
| `--sandbox workspace-write\|read-only` | Set Codex's filesystem boundary |
| `--model ID` | Override the Codex model |
| `--codex-bin PATH` | Use a specific Codex executable |

**Native client:**

| Flag | Use |
|---|---|
| `--app` | Native-client protocol; required for the clients on `CODEX.dsk` |
| `--cols 40\|80` | Screen width (default 80) |

**Pairing** (`--telnet` only):

| Flag | Use |
|---|---|
| `--pair-code CODE` | Fix one shared case-insensitive code for every caller |
| `--clear-paired` | Revoke every stored device token at startup |
| `--no-pair` | Remove the gate entirely; isolated networks only |
| `--host ADDR` | Bind address; use `127.0.0.1` to keep it local |

Run `python3 bridge/bridge.py --help` for flow control, pacing, telnet negotiation, and the remaining options.

## Generic terminal app instructions

Run the bridge without `--app` and it speaks ordinary 40/80-column text. Any Apple II with a terminal program, or a stock IIc using its firmware terminal over serial, can talk to Codex without installing a native client. Wiring, pinouts, and per-machine settings are in [apple2/TERMINAL-SETUP.md](apple2/TERMINAL-SETUP.md).

## Codex slash commands

The bridge handles `/help`, `/new` or `/clear`, `/model NAME`, and `/quit` or `/exit`. Esc or Ctrl-C during **Working** cancels the Codex subprocess and returns any partial reply. Ctrl-C at an idle prompt returns to the menu.

## Building from source

You do not need this to run it; the release disk is prebuilt. To hack on it you need [cc65](https://cc65.github.io/) (`brew install cc65`), [dos33fsprogs](https://github.com/deater/dos33fsprogs), and Python 3. Point `DOS33FSPROGS` at the disk-tool checkout:

```sh
DOS33FSPROGS=/path/to/dos33fsprogs ./apple2gs/build.sh
DOS33FSPROGS=/path/to/dos33fsprogs ./tools/check-release-disk.sh
```

`build.sh` starts from a pristine Apple DOS 3.3 System Master and injects both clients plus a machine-detecting `HELLO`. The result is a reproducible 143,360-byte `apple2gs/CODEX.dsk` containing `CODEX` for the IIgs and `CODEX8` for 8-bit machines. The master is vendored at `apple2gs/dos33-master-jan83.dsk`; it is Apple's OS, not ours. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Generated assets use the Python standard library. The optional screen preview needs Pillow:

```sh
python3 -m pip install Pillow
cd apple2gs
python3 preview.py assets.inc preview.png
```

The 8-bit client has its own MAME harness: an emulated Super Serial Card maps to a TCP socket and Lua drives the boot, dial, session, and reply loop unattended.

## Donate

While this project is free and open source, donations are deeply appreciated, and make ongoing development and support possible. [Donate now](https://www.buymeacoffee.com/wellsworkshop).

## Credits

This project is derived from [Apple II Terminal for Claude Code](https://github.com/wr/apple-ii-terminal-for-claude-code). It is not affiliated with or endorsed by OpenAI.

- **Font:** [UNSCII](http://viznut.fi/unscii/) by Viljami Salminen (CC0)
- **Disk tooling:** [dos33fsprogs](https://github.com/deater/dos33fsprogs) by Vince Weaver
- **Emulators:** [KEGS](https://kegs.sourceforge.net/) and MAME
- The Apple II community... Apple II forever!

## License

MIT, covering this project's own code only. The build and release disk also include third-party material. Provenance and status for each are in [NOTICE.md](NOTICE.md) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). © 2026 Wells Riley.
