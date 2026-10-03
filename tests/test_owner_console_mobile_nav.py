def test_owner_console_loads_clean_responsive_navigation(client) -> None:
    console = client.get("/console")
    assert console.status_code == 200
    assert "/console-assets/console-clean.css" in console.text

    stylesheet = client.get("/console-assets/console-clean.css")
    assert stylesheet.status_code == 200
    assert ".owner-portal-more-menu" in stylesheet.text
    assert "@media (max-width: 760px)" in stylesheet.text
    assert "@media (max-width: 520px)" in stylesheet.text
    assert ".owner-portal .owner-portal-tabs" in stylesheet.text
    assert ".owner-portal .owner-home-actions" in stylesheet.text
    assert ".owner-portal .contact-options" in stylesheet.text
