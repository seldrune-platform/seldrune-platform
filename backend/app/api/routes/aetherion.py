"""Aetherion experimental runtime and Reality Compiler APIs."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.aetherion.evidence_api import build_evidence_payload
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.reality_api import (
    build_demo_reality_payload,
    build_demo_twin_payload,
    build_reality_payload,
    build_twin_payload,
)
from services.aetherion.reality_compiler import InventionCandidate, RealityObjective
from services.aetherion.reality_twin import (
    CausalLink,
    Guardrail,
    Intervention,
    TwinScenario,
    TwinVariable,
)

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


class TwinVariableRequest(BaseModel):
    name: str
    baseline: float
    lower_bound: float
    upper_bound: float

    def to_domain(self) -> TwinVariable:
        return TwinVariable(
            self.name,
            self.baseline,
            self.lower_bound,
            self.upper_bound,
        )


class CausalLinkRequest(BaseModel):
    source: str
    target: str
    coefficient: float

    def to_domain(self) -> CausalLink:
        return CausalLink(self.source, self.target, self.coefficient)


class InterventionRequest(BaseModel):
    variable: str
    delta: float

    def to_domain(self) -> Intervention:
        return Intervention(self.variable, self.delta)


class GuardrailRequest(BaseModel):
    variable: str
    lower_bound: float
    upper_bound: float

    def to_domain(self) -> Guardrail:
        return Guardrail(self.variable, self.lower_bound, self.upper_bound)


class TwinScenarioRequest(BaseModel):
    scenario_id: str
    outcome_variable: str
    steps: int
    interventions: tuple[InterventionRequest, ...]
    guardrails: tuple[GuardrailRequest, ...] = ()
    assumptions: tuple[str, ...] = ()

    def to_domain(self) -> TwinScenario:
        return TwinScenario(
            scenario_id=self.scenario_id,
            outcome_variable=self.outcome_variable,
            steps=self.steps,
            interventions=tuple(item.to_domain() for item in self.interventions),
            guardrails=tuple(item.to_domain() for item in self.guardrails),
            assumptions=self.assumptions,
        )


class TwinSimulationRequest(BaseModel):
    variables: tuple[TwinVariableRequest, ...]
    links: tuple[CausalLinkRequest, ...]
    scenario: TwinScenarioRequest


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


@router.get("/reality-compiler/digital-twin")
def reality_twin_demo() -> dict[str, object]:
    return build_demo_twin_payload()


@router.post("/reality-compiler/simulate")
def reality_twin_simulate(request: TwinSimulationRequest) -> dict[str, object]:
    return build_twin_payload(
        tuple(item.to_domain() for item in request.variables),
        tuple(item.to_domain() for item in request.links),
        request.scenario.to_domain(),
    )
