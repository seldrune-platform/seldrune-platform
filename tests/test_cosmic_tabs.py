from pathlib import Path


def test_cosmic_console_assets_define_unified_owner_portal():
    web = Path("backend/app/web")
    script = (web / "console-cosmic-tabs.js").read_text()
    styles = (web / "console-cosmic-tabs.css").read_text()
    portal_styles = (web / "console-portal.css").read_text()

    assert "data-portal-tab" in script
    assert '["sense", "SENSE", "◉"]' in script
    assert '["operator", "SELDRUNE AI", "✦"]' in script
    assert 'move("#seldrune-gpt", "operator")' in script
    assert 'move("#tool-control", "intelligence")' in script
    assert ".cosmic-tab-panel.active" in styles
    assert "#seldrune-gpt-thread" in styles
    assert ".owner-portal-home" in portal_styles
    assert "portal-depth-scene" in script
    assert "portal-gateway" in script
    assert "neural-grid-layer" in script
    assert "portal-particles" in script
    assert "trigger.dataset.focusTarget" in script
    assert ".portal-quick-card" in portal_styles
    assert ".portal-fractal" in portal_styles
    assert "@keyframes neural-drift" in portal_styles


def test_owner_console_loads_unified_portal_assets():
    html = Path("backend/app/web/index.html").read_text()
    assert "/console-assets/console-cosmic-tabs.css" in html
    assert "/console-assets/console-cosmic-tabs.js" in html
    assert "/console-assets/console-system-sense.js" in html
    assert "/console-assets/console-portal.css" in html
    assert "/console-assets/console-portal-settings.js" in html
