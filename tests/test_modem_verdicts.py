from pathlib import Path

import pytest


SOURCES = (Path("apple2gs/codex.s"), Path("apple2/codex2.s"))


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
