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
    assert "for (const track of session.local.getTracks())" in response.text
    assert "for (const track of local.getTracks())" not in response.text


def test_media_client_stop_cancels_a_pending_camera_session():
    response = TestClient(app).get("/console-assets/seldrune-media.js")

    assert response.status_code == 200
    assert "pending.cancel()" in response.text
    assert "attempt.cancelledPromise" in response.text
    assert "pendingSession !== attempt" in response.text
    assert "remoteClosePromise" in response.text


def test_media_client_waits_for_gateway_teardown_before_restart():
    response = TestClient(app).get("/console-assets/seldrune-media.js")

    source = response.text
    close_start = source.index("function closeRemote(session) {")
    close_end = source.index("async function openSession", close_start)
    close_remote = source[close_start:close_end]

    assert "session.closing = true;" in close_remote
    assert "session.remoteClosePromise || Promise.resolve()" in close_remote
    assert "]).finally(() => {" in close_remote
    assert close_remote.index("]).finally") < close_remote.index(
        "if (activeSession === session) activeSession = null;"
    )
    assert "activeSession && !activeSession.closing && activeSession.peer" in source


def test_product_studio_links_to_the_separate_media_console():
    response = TestClient(app).get("/web/products.html")

    assert response.status_code == 200
    assert 'href="/media"' in response.text
    assert "Seldrune Media Console" in response.text
