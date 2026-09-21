def test_owner_console_serves_xenobiotic_interface(client) -> None:
    page = client.get("/console")
    assert page.status_code == 200
    assert "/console-assets/console-xenobiotic.css" in page.text
    assert "/console-assets/console-xenobiotic.js" in page.text

    stylesheet = client.get("/console-assets/console-xenobiotic.css")
    assert stylesheet.status_code == 200
    assert "V5" in stylesheet.text
    assert ".xeno-nexus" in stylesheet.text
    assert ".xeno-radial-core" in stylesheet.text
    assert '[data-xeno-mode="incident"]' in stylesheet.text
    assert "prefers-reduced-motion:reduce" in stylesheet.text

    script = client.get("/console-assets/console-xenobiotic.js")
    assert script.status_code == 200
    assert "SELDRUNE NEXUS" in script.text
    assert "data-jump" in script.text
    assert "MutationObserver" in script.text
    assert "data-xeno-mode" in script.text
    assert "incident-critical" in script.text
    assert "sti-running" in script.text
    assert "face-cuda-step" in script.text
    assert "ls-webrtc" in script.text


def test_xenobiotic_interface_preserves_measured_state_language(client) -> None:
    script = client.get("/console-assets/console-xenobiotic.js")
    assert script.status_code == 200
    assert "REALITY <b>MEASURED</b>" in script.text
    assert "CORE <b>ONLINE</b>" in script.text
    assert "fake" not in script.text.lower()
    assert "simulated" not in script.text.lower()


def test_xenobiotic_v6_attention_vector_uses_measured_counters(client) -> None:
    script = client.get("/console-assets/console-xenobiotic.js")
    assert script.status_code == 200
    assert "ATTENTION VECTOR" in script.text
    assert "xeno-attention-field" in script.text
    assert 'read("incident-critical")' in script.text
    assert 'read("pending")' in script.text
    assert 'read("sti-running")' in script.text
    assert 'read("sti-failed")' in script.text
    assert "no elevated measured counters" in script.text

    stylesheet = client.get("/console-assets/console-xenobiotic.css")
    assert stylesheet.status_code == 200
    assert "V6" in stylesheet.text
    assert ".xeno-attention-field" in stylesheet.text

# V6 PR validation pulse.


def test_xenobiotic_v7_reality_constellation_uses_measured_state(client) -> None:
    script = client.get("/console-assets/console-xenobiotic.js")
    assert script.status_code == 200
    assert "V7" in script.text
    assert "REALITY CONSTELLATION" in script.text
    assert "xeno-reality-constellation" in script.text
    for source_id in ("pending", "sti-running", "sti-verified", "ls-cuda", "ls-onnx"):
        assert source_id in script.text

    stylesheet = client.get("/console-assets/console-xenobiotic.css")
    assert stylesheet.status_code == 200
    assert "Verified Reality Constellation" in stylesheet.text
    assert ".xeno-reality-node" in stylesheet.text
    assert "prefers-reduced-motion" in stylesheet.text


def test_xenobiotic_v8_owner_command_lens_is_measured_and_navigable(client) -> None:
    script = client.get("/console-assets/console-xenobiotic.js")
    assert script.status_code == 200
    assert "V8" in script.text
    assert "COMMAND LENS" in script.text
    assert "xeno-command-lens" in script.text
    for target in ("action-inbox", "command", "sti-runtime", "liveshift-mission"):
        assert f'data-lens="{target}"' in script.text
    assert 'document.getElementById("pending")' in script.text
    assert 'document.getElementById("sti-running")' in script.text

    stylesheet = client.get("/console-assets/console-xenobiotic.css")
    assert stylesheet.status_code == 200
    assert "Owner Command Lens" in stylesheet.text
    assert '[data-attention="decision"]' in stylesheet.text
    assert '[data-attention="execution"]' in stylesheet.text
