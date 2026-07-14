# Apple II terminal setup

This path uses an ordinary 40/80-column terminal instead of the native client on `CODEX.dsk`. Run the bridge without `--app`. The same authenticated Codex CLI and required Git `--workdir` apply.

## Direct serial

Install the optional serial dependency:

```sh
python3 -m pip install -r bridge/requirements.txt
python3 bridge/bridge.py --serial /dev/tty.usbserial-XXXX --baud 9600 \
  --cols 80 --workdir /absolute/path/to/git/repo
```

Set the Apple II terminal to 9600 baud, 8 data bits, no parity, one stop bit, and local echo off. Start without flow control. At higher speeds, add `--rtscts` when the cable carries handshake lines or `--xonxoff` when the terminal supports it.

Use a classic Mac-compatible mini-DIN-8 serial cable for a IIgs or IIc Plus, an Apple IIc DIN-5 modem cable for the original IIc, or a Super Serial Card in slot 2 for a IIe/II+.

### IIgs and IIc Plus mini-DIN-8

The usual connection to a USB serial adapter is TXD- to RX, RXD- to TX, and ground to ground. A proper RS-422 adapter is preferred. Use the IIgs modem port by convention.

### IIc firmware terminal

From Applesoft, enter `IN#2`, then press Control-A followed by `T`. Exit with Control-A then `Q`. Do not use `IN#2` alone for a session: BASIC will try to parse received lines and print syntax errors.

## Terminal software

ProTERM is a reliable choice on all supported 8-bit machines. Spectrum and Talk Is Cheap are common IIgs choices. Plain TTY mode is enough because the bridge sends printable ASCII plus CR/LF.

## WiFi modem or raw TCP

Start a listener on TCP port 6401:

```sh
python3 bridge/bridge.py --telnet --workdir /absolute/path/to/git/repo
```

Dial `host:6401` from the terminal program. Raw terminal mode cannot persist the native `CDXTK1` disk token, so enter the pairing code shown on the host console for each new connection. Add `--telnet-negotiate` when using a real telnet client that sends IAC negotiation.

The native disk uses phonebook entry 1 and sends `ATDS=1`; manual terminal software can dial the address directly. Device-specific commands are in [docs/MODEM-SETUP.md](../docs/MODEM-SETUP.md).

## Emulator

For KEGS **Incoming** on Serial Slot 2:

```sh
python3 bridge/bridge.py --connect 127.0.0.1:6502 \
  --workdir /absolute/path/to/git/repo
```

Use `--host 127.0.0.1` if you instead run a local listener. The full native client uses the same transport with `--app` and boots from `CODEX.dsk`.

## First contact

1. Start the bridge.
2. Connect from the Apple II terminal.
3. Enter the pairing code printed on the host when asked.
4. Type `/help`, then send a prompt.

The local commands are `/help`, `/new`, `/model`, and `/quit`. Use `--sandbox read-only` for a repository that must not be changed. The default `workspace-write` mode can edit within Codex's sandbox boundary, and `approval_policy=never` makes broader operations fail closed.

If characters are missing, lower the baud or use flow control. If characters double, turn local echo off or pass `--no-echo` and turn local echo on. If nothing arrives, check the selected port, cable direction, and baud.
