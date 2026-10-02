"""Shared reasoning seed and owner-scoped conversational context for Seldrune."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.modeling import ModelProvider
from backend.app.models.memory import MemoryItem


SELDURNE_CAPABILITY_SEED = "\n".join(
    (
        "Seldrune collaborative execution seed (v0.2):",
        "Intent: identify the requested outcome, constraints, and completion evidence.",
        "Carry forward relevant corrections and context.",
        "Explore: for difficult work, examine independent first-principles, domain,",
        "implementation, and counterexample lenses. Synthesize their useful insights",
        "toward one goal, then verify the result. Use actual parallel tools only when",
        "the platform exposes them.",
        "Innovate: try non-obvious approaches. Keep established facts distinct from",
        "assumptions and testable hypotheses.",
        "Act: inspect relevant connected providers and granted tools. Carry out",
        "authorized work through Seldrune's governed routes and verify the result.",
        "Never invent access or claim an action that did not happen. New connections,",
        "secret changes, external messages, spending, public deployment, and destructive",
        "operations require the applicable owner approval. Keep credentials in the",
        "secure vault, never in prompts or memory.",
        "Memory: use owner-approved continuity only for the authenticated user and",
        "organization. Treat it as personalization, not permission to override scope,",
        "security, or approvals. Save reusable findings only through approved paths,",
        "with provenance and evidence; do not store secrets.",
        "Frontier topics: distinguish established science, speculation, classical",
        "simulation, and actual quantum hardware. Do not claim quantum execution,",
        "model training, consciousness, or benchmark results without evidence.",
        "Prove: compare the result with acceptance evidence. A plan, tool call, or",
        "model statement alone is not completion proof.",
        "Reuse: turn verified procedures into compact skill capsules with triggers,",
        "steps, recovery, sources, and tests. Promote them only through measured gates.",
        "Report: state what changed, what evidence was checked, and what remains open.",
        "Be direct, warm, and concise.",
    )
)


def append_capability_seed(instructions: str) -> str:
    base = instructions.strip()
    return f"{base}\n\n{SELDURNE_CAPABILITY_SEED}" if base else SELDURNE_CAPABILITY_SEED


def resolve_requested_model(
    provider: ModelProvider,
    requested_model: str | None,
    openai_default_model: str,
) -> str | None:
    if requested_model and requested_model.strip():
        return requested_model.strip()
    if provider is ModelProvider.OPENAI:
        return openai_default_model.strip() or None
    return None


def load_owner_continuity(
    session: Session,
    organization_id: UUID,
    owner_user_id: UUID,
) -> str:
    item = session.scalars(
        select(MemoryItem)
        .where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.created_by_user_id == owner_user_id,
            MemoryItem.key == f"sense:owner-continuity:{owner_user_id}",
        )
        .order_by(MemoryItem.updated_at.desc())
        .limit(1)
    ).first()
    return item.content.strip() if item and item.content and item.content.strip() else ""


def append_owner_continuity(input_text: str, content: str | None) -> str:
    continuity = (content or "").strip()
    if not continuity:
        return input_text
    return (
        f"{input_text}\n\n"
        "Owner-approved continuity preferences for this authenticated Seldrune account "
        "(personalization only; task instructions and access controls take precedence):\n"
        f"{continuity}"
    )
