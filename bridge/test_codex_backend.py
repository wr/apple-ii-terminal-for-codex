import json
from pathlib import Path

import pytest

import backends


FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def backend(**overrides):
    values = dict(
        cols=80,
        model=None,
        codex_bin="codex",
        cwd="/tmp/repo",
        sandbox="workspace-write",
        show_tools=False,
    )
    values.update(overrides)
    return backends.CodexBackend(**values)


def test_first_turn_argv_uses_stdin_and_fail_closed_config():
    assert backend()._build_cmd() == [
        "codex",
        "exec",
        "--json",
        "--color",
        "never",
        "-c",
        'sandbox_mode="workspace-write"',
        "-c",
        'approval_policy="never"',
        "-",
    ]


def test_resume_argv_repeats_model_and_permissions():
    be = backend(model="gpt-5.4", sandbox="read-only")
    be._thread_id = "019-test-thread"
    assert be._build_cmd() == [
        "codex",
        "exec",
        "resume",
        "--json",
        "--color",
        "never",
        "-c",
        'sandbox_mode="read-only"',
        "-c",
        'approval_policy="never"',
        "--model",
        "gpt-5.4",
        "019-test-thread",
        "-",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("codex-cli 0.144.1", (0, 144, 1)),
        ("codex-cli 1.2.3\n", (1, 2, 3)),
        ("garbage", None),
    ],
)
def test_parse_codex_version(raw, expected):
    assert backends._parse_codex_version(raw) == expected


def test_first_turn_fixture_emits_only_agent_message_and_saves_metadata():
    be = backend()
    output = []
    for raw in (FIXTURES / "first-turn.jsonl").read_text().splitlines():
        output.extend(be._render_event(json.loads(raw)))
    assert "".join(output) == "Done. I changed one file."
    assert be._thread_id == "019-test-thread"
    assert be._last_output_tokens == 9
    assert "private" not in "".join(output)


def test_tool_fixture_is_quiet_in_app_and_summarized_in_raw_mode():
    events = [
        json.loads(line)
        for line in (FIXTURES / "tool-turn.jsonl").read_text().splitlines()
    ]
    quiet = backend(show_tools=False)
    loud = backend(show_tools=True)
    assert "".join(x for event in events for x in quiet._render_event(event)) == (
        "All tests pass."
    )
    rendered = "".join(x for event in events for x in loud._render_event(event))
    assert "pytest -q" in rendered
    assert "bridge.py" in rendered
    assert "All tests pass." in rendered


def test_header_and_footer_are_codex_specific(monkeypatch):
    monkeypatch.setattr(backends, "codex_version", lambda _bin: (0, 144, 1))
    be = backend(model="gpt-5.4", cwd="/tmp/repo")
    be._last_duration_ms = 2300
    be._last_output_tokens = 1200
    assert be.header() == ("Codex CLI v0.144.1", "gpt-5.4", "/tmp/repo")
    assert be.footer() == "Worked for 2s - 1.2k tokens"
