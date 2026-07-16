from pathlib import Path
import re

import pytest


SOURCES = (Path("apple2gs/codex.s"), Path("apple2/codex2.s"))
VERDICTS = {
    "CONNECT": 1,
    "ERROR": 2,
    "BUSY": 3,
    "NO_CARRIER": 4,
    "NO_ANSWER": 5,
}


def classify(transcript):
    """Model the clients' byte-at-a-time modem result state machine."""
    dialres = 0
    phase = 0
    for raw in transcript:
        byte = ord(raw) & 0x7F
        if byte == 0x0D:
            phase = 0
            continue
        if byte < 0x20:
            continue
        char = chr(byte).upper()
        if phase == 0xFF:
            continue
        if phase == ord("C"):
            if char == "O":
                dialres = VERDICTS["CONNECT"]
            phase = 0xFF
            continue
        if phase == ord("N"):
            phase = ord("M") if char == "O" else 0xFF
            continue
        if phase == ord("M"):
            if char == " ":
                continue
            if char == "A":
                dialres = VERDICTS["NO_ANSWER"]
            else:
                dialres = VERDICTS["NO_CARRIER"]
            phase = 0xFF
            continue
        if char == " ":
            continue
        if char == "E":
            dialres = VERDICTS["ERROR"]
            phase = 0xFF
        elif char == "B":
            dialres = VERDICTS["BUSY"]
            phase = 0xFF
        elif char == "C":
            phase = ord("C")
        elif char == "N":
            phase = ord("N")
        else:
            phase = 0xFF
    return dialres


@pytest.mark.parametrize(
    ("symbol", "value"),
    [
        ("DIAL_CONNECT", 1),
        ("DIAL_ERROR", 2),
        ("DIAL_BUSY", 3),
        ("DIAL_NO_CARRIER", 4),
        ("DIAL_NO_ANSWER", 5),
    ],
)
def test_both_clients_define_distinct_modem_verdicts(symbol, value):
    for source in SOURCES:
        assert f"{symbol} = {value}" in source.read_text(), source


@pytest.mark.parametrize(
    "message",
    [
        "AT&Z1=HOST:6401",
        "BRIDGE IS BUSY",
        "NO CARRIER",
        "BRIDGE IS LISTENING",
        "9600 8N1",
    ],
)
def test_both_clients_explain_modem_failures(message):
    for source in SOURCES:
        assert message in source.read_text().upper(), source


def test_direct_bridge_dial_gets_virtual_connect_for_emulators():
    text = Path("bridge/bridge.py").read_text()
    assert "_ack_direct_dial" in text
    assert 'term.write_line("CONNECT")' in text


@pytest.mark.parametrize(
    ("line", "verdict"),
    [
        ("CONNECT\r", "CONNECT"),
        ("connect 9600\r", "CONNECT"),
        ("ERROR\r", "ERROR"),
        ("BUSY\r", "BUSY"),
        ("NO CARRIER\r", "NO_CARRIER"),
        ("NO ANSWER\r", "NO_ANSWER"),
        ("NO DIALTONE\r", "NO_CARRIER"),
        ("   NO DIALTONE\r", "NO_CARRIER"),
    ],
)
def test_modem_classifier_behavior(line, verdict):
    assert classify(line) == VERDICTS[verdict]


@pytest.mark.parametrize("transcript", ["", "OK\r", "RING\r", "ATDS=1\r", "\r\n"])
def test_modem_classifier_leaves_silence_and_chatter_unclassified(transcript):
    assert classify(transcript) == 0


def test_modem_classifier_obeys_transcript_ordering():
    transcript = "ATDS=1\r\nRING\r\n  CONNECT 9600\r"
    assert classify(transcript) == VERDICTS["CONNECT"]


def test_native_parsers_skip_leading_spaces_and_classify_unknown_no_as_carrier():
    for source in SOURCES:
        parser = source.read_text().split("dial_byte:", 1)[1].split("modem_resume:", 1)[0]
        assert "skip a leading space" in parser
        assert "NO DIALTONE / other NO" in parser
        assert "#$FF" in parser


def silent_expiry_allows_session(dcd_trust, dcd_carrier):
    """Model the native-client policy when the dial window saw no verdict."""
    return bool(dcd_trust and dcd_carrier)


@pytest.mark.parametrize(
    ("dcd_trust", "dcd_carrier", "allowed"),
    [
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_silent_expiry_requires_trusted_current_carrier(
    dcd_trust, dcd_carrier, allowed
):
    assert silent_expiry_allows_session(dcd_trust, dcd_carrier) is allowed


def test_gs_silent_expiry_samples_dcd_and_rejects_untrusted_carrier():
    source = Path("apple2gs/codex.s").read_text()
    connect = source.split("act_connect:", 1)[1].split("; dsnd_beat", 1)[0]
    expiry = connect.split("ac_ck:", 1)[1].split("ac_hold:", 1)[0]

    dcd_sample = re.search(
        r"lda\s+#\$10.*?sta\s+SCC_STAT.*?lda\s+SCC_STAT.*?and\s+#\$08",
        expiry,
        re.S,
    )
    trust_check = re.search(r"lda\s+dcd_trust\s+beq\s+ac_fail", expiry)

    assert dcd_sample is not None
    assert trust_check is not None
    assert dcd_sample.start() < trust_check.start()
    # A no-carrier sample at silent expiry proves the DCD pin is live, so it
    # learns trust before failing (matches the Claude fork's unified policy).
    assert re.search(r"and\s+#\$08[^\n]*\n\s*beq\s+ac_silent_nocar", expiry)
    assert "bra     ac_hold" in expiry
    assert "sta     dcd_trust" in expiry
    assert "session_start" not in expiry
    assert "str_dtimeout" in connect.split("ac_fail:", 1)[1]


def test_8bit_silent_expiry_samples_dcd_and_rejects_untrusted_carrier():
    source = Path("apple2/codex2.s").read_text()
    connect = source.split("act_connect:", 1)[1].split("; dsnd_beat", 1)[0]
    expiry = connect.split("@ck:", 1)[1].split("@hold:", 1)[0]

    dcd_sample = re.search(r"lda\s+ACIA_S\s+and\s+#\$20", expiry)
    trust_check = re.search(r"lda\s+dcd_trust\s+beq\s+@fail", expiry)

    assert dcd_sample is not None
    assert trust_check is not None
    assert dcd_sample.start() < trust_check.start()
    # A no-carrier sample at silent expiry proves the DCD pin is live, so it
    # learns trust before failing (matches the Claude fork's unified policy).
    assert re.search(r"and\s+#\$20[^\n]*\n\s*bne\s+@silent_nocar", expiry)
    assert "jmp     @hold" in expiry
    assert "sta     dcd_trust" in expiry
    assert "session_start" not in expiry
    assert "str_dtimeout" in connect.split("@fail:", 1)[1]
