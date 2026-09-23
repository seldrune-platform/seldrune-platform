from pathlib import Path

WEB = Path("backend/app/web")


def test_owner_console_uses_single_owner_portal_shell():
    html = (WEB / "index.html").read_text()
    assert "/console-assets/console-cosmic-tabs.css" in html
    assert "/console-assets/console-cosmic-tabs.js" in html
    assert "/console-assets/console-portal.css" in html
    assert "/console-assets/console-portal-settings.js" in html
    assert "/console-assets/seldrune-gpt-studio.css" in html

    # Engineering/version presentation layers stay out of the normal owner portal.
    assert "/console-assets/console-xenobiotic.css" not in html
    assert "/console-assets/console-xenobiotic.js" not in html
    assert "/console-assets/console-v100.css" not in html
    assert "/console-assets/console-v100.js" not in html
    assert "/console-assets/console-tabs.css" not in html
    assert "/console-assets/console-tabs.js" not in html


def test_gpt_operator_remains_truth_gated_and_multimodal():
    html = (WEB / "index.html").read_text()
    assert 'id="seldrune-gpt-execute"' in html
    assert "confirmation-gated" in html
    assert 'id="seldrune-gpt-model"' in html
    assert 'id="seldrune-gpt-files"' in html
    assert 'id="seldrune-gpt-dropzone"' in html
    assert 'id="seldrune-gpt-attachments"' in html


def test_portal_controller_defines_owner_workspaces_and_fixed_home():
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
    assert 'activate("home", false)' in js
    assert "seldrune.portal.lastWorkspace" not in js


def test_portal_settings_are_browser_scoped_and_home_is_locked():
    js = (WEB / "console-portal-settings.js").read_text()
    assert "seldrune.portal.theme" in js
    assert "seldrune.portal.density" in js
    assert "seldrune.portal.motion" in js
    assert "seldrune.portal.defaultWorkspace" not in js
    assert "Fixed landing page" in js
    assert "Home · Locked" in js
    assert "Preferences are stored in this browser only." in js


def test_owner_portal_hides_legacy_navigation_shell():
    css = (WEB / "console-portal.css").read_text()
    assert "body.owner-portal #console-view>aside" in css
    assert "display:none!important" in css
    assert "header:not(.owner-portal-bar)" in css
    assert "grid-template-columns:minmax(0,1fr)" in css
