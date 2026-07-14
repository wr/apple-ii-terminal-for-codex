# Tests

Two layers: a pure-Python bridge test, and MAME runs that drive the real
8-bit client with scripted keystrokes and read the text page back.

## Bridge (no emulator)

```sh
python3 -m pip install -r requirements-test.txt
python3 -m pytest -q bridge tests/test_interrupt.py
```

This runs the renderer, pairing, cancellation, terminal-protocol, error-hygiene,
and native-client interrupt tests without an emulator or Claude account.

## 8-bit client in MAME

The romset lives in `~/.mame/roms` (assembled per W-482 — Asimov parts plus a
keyboard ROM synthesized from MAME's own matrix source; checksums won't
verify, that's expected). Things the harness learned the hard way:

- `SDL_VIDEODRIVER=dummy` is what actually suppresses the window; `-video
  none` alone still opens one fullscreen on macOS.
- Pass `-aux ""` (no 80-col card): the scripts read the text page from main
  RAM only, and in 80-col mode the even columns live in aux where the Lua
  memory space doesn't see them.
- `natkeyboard:post()` types printable keys and Return but NOT control
  characters — Ctrl-C is pressed through ioport fields `"Control"`
  (`:keyb_special`) and `"c  C"` (`:X3`) with set_value/clear_value.
- `-nothrottle` decouples wall-clock from emulated time: anything on the
  other end of the bitbanger socket must respond immediately, not after a
  wall-clock sleep, or the emulated window it's aiming for is long gone.

Menu/session/keys smoke test (W-516: Ctrl-C idle, /exit, reconnect):

```sh
SDL_VIDEODRIVER=dummy mame apple2ee -rompath ~/.mame/roms -aux "" -sl2 ssc \
  -flop1 apple2gs/CLAUDE.dsk -autoboot_script tests/w516_test.lua \
  -video none -sound none -nothrottle -seconds_to_run 200
```

Dial-window test against a fake Hayes modem (W-517: CONNECT mid-theater
rings out, BUSY cuts immediately). Start the modem first, then MAME with the
bitbanger wired to it; run once per mode:

```sh
python3 tests/fake_modem.py CONNECT &   # or BUSY
SDL_VIDEODRIVER=dummy W517MODE=CONNECT mame apple2ee -rompath ~/.mame/roms \
  -aux "" -sl2 ssc -sl2:ssc:rs232 null_modem -bitbanger socket.127.0.0.1:6502 \
  -flop1 apple2gs/CLAUDE.dsk -autoboot_script tests/w517_test.lua \
  -video none -sound none -nothrottle -seconds_to_run 120
```

Both Lua scripts print `... ALL PASS` (grep for `W516TEST:` / `W517TEST:`).
