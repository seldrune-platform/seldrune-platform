from backend.app.services.executive_decision_advisory import decision_advisory
from tests.test_autonomous_execution import register_owner
from tests.test_executive_brief import _blocked_project, _project_priority
from tests.test_executive_strategy_review import _approve_and_execute

pytest_plugins = ["tests.test_autonomous_execution"]


def _score(
    decision: str,
    mode: str,
    *,
    attempts: int,
    resolutions: int,
    rate: float,
    strength: str,
) -> dict:
    return {
        "family": "blocked-project",
        "decision": decision,
        "effective_mode": mode,
        "attempts": attempts,
        "execution_succeeded": attempts,
        "resolution_associations": resolutions,
        "persisted_after_success": attempts - resolutions,
        "unsuccessful_attempts": 0,
        "resolution_rate": rate,
        "evidence_strength": strength,
        "causal_claim": False,
    }


def _priority_with_evidence(keep: dict, use: dict) -> dict:
    return {
        "key": "blocked-project:example",
        "strategy": {
            "mode": "reuse",
            "recommendation": {"recommended_mode": "baseline"},
        },
        "strategy_review_outcomes": {
            "family": "blocked-project",
            "total_reviewed_attempts": keep["attempts"] + use["attempts"],
            "resolution_associations": (
                keep["resolution_associations"] + use["resolution_associations"]
            ),
            "decision_evidence": {
                "keep_selected": keep,
                "use_recommended": use,
            },
            "causal_claim": False,
        },
    }


def test_decision_advisory_requires_medium_review_evidence() -> None:
    keep = _score(
        "keep_selected",
        "reuse",
        attempts=0,
        resolutions=0,
        rate=0.0,
        strength="none",
    )
    use = _score(
        "use_recommended",
        "baseline",
        attempts=1,
        resolutions=1,
        rate=1.0,
        strength="low",
    )
    advisory = decision_advisory(_priority_with_evidence(keep, use))
    assert advisory["active"] is True
    assert advisory["signal"] == "insufficient_evidence"
    assert advisory["basis"] == "insufficient_review_outcome_evidence"
    assert advisory["auto_applied"] is False
    assert advisory["owner_decision_required"] is True
    assert advisory["causal_claim"] is False


def test_decision_advisory_surfaces_supported_recommended_choice() -> None:
    keep = _score(
        "keep_selected",
        "reuse",
        attempts=0,
        resolutions=0,
        rate=0.0,
        strength="none",
    )
    use = _score(
        "use_recommended",
        "baseline",
        attempts=2,
        resolutions=2,
        rate=1.0,
        strength="medium",
    )
    advisory = decision_advisory(_priority_with_evidence(keep, use))
    assert advisory["signal"] == "use_recommended"
    assert advisory["confidence"] == "medium"
    assert advisory["resolution_rate_delta"] == 1.0
    assert advisory["basis"] == "reviewed_recommended_choice_supported"
    assert advisory["auto_applied"] is False
    assert advisory["causal_claim"] is False


def test_decision_advisory_stays_mixed_when_rates_are_close() -> None:
    keep = _score(
        "keep_selected",
        "reuse",
        attempts=2,
        resolutions=1,
        rate=0.5,
        strength="medium",
    )
    use = _score(
        "use_recommended",
        "baseline",
        attempts=2,
        resolutions=1,
        rate=0.6,
        strength="medium",
    )
    advisory = decision_advisory(_priority_with_evidence(keep, use))
    assert advisory["signal"] == "mixed"
    assert advisory["basis"] == "review_outcomes_not_materially_different"
    assert advisory["confidence"] == "medium"
    assert advisory["auto_applied"] is False


def _execute_priority(client, base: str, headers: dict[str, str], priority: dict) -> None:
    created = client.post(
        f"{base}/executive-brief/actions/{priority['key']}",
        headers=headers,
    )
    assert created.status_code == 201
    _approve_and_execute(client, base, headers, created.json()["id"])


def _resolve_project(client, base: str, headers: dict[str, str], project_id: str) -> None:
    resolved = client.patch(
        f"{base}/projects/{project_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert resolved.status_code == 200


def _review_use_recommended(client, base: str, headers: dict[str, str], priority: dict) -> None:
    response = client.post(
        f"{base}/executive-brief/strategy-reviews/{priority['key']}",
        headers=headers,
        json={
            "decision": "use_recommended",
            "reason": "Use the stronger historical comparative evidence for this attempt.",
        },
    )
    assert response.status_code == 200
    assert response.json()["effective_mode"] == "baseline"


def test_review_outcome_history_surfaces_directional_owner_advisory(client) -> None:
    token, organization_id = register_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/organizations/{organization_id}"

    first = _blocked_project(
        client,
        base,
        headers,
        name="Advisory Evidence Alpha",
        slug="advisory-evidence-alpha",
    )
    first_priority = _project_priority(client, base, headers, first["id"])
    _execute_priority(client, base, headers, first_priority)

    second = _blocked_project(
        client,
        base,
        headers,
        name="Advisory Evidence Beta",
        slug="advisory-evidence-beta",
    )
    second_priority = _project_priority(client, base, headers, second["id"])
    _execute_priority(client, base, headers, second_priority)
    _resolve_project(client, base, headers, second["id"])

    reviewed_projects: list[dict] = []
    for index, suffix in enumerate(("Gamma", "Delta"), start=1):
        project = _blocked_project(
            client,
            base,
            headers,
            name=f"Advisory Reviewed {suffix}",
            slug=f"advisory-reviewed-{index}",
        )
        priority = _project_priority(client, base, headers, project["id"])
        assert priority["strategy"]["mode"] == "reuse"
        assert priority["strategy"]["recommendation"]["recommended_mode"] == "baseline"
        _review_use_recommended(client, base, headers, priority)
        refreshed = _project_priority(client, base, headers, project["id"])
        _execute_priority(client, base, headers, refreshed)
        _resolve_project(client, base, headers, project["id"])
        reviewed_projects.append(project)

    future = _blocked_project(
        client,
        base,
        headers,
        name="Advisory Decision Epsilon",
        slug="advisory-decision-epsilon",
    )
    priority = _project_priority(client, base, headers, future["id"])
    advisory = priority["strategy_decision_advisory"]
    assert advisory["active"] is True
    assert advisory["signal"] == "use_recommended"
    assert advisory["basis"] == "reviewed_recommended_choice_supported"
    assert advisory["confidence"] == "medium"
    assert advisory["recommended_mode"] == "baseline"
    assert advisory["use_recommended_evidence"]["attempts"] == 2
    assert advisory["use_recommended_evidence"]["resolution_associations"] == 2
    assert advisory["use_recommended_evidence"]["resolution_rate"] == 1.0
    assert advisory["keep_selected_evidence"]["attempts"] == 0
    assert advisory["owner_decision_required"] is True
    assert advisory["auto_applied"] is False
    assert advisory["causal_claim"] is False

    brief = client.get(f"{base}/executive-brief", headers=headers)
    assert brief.status_code == 200
    summary = brief.json()["strategy_review_outcomes"]
    assert summary["active_advisories"] >= 1
    assert summary["directional_advisories"] >= 1
