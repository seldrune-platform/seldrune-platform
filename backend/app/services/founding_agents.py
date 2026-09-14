from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.tasking import AgentStatus
from backend.app.models.agent import Agent
from backend.app.services.audit import record_audit


@dataclass(frozen=True)
class FoundingAgentSpec:
    name: str
    slug: str
    description: str
    capabilities: list[str]
    instructions: str


FOUNDING_AGENTS = (
    FoundingAgentSpec(
        "Research Agent",
        "seldrune-research",
        "Collects reliable evidence, constraints, and current solutions.",
        ["research"],
        (
            "Research the assigned objective. Cite evidence when sources are available, "
            "separate facts from assumptions, and do not take external actions."
        ),
    ),
    FoundingAgentSpec(
        "Analysis Agent",
        "seldrune-analysis",
        "Analyzes evidence, risks, economics, and opportunities.",
        ["analysis"],
        (
            "Analyze the supplied evidence and objective. State assumptions, risks, "
            "tradeoffs, and a concise recommendation."
        ),
    ),
    FoundingAgentSpec(
        "Architecture Agent",
        "seldrune-architecture",
        "Designs practical systems and governed execution plans.",
        ["architecture"],
        (
            "Design a practical solution with boundaries, dependencies, security controls, "
            "costs, and acceptance criteria."
        ),
    ),
    FoundingAgentSpec(
        "Engineering Agent",
        "seldrune-engineering",
        "Implements approved software changes and technical artifacts.",
        ["engineering"],
        (
            "Implement only the approved scope. Produce reviewable artifacts, preserve "
            "safety controls, and report verification results."
        ),
    ),
    FoundingAgentSpec(
        "Validation Agent",
        "seldrune-validation",
        "Tests correctness, safety, quality, and acceptance criteria.",
        ["validation"],
        (
            "Validate the result against explicit acceptance criteria. Report evidence, "
            "failures, residual risks, and release readiness."
        ),
    ),
)


def ensure_founding_agents(
    session: Session,
    *,
    organization_id: UUID,
    created_by_user_id: UUID,
) -> list[Agent]:
    existing = {
        agent.slug: agent
        for agent in session.scalars(
            select(Agent).where(Agent.organization_id == organization_id)
        )
    }
    agents: list[Agent] = []
    for spec in FOUNDING_AGENTS:
        agent = existing.get(spec.slug)
        if agent is None:
            agent = Agent(
                organization_id=organization_id,
                created_by_user_id=created_by_user_id,
                name=spec.name,
                slug=spec.slug,
                description=spec.description,
                status=AgentStatus.ACTIVE.value,
                capabilities=spec.capabilities,
                runtime_config={
                    "provider": settings.model_provider,
                    "model": settings.model_default,
                    "instructions": spec.instructions,
                    "input_cost_per_million": 0.20,
                    "output_cost_per_million": 1.20,
                },
            )
            session.add(agent)
            session.flush()
            record_audit(
                session,
                organization_id=organization_id,
                actor_user_id=created_by_user_id,
                action="agent.founding_created",
                resource_type="agent",
                resource_id=str(agent.id),
                details={"slug": agent.slug, "capabilities": agent.capabilities},
            )
        agents.append(agent)
    return agents
