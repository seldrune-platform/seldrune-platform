from pathlib import Path


def test_owner_portal_uses_compact_navigation_and_flat_home():
    web = Path("backend/app/web")
    script = (web / "console-cosmic-tabs.js").read_text()
    clean = (web / "console-clean.css").read_text()
    html = (web / "index.html").read_text()

    for workspace in ("home", "operator", "media", "connections", "contact"):
        assert f'"{workspace}"' in script
    assert "PRIMARY_WORKSPACES" in script
    assert "owner-portal-more-tabs" in script
    assert 'data-open-portal="contact"' in script
    assert "portal-depth-scene" not in script
    assert "portal-gateway" not in script
    assert "pointermove" not in script
    assert "data-depth" not in script
    assert "portal-particles" not in script
    assert "Report a portal issue" in script
    assert 'href="/mail"' in script
    assert "perspective: none !important" in clean
    assert "owner-portal-more-menu" in clean
    assert "seldrune-celestial-hero.png" in clean
    assert "console-clean.css" in html
    assert "console-cinematic.css" not in html
    assert "console-nexus-arena.css" not in html
    assert "console-nexus-arena.js" not in html


def test_media_creation_is_separate_from_text_chat():
    web = Path("backend/app/web")
    html = (web / "index.html").read_text()
    portal = (web / "console-cosmic-tabs.js").read_text()
    gpt = (web / "seldrune-gpt.js").read_text()

    assert "Seldrune AI · text chat" in html
    assert "Create image, narration, or video" in html
    assert 'data-creation-mode="image"' in html
    assert 'data-creation-mode="speech"' in html
    assert 'data-creation-mode="song"' not in html
    assert 'data-creation-mode="video"' in html
    assert 'data-creation-mode="visual"' not in html
    assert 'data-creation-mode="app"' not in html
    assert 'data-creation-mode="game"' not in html
    assert 'id="seldrune-media-creation"' in html
    assert "mediaForgeHost.append(mediaForge)" in portal
    assert "Media creation is opt-in from the Media workspace" in gpt
    assert "startedFromMedia" in gpt
