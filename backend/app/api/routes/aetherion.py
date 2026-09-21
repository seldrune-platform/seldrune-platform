"""Aetherion experimental runtime and Reality Compiler APIs."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.aetherion.evidence_api import build_evidence_payload
from services.aetherion.qir import QIROp, QIROpcode, QIRProgram
from services.aetherion.reality_api import (
    build_calibration_payload,
    build_demo_lab_payload,
    build_demo_reality_payload,
    build_demo_twin_payload,
    build_reality_payload,
    build_twin_payload,
)
from services.aetherion.reality_compiler import InventionCandidate, RealityObjective
from services.aetherion.reality_lab import ExperimentProtocol, Measurement
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


class ExperimentProtocolRequest(BaseModel):
    protocol_id: str
    source_variable: str
    target_variable: str
    input_unit: str
    output_unit: str
    minimum_observations: int
    minimum_r_squared: float
    slope_lower_bound: float
    slope_upper_bound: float
    safety_notes: tuple[str, ...]

    def to_domain(self) -> ExperimentProtocol:
        return ExperimentProtocol(
            protocol_id=self.protocol_id,
            source_variable=self.source_variable,
            target_variable=self.target_variable,
            input_unit=self.input_unit,
            output_unit=self.output_unit,
            minimum_observations=self.minimum_observations,
            minimum_r_squared=self.minimum_r_squared,
            slope_lower_bound=self.slope_lower_bound,
            slope_upper_bound=self.slope_upper_bound,
            safety_notes=self.safety_notes,
        )


class MeasurementRequest(BaseModel):
    measurement_id: str
    input_value: float
    output_value: float
    evidence_sha256: str

    def to_domain(self) -> Measurement:
        return Measurement(
            self.measurement_id,
            self.input_value,
            self.output_value,
            self.evidence_sha256,
        )


class LabCalibrationRequest(BaseModel):
    protocol: ExperimentProtocolRequest
    measurements: tuple[MeasurementRequest, ...]


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


@router.get("/reality-compiler/reality-lab")
def reality_lab_demo() -> dict[str, object]:
    return build_demo_lab_payload()


@router.post("/reality-compiler/calibrate")
def reality_lab_calibrate(request: LabCalibrationRequest) -> dict[str, object]:
    return build_calibration_payload(
        request.protocol.to_domain(),
        tuple(item.to_domain() for item in request.measurements),
    )
