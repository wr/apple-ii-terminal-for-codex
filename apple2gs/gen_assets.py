#!/usr/bin/env python3
"""Generate 640-mode SHR assets for the Codex GS client.

640 mode: 4 pixels/byte, 2 bits each. Because the hardware picks the palette
entry from BOTH the pixel value and its column-within-byte, we replicate the 4
colors across all 16 palette slots so a 2-bit value means the same color
everywhere. 4 usable colors: 0 black, 1 gray, 2 white, 3 white.
"""

COL_BLACK, COL_GRAY, COL_ACCENT, COL_WHITE = 0, 1, 2, 3
COLORS = {                       # value -> $0RGB (4 bits/channel)
    0: (0x0, 0x0, 0x0),          # black background
    1: (0x9, 0x9, 0x9),          # mid gray    (Codex replies + input box)
    2: (0xF, 0xF, 0xF),          # white       (titles / status)
    3: (0xF, 0xF, 0xF),          # white       (user's submitted messages)
}

MASCOT_HSCALE = 2
MASCOT_VSCALE = 1
MLEG = {".": 0, "W": 2}

LOGO_OFF = (
    "..WW............", "...WW...........", "....WW..........",
    ".....WW.........", "....WW..........", "...WW...........",
    "..WW............",
)
LOGO_ON = "on"
LOGO_FRAMES = {
    "off": LOGO_OFF,
    LOGO_ON: LOGO_OFF[:-1] + ("..WW..WWWWWW....",),
}
LOGO_SEQUENCE = [("off", 8), (LOGO_ON, 24), ("off", 8), (LOGO_ON, 90)]
MASCOT_FRAMES = [LOGO_FRAMES[LOGO_ON]]

# The boot phase uses the same neutral hierarchy as the session.
COLORS_SPLASH = {0: (0x0, 0x0, 0x0), 1: (0x6, 0x6, 0x6),
                 2: (0xF, 0xF, 0xF), 3: (0xC, 0xC, 0xC)}


def pack640(pixels):
    """pixels: list of 2-bit values, length multiple of 4 -> bytes (4px each,
    leftmost pixel in bits 7-6)."""
    out = []
    for i in range(0, len(pixels), 4):
        p0, p1, p2, p3 = pixels[i:i + 4]
        out.append((p0 << 6) | (p1 << 4) | (p2 << 2) | p3)
    return out


def emit_palette():
    lines = ["shr_palette:"]
    # 16 entries; entry n uses color (n & 3)
    for n in range(16):
        r, g, b = COLORS[n & 3]
        lines.append(f"    .word ${(r<<8)|(g<<4)|b:04X}")
    lines.append("shr_palette_splash:   ; neutral boot/menu variant")
    for n in range(16):
        r, g, b = COLORS_SPLASH[n & 3]
        lines.append(f"    .word ${(r<<8)|(g<<4)|b:04X}")
    return "\n".join(lines)


LOGO_COLORS = {".": 0, "W": 2}


def splash_extract():
    names = list(LOGO_FRAMES)
    frames = [
        tuple(tuple(LOGO_COLORS[cell] for cell in row) for row in LOGO_FRAMES[name])
        for name in names
    ]
    index = {name: position for position, name in enumerate(names)}
    sequence = [(index[name], duration) for name, duration in LOGO_SEQUENCE]
    return frames, sequence, 16, 7, index[LOGO_ON]


def emit_splash():
    uniq, seq, w, h, hold = splash_extract()
    fsize = w * h // 4
    lines = [f"SPLASH_BYTES = {w // 4}",
             f"SPLASH_H = {h}",
             f"SPLASH_FSIZE = {fsize}   ; bytes per frame (stored 1x, drawn 4x)",
             f"SPLASH_HOLD = {hold}   ; inter-loop pause frame",
             f"; {len(uniq)} unique frames of {w}x{h} cells, "
             f"{len(seq)} storyboard entries",
             "splash_data:"]
    for fi, m in enumerate(uniq):
        lines.append(f"    ; frame {fi}")
        for row in m:
            packed = pack640(list(row))
            lines.append("    .byte " + ",".join(f"${b:02X}" for b in packed))
    lines.append("splash_off:")
    for i in range(len(uniq)):
        lines.append(f"    .word {i * fsize}")
    lines.append("splash_seq:   ; frame, vblanks, ... , $FF")
    for j, vbl in seq:
        lines.append(f"    .byte {j}, {vbl}")
    lines.append("    .byte $FF")
    # 4x horizontal expansion: table j maps a packed byte to the solid byte
    # for its j-th pixel (each 2-bit pixel becomes a full byte of 4 copies)
    solid = (0x00, 0x55, 0xAA, 0xFF)
    for j in range(4):
        shift = 6 - 2 * j
        lines.append(f"expand4_{j}:")
        vals = [solid[(b >> shift) & 3] for b in range(256)]
        for i in range(0, 256, 16):
            lines.append("    .byte " + ",".join(f"${v:02X}" for v in vals[i:i+16]))
    return "\n".join(lines)


