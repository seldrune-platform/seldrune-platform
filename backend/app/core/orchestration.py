from enum import StrEnum
from typing import Any, NamedTuple


class OrchestrationStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PlannedStep(NamedTuple):
    title: str
    objective: str
    required_capabilities: list[str]
    priority: int = 0
    requires_approval: bool = False
    tool_slug: str | None = None
    tool_input: dict[str, Any] | None = None


def build_default_plan(objective: str) -> list[PlannedStep]:
    """Create a deterministic baseline plan until the model gateway is connected."""
    normalized = objective.lower()
    steps = [
        PlannedStep(
            "Research the objective",
            f"Collect reliable evidence, constraints, and current solutions for: {objective}",
            ["research"],
            30,
        ),
        PlannedStep(
            "Analyze findings",
            f"Analyze the evidence, risks, economics, and opportunities for: {objective}",
            ["analysis"],
            20,
        ),
        PlannedStep(
            "Design the solution",
            f"Design a practical solution and execution architecture for: {objective}",
            ["architecture"],
            10,
        ),
    ]

    build_terms = {
        "app",
        "application",
        "automation",
        "build",
        "code",
        "create",
        "develop",
        "platform",
        "software",
        "system",
        "website",
    }
    if any(term in normalized for term in build_terms):
        steps.extend(
            [
                PlannedStep(
                    "Implement the solution",
                    f"Build the approved solution for: {objective}",
                    ["engineering"],
                    10,
                ),
                PlannedStep(
                    "Validate the solution",
                    f"Test quality, correctness, and acceptance criteria for: {objective}",
                    ["validation"],
                    0,
                ),
            ]
        )

    return steps
