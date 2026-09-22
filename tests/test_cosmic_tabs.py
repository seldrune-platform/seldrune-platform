from pathlib import Path


def test_cosmic_console_assets_exist_and_define_tabs():
    web = Path("backend/app/web")
    script = (web / "console-cosmic-tabs.js").read_text()
    styles = (web / "console-cosmic-tabs.css").read_text()
    assert "data-cosmic-tab" in script
    assert "'gpt', 'GPT'" in script
    assert "move('#seldrune-gpt', 'gpt')" in script
    assert ".cosmic-tab-panel.active" in styles
    assert "#seldrune-gpt-thread" in styles


def test_owner_console_loads_cosmic_assets():
    html = Path("backend/app/web/index.html").read_text()
    assert '/console-assets/console-cosmic-tabs.css' in html
    assert '/console-assets/console-cosmic-tabs.js' in html
