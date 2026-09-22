from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.evolution_registry import evolution_registry, evolution_summary


client = TestClient(app)


def test_v22_v100_registry_is_complete_and_contiguous() -> None:
    stages = evolution_registry()
    assert len(stages) == 79
    assert [stage["version"] for stage in stages] == list(range(22, 101))
    assert all(stage["contract_status"] == "registered" for stage in stages)
    assert stages[0]["label"] == "V22"
    assert stages[-1]["label"] == "V100"


def test_v100_summary_preserves_truth_boundary() -> None:
    summary = evolution_summary()
    assert summary["range"] == "V22–V100"
    assert summary["total_stages"] == 79
    assert summary["contract_coverage"] is True
    assert summary["v100_attained"] is False
    assert summary["evidence_counts"]["implemented"] > 0
    assert summary["evidence_counts"]["registered"] > 0
    assert "not reported as production-verified" in summary["truth_boundary"]


def test_sti_evolution_endpoint_exposes_all_version_contracts() -> None:
    response = client.get("/api/v1/sti/evolution")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_stages"] == 79
    assert len(payload["stages"]) == 79
    assert payload["stages"][0]["version"] == 22
    assert payload["stages"][-1]["version"] == 100
    assert payload["arcs"][-1]["name"] == "Convergence"


def test_owner_console_loads_v100_evolution_control() -> None:
    console = client.get("/console")
    assert console.status_code == 200
    assert "/console-assets/console-v100.css" in console.text
    assert "/console-assets/console-v100.js" in console.text

    script = client.get("/console-assets/console-v100.js")
    assert script.status_code == 200
    assert "TECHNICAL EVOLUTION CONTROL · V22–V100" in script.text
    assert "/api/v1/sti/evolution" in script.text
    assert "79 version contracts" in script.text
    assert "EVIDENCE-GATED" in script.text

    stylesheet = client.get("/console-assets/console-v100.css")
    assert stylesheet.status_code == 200
    assert ".v100-deck" in stylesheet.text
    assert ".v100-matrix" in stylesheet.text
    assert "@media(prefers-reduced-motion:reduce)" in stylesheet.text
