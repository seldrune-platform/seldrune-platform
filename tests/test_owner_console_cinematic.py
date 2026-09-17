def test_owner_console_serves_cinematic_theme(client) -> None:
    stylesheet = client.get("/console-assets/console-cinematic.css")
    assert stylesheet.status_code == 200
    assert "data:image/svg+xml" in stylesheet.text
    assert "@keyframes dragonFloat" in stylesheet.text
    assert "@keyframes auroraShift" in stylesheet.text
    assert "prefers-reduced-motion:reduce" in stylesheet.text


def test_owner_console_loads_cinematic_theme_through_stylesheet_chain(client) -> None:
    stylesheet = client.get("/console-assets/console-mobile-nav.css")
    assert stylesheet.status_code == 200
    assert '@import url("/console-assets/console-cinematic.css");' in stylesheet.text
