def test_owner_console_loads_mobile_navigation_override(client) -> None:
    console = client.get("/console")
    assert console.status_code == 200
    assert "/console-assets/console-mobile-nav.css" in console.text


def test_mobile_navigation_override_exposes_sidebar_links(client) -> None:
    stylesheet = client.get("/console-assets/console-mobile-nav.css")
    assert stylesheet.status_code == 200
    assert "@media(max-width:900px)" in stylesheet.text
    assert "aside nav" in stylesheet.text
    assert "display:flex" in stylesheet.text
    assert "overflow-x:auto" in stylesheet.text
    assert "white-space:nowrap" in stylesheet.text
