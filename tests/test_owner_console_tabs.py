from pathlib import Path

WEB = Path("backend/app/web")


def test_owner_console_exposes_dedicated_tabs():
    html = (WEB / "index.html").read_text()
    tabs = ("overview", "gpt", "runtime", "face", "liveshift", "actions", "governance", "commands")
    for tab in tabs:
        assert f'data-console-tab="{tab}"' in html
    assert 'data-console-tab="gpt" href="#seldrune-gpt">ChatGPT</a>' in html
    assert '/console-assets/console-tabs.css' in html
    assert '/console-assets/console-tabs.js' in html


def test_gpt_operator_remains_truth_gated():
    html = (WEB / "index.html").read_text()
    assert 'id="seldrune-gpt-execute"' in html
    assert "require fresh confirmation" in html
    assert 'id="seldrune-gpt-model"' in html


def test_tab_controller_keeps_one_explicit_workspace():
    js = (WEB / "console-tabs.js").read_text()
    assert 'gpt:["seldrune-gpt"]' in js
    assert 'classList.remove("console-tab-active")' in js
    assert 'localStorage.setItem("seldrune.console.tab",selected)' in js
