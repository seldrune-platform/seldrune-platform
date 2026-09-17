def test_background_browser_alerts_use_privacy_safe_envelope(client) -> None:
    script = client.get("/console-assets/console-action-inbox.js")
    assert script.status_code == 200

    text = script.text
    assert "const backgroundAlert=backgroundWatchActive()" in text
    assert "/owner-attention/notification-envelope" in text
    assert "/owner-attention/snapshot?limit=1" in text
    assert "body:envelope.body||'Owner attention changed.'" in text
    assert "const target=envelope.target||'/console#action-inbox'" in text
    assert "data:{target}" in text
    assert "!envelope.has_attention" in text
    assert "snapshot.top_items" not in text
    assert "snapshot.headline" not in text
    assert "privacy-safe counts-only checks every 60s" in text


def test_privacy_safe_browser_alerts_preserve_read_only_console_behavior(client) -> None:
    script = client.get("/console-assets/console-action-inbox.js")
    assert script.status_code == 200

    text = script.text
    assert "If-None-Match" in text
    assert "response.status===304" in text
    assert "const BACKGROUND_ALERT_INTERVAL_MS=60000" in text
    assert "Notification.requestPermission()" in text
    assert "method:'POST'" not in text
    assert 'method:"POST"' not in text
