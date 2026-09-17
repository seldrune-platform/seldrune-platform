def test_secondary_control_surfaces_share_cinematic_theme(client) -> None:
    stylesheet = client.get("/console-assets/secondary-cinematic.css")
    assert stylesheet.status_code == 200
    assert '@import url("/console-assets/console-cinematic.css");' in stylesheet.text
    assert ".brief-shell" in stylesheet.text
    assert ".monitor-shell" in stylesheet.text
    assert ".org-shell" in stylesheet.text
    assert "prefers-reduced-motion:reduce" in stylesheet.text

    paths = (
        "/console-assets/executive-brief.html",
        "/console-assets/command-monitor.html",
        "/console-assets/organization-board.html",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert "/console-assets/secondary-cinematic.css" in response.text


def test_secondary_control_surfaces_do_not_show_stale_release_labels(client) -> None:
    executive_brief = client.get("/console-assets/executive-brief.html")
    command_monitor = client.get("/console-assets/command-monitor.html")

    assert "SELDRUNE v0.52" not in executive_brief.text
    assert "SELDRUNE · EXECUTIVE OUTCOME MEMORY" in executive_brief.text
    assert "SELDRUNE v0.18" not in command_monitor.text
    assert "SELDRUNE · SENSE LAYER" in command_monitor.text
