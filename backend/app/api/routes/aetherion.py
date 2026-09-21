"""Aetherion experimental runtime and Reality Compiler APIs."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.aetherion.evidence_api import build_evidence_payload
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.reality_api import (
    build_demo_reality_payload,
    build_reality_payload,
)
from services.aetherion.reality_compiler import InventionCandidate, RealityObjective

router = APIRouter(prefix="/aetherion", tags=["aetherion"])


class RealityObjectiveRequest(BaseModel):
    objective_id: str
    statement: str
    constraints: tuple[str, ...]
    success_metrics: tuple[str, ...]


class RealityCandidateRequest(BaseModel):
    candidate_id: str
    title: str
    principle: str
    addressed_constraints: tuple[str, ...]
    prototype_steps: tuple[str, ...]
    feasibility: float
    impact: float
    novelty: float
    readiness: float
    risk: float

    def to_domain(self) -> InventionCandidate:
        return InventionCandidate(
            candidate_id=self.candidate_id,
            title=self.title,
            principle=self.principle,
            addressed_constraints=self.addressed_constraints,
            prototype_steps=self.prototype_steps,
            feasibility=self.feasibility,
            impact=self.impact,
            novelty=self.novelty,
            readiness=self.readiness,
            risk=self.risk,
        )


class RealityCompileRequest(BaseModel):
    objective: RealityObjectiveRequest
    candidates: tuple[RealityCandidateRequest, ...]


def _probe_program() -> QIRProgram:
    return QIRProgram(
        (
            QIROp("a", QIROpcode.CONST, value=2),
            QIROp("b", QIROpcode.CONST, value=3),
            QIROp("out", QIROpcode.ADD, ("a", "b")),
        ),
        "out",
    )


@router.get("/evidence")
def evidence() -> dict[str, object]:
    return build_evidence_payload(_probe_program())


@router.get("/reality-compiler")
def reality_compiler_demo() -> dict[str, object]:
    return build_demo_reality_payload()


@router.post("/reality-compiler/compile")
def reality_compiler_compile(request: RealityCompileRequest) -> dict[str, object]:
    objective = RealityObjective(
        objective_id=request.objective.objective_id,
        statement=request.objective.statement,
        constraints=request.objective.constraints,
        success_metrics=request.objective.success_metrics,
    )
    return build_reality_payload(
        objective,
        tuple(candidate.to_domain() for candidate in request.candidates),
    )
