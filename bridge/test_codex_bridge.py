import subprocess

import pytest

import bridge
from backends import CodexBackend


def git_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return str(tmp_path)


def test_defaults_are_codex_workspace_write(tmp_path):
    args = bridge.parse_args(["--telnet", "--workdir", git_repo(tmp_path)])
    assert args.port == 6401
    assert args.sandbox == "workspace-write"
    assert args.codex_bin == "codex"
    assert not hasattr(args, "backend")
    assert not hasattr(args, "effort")


@pytest.mark.parametrize("sandbox", ["workspace-write", "read-only"])
def test_supported_sandboxes(tmp_path, sandbox):
    args = bridge.parse_args(
        ["--telnet", "--workdir", git_repo(tmp_path), "--sandbox", sandbox]
    )
    assert args.sandbox == sandbox


def test_workdir_must_exist_and_be_git(tmp_path):
    with pytest.raises(SystemExit):
        bridge.parse_args(
            ["--telnet", "--workdir", str(tmp_path / "missing")]
        )
    with pytest.raises(SystemExit):
        bridge.parse_args(["--telnet", "--workdir", str(tmp_path)])


def test_make_backend_returns_codex_backend(tmp_path):
    args = bridge.parse_args(["--telnet", "--workdir", git_repo(tmp_path)])
    be = bridge.make_backend(80, args)
    assert isinstance(be, CodexBackend)
    assert be._cwd == str(tmp_path.resolve())
    assert be._sandbox == "workspace-write"


def test_unknown_slash_command_is_never_forwarded():
    class Term:
        def __init__(self):
            self.lines = []

        def write_line(self, value):
            self.lines.append(value)

    term = Term()
    result = bridge.handle_command("/compact", term, None, None)
    assert result is None
    assert term.lines == ["[unknown command: /compact - try /help]"]


def test_pairing_store_is_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert bridge._pairing_store() == str(
        tmp_path / "codex-ii-terminal" / "paired.json"
    )


def test_help_security_epilog_has_no_stale_fragment(capsys):
    with pytest.raises(SystemExit) as stopped:
        bridge.parse_args(["--help"])
    assert stopped.value.code == 0
    help_text = capsys.readouterr().out
    assert "Codex session" in help_text
    assert "shell on this host)" not in help_text
