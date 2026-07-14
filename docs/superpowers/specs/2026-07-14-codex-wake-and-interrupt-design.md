# Codex Wake and Interrupt Styling

## Goal

Give the Codex fork its own restrained menu wake sound and match Codex CLI's interrupted-turn treatment without weakening the existing three-tone `Working` shimmer.

## Scope

- Change the once-per-boot wake gesture on both native clients.
- Add a styled interrupted-turn marker to the bridge protocol.
- Render the marker in red on the IIgs and inverse video on 8-bit Apples.
- Preserve the interrupt styling during live scrolling and scrollback redraws.
- Leave the dial theater, reply bell, `Working` animation, cancellation behavior, and ordinary reply colors unchanged.

## Wake Sound

The Claude and Codex forks currently use the same wake data. Codex will keep the same quiet volume, approximate duration, two-voice GS implementation, and 1-bit 8-bit implementation, but use a different phrase:

1. Four short rising notes instead of Claude's seven-step sweep.
2. A brief silent beat.
3. A compact two-note landing, voiced as a fifth on the GS and approximated by alternating pitches on the 8-bit speaker.

This remains an event sound rather than menu music. It plays once per boot and any key may skip it.

## Interrupt Protocol

Add `CMD_INTERRUPT` (`0x06`) to the native-client protocol. When cancellation finishes, the bridge will send a blank line, the marker, the text `Interrupted by user`, and the normal `EOT`. The marker owns the leading symbol, so the bridge will no longer send the ASCII `*` used by the current unstyled message.

The existing cancellation path stays intact: Esc or Ctrl-C sends one cancellation byte, the bridge cancels the Codex process, partial output is retained, and no worked-duration footer is emitted.

## IIgs Rendering

Super Hi-Res palette 0 remains black, gray, light gray, and white. A new palette 1 will contain the same black, gray, and white entries, with color 2 replaced by a readable muted red. The client will select palette 1 only for the eight scanlines of an interrupt text row.

`CMD_INTERRUPT` will:

- assign palette 1 to the current text row;
- draw and record a small filled square followed by a space;
- select a semantic red text color and render `Interrupted by user` in red.

The scrollback buffer will retain a semantic red color distinct from ordinary light gray, while the pixel renderer masks it to hardware color 2. Screen scrolling will move the row's SCB palette selector with its pixels. Clearing a row restores palette 0, and scrollback redraw will restore palette 1 when it encounters semantic red cells. This keeps old interrupted-turn lines red without reserving one of the four normal session colors.

## 8-bit Rendering

The 8-bit clients cannot display red. `CMD_INTERRUPT` will draw an inverse-space block followed by a space, then select inverse video for `Interrupted by user`. The next reply already resets the normal display state, so no new persistent color model is needed.

## Testing

- Assert the bridge emits `CMD_INTERRUPT`, the unprefixed message, and `EOT` in order.
- Assert the generated IIgs interrupt palette differs from the session palette only at color 2.
- Add native-source contract tests for the new marker, square rendering, semantic red buffer color, SCB row handling, and 8-bit inverse fallback.
- Add asset tests showing that the Codex wake data no longer matches the Claude wake phrase and both voices have equal duration.
- Assemble both clients, run the full test suite, build `CODEX.dsk`, inspect an interrupt preview, and run the release gate.

## Non-goals

- No new sound during interruption.
- No red theme elsewhere in the application.
- No changes to bridge authentication, modem handling, or cancellation timing.
