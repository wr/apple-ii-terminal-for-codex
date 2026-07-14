from pathlib import Path


def test_native_clients_have_codex_identity_and_isolated_dial_token():
    files = [Path("apple2gs/codex.s"), Path("apple2/codex2.s")]
    for path in files:
        text = path.read_text()
        assert '"ATDS=1"' in text
        assert "Terminal for Codex" in text or "TERMINAL FOR CODEX" in text
        assert "github.com/wr/apple-ii-terminal-for-codex" in text
        assert "ATDS=0" not in text
        assert "CLDTK1" not in text
        assert "Claude Code" not in text
    assert '"CDXTK1"' in Path("apple2/codex2.s").read_text()


def test_phonebook_setup_uses_codex_entry_one_everywhere():
    paths = [
        Path("bridge/bridge.py"),
        Path("apple2gs/codex.s"),
        Path("apple2/codex2.s"),
    ]
    for path in paths:
        text = path.read_text()
        assert "AT&Z1=" in text, path
        assert "AT&Z0=" not in text, path


def test_native_help_lists_only_local_commands():
    for path in (Path("apple2gs/codex.s"), Path("apple2/codex2.s")):
        text = path.read_text()
        assert "/new /model /help /quit" in text
        assert "/mode " not in text
        assert "/mode," not in text


def test_8bit_logo_is_a_terminal_prompt_with_blinking_underscore():
    text = Path("apple2/codex2.s").read_text()
    assert '.byte   "   XX   XXXXXX  "' in text
    assert "logo_hide_cursor" in text
    assert "logo_show_cursor" in text


def test_legacy_identity_is_absent_from_product_sources():
    paths = [
        Path("apple2gs/gen_assets.py"),
        Path("apple2gs/preview.py"),
        Path("apple2gs/codex.s"),
        Path("apple2/codex2.s"),
        Path("bridge/bridge.py"),
    ]
    joined = "\n".join(path.read_text() for path in paths)
    assert "Patch" not in joined
    assert "Cogitating" not in joined
    assert "coral" not in joined.lower()
