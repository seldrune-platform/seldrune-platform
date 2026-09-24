from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hosted_ci_providers_share_portable_verifier() -> None:
    circle = (ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
    github = (
        ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    assert "bash scripts/ci_verify.sh" in circle
    assert "bash scripts/ci_verify.sh" in github
    assert "seldrune-ci-receipt.json" in circle
    assert "seldrune-ci-receipt" in github


def test_portable_ci_verifier_covers_required_evidence_gates() -> None:
    script = (ROOT / "scripts" / "ci_verify.sh").read_text(encoding="utf-8")

    required_commands = [
        "ruff check .",
        "pytest -q",
        "alembic upgrade head",
        "uvicorn backend.app.main:app",
    ]
    for command in required_commands:
        assert command in script

    required_receipt_checks = [
        '"postgres-ready"',
        '"ruff"',
        '"pytest"',
        '"alembic-upgrade-head"',
        '"production-ready"',
    ]
    for check in required_receipt_checks:
        assert check in script

    assert "SELDRUNE_CI_RELEASE_SHA is required" in script
    assert '"release_sha": os.environ["SELDRUNE_CI_RELEASE_SHA"]' in script
