# Apple II Terminal for Codex engineering notes

This file provides guidance to agents working with code in this repository.

## Source of truth
- GitHub: github.com/wr/apple-ii-terminal-for-codex
- Branch prefix: wells/
- PR mode: none (commit to main, push directly)

## What this is

A bridge that turns a real Apple II into a terminal for an already-installed and authenticated Codex CLI. Three pieces that must stay in sync:

- **`bridge/`** — Python, runs on a modern host. Reads a line from the Apple II, sends it to Codex, and returns printable 7-bit ASCII word-wrapped to 40/80 columns.
- **`apple2gs/codex.s`** — the IIgs client: 65816, **Super Hi-Res 640 mode**, animated monochrome `>_` menu mark, boxed Codex header, Working status, and scrollback.
- **`apple2/codex2.s`** — the 8-bit client: plain 6502 (no 65C02 ops), text mode, with the same blinking `>_` identity and compact boxed header. Runs on IIe, IIc, IIc Plus, and II/II+.

**Sound design is period-accurate and event-based** — no menu music. Three sounds only: a once-per-boot two-voice wake gesture; the Connect dial theater (dial tone, DTMF `2-6-3-3-9` spelling CODEX, ringback, answer tone, and carrier buzz); and a reply bell after a ≥15 s think. GS = DOC two-voice streams in `gen_assets.py`; 8-bit = cycle-counted 1-bit versions using pulse digits `2-6-3`, which MUST poll `rb_poll` every half-cycle during the dial window.

**One disk boots everything**: `build.sh` assembles both clients into `CODEX.dsk`, and the disk's HELLO reads the ROM ID bytes (Apple II Misc TN #7, plus the `$FE1F` carry probe to split IIgs from enhanced IIe) and BRUNs `CODEX` (GS) or `CODEX8` (everything else).

The bridge sends **only** printable ASCII + CR/LF plus a small in-band control scheme (below). All layout and color live on the Apple II side.

## Commands

Build everything (from `apple2gs/`):

```bash
./build.sh                 # both clients -> inject into DOS 3.3 master -> CODEX.dsk (+ ~/Downloads copy for KEGS)
python3 gen_assets.py      # regenerate assets.inc (palettes, font, mascot, splash frames, sounds) only
python3 preview.py assets.inc out.png   # render the GS session screen to PNG WITHOUT an emulator
../tools/install-sd.sh     # put the built image on a FloppyEmu SD card safely
```