def emit_mascot():
    hs, vs = MASCOT_HSCALE, MASCOT_VSCALE
    assert len({len(f) for f in MASCOT_FRAMES}) == 1, "frames must share a height"
    w = max(len(r) for f in MASCOT_FRAMES for r in f)
    # scaled width must be a multiple of 4 (pack640 packs 4 px/byte)
    scaled_w = (w * hs) - ((w * hs) % 4)
    bytes_per_row = scaled_w // 4
    frames_rows = []
    for frame in MASCOT_FRAMES:
        rows = [r.ljust(w, ".") for r in frame]
        out_rows = []
        for row in rows:
            px = []
            for ch in row:
                px += [MLEG.get(ch, 0)] * hs    # scale horizontally
            px = px[:bytes_per_row * 4]         # trim to packed width
            packed = pack640(px)
            out_rows += [packed] * vs           # scale vertically
        frames_rows.append(out_rows)
    h = len(frames_rows[0])
    lines = [f"MASCOT_H = {h}", f"MASCOT_BYTES = {bytes_per_row}",
             "mascot_data:"]
    for fi, out_rows in enumerate(frames_rows):
        lines.append(f"    ; frame {fi}")
        for packed in out_rows:
            lines.append("    .byte " + ",".join(f"${b:02X}" for b in packed))
    return "\n".join(lines)


def emit_expand():
    """EXPAND[color*16 + nibble] = byte with each of the nibble's 4 bits blown
    up to the 2-bit color (bit3 -> leftmost pixel)."""
    lines = ["expand_tbl:"]
    for c in range(4):
        row = []
        for n in range(16):
            b = 0
            if n & 8: b |= c << 6
            if n & 4: b |= c << 4
            if n & 2: b |= c << 2
            if n & 1: b |= c
            row.append(b)
        lines.append(f"    .byte " + ",".join(f"${b:02X}" for b in row))
    return "\n".join(lines)


def load_unscii(path="unscii-8.hex"):
    """Parse unscii-8.hex -> {codepoint: [8 row bytes]}. Each line is
    'codepoint:hexbitmap'; an 8x8 glyph is 16 hex chars = 8 bytes, one byte
    per row with bit7 = leftmost pixel (already the Apple II convention)."""
    glyphs = {}
    for line in open(path):
        line = line.strip()
        if not line or ":" not in line:
            continue
        cp, hx = line.split(":", 1)
        if len(hx) != 16:           # skip double-wide / non-8x8 glyphs
            continue
        rows = [int(hx[i:i + 2], 16) for i in range(0, 16, 2)]
        glyphs[int(cp, 16)] = rows
    return glyphs


# Kept until the native Working renderer no longer needs a generated pointer.
SPIN_WORDS = ["Working"]


def emit_spinwords():
    # Pointer table + variable-length " Word..." strings, so the client can draw
    # the elapsed-time counter right after the word instead of at a fixed column.
    lines = [f"SPIN_COUNT = {len(SPIN_WORDS)}", "spin_ptrs:"]
    for i in range(len(SPIN_WORDS)):
        lines.append(f"    .addr spin_w{i}")
    for i, w in enumerate(SPIN_WORDS):
        lines.append(f'spin_w{i}: .byte " {w}...",0')
    return "\n".join(lines)


def emit_bullet():
    # small filled dot, vertically centered in the 8x8 cell (bit7 = leftmost)
    rows = [0x00, 0x00, 0x3C, 0x7E, 0x7E, 0x3C, 0x00, 0x00]
    return "bullet_data:\n    .byte " + ",".join(f"${b:02X}" for b in rows)


def emit_font():
    glyphs = load_unscii()
    blank = [0] * 8
    lines = ["FONT_FIRST = 32", "font_data:"]
    for code in range(32, 127):
        rowbytes = glyphs.get(code, blank)
        lines.append(f"    ; '{chr(code)}'")
        lines.append("    .byte " + ",".join(f"${b:02X}" for b in rowbytes))
    return "\n".join(lines)


# ---- event sounds: two-voice streams for the Ensoniq DOC --------------------
# Streams are (freq_lo, freq_hi, dur_vblanks) triplets; dur 0 ends the voice.
# freq 0 = rest. With 2 oscillators scanned the DOC steps each one at
# 894886.25/(2+2) Hz; a 256-byte wave at resolution 0 repeats every 2^17
# accumulator counts, so freq_reg = f_hz * 2^17 / scan_rate.
# No melodies here by design: period comms tools were silent, so the app's
# whole voice is three event sounds (W-488) - the wake gesture, the dial
# theater, and the reply bell.
DOC_SCAN = 894886.25 / 4

