from pathlib import Path


PUBLIC = [
    Path("README.md"),
    Path("SECURITY.md"),
    Path("THIRD-PARTY-NOTICES.md"),
    Path("docs/MODEM-SETUP.md"),
    Path("apple2/TERMINAL-SETUP.md"),
]


def test_public_docs_name_the_shipped_product():
    joined = "\n".join(path.read_text() for path in PUBLIC)
    assert "CODEX.dsk" in joined
    assert "--workdir" in joined
    assert "workspace-write" in joined
    assert "approval_policy" in joined
    assert "TCP port 6401" in joined or ":6401" in joined
    assert "ATDS=1" in joined
    assert "apple-ii-terminal-for-codex" in joined


def test_removed_brand_assets_are_not_shipped():
    assert not Path("apple2gs/clawd.gif").exists()
    assert not Path("docs/demo.gif").exists()


def test_readme_keeps_the_hardware_first_project_voice():
    readme = Path("README.md").read_text()
    assert "A real Apple II, as a terminal for Codex." in readme
    assert "## Apple II instructions" in readme
    assert "### Prerequisites:" in readme
    assert "### Setup:" in readme
    assert "## Emulator instructions" in readme
    assert "## Advanced bridge options" in readme
    assert "## Generic terminal app instructions" in readme
    assert "## Building from source" in readme
    assert "https://buymeacoffee.com/wellsriley" in readme


def test_ci_runs_the_current_asset_test_module():
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "apple2gs/test_codex_assets.py" in workflow
    assert "test_patch_assets.py" not in workflow


def test_ci_installs_the_preview_test_dependency():
    requirements = Path("requirements-test.txt").read_text().splitlines()
    assert "Pillow==12.3.0" in requirements


def test_bridge_supports_reading_toml_on_python_310():
    requirements = Path("bridge/requirements.txt").read_text().splitlines()
    assert 'tomli==2.2.1; python_version < "3.11"' in requirements


def test_release_workflow_uses_codex_tag_namespace():
    workflow = Path(".github/workflows/release.yml").read_text()

    assert '- "codex-v*"' in workflow
    assert '- "v*"' not in workflow
    assert "apple2gs/CODEX.dsk" in workflow


def test_engineering_notes_make_downloads_refresh_opt_in():
    engineering = Path("AGENTS.md").read_text()

    assert "**GS client, full loop**: `COPY_TO_DOWNLOADS=1 ./build.sh`" in engineering


def test_v010_release_docs_match_current_product_state():
    changelog = Path("CHANGELOG.md").read_text()
    license_text = Path("LICENSE").read_text()
    engineering = Path("AGENTS.md").read_text()

    assert "## v0.1.0 - 2026-07-14" in changelog
    assert "These are release blockers" not in changelog
    assert '"Claude"/Clawd mascot artwork' not in license_text
    assert "CMD_INTERRUPT" in engineering
    assert "0x06" in engineering
    assert "IIgs client keeps it in RAM" in engineering


def test_internal_superpowers_plans_are_not_published():
    assert not Path("docs/superpowers").exists()
