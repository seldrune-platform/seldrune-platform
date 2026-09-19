from backend.app.api.routes.aetherion import evidence


def test_aetherion_evidence_endpoint_payload():
    payload = evidence()
    assert payload["health"]["software_ready"]
    assert payload["health"]["research_status"] == "experimental"
    assert payload["health"]["physical_qgpu_status"] == "unverified"
    assert not payload["runtime"]["quantum_speedup_verified"]
