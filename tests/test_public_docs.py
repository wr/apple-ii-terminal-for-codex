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


def test_ci_runs_the_current_asset_test_module():
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "apple2gs/test_codex_assets.py" in workflow
    assert "test_patch_assets.py" not in workflow


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
