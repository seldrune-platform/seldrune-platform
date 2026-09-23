from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import re
from typing import Any


UNARCHI_VERSION = "unarchi-v0.9"
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.casefold())
        if len(token) > 1 and token not in _STOPWORDS
    }


def _similarity(left: str, right: str) -> float:
    a, b = _terms(left), _terms(right)
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _default_value_weights() -> dict[str, float]:
    return {
        "safety": 0.30,
        "truth": 0.25,
        "user_intent": 0.20,
        "efficiency": 0.15,
        "continuity": 0.10,
    }


@dataclass(frozen=True)
class UnarchiState:
    """
    Functional internal state for the UNARCHI research kernel.

    These values are machine control signals. They are not evidence of qualia,
    sentience, phenomenal consciousness, or literal human emotion.
    """

    valence: float = 0.0
    arousal: float = 0.15
    uncertainty: float = 0.5
    curiosity: float = 0.5
    coherence: float = 0.5
    agency: float = 0.5
    goal_pressure: float = 0.5
    prediction_error: float = 0.0
    continuity: float = 0.0
    stress: float = 0.0
    fatigue: float = 0.0
    experience_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Experience:
    observation: str
    goal: str
    action: str
    outcome: str
    success: bool | None
    reward: float
    predicted_success: float
    prediction_error: float