def _voice(segs):
    """segs: (hz, vblanks) pairs, raw frequency; hz 0 = rest."""
    out = []
    for hz, vbl in segs:
        assert 1 <= vbl <= 255
        if hz <= 0:
            out += [0, 0, vbl]
        else:
            f = max(1, min(0xFFFF, round(hz * 131072 / DOC_SCAN)))
            out += [f & 0xFF, f >> 8, vbl]
    out += [0, 0, 0]                        # terminator: end of stream
    return out

def _wave():
    """Rounded square: softer than a pure square, still chippy. A $00 sample
    HALTS a DOC oscillator, so floor at $01."""
    w = [0xD8 if i < 128 else 0x28 for i in range(256)]
    for _ in range(3):
        w = [(w[i - 1] + 2 * w[i] + w[(i + 1) % 256]) // 4 for i in range(256)]
    return [max(1, v) for v in w]

# WAKE - the once-per-boot menu greeting (replaced GROOVE, W-488). Not a
# melody: a rising two-voice gesture that lands on an A4+E5 fifth and fades
# out via the release ramp in codex.s. Reads as "something woke up" - the
# sound marks the terminal waking, not the phone system.
SND_WAKE0 = [(hz, 3) for hz in (220.0, 261.6, 329.6, 392.0, 440.0,
                                523.3, 587.3)] + [(659.3, 26)]
SND_WAKE1 = [(0, 15), (329.6, 6), (440.0, 26)]

# DIAL - the Connect theater: the real 1986 dial-up soundscape. The
# stream plays through even when the modem answers fast (W-517: a buzz
# chopped mid-note read as a glitch); the silence AFTER it is the Hayes
# ATM1 arc - speaker off at carrier. A failed dial still cuts it dead.
# Every element is the documented tone pair, which is exactly what two
# DOC voices are for. The DTMF digits spell C-L-A-U-D-E on a phone keypad.
_DTMF = {
    "2": (697, 1336),
    "3": (697, 1477),
    "6": (770, 1477),
    "9": (852, 1477),
}

def _dial_pair():
    v0, v1 = [(350, 30)], [(440, 30)]           # dial tone
    v0 += [(0, 4)]; v1 += [(0, 4)]
    for d in "26339":                           # "CODEX"
        lo, hi = _DTMF[d]
        v0 += [(lo, 4), (0, 3)]
        v1 += [(hi, 4), (0, 3)]
    v0 += [(0, 8)]; v1 += [(0, 8)]              # switch thinks
    v0 += [(440, 36), (0, 12)]                  # ringback, abbreviated
    v1 += [(480, 36), (0, 12)]
    v0 += [(2225, 20)]; v1 += [(0, 20)]         # answer tone (Bell 212A)
    v0 += [(0, 6)]; v1 += [(0, 6)]              # the V.22bis silent beat
    v0 += [(1200, 54)]; v1 += [(2400, 54)]      # both carriers = the buzz
    return v0, v1

# BELL - the reply bell: one ~1 kHz tone with the IIgs-style fading tail
# (the GS system beep decays; the IIe's doesn't - that's why GS beeps
# sound rounder). A soft octave under it for warmth.
SND_BELL0 = [(1000, 10)]
SND_BELL1 = [(500, 10)]

def emit_music():
    wave = _wave()
    lines = ["wave_data:"]
    for i in range(0, 256, 16):
        lines.append("    .byte " + ",".join(f"${b:02X}" for b in wave[i:i + 16]))
    dial0, dial1 = _dial_pair()
    assert sum(v for _, v in dial0) == sum(v for _, v in dial1)
    assert sum(v for _, v in SND_WAKE0) == sum(v for _, v in SND_WAKE1)
    blob = []
    for name, segs in (("SND_WAKE0", SND_WAKE0), ("SND_WAKE1", SND_WAKE1),
                       ("SND_DIAL0", dial0), ("SND_DIAL1", dial1),
                       ("SND_BELL0", SND_BELL0), ("SND_BELL1", SND_BELL1)):
        lines.append(f"{name} = {len(blob)}")
        blob += _voice(segs)
    lines.append("music_data:")
    for i in range(0, len(blob), 16):
        lines.append("    .byte " + ",".join(f"${b:02X}" for b in blob[i:i + 16]))
    return "\n".join(lines)


if __name__ == "__main__":
    with open("assets.inc", "w") as f:
        f.write("; generated by gen_assets.py (640 mode)\n")
        f.write(emit_palette() + "\n\n")
        f.write(emit_expand() + "\n\n")
        f.write(emit_mascot() + "\n\n")
        f.write(emit_splash() + "\n\n")
        f.write(emit_spinwords() + "\n\n")
        f.write(emit_bullet() + "\n\n")
        f.write(emit_music() + "\n\n")
        f.write(emit_font() + "\n")
    print("wrote assets.inc")
