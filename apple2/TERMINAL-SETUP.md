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

The IIgs and IIc serial ports are RS-422-family ports, not RS-232. Use a classic Mac-compatible mini-DIN-8 serial cable for a IIgs or IIc Plus, an Apple IIc DIN-5 modem cable for the original IIc, or a Super Serial Card in slot 2 for a IIe/II+. A proper RS-422-to-RS-232 adapter is preferred when the USB adapter is RS-232.

### IIgs and IIc Plus mini-DIN-8

The usual connection to a USB serial adapter is:

```text
pin 3  TXD-          -> adapter RXD
pin 5  RXD-          -> adapter TXD
pin 4  GND           -> adapter GND
pin 8  RXD+          -> tie to GND
pin 6  TXD+          -> leave open or tie to GND
pin 1  HSKo (RTS)    -> adapter CTS, only with --rtscts
pin 2  HSKi (CTS)    -> adapter RTS, only with --rtscts
```

Use port 2 (modem) on the IIgs by convention. Port 1 also works. A Mac printer cable may have the same mini-DIN-8 connectors but cross the wrong signals; use a serial or modem cable made for this connection.

### IIc firmware terminal

The IIc serial firmware provides a no-disk terminal. From the Applesoft `]` prompt, enter `IN#2`, then press Control-A followed by `T`. Keyboard input now goes to the modem port and received bytes print without passing through BASIC. Exit with Control-A then `Q`.

To set 9600 baud first, enter Control-A, `1`, `4`, `B`, Return. The default character format is already 8N1. Do not use `IN#2` alone, or `IN#2` followed by `PR#2`, for a session: BASIC will try to parse received lines and print `?SYNTAX ERROR`.

## Terminal software

ProTERM is a reliable choice on all supported 8-bit machines. Spectrum and Talk Is Cheap are common IIgs choices. Plain TTY mode is enough because the bridge sends printable ASCII plus CR/LF.

If replies lose characters, lower the baud first. At higher speeds, enable flow control at both ends: use `--rtscts` only when the cable carries the handshake lines, or `--xonxoff` when the terminal supports software flow control. If neither is available, `--pace-cps 600` throttles bridge output.

## WiFi modem or raw TCP

Start a listener on TCP port 6401:

```sh
python3 bridge/bridge.py --telnet --workdir /absolute/path/to/git/repo
```

Dial `host:6401` from the terminal program. Raw terminal mode cannot persist the native `CDXTK1` disk token, so enter the pairing code shown on the host console for each new connection. Add `--telnet-negotiate` when using a real telnet client that sends IAC negotiation.

The native disk uses phonebook entry 1 and sends `ATDS=1`; manual terminal software can dial the address directly. Device-specific commands are in [docs/MODEM-SETUP.md](../docs/MODEM-SETUP.md).

## KEGS emulator

KEGS routes its emulated serial ports to TCP sockets. Press F4, open Serial Port Configuration, and set Serial Slot 2 to **Incoming**. KEGS listens on TCP port 6502, so connect the bridge to it:

```sh
python3 bridge/bridge.py --connect 127.0.0.1:6502 \
  --workdir /absolute/path/to/git/repo
```

Inside KEGS, use a terminal program on Slot 2 or the IIc firmware-terminal sequence above. Do not use `IN#2` alone or with `PR#2`; that sends received lines to BASIC. Slot 1 listens on port 6501 and Slot 2 on 6502. Baud does not matter for these virtual sockets.

KEGS **Virtual modem** reverses the connection direction. Start a raw bridge listener:

```sh
python3 bridge/bridge.py --telnet --port 6401 \
  --workdir /absolute/path/to/git/repo
```

Then dial `ATDT 127.0.0.1:6401` inside KEGS. Set `g_serial_modem_init_telnet = 0` in `~/config.kegs`, or leave the bridge without `--telnet-negotiate`, so KEGS and the bridge exchange a clean raw byte stream.

Use `--host 127.0.0.1` to keep a local listener off the LAN. The full native client uses the same transport with `--app` and boots from `CODEX.dsk`.

## First contact

1. Start the bridge.
2. Connect from the Apple II terminal.
3. Enter the pairing code printed on the host when asked.
4. Type `/help`, then send a prompt.

The local commands are `/help`, `/new`, `/model`, and `/quit`. Use `--sandbox read-only` for a repository that must not be changed. The default `workspace-write` mode can edit within Codex's sandbox boundary, and `approval_policy=never` makes broader operations fail closed.

If characters are missing, lower the baud or use flow control. If characters double, turn local echo off or pass `--no-echo` and turn local echo on. If nothing arrives, check the selected port, cable direction, and baud.