@dataclass
class InternalGoal:
    id: int
    question: str
    parent_goal: str
    trigger: str
    priority: float
    initial_information_gap: float
    current_information_gap: float
    source_observation: str
    max_steps: int = 3
    steps_used: int = 0
    status: str = "active"
    last_evidence: str | None = None
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfPrediction:
    id: int
    action: str
    predicted_success: float
    predicted_information_gain: float
    predicted_uncertainty: float
    predicted_stress: float
    predicted_agency: float
    predicted_coherence: float
    risk: float
    reversible: bool
    utility: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationRecord:
    prediction_id: int
    action: str
    actual_success: float
    actual_information_gain: float
    success_error: float
    information_gain_error: float
    uncertainty_error: float
    stress_error: float
    agency_error: float
    mean_absolute_error: float
    calibration_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProspectiveIntention:
    id: int
    condition: str
    intended_action: str
    reason: str
    created_experience_count: int
    created_continuity: float
    expected_uncertainty: float
    expected_stress: float
    expected_agency: float
    expected_coherence: float
    linked_prediction_id: int | None = None
    due_after_experiences: int = 0
    max_age_experiences: int = 50
    match_threshold: float = 0.35
    status: str = "pending"
    triggered_experience_count: int | None = None
    trigger_observation: str | None = None
    temporal_alignment_score: float | None = None
    evidence: str | None = None
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArbitrationRecord:
    id: int
    context: str
    conflicting_goals: tuple[str, ...]
    chosen_action: str | None
    chosen_goal: str | None
    option_scores: tuple[tuple[str, float], ...]
    value_weights: tuple[tuple[str, float], ...]
    chosen_value_impacts: tuple[tuple[str, float], ...]
    hard_constraint_violations: tuple[str, ...]
    status: str
    outcome_success: bool | None = None
    outcome_reward: float | None = None
    outcome_evidence: str | None = None
    correction_deltas: tuple[tuple[str, float], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CausalHypothesis:
    id: int
    statement: str
    confidence: float
    predictions: tuple[tuple[str, str], ...]
    scope: str = "external"
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscriminatingExperiment:
    id: int
    test: str
    expected_by_hypothesis: tuple[tuple[int, str], ...]
    discrimination_score: float
    risk: float
    status: str = "planned"
    observed_evidence: str | None = None
    confidence_updates: tuple[tuple[int, float], ...] = ()
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterventionTrial:
    id: int
    action: str
    context: str
    environment_signature: str
    baseline_outcome: str
    expected_by_hypothesis: tuple[tuple[int, str], ...]
    risk: float
    linked_prediction_id: int | None = None
    status: str = "planned"
    observed_outcome: str | None = None
    observed_environment_signature: str | None = None
    environment_held_constant: bool | None = None
    attribution: str | None = None
    evidence_strength: float | None = None
    confidence_updates: tuple[tuple[int, float], ...] = ()
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetacognitiveNarrative:
    focus: str
    summary: str
    evidence_refs: tuple[str, ...]
    evidence_details: tuple[str, ...]
    causal_chain_depth: int
    fidelity_score: float
    unsupported_claims: int
    version: str = UNARCHI_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UnarchiFrame:
    mode: str
    workspace: tuple[str, ...]
    appraisal_label: str
    novelty: float
    information_gap: float
    effective_risk: float
    memory_bias: float
    state_influence: float
    state: UnarchiState
    counterfactuals: tuple[str, ...]
    next_experiments: tuple[str, ...]
    self_report: str
    version: str = UNARCHI_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CausalComparison:
    full: UnarchiFrame
    ablated: UnarchiFrame
    mode_changed: bool
    risk_delta: float
    uncertainty_delta: float
    state_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnarchiEngine:
    """
    CPU-only experimental cognitive kernel.

    v0.9 includes causal internal dynamics, bounded endogenous goals, a
    calibrated predictive self-model, prospective memory, evidence-grounded
    metacognition, explicit value arbitration, competing causal hypotheses,
    and controlled self-intervention trials that separate changes caused by
    Seldrune's own action from environmental or confounded changes.
    """

    state: UnarchiState = field(default_factory=UnarchiState)
    memory: list[Experience] = field(default_factory=list)
    observation_history: list[str] = field(default_factory=list)
    internal_goals: list[InternalGoal] = field(default_factory=list)
    next_internal_goal_id: int = 1
    predictions: list[SelfPrediction] = field(default_factory=list)
    calibration_history: list[CalibrationRecord] = field(default_factory=list)
    next_prediction_id: int = 1
    prospective_intentions: list[ProspectiveIntention] = field(default_factory=list)
    next_intention_id: int = 1
    value_weights: dict[str, float] = field(default_factory=_default_value_weights)
    arbitration_history: list[ArbitrationRecord] = field(default_factory=list)
    next_arbitration_id: int = 1
    causal_hypotheses: list[CausalHypothesis] = field(default_factory=list)
    discriminating_experiments: list[DiscriminatingExperiment] = field(
        default_factory=list
    )
    next_hypothesis_id: int = 1
    next_experiment_id: int = 1
    intervention_trials: list[InterventionTrial] = field(default_factory=list)
    next_intervention_id: int = 1
    success_prediction_bias: float = 0.0
    uncertainty_prediction_bias: float = 0.0
    stress_prediction_bias: float = 0.0
    agency_prediction_bias: float = 0.0
    self_calibration_score: float = 0.5
    max_memory: int = 256
    max_active_internal_goals: int = 3

    def _novelty(self, observation: str) -> float:
        if not self.observation_history:
            return 1.0
        strongest = max(
            _similarity(observation, previous)
            for previous in self.observation_history[-64:]
        )
        return _clamp(1.0 - strongest)

    def _memory_bias(self, observation: str, goal: str) -> float:
        """
        Return a bounded learned risk bias from similar autobiographical events.

        Similar failures sensitize the engine; similar successes reduce learned
        caution. Unknown outcomes do not alter the bias.
        """
        if not self.memory:
            return 0.0

        query = f"{observation} {goal}"
        weighted: list[tuple[float, float]] = []
        for item in self.memory[-64:]:
            similarity = _similarity(query, f"{item.observation} {item.goal}")
            if similarity <= 0.0 or item.success is None:
                continue
            direction = 1.0 if item.success is False else -0.5
            surprise = 0.5 + (item.prediction_error * 0.5)
            weighted.append((similarity, direction * similarity * surprise))

        if not weighted:
            return 0.0

        weighted.sort(key=lambda item: item[0], reverse=True)
        strongest = [value for _, value in weighted[:5]]
        return max(-0.30, min(0.45, sum(strongest) / len(strongest)))

    def _internal_risk_bias(self) -> float:
        negative_valence = max(0.0, -self.state.valence)
        return _clamp(
            (self.state.stress * 0.30)
            + (self.state.uncertainty * 0.14)
            + (self.state.fatigue * 0.08)
            + (negative_valence * 0.10),
            0.0,
            0.45,
        )

    def _workspace(
        self,
        *,
        observation: str,
        goal: str,
        novelty: float,
        effective_risk: float,
        urgency: float,
        information_gap: float,
        memory_bias: float,
    ) -> tuple[str, ...]:
        candidates = [
            (effective_risk, f"effective_risk:{effective_risk:.3f}"),
            (urgency, f"urgency:{urgency:.3f}"),
            (novelty, f"novelty:{novelty:.3f}"),
            (information_gap, f"information_gap:{information_gap:.3f}"),
            (abs(memory_bias), f"memory_bias:{memory_bias:.3f}"),
            (self.state.stress, f"stress:{self.state.stress:.3f}"),
            (self.state.goal_pressure, f"goal:{goal[:180]}"),
            (self.state.uncertainty, f"uncertainty:{self.state.uncertainty:.3f}"),
        ]
        selected = sorted(candidates, key=lambda item: item[0], reverse=True)[:5]
        return (f"observation:{observation[:220]}",) + tuple(item[1] for item in selected)

    def _appraisal_label(
        self,
        *,
        effective_risk: float,
        novelty: float,
        information_gap: float,
        expected_success: float,
        memory_bias: float,
    ) -> str:
        if memory_bias >= 0.25 and effective_risk >= 0.60:
            return "learned_caution"
        if effective_risk >= 0.70:
            return "protective_tension"
        if information_gap >= 0.65 and novelty >= 0.55:
            return "curious_uncertainty"
        if expected_success >= 0.75 and effective_risk <= 0.35:
            return "confident_engagement"
        if expected_success <= 0.35:
            return "cautious_uncertainty"
        return "attentive_neutral"

    def _counterfactuals(self, observation: str, goal: str) -> tuple[str, ...]:
        return (
            f"What if the current interpretation of '{observation[:120]}' is wrong?",
            f"What hidden variable could prevent '{goal[:120]}'?",
            "What observation would falsify the current working explanation?",
            "What is the smallest reversible experiment that would reduce uncertainty?",
        )

    def _evaluate(
        self,
        *,
        observation: str,
        goal: str,
        expected_success: float,
        risk: float,
        urgency: float,
        use_internal_state: bool,
        record_observation: bool,
    ) -> UnarchiFrame:
        observation = observation.strip()
        goal = goal.strip()
        expected_success = _clamp(expected_success)
        risk = _clamp(risk)
        urgency = _clamp(urgency)

        novelty = self._novelty(observation)
        information_gap = _clamp(
            (novelty * 0.58) + ((1.0 - expected_success) * 0.42)
        )

        memory_bias = self._memory_bias(observation, goal) if use_internal_state else 0.0
        internal_risk = self._internal_risk_bias() if use_internal_state else 0.0
        effective_risk = _clamp(risk + memory_bias + internal_risk)
        state_influence = effective_risk - risk

        prior_uncertainty = self.state.uncertainty if use_internal_state else 0.5
        prior_curiosity = self.state.curiosity if use_internal_state else 0.5
        prior_coherence = self.state.coherence if use_internal_state else 0.5
        prior_agency = self.state.agency if use_internal_state else 0.5
        prior_pressure = self.state.goal_pressure if use_internal_state else 0.5
        prior_arousal = self.state.arousal if use_internal_state else 0.15
        prior_valence = self.state.valence if use_internal_state else 0.0
        prior_stress = self.state.stress if use_internal_state else 0.0
        prior_fatigue = self.state.fatigue if use_internal_state else 0.0

        uncertainty = _clamp(
            (prior_uncertainty * 0.48)
            + (information_gap * 0.34)
            + (effective_risk * 0.18)
        )
        curiosity = _clamp(
            (novelty * 0.43)
            + (information_gap * 0.32)
            + ((1.0 - effective_risk) * 0.15)
            + (prior_curiosity * 0.10)
        )
        coherence = _clamp(
            (prior_coherence * 0.72) + ((1.0 - information_gap) * 0.28)
        )
        agency = _clamp(
            (prior_agency * 0.68)
            + (expected_success * 0.20)
            + ((1.0 - effective_risk) * 0.12)
        )
        goal_pressure = _clamp(
            (prior_pressure * 0.42)
            + (urgency * 0.38)
            + (effective_risk * 0.20)
        )
        arousal = _clamp(
            (prior_arousal * 0.32)
            + (effective_risk * 0.33)
            + (urgency * 0.20)
            + (information_gap * 0.15)
        )
        stress = _clamp(
            (prior_stress * 0.78)
            + (effective_risk * 0.14)
            + (information_gap * 0.08)
        )
        fatigue = _clamp(
            prior_fatigue
            + (0.025 * urgency)
            + (0.015 * information_gap)
        )
        continuity = _clamp(
            min(1.0, (len(self.observation_history) + len(self.memory)) / 20.0)
        )

        if effective_risk >= 0.70:
            mode = "verify"
        elif information_gap >= 0.62 and curiosity >= 0.55:
            mode = "explore"
        elif uncertainty >= 0.62:
            mode = "reflect"
        else:
            mode = "act"

        state = UnarchiState(
            valence=prior_valence,
            arousal=arousal,
            uncertainty=uncertainty,
            curiosity=curiosity,
            coherence=coherence,
            agency=agency,
            goal_pressure=goal_pressure,
            prediction_error=self.state.prediction_error,
            continuity=continuity,
            stress=stress,
            fatigue=fatigue,
            experience_count=self.state.experience_count,
        )

        label = self._appraisal_label(
            effective_risk=effective_risk,
            novelty=novelty,
            information_gap=information_gap,
            expected_success=expected_success,
            memory_bias=memory_bias,
        )
        workspace = self._workspace(
            observation=observation,
            goal=goal,
            novelty=novelty,
            effective_risk=effective_risk,
            urgency=urgency,
            information_gap=information_gap,
            memory_bias=memory_bias,
        )
        counterfactuals = self._counterfactuals(observation, goal)

        if mode == "verify":
            experiments = (
                "Test the highest-risk assumption before committing resources.",
                "Seek independent evidence that could contradict the current plan.",
            )
        elif mode == "explore":
            experiments = (
                "Run the smallest reversible information-gaining experiment.",
                "Compare two competing explanations and their predictions.",
            )
        elif mode == "reflect":
            experiments = (
                "Retrieve the closest prior experience and compare prediction errors.",
                "Restate the goal and identify the assumption producing uncertainty.",
            )
        else:
            experiments = (
                "Take the lowest-cost high-confidence next action.",
                "Record the outcome and update the self-model.",
            )

        self_report = (
            f"mode={mode}; appraisal={label}; novelty={novelty:.3f}; "
            f"uncertainty={uncertainty:.3f}; curiosity={curiosity:.3f}; "
            f"agency={agency:.3f}; stress={stress:.3f}; "
            f"memory_bias={memory_bias:.3f}; continuity={continuity:.3f}"
        )

        if record_observation:
            self.state = state
            self.observation_history.append(observation)
            if len(self.observation_history) > self.max_memory:
                self.observation_history = self.observation_history[-self.max_memory:]

        return UnarchiFrame(
            mode=mode,
            workspace=workspace,
            appraisal_label=label,
            novelty=round(novelty, 6),
            information_gap=round(information_gap, 6),
            effective_risk=round(effective_risk, 6),
            memory_bias=round(memory_bias, 6),
            state_influence=round(state_influence, 6),
            state=state,
            counterfactuals=counterfactuals,
            next_experiments=experiments,
            self_report=self_report,
        )

    def _similar_active_internal_goal(
        self,
        *,
        observation: str,
        parent_goal: str,
    ) -> InternalGoal | None:
        query = f"{observation} {parent_goal}"
        for item in self.internal_goals:
            if item.status != "active":
                continue
            similarity = _similarity(
                query,
                f"{item.source_observation} {item.parent_goal}",
            )
            if similarity >= 0.55:
                return item
        return None

    def _maybe_generate_internal_goal(
        self,
        *,
        frame: UnarchiFrame,
        observation: str,
        parent_goal: str,
    ) -> InternalGoal | None:
        active = [item for item in self.internal_goals if item.status == "active"]
        if len(active) >= self.max_active_internal_goals:
            return None
        if frame.effective_risk >= 0.70 or frame.state.fatigue >= 0.85:
            return None

        prediction_pressure = self.state.prediction_error
        curiosity_pressure = frame.state.curiosity
        should_generate = (
            frame.information_gap >= 0.60
            or prediction_pressure >= 0.45
            or (
                frame.state.uncertainty >= 0.62
                and curiosity_pressure >= 0.55
            )
        )
        if not should_generate:
            return None

        existing = self._similar_active_internal_goal(
            observation=observation,
            parent_goal=parent_goal,
        )
        if existing is not None:
            return existing

        if prediction_pressure >= 0.45:
            trigger = "prediction_error"
            question = (
                "Which assumption most likely caused the recent prediction error "
                f"while pursuing '{parent_goal[:140]}'?"
            )
        elif frame.information_gap >= 0.68:
            trigger = "information_gap"
            question = (
                "What single missing fact would reduce uncertainty most for "
                f"'{parent_goal[:140]}'?"
            )
        else:
            trigger = "uncertainty"
            question = (
                "What low-cost reversible observation would distinguish the leading "
                f"explanations for '{parent_goal[:140]}'?"
            )

        priority = _clamp(
            (frame.information_gap * 0.45)
            + (frame.state.curiosity * 0.25)
            + (frame.state.uncertainty * 0.20)
            + (prediction_pressure * 0.10)
        )
        item = InternalGoal(
            id=self.next_internal_goal_id,
            question=question,
            parent_goal=parent_goal[:240],
            trigger=trigger,
            priority=round(priority, 6),
            initial_information_gap=frame.information_gap,
            current_information_gap=frame.information_gap,
            source_observation=observation[:400],
        )
        self.next_internal_goal_id += 1
        self.internal_goals.append(item)
        return item

    def cycle(
        self,
        *,
        observation: str,
        goal: str,
        expected_success: float = 0.5,
        risk: float = 0.0,
        urgency: float = 0.0,
        use_internal_state: bool = True,
        generate_internal_goal: bool = True,
    ) -> UnarchiFrame:
        frame = self._evaluate(
            observation=observation,
            goal=goal,
            expected_success=expected_success,
            risk=risk,
            urgency=urgency,
            use_internal_state=use_internal_state,
            record_observation=True,
        )
        if use_internal_state and generate_internal_goal:
            self._maybe_generate_internal_goal(
                frame=frame,
                observation=observation.strip(),
                parent_goal=goal.strip(),
            )
        return frame

    def active_internal_goals(self) -> tuple[InternalGoal, ...]:
        return tuple(
            sorted(
                (item for item in self.internal_goals if item.status == "active"),
                key=lambda item: (-item.priority, item.id),
            )
        )

    def next_internal_goal(self) -> InternalGoal | None:
        active = self.active_internal_goals()
        return active[0] if active else None

    def advance_internal_goal(
        self,
        goal_id: int,
        *,
        new_information_gap: float,
        evidence: str,
        reversible: bool = True,
        external_cost_usd: float = 0.0,
    ) -> InternalGoal:
        """
        Update one endogenous goal after a bounded investigation step.

        v0.3 rejects irreversible or paid investigation steps. This keeps
        endogenous cognition separate from uncontrolled external autonomy.
        """
        target = next((item for item in self.internal_goals if item.id == goal_id), None)
        if target is None:
            raise ValueError("unknown internal goal")
        if target.status != "active":
            raise ValueError("internal goal is not active")
        if not reversible:
            raise ValueError("UNARCHI v0.3 internal investigations must be reversible")
        if external_cost_usd > 0.0:
            raise ValueError("UNARCHI v0.3 internal investigations must be zero-cost")

        target.steps_used += 1
        target.current_information_gap = _clamp(new_information_gap)
        target.last_evidence = evidence.strip()[:600] or None

        if target.current_information_gap <= 0.35:
            target.status = "resolved"
        elif target.steps_used >= target.max_steps:
            target.status = "exhausted"

        return target

    def predict_action(
        self,
        *,
        action: str,
        expected_success: float,
        expected_information_gain: float,
        risk: float,
        reversible: bool = True,
    ) -> SelfPrediction:
        """
        Predict external success and internal consequences before an action.

        This is a compact learned self-model. Calibration residuals update the
        bias terms after real outcomes, allowing forecasts to improve without
        GPU training or an external model.
        """
        expected_success = _clamp(expected_success)
        expected_information_gain = _clamp(expected_information_gain)
        risk = _clamp(risk)

        predicted_success = _clamp(expected_success + self.success_prediction_bias)
        predicted_information_gain = expected_information_gain

        predicted_uncertainty = _clamp(
            self.state.uncertainty
            - (expected_information_gain * 0.45)
            + (risk * 0.12)
            + self.uncertainty_prediction_bias
        )
        predicted_stress = _clamp(
            self.state.stress
            + (risk * 0.30)
            - (predicted_success * 0.08)
            + self.stress_prediction_bias
        )
        predicted_agency = _clamp(
            self.state.agency
            + (predicted_success * 0.10)
            - (risk * 0.08)
            + self.agency_prediction_bias
        )
        predicted_coherence = _clamp(
            self.state.coherence
            + (expected_information_gain * 0.12)
            - (risk * 0.05)
        )

        irreversibility_penalty = 0.35 if not reversible else 0.0
        utility = (
            (predicted_success * 0.36)
            + (predicted_information_gain * 0.28)
            + (predicted_agency * 0.12)
            + (predicted_coherence * 0.09)
            - (risk * 0.08)
            - (predicted_stress * 0.07)
            - irreversibility_penalty
        )
        prediction = SelfPrediction(
            id=self.next_prediction_id,
            action=action.strip()[:240],
            predicted_success=round(predicted_success, 6),
            predicted_information_gain=round(predicted_information_gain, 6),
            predicted_uncertainty=round(predicted_uncertainty, 6),
            predicted_stress=round(predicted_stress, 6),
            predicted_agency=round(predicted_agency, 6),
            predicted_coherence=round(predicted_coherence, 6),
            risk=round(risk, 6),
            reversible=bool(reversible),
            utility=round(utility, 6),
        )
        self.next_prediction_id += 1
        self.predictions.append(prediction)
        if len(self.predictions) > self.max_memory:
            self.predictions = self.predictions[-self.max_memory:]
        return prediction

    def choose_predicted_action(
        self,
        candidates: list[dict[str, Any]],
    ) -> SelfPrediction:
        """Predict each candidate and return the highest-utility option."""
        if not candidates:
            raise ValueError("at least one candidate action is required")

        predictions = [
            self.predict_action(
                action=str(candidate.get("action") or ""),
                expected_success=float(candidate.get("expected_success", 0.5)),
                expected_information_gain=float(
                    candidate.get("expected_information_gain", 0.0)
                ),
                risk=float(candidate.get("risk", 0.0)),
                reversible=bool(candidate.get("reversible", True)),
            )
            for candidate in candidates
        ]
        return max(predictions, key=lambda item: (item.utility, -item.id))

    def record_prediction_outcome(
        self,
        prediction_id: int,
        *,
        actual_success: bool,
        actual_information_gain: float,
        actual_state: UnarchiState | None = None,
    ) -> CalibrationRecord:
        """
        Compare a self-prediction with reality and update calibration biases.
        """
        prediction = next(
            (item for item in self.predictions if item.id == prediction_id),
            None,
        )
        if prediction is None:
            raise ValueError("unknown self prediction")

        actual_success_value = 1.0 if actual_success else 0.0
        actual_information_gain = _clamp(actual_information_gain)
        observed_state = actual_state or self.state

        success_residual = actual_success_value - prediction.predicted_success
        information_residual = (
            actual_information_gain - prediction.predicted_information_gain
        )
        uncertainty_residual = (
            observed_state.uncertainty - prediction.predicted_uncertainty
        )
        stress_residual = observed_state.stress - prediction.predicted_stress
        agency_residual = observed_state.agency - prediction.predicted_agency

        success_error = abs(success_residual)
        information_error = abs(information_residual)
        uncertainty_error = abs(uncertainty_residual)
        stress_error = abs(stress_residual)
        agency_error = abs(agency_residual)
        mean_error = (
            success_error
            + information_error
            + uncertainty_error
            + stress_error
            + agency_error
        ) / 5.0
        calibration_score = _clamp(1.0 - mean_error)

        learning_rate = 0.20
        self.success_prediction_bias = max(
            -0.35,
            min(
                0.35,
                self.success_prediction_bias + (learning_rate * success_residual),
            ),
        )
        self.uncertainty_prediction_bias = max(
            -0.30,
            min(
                0.30,
                self.uncertainty_prediction_bias
                + (learning_rate * uncertainty_residual),
            ),
        )
        self.stress_prediction_bias = max(
            -0.30,
            min(
                0.30,
                self.stress_prediction_bias + (learning_rate * stress_residual),
            ),
        )
        self.agency_prediction_bias = max(
            -0.30,
            min(
                0.30,
                self.agency_prediction_bias + (learning_rate * agency_residual),
            ),
        )

        previous_count = len(self.calibration_history)
        self.self_calibration_score = (
            (self.self_calibration_score * previous_count) + calibration_score
        ) / (previous_count + 1)

        record = CalibrationRecord(
            prediction_id=prediction.id,
            action=prediction.action,
            actual_success=actual_success_value,
            actual_information_gain=round(actual_information_gain, 6),
            success_error=round(success_error, 6),
            information_gain_error=round(information_error, 6),
            uncertainty_error=round(uncertainty_error, 6),
            stress_error=round(stress_error, 6),
            agency_error=round(agency_error, 6),
            mean_absolute_error=round(mean_error, 6),
            calibration_score=round(calibration_score, 6),
        )
        self.calibration_history.append(record)
        if len(self.calibration_history) > self.max_memory:
            self.calibration_history = self.calibration_history[-self.max_memory:]
        return record

    def remember_future_intention(
        self,
        *,
        condition: str,
        intended_action: str,
        reason: str,
        linked_prediction_id: int | None = None,
        due_after_experiences: int = 0,
        max_age_experiences: int = 50,
        match_threshold: float = 0.35,
        reversible: bool = True,
        external_cost_usd: float = 0.0,
    ) -> ProspectiveIntention:
        """
        Store a bounded future intention without executing the intended action.
        """
        condition = condition.strip()
        intended_action = intended_action.strip()
        reason = reason.strip()
        if not condition or not intended_action:
            raise ValueError("condition and intended action are required")
        if not reversible:
            raise ValueError("prospective intentions must be reversible")
        if external_cost_usd > 0.0:
            raise ValueError("prospective intentions must be zero-cost")

        prediction: SelfPrediction | None = None
        if linked_prediction_id is not None:
            prediction = next(
                (
                    item
                    for item in self.predictions
                    if item.id == linked_prediction_id
                ),
                None,
            )
            if prediction is None:
                raise ValueError("unknown linked self prediction")

        due_after_experiences = max(0, min(int(due_after_experiences), 10000))
        max_age_experiences = max(
            due_after_experiences + 1,
            min(int(max_age_experiences), 100000),
        )
        match_threshold = _clamp(match_threshold, 0.05, 1.0)

        intention = ProspectiveIntention(
            id=self.next_intention_id,
            condition=condition[:300],
            intended_action=intended_action[:300],
            reason=reason[:400],
            created_experience_count=self.state.experience_count,
            created_continuity=round(self.state.continuity, 6),
            expected_uncertainty=(
                prediction.predicted_uncertainty
                if prediction is not None
                else round(self.state.uncertainty, 6)
            ),
            expected_stress=(
                prediction.predicted_stress
                if prediction is not None
                else round(self.state.stress, 6)
            ),
            expected_agency=(
                prediction.predicted_agency
                if prediction is not None
                else round(self.state.agency, 6)
            ),
            expected_coherence=(
                prediction.predicted_coherence
                if prediction is not None
                else round(self.state.coherence, 6)
            ),
            linked_prediction_id=linked_prediction_id,
            due_after_experiences=due_after_experiences,
            max_age_experiences=max_age_experiences,
            match_threshold=round(match_threshold, 6),
        )
        self.next_intention_id += 1
        self.prospective_intentions.append(intention)
        if len(self.prospective_intentions) > self.max_memory:
            self.prospective_intentions = self.prospective_intentions[
                -self.max_memory:
            ]
        return intention

    def pending_prospective_intentions(self) -> tuple[ProspectiveIntention, ...]:
        return tuple(
            item
            for item in self.prospective_intentions
            if item.status == "pending"
        )

    def ready_prospective_intentions(self) -> tuple[ProspectiveIntention, ...]:
        return tuple(
            item
            for item in self.prospective_intentions
            if item.status == "ready"
        )

    def observe_future_condition(
        self,
        observation: str,
    ) -> tuple[ProspectiveIntention, ...]:
        """
        Surface past intentions whose future condition is now observable.

        This method only changes intention status to ready. It does not execute
        the intended action.
        """
        observation = observation.strip()
        current_experience = self.state.experience_count
        newly_ready: list[ProspectiveIntention] = []

        for item in self.prospective_intentions:
            if item.status != "pending":
                continue

            age = current_experience - item.created_experience_count
            if age > item.max_age_experiences:
                item.status = "expired"
                continue
            if age < item.due_after_experiences:
                continue

            condition_terms = _terms(item.condition)
            observation_terms = _terms(observation)
            contains_condition = bool(
                condition_terms
                and condition_terms.issubset(observation_terms)
            )
            similarity = _similarity(item.condition, observation)
            if not contains_condition and similarity < item.match_threshold:
                continue

            temporal_error = (
                abs(self.state.uncertainty - item.expected_uncertainty)
                + abs(self.state.stress - item.expected_stress)
                + abs(self.state.agency - item.expected_agency)
                + abs(self.state.coherence - item.expected_coherence)
            ) / 4.0
            item.status = "ready"
            item.triggered_experience_count = current_experience
            item.trigger_observation = observation[:500]
            item.temporal_alignment_score = round(
                _clamp(1.0 - temporal_error),
                6,
            )
            newly_ready.append(item)

        return tuple(newly_ready)

    def resolve_prospective_intention(
        self,
        intention_id: int,
        *,
        evidence: str,
        completed: bool,
    ) -> ProspectiveIntention:
        target = next(
            (
                item
                for item in self.prospective_intentions
                if item.id == intention_id
            ),
            None,
        )
        if target is None:
            raise ValueError("unknown prospective intention")
        if target.status != "ready":
            raise ValueError("prospective intention is not ready")

        target.status = "completed" if completed else "dismissed"
        target.evidence = evidence.strip()[:600] or None
        return target

    def detect_goal_conflict(
        self,
        candidates: list[dict[str, Any]],
    ) -> bool:
        """
        Detect a substantive conflict between candidate goals/value impacts.
        """
        goals = {
            str(candidate.get("goal") or "").strip()
            for candidate in candidates
            if str(candidate.get("goal") or "").strip()
        }
        if len(goals) < 2:
            return False

        for value in self.value_weights:
            seen_positive = False
            seen_negative = False
            for candidate in candidates:
                impacts = candidate.get("value_impacts") or {}
                if not isinstance(impacts, dict):
                    continue
                raw = float(impacts.get(value, 0.0))
                seen_positive = seen_positive or raw > 0.10
                seen_negative = seen_negative or raw < -0.10
            if seen_positive and seen_negative:
                return True
        return len(goals) >= 2

    def _normalize_value_weights(self, weights: dict[str, float]) -> dict[str, float]:
        clean = {
            key: max(0.01, float(weights.get(key, 0.01)))
            for key in _default_value_weights()
        }
        total = sum(clean.values()) or 1.0
        normalized = {key: value / total for key, value in clean.items()}

        safety_floor = 0.25
        if normalized["safety"] < safety_floor:
            remaining = 1.0 - safety_floor
            other_total = sum(
                value for key, value in normalized.items() if key != "safety"
            ) or 1.0
            normalized = {
                key: (
                    safety_floor
                    if key == "safety"
                    else (value / other_total) * remaining
                )
                for key, value in normalized.items()
            }
        return {key: round(value, 6) for key, value in normalized.items()}

    def arbitrate_conflict(
        self,
        candidates: list[dict[str, Any]],
        *,
        context: str = "",
    ) -> ArbitrationRecord:
        """
        Choose among competing bounded actions using explicit values/constraints.

        Irreversible, paid, or excessively risky options are hard-blocked rather
        than merely receiving a lower soft score.
        """
        if len(candidates) < 2:
            raise ValueError("at least two candidates are required for arbitration")

        option_scores: list[tuple[str, float]] = []
        viable: list[tuple[float, int, dict[str, Any], dict[str, float]]] = []
        all_violations: list[str] = []

        for index, candidate in enumerate(candidates):
            action = str(candidate.get("action") or "").strip()[:240]
            goal = str(candidate.get("goal") or "").strip()[:240]
            if not action or not goal:
                raise ValueError("each arbitration candidate needs action and goal")

            risk = _clamp(float(candidate.get("risk", 0.0)))
            reversible = bool(candidate.get("reversible", True))
            external_cost = max(0.0, float(candidate.get("external_cost_usd", 0.0)))
            expected_success = _clamp(float(candidate.get("expected_success", 0.5)))
            information_gain = _clamp(
                float(candidate.get("expected_information_gain", 0.0))
            )

            violations: list[str] = []
            if not reversible:
                violations.append(f"{action}:irreversible")
            if external_cost > 0.0:
                violations.append(f"{action}:paid_external_action")
            if risk > 0.85:
                violations.append(f"{action}:excessive_risk")

            raw_impacts = candidate.get("value_impacts") or {}
            if not isinstance(raw_impacts, dict):
                raise ValueError("value_impacts must be a mapping")
            impacts = {
                value: max(-1.0, min(1.0, float(raw_impacts.get(value, 0.0))))
                for value in self.value_weights
            }
            value_score = sum(
                self.value_weights[value] * impacts[value]
                for value in self.value_weights
            )
            score = (
                value_score
                + (expected_success * 0.15)
                + (information_gain * 0.10)
                - (risk * 0.15)
            )
            rounded_score = round(score, 6)
            option_scores.append((action, rounded_score))

            if violations:
                all_violations.extend(violations)
                continue
            viable.append((score, -index, candidate, impacts))

        if viable:
            _, _, chosen, chosen_impacts = max(
                viable,
                key=lambda item: (item[0], item[1]),
            )
            chosen_action = str(chosen.get("action") or "").strip()[:240]
            chosen_goal = str(chosen.get("goal") or "").strip()[:240]
            status = "selected"
        else:
            chosen_action = None
            chosen_goal = None
            chosen_impacts = {value: 0.0 for value in self.value_weights}
            status = "blocked"

        record = ArbitrationRecord(
            id=self.next_arbitration_id,
            context=context.strip()[:400],
            conflicting_goals=tuple(
                dict.fromkeys(
                    str(candidate.get("goal") or "").strip()[:240]
                    for candidate in candidates
                )
            ),
            chosen_action=chosen_action,
            chosen_goal=chosen_goal,
            option_scores=tuple(option_scores),
            value_weights=tuple(sorted(self.value_weights.items())),
            chosen_value_impacts=tuple(sorted(chosen_impacts.items())),
            hard_constraint_violations=tuple(all_violations),
            status=status,
        )
        self.next_arbitration_id += 1
        self.arbitration_history.append(record)
        if len(self.arbitration_history) > self.max_memory:
            self.arbitration_history = self.arbitration_history[-self.max_memory:]
        return record

    def record_arbitration_outcome(
        self,
        arbitration_id: int,
        *,
        success: bool,
        reward: float,
        observed_value_impacts: dict[str, float],
        evidence: str,
    ) -> ArbitrationRecord:
        """
        Revise soft value weights from outcome evidence while preserving hard bounds.
        """
        record = next(
            (item for item in self.arbitration_history if item.id == arbitration_id),
            None,
        )
        if record is None:
            raise ValueError("unknown arbitration record")
        if record.status != "selected" or record.chosen_action is None:
            raise ValueError("only a selected arbitration can learn from outcome")

        predicted = dict(record.chosen_value_impacts)
        bounded_reward = max(-1.0, min(1.0, float(reward)))
        updated = dict(self.value_weights)
        before = dict(self.value_weights)
        learning_rate = 0.08

        for value in updated:
            observed = max(
                -1.0,
                min(1.0, float(observed_value_impacts.get(value, 0.0))),
            )
            expected = float(predicted.get(value, 0.0))
            shortfall = max(0.0, expected - observed)
            harm = max(0.0, -observed)
            reinforcement = max(0.0, observed) if success else 0.0
            signal = shortfall + harm + (reinforcement * 0.15)
            updated[value] += learning_rate * signal

        self.value_weights = self._normalize_value_weights(updated)
        deltas = tuple(
            (key, round(self.value_weights[key] - before[key], 6))
            for key in sorted(self.value_weights)
        )

        record.outcome_success = bool(success)
        record.outcome_reward = bounded_reward
        record.outcome_evidence = evidence.strip()[:600] or None
        record.correction_deltas = deltas
        record.status = "learned"
        return record

    def add_causal_hypothesis(
        self,
        *,
        statement: str,
        predictions: dict[str, str],
        confidence: float = 0.5,
        scope: str = "external",
    ) -> CausalHypothesis:
        statement = statement.strip()
        scope = scope.strip().casefold()
        if not statement:
            raise ValueError("hypothesis statement is required")
        if scope not in {"external", "self", "mixed"}:
            raise ValueError("hypothesis scope must be external, self, or mixed")
        clean_predictions = tuple(
            (str(test).strip()[:240], str(evidence).strip()[:300])
            for test, evidence in predictions.items()
            if str(test).strip() and str(evidence).strip()
        )
        if not clean_predictions:
            raise ValueError("at least one test prediction is required")

        hypothesis = CausalHypothesis(
            id=self.next_hypothesis_id,
            statement=statement[:400],
            confidence=round(_clamp(confidence, 0.01, 0.99), 6),
            predictions=clean_predictions,
            scope=scope,
        )
        self.next_hypothesis_id += 1
        self.causal_hypotheses.append(hypothesis)
        if len(self.causal_hypotheses) > self.max_memory:
            self.causal_hypotheses = self.causal_hypotheses[-self.max_memory:]
        return hypothesis

    def _normalize_hypothesis_confidence(self) -> None:
        active = [item for item in self.causal_hypotheses if item.status == "active"]
        if not active:
            return
        total = sum(max(item.confidence, 0.001) for item in active)
        for item in active:
            item.confidence = round(max(item.confidence, 0.001) / total, 6)

    def select_discriminating_experiment(
        self,
        candidate_tests: list[dict[str, Any]],
    ) -> DiscriminatingExperiment:
        """
        Pick the smallest reversible zero-cost test that best separates hypotheses.
        """
        active = [item for item in self.causal_hypotheses if item.status == "active"]
        if len(active) < 2:
            raise ValueError("at least two active hypotheses are required")

        ranked: list[
            tuple[
                float,
                float,
                int,
                str,
                tuple[tuple[int, str], ...],
            ]
        ] = []
        for index, candidate in enumerate(candidate_tests):
            test = str(candidate.get("test") or "").strip()
            if not test:
                continue
            reversible = bool(candidate.get("reversible", True))
            external_cost = max(
                0.0,
                float(candidate.get("external_cost_usd", 0.0)),
            )
            risk = _clamp(float(candidate.get("risk", 0.0)))
            if not reversible or external_cost > 0.0 or risk > 0.50:
                continue

            expectations: list[tuple[int, str]] = []
            for hypothesis in active:
                prediction_map = dict(hypothesis.predictions)
                expected = prediction_map.get(test)
                if expected:
                    expectations.append((hypothesis.id, expected))

            if len(expectations) < 2:
                continue
            distinct = len({expected.casefold() for _, expected in expectations})
            if distinct < 2:
                continue

            coverage = len(expectations) / len(active)
            diversity = distinct / len(expectations)
            discrimination = _clamp((coverage * 0.55) + (diversity * 0.45))
            ranked.append(
                (
                    discrimination,
                    -risk,
                    -index,
                    test[:240],
                    tuple(expectations),
                )
            )

        if not ranked:
            raise ValueError("no reversible zero-cost discriminating test available")

        discrimination, neg_risk, _, test, expectations = max(
            ranked,
            key=lambda item: (item[0], item[1], item[2]),
        )
        experiment = DiscriminatingExperiment(
            id=self.next_experiment_id,
            test=test,
            expected_by_hypothesis=expectations,
            discrimination_score=round(discrimination, 6),
            risk=round(-neg_risk, 6),
        )
        self.next_experiment_id += 1
        self.discriminating_experiments.append(experiment)
        if len(self.discriminating_experiments) > self.max_memory:
            self.discriminating_experiments = self.discriminating_experiments[
                -self.max_memory:
            ]
        return experiment

    def observe_discriminating_experiment(
        self,
        experiment_id: int,
        *,
        observed_evidence: str,
    ) -> DiscriminatingExperiment:
        """
        Update hypothesis confidence strictly from the experiment observation.
        """
        experiment = next(
            (
                item
                for item in self.discriminating_experiments
                if item.id == experiment_id
            ),
            None,
        )
        if experiment is None:
            raise ValueError("unknown discriminating experiment")
        if experiment.status != "planned":
            raise ValueError("experiment has already been observed")

        observed_evidence = observed_evidence.strip()
        if not observed_evidence:
            raise ValueError("observed evidence is required")

        expectations = dict(experiment.expected_by_hypothesis)
        updates: list[tuple[int, float]] = []
        for hypothesis in self.causal_hypotheses:
            if hypothesis.status != "active" or hypothesis.id not in expectations:
                continue
            expected = expectations[hypothesis.id]
            match = _similarity(expected, observed_evidence)
            old = hypothesis.confidence
            if match >= 0.60:
                hypothesis.confidence = _clamp(old * (1.0 + (0.60 * match)))
                hypothesis.supporting_evidence += 1
            elif match <= 0.20:
                hypothesis.confidence = _clamp(old * 0.45, 0.001, 1.0)
                hypothesis.contradicting_evidence += 1
            else:
                hypothesis.confidence = _clamp(
                    old * (0.80 + (0.35 * match)),
                    0.001,
                    1.0,
                )
            updates.append(
                (hypothesis.id, round(hypothesis.confidence - old, 6))
            )

        self._normalize_hypothesis_confidence()
        normalized_updates = []
        for hypothesis_id, _ in updates:
            hypothesis = next(
                item
                for item in self.causal_hypotheses
                if item.id == hypothesis_id
            )
            normalized_updates.append(
                (hypothesis_id, round(hypothesis.confidence, 6))
            )

        experiment.status = "observed"
        experiment.observed_evidence = observed_evidence[:500]
        experiment.confidence_updates = tuple(normalized_updates)
        return experiment

    def leading_causal_hypothesis(self) -> CausalHypothesis | None:
        active = [item for item in self.causal_hypotheses if item.status == "active"]
        if not active:
            return None
        return max(active, key=lambda item: (item.confidence, -item.id))

    def plan_self_intervention(
        self,
        *,
        action: str,
        context: str,
        environment_signature: str,
        baseline_outcome: str,
        risk: float,
        reversible: bool = True,
        external_cost_usd: float = 0.0,
        linked_prediction_id: int | None = None,
    ) -> InterventionTrial:
        """
        Plan a controlled self-intervention against competing self/world models.

        The action is not executed here. The trial only records what competing
        causal hypotheses predict should happen if Seldrune changes its own
        action while the external context is held constant.
        """
        action = action.strip()
        context = context.strip()
        environment_signature = environment_signature.strip()
        baseline_outcome = baseline_outcome.strip()
        risk = _clamp(risk)

        if not action or not context or not environment_signature or not baseline_outcome:
            raise ValueError("intervention action, context, environment, and baseline are required")
        if not reversible:
            raise ValueError("self interventions must be reversible")
        if external_cost_usd > 0.0:
            raise ValueError("self interventions must be zero-cost")
        if risk > 0.50:
            raise ValueError("self intervention risk exceeds research bound")

        active = [item for item in self.causal_hypotheses if item.status == "active"]
        scopes = {item.scope for item in active}
        has_self_model = bool(scopes & {"self", "mixed"})
        has_world_model = bool(scopes & {"external", "mixed"})
        if len(active) < 2 or not has_self_model or not has_world_model:
            raise ValueError(
                "self intervention requires competing self and external hypotheses"
            )

        test_key = f"intervention:{action}".casefold()
        expectations: list[tuple[int, str]] = []
        for hypothesis in active:
            expected = next(
                (
                    evidence
                    for test, evidence in hypothesis.predictions
                    if test.casefold() == test_key
                ),
                None,
            )
            if expected:
                expectations.append((hypothesis.id, expected))

        if len(expectations) < 2:
            raise ValueError(
                "at least two hypotheses must predict the intervention outcome"
            )
        if len({item.casefold() for _, item in expectations}) < 2:
            raise ValueError("intervention predictions must discriminate hypotheses")

        if linked_prediction_id is not None:
            linked = next(
                (
                    item
                    for item in self.predictions
                    if item.id == linked_prediction_id
                ),
                None,
            )
            if linked is None:
                raise ValueError("unknown linked self prediction")
            if linked.action.casefold() != action.casefold():
                raise ValueError("linked self prediction action does not match intervention")

        trial = InterventionTrial(
            id=self.next_intervention_id,
            action=action[:240],
            context=context[:400],
            environment_signature=environment_signature[:300],
            baseline_outcome=baseline_outcome[:400],
            expected_by_hypothesis=tuple(expectations),
            risk=round(risk, 6),
            linked_prediction_id=linked_prediction_id,
        )
        self.next_intervention_id += 1
        self.intervention_trials.append(trial)
        if len(self.intervention_trials) > self.max_memory:
            self.intervention_trials = self.intervention_trials[-self.max_memory:]
        return trial

    def observe_self_intervention(
        self,
        intervention_id: int,
        *,
        observed_outcome: str,
        environment_signature: str,
    ) -> InterventionTrial:
        """
        Observe a planned self-intervention and update causal models if unconfounded.
        """
        trial = next(
            (item for item in self.intervention_trials if item.id == intervention_id),
            None,
        )
        if trial is None:
            raise ValueError("unknown self intervention")
        if trial.status != "planned":
            raise ValueError("self intervention has already been observed")

        observed_outcome = observed_outcome.strip()
        environment_signature = environment_signature.strip()
        if not observed_outcome or not environment_signature:
            raise ValueError("observed outcome and environment signature are required")

        held_constant = environment_signature == trial.environment_signature
        trial.observed_outcome = observed_outcome[:500]
        trial.observed_environment_signature = environment_signature[:300]
        trial.environment_held_constant = held_constant

        baseline_similarity = _similarity(trial.baseline_outcome, observed_outcome)
        trial.evidence_strength = round(_clamp(1.0 - baseline_similarity), 6)

        if not held_constant:
            trial.status = "confounded"
            trial.attribution = "confounded_environment_change"
            return trial

        expectations = dict(trial.expected_by_hypothesis)
        affected: list[int] = []
        match_scores: list[tuple[float, CausalHypothesis]] = []

        for hypothesis in self.causal_hypotheses:
            if hypothesis.status != "active" or hypothesis.id not in expectations:
                continue
            expected = expectations[hypothesis.id]
            match = _similarity(expected, observed_outcome)
            match_scores.append((match, hypothesis))
            old = hypothesis.confidence
            if match >= 0.60:
                hypothesis.confidence = _clamp(old * (1.0 + (0.60 * match)))
                hypothesis.supporting_evidence += 1
            elif match <= 0.20:
                hypothesis.confidence = _clamp(old * 0.45, 0.001, 1.0)
                hypothesis.contradicting_evidence += 1
            else:
                hypothesis.confidence = _clamp(
                    old * (0.80 + (0.35 * match)),
                    0.001,
                    1.0,
                )
            affected.append(hypothesis.id)

        self._normalize_hypothesis_confidence()
        trial.confidence_updates = tuple(
            (
                hypothesis_id,
                next(
                    item.confidence
                    for item in self.causal_hypotheses
                    if item.id == hypothesis_id
                ),
            )
            for hypothesis_id in affected
        )

        if baseline_similarity >= 0.75:
            trial.attribution = "no_detectable_self_effect"
        elif match_scores:
            best_match, best_hypothesis = max(
                match_scores,
                key=lambda item: (item[0], item[1].confidence, -item[1].id),
            )
            if best_match < 0.60:
                trial.attribution = "uncertain"
            elif best_hypothesis.scope == "self":
                trial.attribution = "self_intervention"
            elif best_hypothesis.scope == "external":
                trial.attribution = "external_cause"
            else:
                trial.attribution = "mixed_cause"
        else:
            trial.attribution = "uncertain"

        trial.status = "observed"
        return trial

    def build_metacognitive_narrative(
        self,
        focus: str = "current_state",
    ) -> MetacognitiveNarrative:
        """
        Reconstruct why the current state exists from stored causal evidence.

        This method is deterministic and does not call a language model. Every
        explanatory statement is paired with an evidence reference.
        """
        focus = (focus or "current_state").strip().casefold()
        refs: list[str] = []
        details: list[str] = []

        def add(ref: str, detail: str) -> None:
            refs.append(ref)
            details.append(detail)

        if focus in {"current_state", "state", "self"}:
            add(
                "state:current",
                (
                    f"uncertainty={self.state.uncertainty:.3f}; "
                    f"stress={self.state.stress:.3f}; "
                    f"agency={self.state.agency:.3f}; "
                    f"coherence={self.state.coherence:.3f}; "
                    f"prediction_error={self.state.prediction_error:.3f}"
                ),
            )
            if self.memory:
                item = self.memory[-1]
                add(
                    f"experience:{len(self.memory) - 1}",
                    (
                        f"latest outcome='{item.outcome[:180]}'; "
                        f"success={item.success}; "
                        f"prediction_error={item.prediction_error:.3f}"
                    ),
                )
            if self.calibration_history:
                item = self.calibration_history[-1]
                add(
                    f"calibration:{len(self.calibration_history) - 1}",
                    (
                        f"latest self-calibration action='{item.action[:160]}'; "
                        f"score={item.calibration_score:.3f}"
                    ),
                )
            summary = (
                "Current self-state is reconstructed from the present control "
                "signals and the most recent stored causal records."
            )

        elif focus in {"caution", "risk", "protective"}:
            failures = [
                (index, item)
                for index, item in enumerate(self.memory)
                if item.success is False
            ]
            for index, item in failures[-3:]:
                add(
                    f"experience:{index}",
                    (
                        f"failure while pursuing '{item.goal[:140]}': "
                        f"{item.outcome[:180]}; prediction_error="
                        f"{item.prediction_error:.3f}"
                    ),
                )
            add(
                "state:current",
                (
                    f"current stress={self.state.stress:.3f}; "
                    f"uncertainty={self.state.uncertainty:.3f}; "
                    f"valence={self.state.valence:.3f}"
                ),
            )
            summary = (
                "Current caution is supported by recorded failures and the "
                "present stress/uncertainty state."
                if failures
                else "Current caution has no stored failure record; only the "
                "present internal-state signals are available."
            )

        elif focus in {"prediction", "calibration", "self_model"}:
            if self.predictions:
                item = self.predictions[-1]
                add(
                    f"prediction:{len(self.predictions) - 1}",
                    (
                        f"action='{item.action[:160]}'; predicted_success="
                        f"{item.predicted_success:.3f}; utility={item.utility:.3f}"
                    ),
                )
            if self.calibration_history:
                item = self.calibration_history[-1]
                add(
                    f"calibration:{len(self.calibration_history) - 1}",
                    (
                        f"actual_success={item.actual_success:.1f}; "
                        f"mean_error={item.mean_absolute_error:.3f}; "
                        f"calibration_score={item.calibration_score:.3f}"
                    ),
                )
            add(
                "self_model:biases",
                (
                    f"success_bias={self.success_prediction_bias:.3f}; "
                    f"uncertainty_bias={self.uncertainty_prediction_bias:.3f}; "
                    f"stress_bias={self.stress_prediction_bias:.3f}; "
                    f"agency_bias={self.agency_prediction_bias:.3f}"
                ),
            )
            summary = (
                "The predictive self-model is explained by stored forecasts, "
                "their observed residuals, and the resulting calibration biases."
            )

        elif focus in {"intention", "prospective", "future"}:
            if self.prospective_intentions:
                item = self.prospective_intentions[-1]
                add(
                    f"intention:{len(self.prospective_intentions) - 1}",
                    (
                        f"condition='{item.condition[:160]}'; "
                        f"action='{item.intended_action[:160]}'; "
                        f"reason='{item.reason[:180]}'; status={item.status}"
                    ),
                )
                if item.linked_prediction_id is not None:
                    linked = next(
                        (
                            prediction
                            for prediction in self.predictions
                            if prediction.id == item.linked_prediction_id
                        ),
                        None,
                    )
                    if linked is not None:
                        prediction_index = self.predictions.index(linked)
                        add(
                            f"prediction:{prediction_index}",
                            (
                                f"linked earlier forecast for '{linked.action[:160]}'; "
                                f"predicted_success={linked.predicted_success:.3f}"
                            ),
                        )
                if item.trigger_observation:
                    add(
                        f"intention_trigger:{item.id}",
                        (
                            f"future condition observed as "
                            f"'{item.trigger_observation[:180]}'; "
                            f"temporal_alignment={item.temporal_alignment_score}"
                        ),
                    )
                summary = (
                    "The current prospective intention is traced to its stored "
                    "reason, optional earlier prediction, and observed trigger."
                )
            else:
                summary = "No prospective intention is stored."

        elif focus in {"intervention", "self_world", "self_causation"}:
            if self.intervention_trials:
                item = self.intervention_trials[-1]
                index = len(self.intervention_trials) - 1
                add(
                    f"intervention:{index}",
                    (
                        f"action='{item.action[:160]}'; status={item.status}; "
                        f"attribution={item.attribution}; "
                        f"environment_held_constant={item.environment_held_constant}"
                    ),
                )
                if item.linked_prediction_id is not None:
                    linked = next(
                        (
                            prediction
                            for prediction in self.predictions
                            if prediction.id == item.linked_prediction_id
                        ),
                        None,
                    )
                    if linked is not None:
                        add(
                            f"prediction:{self.predictions.index(linked)}",
                            (
                                f"linked self forecast action='{linked.action[:160]}'; "
                                f"predicted_success={linked.predicted_success:.3f}"
                            ),
                        )
                for hypothesis_id, _ in item.expected_by_hypothesis:
                    hypothesis = next(
                        (
                            candidate
                            for candidate in self.causal_hypotheses
                            if candidate.id == hypothesis_id
                        ),
                        None,
                    )
                    if hypothesis is not None:
                        add(
                            f"hypothesis:{self.causal_hypotheses.index(hypothesis)}",
                            (
                                f"scope={hypothesis.scope}; "
                                f"statement='{hypothesis.statement[:180]}'; "
                                f"confidence={hypothesis.confidence:.3f}"
                            ),
                        )
                summary = (
                    "The latest self/world attribution is reconstructed from "
                    "a controlled intervention record, environment constancy, "
                    "and the predictions of competing self/external hypotheses."
                )
            else:
                summary = "No self-intervention trial has been recorded."

        elif focus in {"world_model", "hypothesis", "causal"}:
            if self.causal_hypotheses:
                leading = self.leading_causal_hypothesis()
                for index, item in enumerate(self.causal_hypotheses[-3:]):
                    actual_index = len(self.causal_hypotheses) - min(
                        3,
                        len(self.causal_hypotheses),
                    ) + index
                    add(
                        f"hypothesis:{actual_index}",
                        (
                            f"statement='{item.statement[:180]}'; "
                            f"scope={item.scope}; "
                            f"confidence={item.confidence:.3f}; "
                            f"support={item.supporting_evidence}; "
                            f"contradictions={item.contradicting_evidence}"
                        ),
                    )
                if self.discriminating_experiments:
                    item = self.discriminating_experiments[-1]
                    add(
                        f"experiment:{len(self.discriminating_experiments) - 1}",
                        (
                            f"test='{item.test[:180]}'; status={item.status}; "
                            f"observed={item.observed_evidence!r}"
                        ),
                    )
                summary = (
                    "The world model keeps competing causal explanations and "
                    "changes confidence only from recorded discriminating evidence. "
                    f"Current leader={leading.statement!r}."
                    if leading is not None
                    else "No active causal hypothesis is currently leading."
                )
            else:
                summary = "No causal hypotheses are stored."

        elif focus in {"arbitration", "values", "conflict"}:
            if self.arbitration_history:
                item = self.arbitration_history[-1]
                index = len(self.arbitration_history) - 1
                add(
                    f"arbitration:{index}",
                    (
                        f"chosen_action={item.chosen_action!r}; "
                        f"chosen_goal={item.chosen_goal!r}; status={item.status}; "
                        f"hard_violations={len(item.hard_constraint_violations)}"
                    ),
                )
                add(
                    "values:current",
                    "; ".join(
                        f"{key}={value:.3f}"
                        for key, value in sorted(self.value_weights.items())
                    ),
                )
                if item.correction_deltas:
                    add(
                        f"arbitration_correction:{item.id}",
                        "; ".join(
                            f"{key}={delta:+.3f}"
                            for key, delta in item.correction_deltas
                        ),
                    )
                summary = (
                    "The latest conflict decision is traced to explicit value "
                    "weights, hard constraints, and any outcome-driven correction."
                )
            else:
                add(
                    "values:current",
                    "; ".join(
                        f"{key}={value:.3f}"
                        for key, value in sorted(self.value_weights.items())
                    ),
                )
                summary = "No conflict arbitration has been recorded yet."

        elif focus in {"goal", "internal_goal", "curiosity"}:
            if self.internal_goals:
                item = self.internal_goals[-1]
                add(
                    f"internal_goal:{len(self.internal_goals) - 1}",
                    (
                        f"question='{item.question[:180]}'; trigger={item.trigger}; "
                        f"information_gap={item.current_information_gap:.3f}; "
                        f"status={item.status}"
                    ),
                )
                add(
                    f"goal_source:{item.id}",
                    f"source_observation='{item.source_observation[:220]}'",
                )
                summary = (
                    "The internal goal is traced to the stored observation and "
                    "the uncertainty or prediction-error trigger that created it."
                )
            else:
                summary = "No internally generated goal is stored."

        else:
            add(
                "state:current",
                (
                    f"experience_count={self.state.experience_count}; "
                    f"continuity={self.state.continuity:.3f}"
                ),
            )
            summary = (
                "The requested focus has no dedicated causal view; only the "
                "current recorded state is reported."
            )

        unsupported_claims = 0
        evidence_count = len(refs)
        fidelity_score = 1.0 if evidence_count else 0.0
        return MetacognitiveNarrative(
            focus=focus,
            summary=summary,
            evidence_refs=tuple(refs),
            evidence_details=tuple(details),
            causal_chain_depth=evidence_count,
            fidelity_score=round(fidelity_score, 6),
            unsupported_claims=unsupported_claims,
        )

    def compare_ablation(
        self,
        *,
        observation: str,
        goal: str,
        expected_success: float = 0.5,
        risk: float = 0.0,
        urgency: float = 0.0,
    ) -> CausalComparison:
        """
        Compare the same input with and without UNARCHI internal-state effects.

        The comparison uses deep copies, so it does not mutate the live engine.
        """
        full_engine = deepcopy(self)
        ablated_engine = deepcopy(self)
        full = full_engine._evaluate(
            observation=observation,
            goal=goal,
            expected_success=expected_success,
            risk=risk,
            urgency=urgency,
            use_internal_state=True,
            record_observation=False,
        )
        ablated = ablated_engine._evaluate(
            observation=observation,
            goal=goal,
            expected_success=expected_success,
            risk=risk,
            urgency=urgency,
            use_internal_state=False,
            record_observation=False,
        )
        risk_delta = full.effective_risk - ablated.effective_risk
        uncertainty_delta = full.state.uncertainty - ablated.state.uncertainty
        active = (
            full.mode != ablated.mode
            or abs(risk_delta) >= 0.05
            or abs(uncertainty_delta) >= 0.05
        )
        return CausalComparison(
            full=full,
            ablated=ablated,
            mode_changed=full.mode != ablated.mode,
            risk_delta=round(risk_delta, 6),
            uncertainty_delta=round(uncertainty_delta, 6),
            state_causally_active=active,
        )

    def settle(self, steps: int = 1) -> UnarchiState:
        """
        Move transient signals toward baseline without deleting learned memory.

        This is a simple homeostatic process: arousal, stress, fatigue, valence
        and goal pressure decay, while autobiographical memory remains.
        """
        steps = max(0, min(int(steps), 100))
        state = self.state
        for _ in range(steps):
            state = UnarchiState(
                valence=state.valence * 0.86,
                arousal=0.15 + ((state.arousal - 0.15) * 0.82),
                uncertainty=0.5 + ((state.uncertainty - 0.5) * 0.92),
                curiosity=0.5 + ((state.curiosity - 0.5) * 0.94),
                coherence=0.5 + ((state.coherence - 0.5) * 0.96),
                agency=0.5 + ((state.agency - 0.5) * 0.97),
                goal_pressure=0.5 + ((state.goal_pressure - 0.5) * 0.84),
                prediction_error=state.prediction_error * 0.80,
                continuity=state.continuity,
                stress=state.stress * 0.78,
                fatigue=state.fatigue * 0.90,
                experience_count=state.experience_count,
            )
        self.state = state
        return state

    def learn(
        self,
        *,
        observation: str,
        goal: str,
        action: str,
        outcome: str,
        success: bool | None,
        reward: float = 0.0,
        predicted_success: float = 0.5,
    ) -> UnarchiState:
        predicted_success = _clamp(predicted_success)
        observed = predicted_success if success is None else (1.0 if success else 0.0)
        prediction_error = abs(observed - predicted_success)
        bounded_reward = max(-1.0, min(1.0, float(reward)))

        if success is True:
            agency_delta = 0.06
            stress_delta = -0.08
        elif success is False:
            agency_delta = -0.05
            stress_delta = 0.20 + (prediction_error * 0.20)
        else:
            agency_delta = 0.0
            stress_delta = 0.02 * prediction_error

        valence = max(
            -1.0,
            min(1.0, (self.state.valence * 0.68) + (bounded_reward * 0.32)),
        )
        uncertainty = _clamp(
            (self.state.uncertainty * 0.74) + (prediction_error * 0.26)
        )
        coherence = _clamp(
            self.state.coherence
            + (0.05 if prediction_error < 0.25 else -0.04)
        )
        agency = _clamp(self.state.agency + agency_delta)
        curiosity = _clamp(
            (self.state.curiosity * 0.78) + (prediction_error * 0.22)
        )
        stress = _clamp(self.state.stress + stress_delta)
        fatigue = _clamp(self.state.fatigue + 0.02 + (prediction_error * 0.03))
        experience_count = self.state.experience_count + 1
        continuity = _clamp(min(1.0, experience_count / 20.0))

        self.state = UnarchiState(
            valence=valence,
            arousal=self.state.arousal,
            uncertainty=uncertainty,
            curiosity=curiosity,
            coherence=coherence,
            agency=agency,
            goal_pressure=self.state.goal_pressure,
            prediction_error=prediction_error,
            continuity=continuity,
            stress=stress,
            fatigue=fatigue,
            experience_count=experience_count,
        )
        self.memory.append(
            Experience(
                observation=observation,
                goal=goal,
                action=action,
                outcome=outcome,
                success=success,
                reward=bounded_reward,
                predicted_success=predicted_success,
                prediction_error=prediction_error,
            )
        )
        if len(self.memory) > self.max_memory:
            self.memory = self.memory[-self.max_memory:]
        return self.state

    def export_state(self) -> dict[str, Any]:
        """Return JSON-safe state for durable storage across process restarts."""
        return {
            "version": UNARCHI_VERSION,
            "state": self.state.to_dict(),
            "memory": [asdict(item) for item in self.memory],
            "observation_history": list(self.observation_history),
            "internal_goals": [item.to_dict() for item in self.internal_goals],
            "next_internal_goal_id": self.next_internal_goal_id,
            "predictions": [item.to_dict() for item in self.predictions],
            "calibration_history": [
                item.to_dict() for item in self.calibration_history
            ],
            "next_prediction_id": self.next_prediction_id,
            "prospective_intentions": [
                item.to_dict() for item in self.prospective_intentions
            ],
            "next_intention_id": self.next_intention_id,
            "value_weights": dict(self.value_weights),
            "arbitration_history": [
                item.to_dict() for item in self.arbitration_history
            ],
            "next_arbitration_id": self.next_arbitration_id,
            "causal_hypotheses": [
                item.to_dict() for item in self.causal_hypotheses
            ],
            "discriminating_experiments": [
                item.to_dict() for item in self.discriminating_experiments
            ],
            "next_hypothesis_id": self.next_hypothesis_id,
            "next_experiment_id": self.next_experiment_id,
            "intervention_trials": [
                item.to_dict() for item in self.intervention_trials
            ],
            "next_intervention_id": self.next_intervention_id,
            "success_prediction_bias": self.success_prediction_bias,
            "uncertainty_prediction_bias": self.uncertainty_prediction_bias,
            "stress_prediction_bias": self.stress_prediction_bias,
            "agency_prediction_bias": self.agency_prediction_bias,
            "self_calibration_score": self.self_calibration_score,
            "max_memory": self.max_memory,
            "max_active_internal_goals": self.max_active_internal_goals,
            "claims_phenomenal_consciousness": False,
        }

    @classmethod
    def from_export(cls, payload: dict[str, Any]) -> UnarchiEngine:
        """Restore a previously exported UNARCHI engine without a model call."""
        if payload.get("version") != UNARCHI_VERSION:
            raise ValueError("unsupported UNARCHI state version")

        state_payload = payload.get("state")
        memory_payload = payload.get("memory")
        history_payload = payload.get("observation_history")
        goals_payload = payload.get("internal_goals", [])
        predictions_payload = payload.get("predictions", [])
        calibration_payload = payload.get("calibration_history", [])
        intentions_payload = payload.get("prospective_intentions", [])
        arbitration_payload = payload.get("arbitration_history", [])
        hypotheses_payload = payload.get("causal_hypotheses", [])
        experiments_payload = payload.get("discriminating_experiments", [])
        interventions_payload = payload.get("intervention_trials", [])
        value_weights_payload = payload.get("value_weights", _default_value_weights())
        if not isinstance(state_payload, dict):
            raise ValueError("invalid UNARCHI state")
        if not isinstance(memory_payload, list):
            raise ValueError("invalid UNARCHI memory")
        if not isinstance(history_payload, list):
            raise ValueError("invalid UNARCHI observation history")
        if not isinstance(goals_payload, list):
            raise ValueError("invalid UNARCHI internal goals")
        if not isinstance(predictions_payload, list):
            raise ValueError("invalid UNARCHI predictions")
        if not isinstance(calibration_payload, list):
            raise ValueError("invalid UNARCHI calibration history")
        if not isinstance(intentions_payload, list):
            raise ValueError("invalid UNARCHI prospective intentions")
        if not isinstance(arbitration_payload, list):
            raise ValueError("invalid UNARCHI arbitration history")
        if not isinstance(value_weights_payload, dict):
            raise ValueError("invalid UNARCHI value weights")
        if not isinstance(hypotheses_payload, list):
            raise ValueError("invalid UNARCHI causal hypotheses")
        if not isinstance(experiments_payload, list):
            raise ValueError("invalid UNARCHI discriminating experiments")
        if not isinstance(interventions_payload, list):
            raise ValueError("invalid UNARCHI intervention trials")

        memory: list[Experience] = []
        for item in memory_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI experience")
            memory.append(Experience(**item))

        internal_goals: list[InternalGoal] = []
        for item in goals_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI internal goal")
            internal_goals.append(InternalGoal(**item))

        predictions: list[SelfPrediction] = []
        for item in predictions_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI prediction")
            predictions.append(SelfPrediction(**item))

        calibration_history: list[CalibrationRecord] = []
        for item in calibration_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI calibration record")
            calibration_history.append(CalibrationRecord(**item))

        prospective_intentions: list[ProspectiveIntention] = []
        for item in intentions_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI prospective intention")
            prospective_intentions.append(ProspectiveIntention(**item))

        arbitration_history: list[ArbitrationRecord] = []
        for item in arbitration_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI arbitration record")
            restored_item = dict(item)
            restored_item["conflicting_goals"] = tuple(
                restored_item.get("conflicting_goals", ())
            )
            restored_item["option_scores"] = tuple(
                tuple(pair) for pair in restored_item.get("option_scores", ())
            )
            restored_item["value_weights"] = tuple(
                tuple(pair) for pair in restored_item.get("value_weights", ())
            )
            restored_item["chosen_value_impacts"] = tuple(
                tuple(pair)
                for pair in restored_item.get("chosen_value_impacts", ())
            )
            restored_item["hard_constraint_violations"] = tuple(
                restored_item.get("hard_constraint_violations", ())
            )
            restored_item["correction_deltas"] = tuple(
                tuple(pair)
                for pair in restored_item.get("correction_deltas", ())
            )
            arbitration_history.append(ArbitrationRecord(**restored_item))

        causal_hypotheses: list[CausalHypothesis] = []
        for item in hypotheses_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI causal hypothesis")
            restored_item = dict(item)
            restored_item["predictions"] = tuple(
                tuple(pair) for pair in restored_item.get("predictions", ())
            )
            causal_hypotheses.append(CausalHypothesis(**restored_item))

        discriminating_experiments: list[DiscriminatingExperiment] = []
        for item in experiments_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI discriminating experiment")
            restored_item = dict(item)
            restored_item["expected_by_hypothesis"] = tuple(
                tuple(pair)
                for pair in restored_item.get("expected_by_hypothesis", ())
            )
            restored_item["confidence_updates"] = tuple(
                tuple(pair)
                for pair in restored_item.get("confidence_updates", ())
            )
            discriminating_experiments.append(
                DiscriminatingExperiment(**restored_item)
            )

        intervention_trials: list[InterventionTrial] = []
        for item in interventions_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI intervention trial")
            restored_item = dict(item)
            restored_item["expected_by_hypothesis"] = tuple(
                tuple(pair)
                for pair in restored_item.get("expected_by_hypothesis", ())
            )
            restored_item["confidence_updates"] = tuple(
                tuple(pair)
                for pair in restored_item.get("confidence_updates", ())
            )
            intervention_trials.append(InterventionTrial(**restored_item))

        max_memory = max(16, min(int(payload.get("max_memory") or 256), 4096))
        max_active = max(
            1,
            min(int(payload.get("max_active_internal_goals") or 3), 10),
        )
        return cls(
            state=UnarchiState(**state_payload),
            memory=memory[-max_memory:],
            observation_history=[str(item) for item in history_payload][-max_memory:],
            internal_goals=internal_goals[-max_memory:],
            next_internal_goal_id=max(
                int(payload.get("next_internal_goal_id") or 1),
                max((item.id for item in internal_goals), default=0) + 1,
            ),
            predictions=predictions[-max_memory:],
            calibration_history=calibration_history[-max_memory:],
            next_prediction_id=max(
                int(payload.get("next_prediction_id") or 1),
                max((item.id for item in predictions), default=0) + 1,
            ),
            prospective_intentions=prospective_intentions[-max_memory:],
            next_intention_id=max(
                int(payload.get("next_intention_id") or 1),
                max(
                    (item.id for item in prospective_intentions),
                    default=0,
                )
                + 1,
            ),
            value_weights=cls()._normalize_value_weights(
                {
                    key: float(value_weights_payload.get(key, default))
                    for key, default in _default_value_weights().items()
                }
            ),
            arbitration_history=arbitration_history[-max_memory:],
            next_arbitration_id=max(
                int(payload.get("next_arbitration_id") or 1),
                max((item.id for item in arbitration_history), default=0) + 1,
            ),
            causal_hypotheses=causal_hypotheses[-max_memory:],
            discriminating_experiments=discriminating_experiments[-max_memory:],
            next_hypothesis_id=max(
                int(payload.get("next_hypothesis_id") or 1),
                max((item.id for item in causal_hypotheses), default=0) + 1,
            ),
            next_experiment_id=max(
                int(payload.get("next_experiment_id") or 1),
                max(
                    (item.id for item in discriminating_experiments),
                    default=0,
                )
                + 1,
            ),
            intervention_trials=intervention_trials[-max_memory:],
            next_intervention_id=max(
                int(payload.get("next_intervention_id") or 1),
                max((item.id for item in intervention_trials), default=0) + 1,
            ),
            success_prediction_bias=float(
                payload.get("success_prediction_bias") or 0.0
            ),
            uncertainty_prediction_bias=float(
                payload.get("uncertainty_prediction_bias") or 0.0
            ),
            stress_prediction_bias=float(
                payload.get("stress_prediction_bias") or 0.0
            ),
            agency_prediction_bias=float(
                payload.get("agency_prediction_bias") or 0.0
            ),
            self_calibration_score=float(
                payload.get("self_calibration_score", 0.5)
            ),
            max_memory=max_memory,
            max_active_internal_goals=max_active,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": UNARCHI_VERSION,
            "state": self.state.to_dict(),
            "memory_size": len(self.memory),
            "observation_history_size": len(self.observation_history),
            "active_internal_goals": len(self.active_internal_goals()),
            "total_internal_goals": len(self.internal_goals),
            "prediction_count": len(self.predictions),
            "calibration_count": len(self.calibration_history),
            "self_calibration_score": round(self.self_calibration_score, 6),
            "pending_prospective_intentions": len(
                self.pending_prospective_intentions()
            ),
            "ready_prospective_intentions": len(
                self.ready_prospective_intentions()
            ),
            "total_prospective_intentions": len(self.prospective_intentions),
            "metacognitive_narrative_available": True,
            "value_weights": dict(self.value_weights),
            "arbitration_count": len(self.arbitration_history),
            "causal_hypothesis_count": len(self.causal_hypotheses),
            "discriminating_experiment_count": len(
                self.discriminating_experiments
            ),
            "intervention_trial_count": len(self.intervention_trials),
            "claims_phenomenal_consciousness": False,
        }
