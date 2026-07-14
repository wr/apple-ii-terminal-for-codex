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
