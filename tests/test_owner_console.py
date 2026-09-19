from fastapi.testclient import TestClient

from backend.app.main import app


def test_owner_console_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/console")
        assert response.status_code == 200
        assert "Seldrune Owner Console" in response.text
        assert "/console-assets/console.css" in response.text
        assert "Command monitor" in response.text
        assert "Organization board" in response.text
        assert "ORGANIZATION TREASURY" in response.text
        assert "treasury-allocated" in response.text
        assert "treasury-available" in response.text
        assert "AGENT PERFORMANCE OBSERVATORY" in response.text
        assert "agent-performance-list" in response.text
        assert "runtime-status" in response.text
        assert "runtime-version" in response.text
        assert "OPERATIONAL INCIDENT CENTER" in response.text
        assert "incident-list" in response.text
        assert "GOVERNANCE AUDIT CENTER" in response.text
        assert "audit-list" in response.text
        assert "audit-filter" in response.text
        assert "download-audit" in response.text
        assert "Download evidence" in response.text
        assert "verify-audit-file" in response.text
        assert "Verify evidence" in response.text
        assert "audit-verification" in response.text
        assert "GOVERNANCE POLICY CENTER" in response.text
        assert "policy-form" in response.text
        assert "policy-max-steps" in response.text
        assert "policy-autonomous" in response.text
        assert "policy-preview-button" in response.text
        assert "Preview impact" in response.text
        assert "policy-preview" in response.text
        assert "Policy history" in response.text
        assert "policy-history" in response.text
        assert "face-reference" in response.text
        assert "face-paired-training" in response.text
        assert "face-verification-receipt" in response.text
        assert "face-file-evidence" in response.text
        assert "face-verification-cli" in response.text


def test_owner_console_assets_are_served() -> None:
    with TestClient(app) as client:
        assert client.get("/console-assets/console.css").status_code == 200
        script = client.get("/console-assets/console.js")
        assert script.status_code == 200
        assert "owner-dashboard" in script.text
        assert "Download report" in script.text
        assert "Total tokens" in script.text
        assert "Recorded cost" in script.text
        assert "Execution time" in script.text
        assert "result-step" in script.text
        assert "Promote to organization" in script.text
        assert "/promote" in script.text
        assert "Open Organization Board" in script.text
        assert "Revoke approval" in script.text
        assert "/revoke" in script.text
        assert "Governed project budget" in script.text
        assert "Circuit breaker stopped execution" in script.text
        assert "treasury-utilization" in script.text
        assert "allocated_budget_usd" in script.text
        assert "reserved_budget_usd" in script.text
        assert "renderAgentPerformance" in script.text
        assert "Cost / success" in script.text
        assert "Avg latency" in script.text
        assert "renderRuntimeStatus" in script.text
        assert "Runtime ready" in script.text
        assert "Live AI" in script.text
        assert "renderOperationalIncidents" in script.text
        assert "No active incidents" in script.text
        assert "incident-critical" in script.text
        assert "renderAuditLog" in script.text
        assert "/audit-log?limit=30" in script.text
        assert "No governance events yet." in script.text
        assert "downloadAuditEvidence" in script.text
        assert "/audit-export" in script.text
        assert "seldrune-governance-evidence-" in script.text
        assert "verifyAuditEvidence" in script.text
        assert "/audit-export/verify" in script.text
        assert "Evidence integrity verified" in script.text
        assert "renderGovernancePolicy" in script.text
        assert "/governance-policy" in script.text
        assert "Governance policy saved" in script.text
        assert "previewGovernancePolicy" in script.text
        assert "/governance-policy/preview" in script.text
        assert "Impact detected" in script.text
        assert "renderPolicyHistory" in script.text
        assert "/governance-policy/history?limit=10" in script.text
        assert "rollbackGovernancePolicy" in script.text
        assert "/governance-policy/rollback" in script.text
