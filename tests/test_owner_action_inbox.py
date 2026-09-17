def test_owner_console_serves_action_inbox_assets(client) -> None:
    page = client.get("/console")
    assert page.status_code == 200
    assert 'id="action-inbox"' in page.text
    assert 'href="#action-inbox"' in page.text
    assert 'id="attention-sync"' in page.text
    assert 'id="attention-alert-toggle"' in page.text
    assert 'id="attention-alert-detail"' in page.text
    assert "Live attention will poll every 30 seconds" in page.text
    assert "/console-assets/console-action-inbox.css" in page.text
    assert "/console-assets/console-action-inbox.js" in page.text
    assert "Complete governed command history" in page.text

    stylesheet = client.get("/console-assets/console-action-inbox.css")
    assert stylesheet.status_code == 200
    assert ".action-inbox-item" in stylesheet.text
    assert ".action-inbox-critical" in stylesheet.text
    assert ".action-inbox-review" in stylesheet.text
    assert ".action-inbox-approval" in stylesheet.text
    assert ".attention-alert-controls" in stylesheet.text
    assert ".attention-sync-live" in stylesheet.text
    assert ".attention-sync-paused" in stylesheet.text
    assert ".attention-sync-error" in stylesheet.text
    assert "prefers-reduced-motion:reduce" in stylesheet.text


def test_action_inbox_uses_server_ranked_attention(client) -> None:
    script = client.get("/console-assets/console-action-inbox.js")
    assert script.status_code == 200
    assert "/owner-attention" in script.text
    assert "/owner-commands" in script.text
    assert "/owner-dashboard" not in script.text
    assert "/executive-brief" not in script.text
    assert "attention.items" in script.text
    assert "renderAllCommands" in script.text
    assert "commandListMatches" in script.text
    assert "dataset.action" in script.text


def test_action_inbox_live_polling_uses_conditional_snapshot(client) -> None:
    script = client.get("/console-assets/console-action-inbox.js")
    assert script.status_code == 200
    assert "const POLL_INTERVAL_MS=30000" in script.text
    assert "const BACKGROUND_ALERT_INTERVAL_MS=60000" in script.text
    assert "/owner-attention/snapshot?limit=1" in script.text
    assert "If-None-Match" in script.text
    assert "response.status===304" in script.text
    assert "document.hidden" in script.text
    assert "visibilitychange" in script.text
    assert "Keeping the last good owner-attention view" in script.text
    assert "schedulePoll()" in script.text


def test_owner_attention_browser_alerts_are_explicit_opt_in(client) -> None:
    page = client.get("/console")
    script = client.get("/console-assets/console-action-inbox.js")

    assert "Enable browser alerts" in page.text
    assert "Notification.requestPermission()" in script.text
    assert "seldruneOwnerAttentionAlerts" in script.text
    assert "localStorage.setItem" in script.text
    assert "new Notification(envelope.title||'Seldrune Owner Attention'" in script.text
    assert "previousFingerprint" in script.text
    assert "previousFingerprint!==lastAttentionFingerprint" in script.text
    assert "if(!alertsEnabled()||!document.hidden||!envelope.has_attention)return" in script.text
    assert "surfaceStale=true" in script.text
    assert "60s privacy-safe background watch" in script.text


def test_action_inbox_is_navigation_and_review_surface(client) -> None:
    page = client.get("/console")
    script = client.get("/console-assets/console-action-inbox.js")

    assert "Seldrune never acts from this inbox without the existing owner controls." in page.text
    assert "review_command" in script.text
    assert "action.kind==='navigate'" in script.text
    assert "method:'POST'" not in script.text
    assert 'method:"POST"' not in script.text
