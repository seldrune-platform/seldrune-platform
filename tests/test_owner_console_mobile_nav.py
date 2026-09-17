def test_owner_console_loads_mobile_navigation_override(client) -> None:
    console = client.get("/console")
    assert console.status_code == 200
    assert "/console-assets/console-mobile-nav.css" in console.text


def test_mobile_navigation_override_keeps_review_drift_visible(client) -> None:
    stylesheet = client.get("/console-assets/console-mobile-nav.css")
    assert stylesheet.status_code == 200
    assert "@media(max-width:900px)" in stylesheet.text
    assert "aside nav" in stylesheet.text
    assert "display:grid" in stylesheet.text
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in stylesheet.text
    assert "overflow:visible" in stylesheet.text
    assert 'a[href="/console-assets/executive-brief.html"]' in stylesheet.text
    assert "grid-column:1/-1" in stylesheet.text
    assert "background:#d6f56f" in stylesheet.text


def test_mobile_navigation_stacks_all_links_on_narrow_phones(client) -> None:
    stylesheet = client.get("/console-assets/console-mobile-nav.css")
    assert stylesheet.status_code == 200
    assert "@media(max-width:520px)" in stylesheet.text
    assert "aside nav{grid-template-columns:1fr;}" in stylesheet.text
