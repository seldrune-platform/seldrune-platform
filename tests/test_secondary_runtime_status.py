def test_shared_secondary_runtime_asset_is_served(client) -> None:
    script = client.get("/console-assets/secondary-runtime.js")
    assert script.status_code == 200
    assert "fetch('/api/v1/status'" in script.text
    assert "surface-runtime-ready" in script.text
    assert "surface-runtime-degraded" in script.text
    assert "provider.live_ai" in script.text


def test_secondary_control_surfaces_load_runtime_status(client) -> None:
    paths = (
        "/console-assets/executive-brief.html",
        "/console-assets/command-monitor.html",
        "/console-assets/organization-board.html",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert "/console-assets/secondary-runtime.js" in response.text


def test_secondary_runtime_styles_are_available(client) -> None:
    stylesheet = client.get("/console-assets/secondary-cinematic.css")
    assert stylesheet.status_code == 200
    assert ".surface-runtime{" in stylesheet.text
    assert ".surface-runtime-ready .surface-runtime-indicator" in stylesheet.text
    assert ".surface-runtime-degraded .surface-runtime-indicator" in stylesheet.text
    assert "@media(max-width:720px)" in stylesheet.text