`build.sh` needs the `cc65` toolchain (`ca65`/`ld65`), the pinned [dos33fsprogs](https://github.com/deater/dos33fsprogs) build, and Python. The `>_` assets are code-native and generated without Pillow. The output disk is the vendored DOS 3.3 System Master (`dos33-master-jan83.dsk`) with HELLO replaced and the client binaries added — never a from-scratch image.

Run the bridge against KEGS (KEGS F4 → Serial Slot 2 → **Incoming**, which listens on TCP 6502):

```bash
cd bridge
python3 bridge.py --connect 127.0.0.1:6502 --app --cols 80 --workdir /path/to/git/repo
```

- `--app` enables the native-client protocol (bridge stays silent, frames replies with `EOT` = `0x04`). Required for both native clients.
- The bridge runs an already-installed and authenticated Codex CLI with workspace-write access inside the required `--workdir`; `--sandbox read-only` narrows it.
- Serial hardware instead of KEGS: `--serial /dev/tty.usbserial-XXXX --baud 9600`.
- A listening bridge (`--telnet`) locks itself behind a 6-character pairing code with per-source-IP retry limits and revocation. By default, `code_for` creates a code when an unpaired source IP needs it; successful use consumes that generated code. In `--app` mode the bridge also issues a 32-char client token via `CMD_TOKEN`, stores its hash plus first IP and pairing time under `$XDG_CONFIG_HOME/codex-ii-terminal/paired.json` (or the `~/.config` fallback), and accepts token possession on reconnect. Raw telnet gets no token and must enter a code each session. `--pair-code` fixes one case-insensitive shared code; `--no-pair` disables the gate. Telnet is plaintext, so captured unused codes or tokens can be replayed; this remains a trusted-LAN design.

## The edit → see-it loop

- **GS client, fast path: `preview.py`.** It reproduces `codex.s`'s exact SHR pixel math at KEGS's real display geometry (640×200 stretched to 4:3 → pixels are ~0.42 wide : 1 tall). What the PNG shows is what KEGS shows. It writes a full screen and a zoomed `*_header.png`.
- **GS client, full loop**: `./build.sh`, then **Ctrl-⌘-Reset** in KEGS (boots `~/Downloads/CODEX.dsk` via `~/config.kegs`). No bridge restart needed.
- **8-bit client**: MAME, fully scripted. `mame apple2ee -sl2 ssc -sl2:ssc:rs232 null_modem -bitbanger socket.127.0.0.1:6502 -flop1 CODEX.dsk` wires an emulated Super Serial Card to the bridge's socket; `-autoboot_script` (Lua) types keys and takes snapshots, and Lua read/write taps on memory are how the hard bugs here were actually found. The IIc is `mame apple2c` with `-modem null_modem`. ROMs aren't distributable; the romset was assembled from Asimov parts + a keyboard ROM synthesized from MAME's own matrix source.
- **Bridge change** (`bridge/*.py`): restart the `python3 bridge.py` process.
- **Real hardware** (Wells: IIgs + IIc, WiModem 232 Pro, FloppyEmu): `tools/install-sd.sh` — in-place overwrite of the card's existing image (can't fragment). The tool is [wr/floppyemu-sd](https://github.com/wr/floppyemu-sd), vendored in `tools/`.

## Rendering pipeline (bridge → client)

`backends.py` (`CodexBackend`) maps Codex JSONL to clean text → `render.py` `StreamFormatter` reduces Markdown, `to_ascii` sanitizes to 7-bit, `wrap` word-wraps → `bridge.py` `run_app_session` writes lines and terminates with `EOT`. `terminal.py`/`transports.py` are byte plumbing.

`CodexBackend` runs `codex exec --json ... -` with the prompt on stdin, then `codex exec resume --json ... <thread-id> -` on later turns. Each turn is a fresh process with no PTY. The interactive Codex TUI does not exist in this transport; the bridge synthesizes the bullet/footer and suppresses reasoning events.

## In-band control scheme

The reply stream carries a few control bytes the native clients interpret (kept below `EOT`=`0x04`):

- `0x01 <n>` — set text color: `1`=gray (reply/input), `2`=white accent (titles/status), `3`=white (your messages, inline code). The 8-bit client maps 3 → inverse video, others → normal.
- `0x02` — draw the reply bullet.
- `0x03` — session over (bridge-side `/quit`): the client returns to its menu.
- `0x0E` — header frame follows (4 CR-terminated lines: title, model, directory, permissions); sent in reply to the client's session-open CR probe and before each reply. An **unpaired** peer's probe is answered with a LOCKED header instead — that's how the pairing prompt reaches the screen (idle clients discard unsolicited text but always render headers).
- `0x05 <token> CR` — (bridge → client, app mode) a freshly issued device token; the native client writes it to a reserved disk sector and auto-sends it as its first line on every future connect, so pairing survives reboots. `to_ascii` drops 0x05 from model text, so a reply can't forge it.

These are injected in `bridge.py:run_app_session` (bullet, footer) and inside `render.py` (inline/fenced `code` spans → white). `to_ascii` deliberately **passes through bytes 1–3** rather than dropping them; the clients' `recv_reply`/`spinner` intercept them before `cout`. Color markers currently count toward wrap width, so code-dense lines may wrap a few columns early.

## The splash pipeline (GS)

`gen_assets.py` packs two hand-authored `>_` frames into SHR data. They differ only by the underscore, which creates the menu blink. The session header renders `>_` as text rather than a separate mascot.

## Non-obvious constraints & gotchas

The theme of this list: **KEGS and MAME forgive what real chips don't.** Every entry below was a working-in-emulation, broken-on-metal bug.

Both clients:
- **Never go deaf to the serial port.** The GS's SCC FIFO is 3 bytes; the 8-bit 6551 buffers ONE byte — at 9600 that's ~1ms of slack. Both clients keep a 256-byte ring buffer (`rb_poll`/`getbyte`/`havebyte`) and every loop that can run longer than ~600 cycles calls `rb_poll` inside it (scrolls, row clears, VBL waits, do_header's pad loop). Any new slow loop MUST do the same; the symptom of forgetting is dropped bytes on metal that emulators never show.
- **Local `/quit` (and any client-side command) must be matched BEFORE transmitting** — a line sent with no carrier reaches the modem's command processor.
- **Zero page must dodge live Applesoft/DOS state.** Users Ctrl-Reset from the client back into BASIC; any ZP the client scribbles is corruption BASIC resumes with. $B1-$C8 is CHRGET (executable code — trashing it = "everything is a syntax error"), $D6 auto-RUN, $D8 ONERR. Known-safe: $06-$09, $FA-$FE.

GS client (`codex.s`):
- **640-mode palette is full at 4 slots** (black/gray/white/white). Another distinct color needs 320 mode, which halves to 40 columns.
- **Real hardware needs `scc_init`** — a IIgs never initializes the SCC at power-on (Apple TN #018); KEGS works without it.
- **A real 8530 latches Rx overrun and can wedge the status poll** — `rb_poll` bounds its drain (4 bytes) and ends every pass with WR0 = $30 (Error Reset). Never write a raw `lda SCC_STAT` loop. Boot breadcrumbs remain in `start`: border flashes white→red→yellow→black through init; a stuck color names the hung stage.
- **The real Sound GLU raises a busy bit around DOC cycles and drops accesses made while it's set** — all DOC access goes through `glu_wait`+`doc_wr`. KEGS doesn't model it. Also: DOC register `$E1` (osc enable) = oscillator count × 2.
- **65816 mode tracking**: after `jsr`ing a routine that changes M/X width, put `.a8`/`.a16` after the call or operands mis-assemble into a `BRK`. `mvn` also corrupts KEGS state — `scroll_up` uses a plain `[dp],y` copy.
- Connect dials `ATDS=1` without a separate phonebook probe. The dial window distinguishes CONNECT, ERROR, BUSY, NO CARRIER, NO ANSWER, and timeout while preserving modem echo. A direct emulator bridge answers passed-through `ATDS=1` with synthetic CONNECT. Both clients skip the dial entirely when DCD reads carrier AND `dcd_trust` is set (the pin has read "no carrier" at least once, proving it's live, not strapped).

8-bit client (`codex2.s`):
- **Don't use IRQ-driven serial.** The enhanced IIe/IIc ROM interrupt dispatcher doesn't follow the II+'s "A saved at $45" convention; a handler assuming it corrupts the ROM's banking restore (80STORE drops, even columns garble, eventual crash). The client is 100% polled.
- **Inverse text with ALTCHARSET on**: screen codes $40-$5F are **MouseText**, not inverse uppercase — fold to $00-$1F. Without ALTCHARSET, $40-$7F flash.
- **80-col writes**: even columns live in aux RAM via 80STORE+PAGE2 ($C001 + $C055/$C054); odd columns in main. An IIe without an aux card is probed (`aux_test`) and falls back to 40-col.
- **Don't trust $C019**: the IIe's VBLBAR free-runs; the IIc's is interrupt plumbing that may sit still. The client probes it at boot and falls back to cycle-counted delays (scaled ×4 on the 4MHz IIc Plus via `$FBBF`).
- 6551 TX polls TDRE with a timeout because new-production W65C51N chips never set the bit.

Environment:
- **KEGS reads `~/config.kegs`** (home dir, not the app folder — macOS translocation). `s6d1` points at `~/Downloads/CODEX.dsk`, which `build.sh` refreshes; a leading `#` on the path means "ejected".
- **Slash commands**: `bridge.py:handle_command` owns `/new`/`/clear`, `/model`, `/help`, and `/quit`/`/exit`. Unknown commands are rejected; they are never forwarded as Codex TUI commands.
- **Interrupt**: Ctrl-C at an idle prompt = local quit-to-menu. During Working, Esc or Ctrl-C sends one bare `0x03`; `run_app_session` polls the transport and `backend.cancel()` kills the complete Codex process group, then sends partial output + `Interrupted by user` + EOT. During printing, Ctrl-C mutes and drains to EOT locally.
