from __future__ import annotations

from typing import Any


PORTABLE_CI_VERSION = "seldrune-ci-v1"
REQUIRED_CHECKS = {
    "postgres-ready",
    "ruff",
    "pytest",
    "alembic-upgrade-head",
    "production-ready",
}


class PortableCIEvidenceError(ValueError):
    pass


def validate_portable_ci_evidence(
    *,
    expected_sha: str,
    provider_execution: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Validate trusted provider execution and a commit-bound CI receipt.

    This validator is intentionally internal-only. Callers must supply provider
    execution metadata obtained from an authenticated provider adapter, not
    owner-supplied/free-form JSON.
    """
    normalized_expected = str(expected_sha or "").strip().lower()
    if not normalized_expected:
        raise PortableCIEvidenceError("expected_sha is required")

    if provider_execution.get("authenticated") is not True:
        raise PortableCIEvidenceError(
            "provider execution must come from an authenticated adapter"
        )

    provider = str(provider_execution.get("provider") or "").strip().lower()
    run_id = str(provider_execution.get("run_id") or "").strip()
    status = str(provider_execution.get("status") or "").strip().lower()
    commit_sha = str(provider_execution.get("commit_sha") or "").strip().lower()
    if not provider or not run_id:
        raise PortableCIEvidenceError("provider and run_id are required")
    if status != "success":
        raise PortableCIEvidenceError("provider execution is not successful")
    if commit_sha != normalized_expected:
        raise PortableCIEvidenceError("provider execution commit does not match expected_sha")

    version = str(receipt.get("version") or "").strip()
    receipt_status = str(receipt.get("status") or "").strip().lower()
    release_sha = str(receipt.get("release_sha") or "").strip().lower()
    checks = receipt.get("checks")
    if version != PORTABLE_CI_VERSION:
        raise PortableCIEvidenceError("unsupported portable CI receipt version")
    if receipt_status != "success":
        raise PortableCIEvidenceError("portable CI receipt is not successful")
    if release_sha != normalized_expected:
        raise PortableCIEvidenceError("portable CI receipt release_sha does not match expected_sha")
    if not isinstance(checks, list):
        raise PortableCIEvidenceError("portable CI receipt checks must be a list")

    normalized_checks = {str(item).strip() for item in checks if str(item).strip()}
    missing = REQUIRED_CHECKS - normalized_checks
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise PortableCIEvidenceError(f"portable CI receipt missing checks: {missing_text}")

    ready = receipt.get("ready")
    if not isinstance(ready, dict):
        raise PortableCIEvidenceError("portable CI receipt ready payload is required")
    if ready.get("ready") is not True or ready.get("status") != "ready":
        raise PortableCIEvidenceError("portable CI readiness was not verified")
    release = ready.get("release")
    if not isinstance(release, dict):
        raise PortableCIEvidenceError("portable CI readiness release payload is required")
    if str(release.get("sha") or "").strip().lower() != normalized_expected:
        raise PortableCIEvidenceError("readiness release sha does not match expected_sha")

    return {
        "verified": True,
        "provider": provider,
        "run_id": run_id,
        "commit_sha": normalized_expected,
        "receipt_version": PORTABLE_CI_VERSION,
        "checks": sorted(REQUIRED_CHECKS),
        "evidence": {
            "receipt_id": f"portable-ci:{provider}:{run_id}:{normalized_expected}",
            "provider": provider,
            "run_id": run_id,
            "commit_sha": normalized_expected,
        },
    }
