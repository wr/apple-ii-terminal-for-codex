# IIgs Working shimmer design

## Goal

Give the IIgs `Working` status a restrained three-tone shimmer inspired by the
ChatGPT activity treatment. Animate only the word `Working`; keep the elapsed
time and interrupt hint steady. Replace the leading star's on/off blink with a
continuous pulse through the same three tones.

## Palette

The 640-mode session already has four hardware color values. Use them as:

- 0: black background
- 1: gray (`$0999`)
- 2: light gray (`$0CCC`)
- 3: white (`$0FFF`)

The splash palette stays unchanged. Existing session elements that must remain
white, including the real Codex header title, use color 3 explicitly. Color 2
becomes the intermediate shimmer tone rather than a duplicate white.

## Animation

Render the leading `*` on every frame. Its color repeats
`gray, light gray, white, light gray`, so it pulses without disappearing.

Render `Working` one character at a time from a small table. A white center and
light-gray neighbor move left to right across the seven letters over eight
frames, with all other letters gray. At the trailing frame, the highlight moves
past `g` before wrapping to `W`. The existing approximately 100 ms spinner pace
produces an approximately 800 ms sweep.

Render the space, timer, `s`, and `* esc to interrupt` suffix in steady gray.
The status text, timer behavior, keyboard interrupt handling, serial polling,
and reply detection do not change.

## Verification

- Test the session palette's exact gray, light-gray, and white entries.
- Test that the star is always drawn and uses the four-step color pulse table.
- Test that `Working` is drawn character-by-character through an eight-frame,
  seven-character color table while the suffix stays gray.
- Regenerate assets, render the preview, assemble both clients, run the full
  suite and disk release gate, then verify the animation in KEGS and on the
  real IIgs.
