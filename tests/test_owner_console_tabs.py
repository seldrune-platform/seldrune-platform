from pathlib import Path

WEB = Path("backend/app/web")


def test_owner_console_uses_single_owner_portal_shell():
    html = (WEB / "index.html").read_text()
    assert "/console-assets/console-cosmic-tabs.css" in html
    assert "/console-assets/console-cosmic-tabs.js" in html
    assert "/console-assets/console-portal.css" in html
    assert "/console-assets/console-portal-settings.js" in html

    # Engineering/version presentation layers stay out of the normal owner portal.
    assert "/console-assets/console-xenobiotic.css" not in html
    assert "/console-assets/console-xenobiotic.js" not in html
    assert "/console-assets/console-v100.css" not in html
    assert "/console-assets/console-v100.js" not in html
    assert "/console-assets/console-tabs.css" not in html
    assert "/console-assets/console-tabs.js" not in html


def test_gpt_operator_remains_truth_gated():
    html = (WEB / "index.html").read_text()
    assert 'id="seldrune-gpt-execute"' in html
    assert "require fresh confirmation" in html
    assert 'id="seldrune-gpt-model"' in html


def test_portal_controller_defines_owner_workspaces():
    js = (WEB / "console-cosmic-tabs.js").read_text()
    for workspace in (
        "home",
        "operator",
        "operations",
        "media",
        "intelligence",
        "tools",
        "settings",
    ):
        assert f'["{workspace}",' in js
    assert "OWNER PORTAL" in js
    assert 'move("#seldrune-gpt", "operator")' in js
    assert 'move("#sti-runtime", "operations")' in js
    assert 'move("#face-v01-mission", "media")' in js
    assert 'move("#tool-control", "tools")' in js
    assert 'portalSettings.id = "portal-settings"' in js
    assert "seldrune.portal.lastWorkspace" in js


def test_portal_settings_are_browser_scoped_and_non_governance():
    js = (WEB / "console-portal-settings.js").read_text()
    assert "seldrune.portal.theme" in js
    assert "seldrune.portal.density" in js
    assert "seldrune.portal.motion" in js
    assert "seldrune.portal.defaultWorkspace" in js
    assert "Preferences are stored in this browser only." in js
    assert "without changing backend execution policy" not in js.lower()
