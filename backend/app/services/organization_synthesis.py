from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OrganizationUnitSpec:
    name: str
    slug: str
    capabilities: tuple[str, ...]
    purpose: str


_BASE_UNITS = (
    OrganizationUnitSpec(
        "Research",
        "research",
        ("research",),
        "Discover evidence, constraints, and unknowns.",
    ),
    OrganizationUnitSpec(
        "Strategy & Analysis",
        "strategy-analysis",
        ("analysis",),
        "Evaluate options, risks, economics, and outcomes.",
    ),
    OrganizationUnitSpec(
        "Architecture",
        "architecture",
        ("architecture",),
        "Design the organization, systems, controls, and interfaces.",
    ),
    OrganizationUnitSpec(
        "Engineering",
        "engineering",
        ("engineering",),
        "Build verified technical artifacts and capabilities.",
    ),
    OrganizationUnitSpec(
        "Validation",
        "validation",
        ("validation",),
        "Independently test evidence, quality, safety, and acceptance criteria.",
    ),
)

_DOMAIN_HINTS = {
    "software": ("app", "api", "code", "software", "website", "platform", "system"),
    "automation": ("automation", "workflow", "agent", "integrat"),
    "healthcare": ("healthcare", "medical", "rcm", "billing", "denial", "patient"),
    "business": ("business", "company", "startup", "client", "vendor", "investor"),
    "talent": ("hire", "hiring", "recruit", "manpower", "workforce", "talent"),
    "growth": ("sales", "marketing", "lead", "customer", "growth"),
    "infrastructure": (
        "cloud", "deploy", "gpu", "server", "database", "infrastructure"
    ),
    "creative-game": ("game", "3d", "animation", "creative", "unreal", "unity"),
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80]


def infer_domain_factories(objective: str) -> list[str]:
    lowered = objective.lower()
    return [
        name
        for name, hints in _DOMAIN_HINTS.items()
        if any(hint in lowered for hint in hints)
    ]


def synthesize_organization(objective: str) -> dict:
    """Create a deterministic, auditable organization blueprint for an objective."""
    objective = objective.strip()
    if not objective:
        raise ValueError("Objective is required")
    domains = infer_domain_factories(objective)
    units = [
        {
            "name": unit.name,
            "slug": unit.slug,
            "capabilities": list(unit.capabilities),
            "purpose": unit.purpose,
        }
        for unit in _BASE_UNITS
    ]
    for domain in domains:
        units.append(
            {
                "name": f"{domain.replace('-', ' ').title()} Factory",
                "slug": f"factory-{_slug(domain)}",
                "capabilities": [
                    "research",
                    "analysis",
                    "architecture",
                    "engineering",
                    "validation",
                ],
                "purpose": (
                    f"Compose domain-specialist work for the {domain} requirements "
                    "of the objective."
                ),
            }
        )
    return {
        "version": "universal-org-v1",
        "objective": objective,
        "mode": "deterministic-fallback",
        "domain_factories": domains,
        "units": units,
        "principles": {
            "dynamic_structure": True,
            "independent_validation": True,
            "unknown_capabilities_fail_closed": True,
            "consequential_actions_require_approval": True,
        },
    }
