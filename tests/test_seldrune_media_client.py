from fastapi.testclient import TestClient

from backend.app.main import app


def test_media_console_route_serves_the_live_studio():
    response = TestClient(app).get("/media")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Seldrune Media Console" in response.text
    assert 'id="default-media"' in response.text


def test_media_client_is_available_to_seldrune_web_apps():
    response = TestClient(app).get("/console-assets/seldrune-media.js")

    assert response.status_code == 200
    assert "installDefault" in response.text
    assert "synthetic_media_indicator_enabled: true" in response.text
    assert "Turn on “Use Seldrune Media by default”" in response.text
    assert "This Seldrune Media default belongs to another signed-in account" in response.text


def test_product_studio_links_to_the_separate_media_console():
    response = TestClient(app).get("/web/products.html")

    assert response.status_code == 200
    assert 'href="/media"' in response.text
    assert "Seldrune Media Console" in response.text
