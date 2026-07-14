# Codex-native UI and modem diagnostics design

Date: 2026-07-14
Status: approved
Target repository: `github.com/wr/apple-ii-terminal-for-codex`

## Goal

Make the first public disk feel like Codex on an Apple II and make the most
common WiModem setup failure understandable from the Apple screen. This design
supersedes the Patch mascot and Claude-style spinner sections of the original
fork design. It does not change the Codex backend, pairing boundary, disk
layout, or supported Apple models.

## Identity and palette

Patch is removed. Both clients use `>_` as the product mark. The underscore
blinks where the existing event loop can animate it without risking serial
input. The mark appears in the menu, session header, and generated preview.

The IIgs palette is black, gray, and white. The former coral role becomes
white, including titles, status, and control markers. The 8-bit client keeps
normal and inverse text as its two available emphasis levels.

## Codex-style session header

The native clients draw a compact ASCII box because the Apple character sets
cannot reproduce Codex's Unicode border. It contains these fields:

```text
+--------------------------------------+
| >_ OpenAI Codex (v0.144.4)           |
| model: gpt-5.6-sol high               |
| directory: ~                          |
| permissions: YOLO mode                |
+--------------------------------------+
```

The box adapts to 40 or 80 columns. At 80 columns, the model row may also show
`/model to change`. At 40 columns, values are truncated at the right border;
labels and the beginning of each value take priority. The header occupies six
rows without the blank row used by the desktop TUI. The transcript begins
below it and otherwise retains the existing scrolling behavior.

The bridge sends four CR-terminated data lines in the existing header frame:
title, model, directory, and permissions. Locked/pairing headers use the same
four-line shape. Both native clients consume exactly four lines so a partial
or extra frame cannot desynchronize the serial stream.

The values come from local, non-secret state:

- Version: `codex --version`.
- Model: the explicit bridge override when present; otherwise the resolved
  model reported by `codex doctor --json`.
- Reasoning effort: `model_reasoning_effort` from Codex's TOML configuration,
  when present. The bridge reads only that key and does not inspect auth files.
- Directory: the bridge's effective `--workdir`, abbreviated beneath the home
  directory with `~`.
- Permissions: the effective sandbox and approval policy passed to Codex.

`YOLO mode` is reserved for genuinely unrestricted execution with approvals
bypassed. The supported default renders as a compact truthful label such as
`workspace-write / never`; read-only mode renders `read-only / never`. If the
diagnostic command fails or omits the model, the header says `default model`
rather than guessing. Header discovery is bounded by a timeout, fails open to
the fallback text, and never prevents the bridge from starting.

## Working state and interruption

The Claude-style rotating star and gerunds are removed. While Codex is
running, the clients show:

```text
* Working (5s * esc to interrupt)
```

On the IIgs the two `*` placeholders render as the closest available bullet
glyph; on 8-bit machines they use a stable Apple character that remains clear
in both 40- and 80-column modes. The leading mark blinks, the seconds counter
increments, and the text otherwise stays fixed.

Escape during work sends the existing interrupt control byte to the bridge.
The bridge cancels the complete Codex process group and returns the normal
interruption result plus EOT. Ctrl-C remains an interrupt alias. Escape at an
idle prompt retains the existing return-to-menu behavior. If the carrier or
bridge disappears after an interrupt, the client's existing bounded link
failure path remains available; the spinner must not wait forever without
polling serial input.

## WiModem setup and dial diagnostics

Codex uses WiModem phonebook entry 1. Every Codex instruction and host banner
must therefore save the bridge with:

```text
AT&Z1=<bridge-address>:6401
```

The clients continue to dial with `ATDS=1`. They do not issue a separate
firmware-specific phonebook query. Instead, the dial window classifies the
standard result text already returned by the modem and preserves raw modem
echo on screen:

- `ERROR`: entry 1 is probably missing or the command is unsupported; show the
  `AT&Z1=...` setup guidance.
- `BUSY`: the bridge or destination is occupied.
- `NO CARRIER`: no carrier was established; check the saved address, bridge,
  and network.
- `NO ANSWER`: the destination did not answer; check that the bridge is
  listening.
- Silence/timeout: check modem connection and 9600 8N1 serial settings.

Matching is case-insensitive, incremental, and bounded. Both clients continue
to call their receive-ring polling routine inside every slow display or delay
loop. A successful `CONNECT` verdict still latches while the period dial
theater finishes, and a failure still stops the theater immediately.

After this fork ships the behavior, create a sister-repository issue proposing
the portable verdict classification for the Claude client. Entry numbering is
not copied: Claude correctly owns phonebook entry 0.

## Verification and acceptance

Automated coverage must prove:

- header discovery, explicit model precedence, effort formatting, directory
  abbreviation, truthful permissions, timeout, malformed JSON, and fallback;
- four-line header framing and locked-header compatibility;
- exact `AT&Z1=` setup copy with no remaining Codex `AT&Z0=` references;
- each modem verdict and timeout maps to its intended client state/message;
- Escape and Ctrl-C use the same in-flight interruption path;
- the removed Patch/coral/Cogitating assets and strings do not survive;
- both 6502 and 65816 clients assemble and the disk retains both catalog files.

Final visual verification uses the IIgs preview at real display geometry plus
an 8-bit emulator screenshot in 40-column mode. The generated `CODEX.dsk` is
then built through the existing DOS 3.3 master workflow. Real WiModem hardware
remains the final authority for dialing and result text; if it is not attached
during implementation, that hardware check is reported as outstanding rather
than inferred from emulation.
