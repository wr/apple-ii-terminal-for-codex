from pathlib import Path


def test_native_clients_have_codex_identity_and_isolated_dial_token():
    files = [Path("apple2gs/codex.s"), Path("apple2/codex2.s")]
    for path in files:
        text = path.read_text()
        assert '"ATDS=1"' in text
        assert '"CDXTK1"' in text
        assert "Terminal for Codex" in text or "TERMINAL FOR CODEX" in text
        assert "github.com/wr/apple-ii-terminal-for-codex" in text
        assert "ATDS=0" not in text
        assert "CLDTK1" not in text
        assert "Claude Code" not in text


def test_native_help_lists_only_local_commands():
    for path in (Path("apple2gs/codex.s"), Path("apple2/codex2.s")):
        text = path.read_text()
        assert "/new /model /help /quit" in text
        assert "/mode " not in text
        assert "/mode," not in text
