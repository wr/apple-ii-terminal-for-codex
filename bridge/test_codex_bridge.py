import subprocess
from types import SimpleNamespace

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


def test_app_session_installs_host_console_activity_observer(monkeypatch):
    backend = SimpleNamespace(on_activity=None)
    shown = []
    sentinel = object()

    monkeypatch.setattr(bridge, "make_backend", lambda *_args: backend)
    monkeypatch.setattr(
        bridge,
        "show_activity",
        lambda peer, kind, detail: shown.append((peer, kind, detail)),
        raising=False,
    )

    def fake_app_session(_term, _args, observed, *_rest):
        assert observed is backend
        assert callable(observed.on_activity)
        observed.on_activity("tool", "pytest -q")
        return sentinel

    monkeypatch.setattr(bridge, "run_app_session", fake_app_session)
    term = SimpleNamespace(ch=SimpleNamespace(peer="apple2.local"))
    args = SimpleNamespace(cols=80, app=True)

    assert bridge._run_session(term, args, pm=None, guard=None) is sentinel
    assert shown == [("apple2.local", "tool", "pytest -q")]


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
