from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import re
from typing import Any


UNARCHI_VERSION = "unarchi-v0.32"
_LEGACY_UNARCHI_VERSIONS = {"unarchi-v0.31", "unarchi-v0.30"}
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


@dataclass
class GlobalWorkspaceItem:
    id: int
    source: str
    content: str
    salience: float
    evidence_refs: tuple[str, ...] = ()
    status: str = "active"
    recurrence_count: int = 0
    max_recurrence: int = 3
    resolution_evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GlobalWorkspaceCycle:
    id: int
    selected_item_ids: tuple[int, ...]
    integrated_sources: tuple[str, ...]
    broadcast_targets: tuple[str, ...]
    recurrence_depth: int
    coherence_score: float
    decision_mode: str
    broadcast_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkspaceComparison:
    full: GlobalWorkspaceCycle
    ablated: GlobalWorkspaceCycle
    target_delta: int
    mode_changed: bool
    workspace_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CounterfactualFuture:
    id: int
    action: str
    predicted_outcome: str
    predicted_success: float
    predicted_information_gain: float
    predicted_uncertainty: float
    risk: float
    utility: float
    linked_workspace_cycle_id: int | None
    recurrence_rounds: int
    status: str = "simulated"
    observed_outcome: str | None = None
    actual_success: float | None = None
    actual_information_gain: float | None = None
    discrepancy: float | None = None
    feedback_workspace_item_id: int | None = None
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CounterfactualComparison:
    full_action: str
    ablated_action: str
    full_information_gain: float
    ablated_information_gain: float
    information_gain_delta: float
    choice_changed: bool
    simulation_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SelfSchemaEntry:
    id: int
    pattern: str
    kind: str
    confidence: float
    evidence_count: int
    success_count: int
    failure_count: int
    success_rate: float
    mean_reward: float
    success_bias: float
    risk_bias: float
    evidence_refs: tuple[str, ...] = ()
    status: str = "active"
    last_updated_experience_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfSchemaRevision:
    id: int
    schema_id: int
    prior_kind: str
    revised_kind: str
    prior_confidence: float
    revised_confidence: float
    prior_success_rate: float
    revised_success_rate: float
    contradictory_evidence_refs: tuple[str, ...]
    contradiction_ratio: float
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfSchemaRevisionComparison:
    revised_action: str
    frozen_action: str
    revised_predicted_success: float
    frozen_predicted_success: float
    predicted_success_delta: float
    choice_changed: bool
    revision_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextualSelfSchemaEntry:
    id: int
    parent_schema_id: int
    context_label: str
    context_terms: tuple[str, ...]
    pattern: str
    kind: str
    confidence: float
    evidence_count: int
    success_count: int
    failure_count: int
    success_rate: float
    mean_reward: float
    success_bias: float
    risk_bias: float
    evidence_refs: tuple[str, ...] = ()
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfSchemaDecomposition:
    id: int
    parent_schema_id: int
    context_schema_ids: tuple[int, ...]
    context_labels: tuple[str, ...]
    global_success_rate: float
    global_holdout_mae: float
    contextual_holdout_mae: float
    improvement: float
    held_out_count: int
    status: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextualSchemaComparison:
    contextual_action: str
    global_action: str
    contextual_predicted_success: float
    global_predicted_success: float
    predicted_success_delta: float
    choice_changed: bool
    contextual_schema_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextTransferBoundary:
    id: int
    parent_schema_id: int
    source_context_schema_id: int
    target_label: str
    target_terms: tuple[str, ...]
    evidence_count: int
    target_success_rate: float
    source_success_rate: float
    global_success_rate: float
    source_holdout_mae: float
    global_holdout_mae: float
    improvement: float
    transfer_strength: float
    status: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextTransferComparison:
    transfer_action: str
    no_transfer_action: str
    transfer_predicted_success: float
    no_transfer_predicted_success: float
    predicted_success_delta: float
    choice_changed: bool
    transfer_causally_active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LatentContextHypothesis:
    id: int
    parent_schema_id: int
    positive_term: str
    negative_term: str
    positive_support: int
    negative_support: int
    positive_success_rate: float
    negative_success_rate: float
    rate_contrast: float
    validation_status: str
    holdout_improvement: float
    decomposition_id: int | None
    evidence_refs: tuple[str, ...]
    causal_status: str = "unverified"
    causal_evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextCausalityTrial:
    id: int
    hypothesis_id: int
    from_context: str
    to_context: str
    controlled_signature: str
    baseline_success_rate: float
    predicted_target_success_rate: float
    risk: float
    min_samples: int
    status: str = "planned"
    observed_target_success_rate: float | None = None
    observed_signature: str | None = None
    sample_count: int = 0
    competing_variables_held_constant: bool | None = None
    predicted_direction_followed: bool | None = None
    causal_strength: float | None = None
    evidence_refs: tuple[str, ...] = ()
    reversible_only: bool = True
    paid_actions_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextCausalStabilityAssessment:
    id: int
    hypothesis_id: int
    forward_trial_ids: tuple[int, ...]
    reverse_trial_ids: tuple[int, ...]
    independent_forward_batches: int
    independent_reverse_batches: int
    forward_replication_rate: float
    reverse_replication_rate: float
    mean_causal_strength: float
    reversal_direction_followed: bool
    status: str
    confidence: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextCausalInvarianceAssessment:
    id: int
    hypothesis_id: int
    stability_assessment_ids: tuple[int, ...]
    environment_signatures: tuple[str, ...]
    distinct_environment_count: int
    stable_environment_count: int
    effect_direction_consistent: bool
    minimum_causal_strength: float
    maximum_causal_strength: float
    strength_spread: float
    status: str
    confidence: float
    boundary_signatures: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextBoundaryDiscoveryPlan:
    id: int
    hypothesis_id: int
    invariance_assessment_id: int
    candidate_signatures: tuple[str, ...]
    selected_signature: str
    selected_risk: float
    selected_information_gain: float
    selected_priority_score: float
    nearest_stable_distance: int
    nearest_boundary_distance: int | None
    changed_dimensions: tuple[str, ...]
    status: str = "planned"
    outcome_stability_assessment_id: int | None = None
    outcome_status: str | None = None
    uncertainty_reduction: float | None = None
    evidence_refs: tuple[str, ...] = ()
    reversible_only: bool = True
    paid_actions_allowed: bool = False
    external_execution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextCausalValidityMap:
    id: int
    hypothesis_id: int
    source_invariance_assessment_ids: tuple[int, ...]
    source_boundary_plan_ids: tuple[int, ...]
    signature_assessment_ids: tuple[tuple[str, int], ...]
    tested_valid_signatures: tuple[str, ...]
    tested_invalid_signatures: tuple[str, ...]
    dimensions: tuple[str, ...]
    max_generalization_distance: int
    confidence: float
    evidence_refs: tuple[str, ...]
    status: str = "active"
    parent_map_id: int | None = None
    revision_number: int = 1
    source_calibration_ids: tuple[int, ...] = ()
    calibrated_supported_signatures: tuple[str, ...] = ()
    revoked_inferred_signatures: tuple[str, ...] = ()
    revision_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityMapSelection:
    id: int
    hypothesis_id: int
    previous_map_id: int | None
    selected_map_id: int
    action: str
    reason: str
    lineage: tuple[int, ...]
    evidence_refs: tuple[str, ...]
    calibration_watermark_id: int = 0
    decision_gate_watermark_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityDegradationWatch:
    id: int
    hypothesis_id: int
    active_map_id: int
    activation_selection_id: int
    calibration_watermark_id: int
    observed_calibration_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_active_advantage: float
    recommended_map_id: int | None
    recommended_revision_number: int | None
    ancestor_support_calibration_ids: tuple[int, ...]
    status: str
    reason: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRecommendationResolution:
    id: int
    watch_id: int
    hypothesis_id: int
    decision: str
    reason: str
    recommended_map_id: int | None
    blocked_descendant_map_id: int | None
    rollback_selection_id: int | None
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRollbackValidation:
    id: int
    resolution_id: int
    watch_id: int
    hypothesis_id: int
    rollback_selection_id: int
    rollback_map_id: int
    blocked_descendant_map_id: int
    observed_outcome_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_rollback_advantage: float
    prior_degraded_advantage: float
    improvement_delta: float
    status: str
    reactivation_allowed: bool
    evidence_refs: tuple[str, ...]
    holdout_gate_watermark_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRollbackHoldoutValidation:
    id: int
    recovery_validation_id: int
    resolution_id: int
    watch_id: int
    hypothesis_id: int
    rollback_selection_id: int
    rollback_map_id: int
    blocked_descendant_map_id: int
    recovery_outcome_ids: tuple[int, ...]
    holdout_outcome_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_recovery_advantage: float
    mean_holdout_advantage: float
    prior_degraded_advantage: float
    holdout_improvement_delta: float
    recovery_to_holdout_delta: float
    status: str
    reactivation_allowed: bool
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityReactivationDriftWatch:
    id: int
    holdout_validation_id: int
    hypothesis_id: int
    reactivation_selection_id: int
    active_map_id: int
    decision_gate_watermark_id: int
    observed_outcome_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_post_reactivation_advantage: float
    holdout_advantage: float
    advantage_delta: float
    status: str
    recommended_action: str
    reason: str
    evidence_refs: tuple[str, ...]
    holdout_source: str = "initial"
    episode_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityReactivationDriftResolution:
    id: int
    drift_watch_id: int
    holdout_validation_id: int
    hypothesis_id: int
    decision: str
    reason: str
    active_map_id_before: int
    rollback_target_map_id: int | None
    rollback_selection_id: int | None
    blocked_descendant_map_id: int | None
    requires_new_evidence_cycle: bool
    evidence_refs: tuple[str, ...]
    holdout_source: str = "initial"
    episode_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRenewedRecoveryValidation:
    id: int
    drift_resolution_id: int
    drift_watch_id: int
    prior_holdout_validation_id: int
    hypothesis_id: int
    rollback_selection_id: int
    rollback_map_id: int
    blocked_descendant_map_id: int
    observed_outcome_ids: tuple[int, ...]
    excluded_prior_outcome_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_recovery_advantage: float
    prior_degraded_advantage: float
    improvement_delta: float
    status: str
    reactivation_allowed: bool
    evidence_refs: tuple[str, ...]
    holdout_gate_watermark_id: int = 0
    prior_holdout_source: str = "initial"
    episode_id: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRenewedHoldoutValidation:
    id: int
    recovery_validation_id: int
    drift_resolution_id: int
    drift_watch_id: int
    prior_holdout_validation_id: int
    hypothesis_id: int
    rollback_selection_id: int
    rollback_map_id: int
    blocked_descendant_map_id: int
    recovery_outcome_ids: tuple[int, ...]
    holdout_outcome_ids: tuple[int, ...]
    excluded_prior_outcome_ids: tuple[int, ...]
    degraded_signatures: tuple[str, ...]
    mean_recovery_advantage: float
    mean_holdout_advantage: float
    prior_degraded_advantage: float
    holdout_improvement_delta: float
    recovery_to_holdout_delta: float
    status: str
    reactivation_allowed: bool
    evidence_refs: tuple[str, ...]
    prior_holdout_source: str = "initial"
    episode_id: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityClassification:
    map_id: int
    hypothesis_id: int
    environment_signature: str
    status: str
    nearest_valid_distance: int | None
    nearest_invalid_distance: int | None
    confidence: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityDecisionGate:
    id: int
    validity_map_id: int
    hypothesis_id: int
    environment_signature: str
    classification_status: str
    classification_confidence: float
    causal_context_allowed: bool
    gated_action: str
    gated_predicted_success: float
    causal_enabled_action: str
    causal_enabled_predicted_success: float
    causal_ablated_action: str
    causal_ablated_predicted_success: float
    gated_matches_expected_path: bool
    choice_changed_vs_causal_enabled: bool
    choice_changed_vs_causal_ablated: bool
    predicted_success_delta_vs_ablated: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityGateOutcome:
    id: int
    gate_id: int
    validity_map_id: int
    environment_signature: str
    actual_success_by_action: tuple[tuple[str, bool], ...]
    gated_error: float
    causal_enabled_error: float
    causal_ablated_error: float
    alternative_error: float
    gated_advantage_vs_alternative: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextValidityRegionCalibration:
    id: int
    validity_map_id: int
    hypothesis_id: int
    environment_signature: str
    source_classification_status: str
    outcome_ids: tuple[int, ...]
    sample_count: int
    mean_gated_error: float
    mean_causal_enabled_error: float
    mean_causal_ablated_error: float
    mean_alternative_error: float
    gated_advantage_vs_alternative: float
    status: str
    confidence_delta: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LatentContextDiscovery:
    id: int
    parent_schema_id: int
    hypothesis_ids: tuple[int, ...]
    proposed_count: int
    validated_count: int
    selected_hypothesis_id: int | None
    selected_decomposition_id: int | None
    status: str
    evidence_refs: tuple[str, ...]

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

    v0.32 includes causal internal dynamics, bounded endogenous goals, a
    calibrated predictive self-model, prospective memory, evidence-grounded
    metacognition, explicit value arbitration, competing causal hypotheses,
    controlled self-intervention trials, a bounded recurrent global workspace,
    counterfactual future simulation with prediction-error feedback, a compact
    autobiographical self-schema, contradiction-driven revision, validated
    context decomposition, transfer boundaries, conservative latent context
    discovery, intervention-supported context causality evidence, replicated
    reversible context-causality stability checks, bounded causal-invariance
    tests across distinct controlled environments, active low-risk boundary
    probe planning, compact boundary-aware causal validity maps,
    validity-gated causal-context decision use, evidence-backed gate outcome
    calibration, immutable calibration-aware validity-map revisions,
    lineage-checked active revision selection with auditable rollback,
    evidence-triggered active-revision degradation recommendations, explicit
    recommendation resolution, separate rollback recovery/holdout gates,
    post-reactivation drift monitoring, and renewed-degradation resolution
    that invalidates stale reactivation authorization after a second rollback,
    plus renewed recovery and independent holdout cycles that carry immutable
    episode identities, bind each recurrence to its newest confirmed holdout,
    and forbid evidence or reactivation authorization from leaking across
    repeated degradation/recovery episodes.
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
    global_workspace_items: list[GlobalWorkspaceItem] = field(default_factory=list)
    global_workspace_cycles: list[GlobalWorkspaceCycle] = field(default_factory=list)
    next_workspace_item_id: int = 1
    next_workspace_cycle_id: int = 1
    workspace_recurrence_limit: int = 3
    counterfactual_futures: list[CounterfactualFuture] = field(default_factory=list)
    next_counterfactual_id: int = 1
    max_counterfactual_futures: int = 4
    self_schema: list[SelfSchemaEntry] = field(default_factory=list)
    next_self_schema_id: int = 1
    max_self_schema_entries: int = 32
    self_schema_revisions: list[SelfSchemaRevision] = field(default_factory=list)
    next_self_schema_revision_id: int = 1
    contextual_self_schema: list[ContextualSelfSchemaEntry] = field(
        default_factory=list
    )
    next_contextual_self_schema_id: int = 1
    self_schema_decompositions: list[SelfSchemaDecomposition] = field(
        default_factory=list
    )
    next_self_schema_decomposition_id: int = 1
    context_transfer_boundaries: list[ContextTransferBoundary] = field(
        default_factory=list
    )
    next_context_transfer_boundary_id: int = 1
    latent_context_hypotheses: list[LatentContextHypothesis] = field(
        default_factory=list
    )
    next_latent_context_hypothesis_id: int = 1
    latent_context_discoveries: list[LatentContextDiscovery] = field(
        default_factory=list
    )
    next_latent_context_discovery_id: int = 1
    context_causality_trials: list[ContextCausalityTrial] = field(
        default_factory=list
    )
    next_context_causality_trial_id: int = 1
    context_causal_stability_assessments: list[
        ContextCausalStabilityAssessment
    ] = field(default_factory=list)
    next_context_causal_stability_assessment_id: int = 1
    context_causal_invariance_assessments: list[
        ContextCausalInvarianceAssessment
    ] = field(default_factory=list)
    next_context_causal_invariance_assessment_id: int = 1
    context_boundary_discovery_plans: list[
        ContextBoundaryDiscoveryPlan
    ] = field(default_factory=list)
    next_context_boundary_discovery_plan_id: int = 1
    context_causal_validity_maps: list[
        ContextCausalValidityMap
    ] = field(default_factory=list)
    next_context_causal_validity_map_id: int = 1
    context_validity_decision_gates: list[
        ContextValidityDecisionGate
    ] = field(default_factory=list)
    next_context_validity_decision_gate_id: int = 1
    context_validity_gate_outcomes: list[
        ContextValidityGateOutcome
    ] = field(default_factory=list)
    next_context_validity_gate_outcome_id: int = 1
    context_validity_region_calibrations: list[
        ContextValidityRegionCalibration
    ] = field(default_factory=list)
    next_context_validity_region_calibration_id: int = 1
    active_context_validity_map_ids: dict[int, int] = field(default_factory=dict)
    context_validity_map_selection_history: list[
        ContextValidityMapSelection
    ] = field(default_factory=list)
    next_context_validity_map_selection_id: int = 1
    context_validity_degradation_watches: list[
        ContextValidityDegradationWatch
    ] = field(default_factory=list)
    next_context_validity_degradation_watch_id: int = 1
    context_validity_recommendation_resolutions: list[
        ContextValidityRecommendationResolution
    ] = field(default_factory=list)
    next_context_validity_recommendation_resolution_id: int = 1
    context_validity_rollback_validations: list[
        ContextValidityRollbackValidation
    ] = field(default_factory=list)
    next_context_validity_rollback_validation_id: int = 1
    context_validity_rollback_holdout_validations: list[
        ContextValidityRollbackHoldoutValidation
    ] = field(default_factory=list)
    next_context_validity_rollback_holdout_validation_id: int = 1
    context_validity_reactivation_drift_watches: list[
        ContextValidityReactivationDriftWatch
    ] = field(default_factory=list)
    next_context_validity_reactivation_drift_watch_id: int = 1
    context_validity_reactivation_drift_resolutions: list[
        ContextValidityReactivationDriftResolution
    ] = field(default_factory=list)
    next_context_validity_reactivation_drift_resolution_id: int = 1
    context_validity_renewed_recovery_validations: list[
        ContextValidityRenewedRecoveryValidation
    ] = field(default_factory=list)
    next_context_validity_renewed_recovery_validation_id: int = 1
    context_validity_renewed_holdout_validations: list[
        ContextValidityRenewedHoldoutValidation
    ] = field(default_factory=list)
    next_context_validity_renewed_holdout_validation_id: int = 1
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
        context: str = "",
        use_self_schema: bool = True,
        use_contextual_schema: bool = True,
        use_context_transfer: bool = True,
    ) -> SelfPrediction:
        """
        Predict external success and internal consequences before an action.

        v0.12 can transfer bounded evidence from the autobiographical self-schema.
        Passing use_self_schema=False provides the longitudinal-transfer ablation.
        """
        expected_success = _clamp(expected_success)
        expected_information_gain = _clamp(expected_information_gain)
        risk = _clamp(risk)

        schema_success_bias = 0.0
        schema_risk_bias = 0.0
        if use_self_schema:
            (
                schema_success_bias,
                schema_risk_bias,
                _,
            ) = self.self_schema_adjustment(
                context=context,
                action=action,
                use_contextual_schema=use_contextual_schema,
                use_context_transfer=use_context_transfer,
            )

        effective_risk = _clamp(risk + schema_risk_bias)
        predicted_success = _clamp(
            expected_success
            + self.success_prediction_bias
            + schema_success_bias
        )
        predicted_information_gain = expected_information_gain

        predicted_uncertainty = _clamp(
            self.state.uncertainty
            - (expected_information_gain * 0.45)
            + (effective_risk * 0.12)
            + self.uncertainty_prediction_bias
        )
        predicted_stress = _clamp(
            self.state.stress
            + (effective_risk * 0.30)
            - (predicted_success * 0.08)
            + self.stress_prediction_bias
        )
        predicted_agency = _clamp(
            self.state.agency
            + (predicted_success * 0.10)
            - (effective_risk * 0.08)
            + self.agency_prediction_bias
        )
        predicted_coherence = _clamp(
            self.state.coherence
            + (expected_information_gain * 0.12)
            - (effective_risk * 0.05)
        )

        irreversibility_penalty = 0.35 if not reversible else 0.0
        utility = (
            (predicted_success * 0.36)
            + (predicted_information_gain * 0.28)
            + (predicted_agency * 0.12)
            + (predicted_coherence * 0.09)
            - (effective_risk * 0.08)
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
            risk=round(effective_risk, 6),
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
        *,
        context: str = "",
        use_self_schema: bool = True,
        use_contextual_schema: bool = True,
        use_context_transfer: bool = True,
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
                context=str(candidate.get("context") or context),
                use_self_schema=use_self_schema,
                use_contextual_schema=use_contextual_schema,
                use_context_transfer=use_context_transfer,
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

    def stage_global_workspace_item(
        self,
        *,
        source: str,
        content: str,
        salience: float,
        evidence_refs: tuple[str, ...] = (),
    ) -> GlobalWorkspaceItem:
        """Stage bounded evidence for possible global broadcast."""
        source = source.strip().casefold()
        content = content.strip()
        allowed_sources = {
            "state",
            "memory",
            "goal",
            "self_model",
            "world_model",
            "intention",
            "arbitration",
            "intervention",
            "self_schema",
        }
        if source not in allowed_sources:
            raise ValueError("unsupported global workspace source")
        if not content:
            raise ValueError("global workspace content is required")

        for item in self.global_workspace_items:
            if (
                item.status == "active"
                and item.source == source
                and _similarity(item.content, content) >= 0.85
            ):
                item.salience = max(item.salience, _clamp(salience))
                if evidence_refs:
                    item.evidence_refs = tuple(
                        dict.fromkeys(item.evidence_refs + tuple(evidence_refs))
                    )
                return item

        item = GlobalWorkspaceItem(
            id=self.next_workspace_item_id,
            source=source,
            content=content[:500],
            salience=round(_clamp(salience), 6),
            evidence_refs=tuple(str(ref)[:160] for ref in evidence_refs),
            max_recurrence=max(1, min(self.workspace_recurrence_limit, 8)),
        )
        self.next_workspace_item_id += 1
        self.global_workspace_items.append(item)
        if len(self.global_workspace_items) > self.max_memory:
            self.global_workspace_items = self.global_workspace_items[-self.max_memory:]
        return item

    def seed_global_workspace(self) -> tuple[GlobalWorkspaceItem, ...]:
        """Stage current evidence from the major cognitive modules."""
        staged: list[GlobalWorkspaceItem] = []
        state_salience = max(
            self.state.uncertainty,
            self.state.prediction_error,
            self.state.stress,
            self.state.goal_pressure,
        )
        staged.append(
            self.stage_global_workspace_item(
                source="state",
                content=(
                    f"uncertainty={self.state.uncertainty:.3f}; "
                    f"prediction_error={self.state.prediction_error:.3f}; "
                    f"stress={self.state.stress:.3f}; "
                    f"goal_pressure={self.state.goal_pressure:.3f}"
                ),
                salience=state_salience,
                evidence_refs=("state:current",),
            )
        )

        if self.memory:
            item = self.memory[-1]
            staged.append(
                self.stage_global_workspace_item(
                    source="memory",
                    content=(
                        f"latest outcome={item.outcome}; success={item.success}; "
                        f"prediction_error={item.prediction_error:.3f}"
                    ),
                    salience=max(0.35, item.prediction_error),
                    evidence_refs=(f"experience:{len(self.memory) - 1}",),
                )
            )

        active_goal = self.next_internal_goal()
        if active_goal is not None:
            staged.append(
                self.stage_global_workspace_item(
                    source="goal",
                    content=active_goal.question,
                    salience=active_goal.priority,
                    evidence_refs=(f"internal_goal:{active_goal.id - 1}",),
                )
            )

        if self.predictions:
            prediction = self.predictions[-1]
            staged.append(
                self.stage_global_workspace_item(
                    source="self_model",
                    content=(
                        f"action={prediction.action}; "
                        f"predicted_success={prediction.predicted_success:.3f}; "
                        f"utility={prediction.utility:.3f}"
                    ),
                    salience=max(
                        0.30,
                        1.0 - self.self_calibration_score,
                        prediction.risk,
                    ),
                    evidence_refs=(f"prediction:{len(self.predictions) - 1}",),
                )
            )

        active_schema = self.active_self_schema()
        if active_schema:
            schema = active_schema[0]
            staged.append(
                self.stage_global_workspace_item(
                    source="self_schema",
                    content=(
                        f"kind={schema.kind}; pattern={schema.pattern}; "
                        f"confidence={schema.confidence:.3f}; "
                        f"success_bias={schema.success_bias:+.3f}; "
                        f"risk_bias={schema.risk_bias:+.3f}"
                    ),
                    salience=max(0.30, schema.confidence),
                    evidence_refs=(f"self_schema:{schema.id}",),
                )
            )

        leading = self.leading_causal_hypothesis()
        if leading is not None:
            staged.append(
                self.stage_global_workspace_item(
                    source="world_model",
                    content=(
                        f"scope={leading.scope}; hypothesis={leading.statement}; "
                        f"confidence={leading.confidence:.3f}"
                    ),
                    salience=max(0.30, leading.confidence),
                    evidence_refs=(
                        f"hypothesis:{self.causal_hypotheses.index(leading)}",
                    ),
                )
            )

        ready_intentions = self.ready_prospective_intentions()
        if ready_intentions:
            intention = ready_intentions[0]
            staged.append(
                self.stage_global_workspace_item(
                    source="intention",
                    content=(
                        f"condition={intention.condition}; "
                        f"intended_action={intention.intended_action}"
                    ),
                    salience=0.90,
                    evidence_refs=(
                        f"intention:{self.prospective_intentions.index(intention)}",
                    ),
                )
            )

        if self.arbitration_history:
            arbitration = self.arbitration_history[-1]
            staged.append(
                self.stage_global_workspace_item(
                    source="arbitration",
                    content=(
                        f"chosen_action={arbitration.chosen_action}; "
                        f"chosen_goal={arbitration.chosen_goal}; "
                        f"status={arbitration.status}"
                    ),
                    salience=0.72,
                    evidence_refs=(
                        f"arbitration:{len(self.arbitration_history) - 1}",
                    ),
                )
            )

        if self.intervention_trials:
            intervention = self.intervention_trials[-1]
            staged.append(
                self.stage_global_workspace_item(
                    source="intervention",
                    content=(
                        f"action={intervention.action}; "
                        f"attribution={intervention.attribution}; "
                        f"status={intervention.status}"
                    ),
                    salience=max(0.45, intervention.evidence_strength or 0.0),
                    evidence_refs=(
                        f"intervention:{len(self.intervention_trials) - 1}",
                    ),
                )
            )

        return tuple(staged)

    def run_global_workspace_cycle(
        self,
        *,
        max_items: int = 4,
        broadcast: bool = True,
        seed_from_engine: bool = True,
    ) -> GlobalWorkspaceCycle:
        """Run one bounded recurrent selection-and-broadcast cycle."""
        if seed_from_engine:
            self.seed_global_workspace()

        max_items = max(1, min(int(max_items), 8))
        active = [
            item
            for item in self.global_workspace_items
            if item.status == "active"
        ]
        ranked = sorted(
            active,
            key=lambda item: (
                item.salience + min(0.12, item.recurrence_count * 0.04),
                -item.id,
            ),
            reverse=True,
        )

        selected: list[GlobalWorkspaceItem] = []
        used_sources: set[str] = set()
        for item in ranked:
            if item.source in used_sources:
                continue
            selected.append(item)
            used_sources.add(item.source)
            if len(selected) >= max_items:
                break
        if len(selected) < max_items:
            for item in ranked:
                if item in selected:
                    continue
                selected.append(item)
                if len(selected) >= max_items:
                    break

        for item in selected:
            item.recurrence_count += 1
            if item.recurrence_count >= item.max_recurrence:
                item.status = "retired"

        integrated_sources = tuple(dict.fromkeys(item.source for item in selected))
        all_targets = (
            "state",
            "memory",
            "goal",
            "self_model",
            "world_model",
            "intention",
            "arbitration",
            "intervention",
        )
        broadcast_targets = all_targets if broadcast and selected else ()
        if broadcast and len(integrated_sources) >= 3:
            decision_mode = "integrated"
        elif broadcast and len(integrated_sources) >= 2:
            decision_mode = "partial"
        else:
            decision_mode = "local"

        evidence_items = sum(bool(item.evidence_refs) for item in selected)
        source_score = min(1.0, len(integrated_sources) / 4.0)
        evidence_score = evidence_items / len(selected) if selected else 0.0
        coherence_score = _clamp(
            (source_score * 0.70) + (evidence_score * 0.30)
        )
        recurrence_depth = max(
            (item.recurrence_count for item in selected),
            default=0,
        )

        cycle = GlobalWorkspaceCycle(
            id=self.next_workspace_cycle_id,
            selected_item_ids=tuple(item.id for item in selected),
            integrated_sources=integrated_sources,
            broadcast_targets=broadcast_targets,
            recurrence_depth=recurrence_depth,
            coherence_score=round(coherence_score, 6),
            decision_mode=decision_mode,
            broadcast_enabled=bool(broadcast),
        )
        self.next_workspace_cycle_id += 1
        self.global_workspace_cycles.append(cycle)
        if len(self.global_workspace_cycles) > self.max_memory:
            self.global_workspace_cycles = self.global_workspace_cycles[-self.max_memory:]
        return cycle

    def resolve_global_workspace_item(
        self,
        item_id: int,
        *,
        evidence: str,
    ) -> GlobalWorkspaceItem:
        item = next(
            (
                candidate
                for candidate in self.global_workspace_items
                if candidate.id == item_id
            ),
            None,
        )
        if item is None:
            raise ValueError("unknown global workspace item")
        if item.status not in {"active", "retired"}:
            raise ValueError("global workspace item is already resolved")
        item.status = "resolved"
        item.resolution_evidence = evidence.strip()[:600] or None
        return item

    def compare_global_workspace_ablation(
        self,
        *,
        max_items: int = 4,
        seed_from_engine: bool = True,
    ) -> WorkspaceComparison:
        """Compare one workspace cycle with broadcast enabled and ablated."""
        full_engine = deepcopy(self)
        ablated_engine = deepcopy(self)
        full = full_engine.run_global_workspace_cycle(
            max_items=max_items,
            broadcast=True,
            seed_from_engine=seed_from_engine,
        )
        ablated = ablated_engine.run_global_workspace_cycle(
            max_items=max_items,
            broadcast=False,
            seed_from_engine=seed_from_engine,
        )
        target_delta = len(full.broadcast_targets) - len(ablated.broadcast_targets)
        mode_changed = full.decision_mode != ablated.decision_mode
        active = (
            target_delta > 0
            and mode_changed
            and len(full.integrated_sources) >= 2
        )
        return WorkspaceComparison(
            full=full,
            ablated=ablated,
            target_delta=target_delta,
            mode_changed=mode_changed,
            workspace_causally_active=active,
        )

    def simulate_counterfactual_futures(
        self,
        candidates: list[dict[str, Any]],
        *,
        max_futures: int | None = None,
        recurrence_rounds: int = 2,
        use_workspace: bool = True,
    ) -> tuple[CounterfactualFuture, ...]:
        """
        Simulate bounded reversible futures without executing an action.

        The recurrent workspace can refine predicted information gain and
        uncertainty, but simulation never performs paid or irreversible work.
        """
        limit = max_futures if max_futures is not None else self.max_counterfactual_futures
        limit = max(1, min(int(limit), self.max_counterfactual_futures, 8))
        recurrence_rounds = max(0, min(int(recurrence_rounds), 3))

        workspace_cycle: GlobalWorkspaceCycle | None = None
        if use_workspace:
            if self.global_workspace_cycles:
                workspace_cycle = self.global_workspace_cycles[-1]
            elif self.global_workspace_items:
                workspace_cycle = self.run_global_workspace_cycle(
                    max_items=4,
                    broadcast=True,
                    seed_from_engine=False,
                )
            else:
                workspace_cycle = self.run_global_workspace_cycle(
                    max_items=4,
                    broadcast=True,
                    seed_from_engine=True,
                )

        coherence = workspace_cycle.coherence_score if workspace_cycle else 0.0
        linked_cycle_id = workspace_cycle.id if workspace_cycle else None
        simulated: list[CounterfactualFuture] = []

        for candidate in candidates:
            action = str(candidate.get("action") or "").strip()
            predicted_outcome = str(
                candidate.get("predicted_outcome") or ""
            ).strip()
            if not action or not predicted_outcome:
                continue

            reversible = bool(candidate.get("reversible", True))
            external_cost = max(
                0.0,
                float(candidate.get("external_cost_usd", 0.0)),
            )
            risk = _clamp(float(candidate.get("risk", 0.0)))
            if not reversible or external_cost > 0.0 or risk > 0.50:
                continue

            expected_success = _clamp(
                float(candidate.get("expected_success", 0.5))
            )
            information_gain = _clamp(
                float(candidate.get("expected_information_gain", 0.0))
            )
            recurrence_bonus = (
                min(0.15, (coherence * 0.06) + (recurrence_rounds * 0.03))
                if use_workspace
                else 0.0
            )
            predicted_success = _clamp(
                expected_success
                + (self.success_prediction_bias * 0.25)
                + (recurrence_bonus * 0.20)
            )
            predicted_information_gain = _clamp(
                information_gain + recurrence_bonus
            )
            predicted_uncertainty = _clamp(
                self.state.uncertainty
                - (predicted_information_gain * 0.45)
                + (risk * 0.10)
            )
            utility = (
                (predicted_success * 0.42)
                + (predicted_information_gain * 0.38)
                + (coherence * 0.10)
                - (risk * 0.25)
                - (predicted_uncertainty * 0.08)
            )
            future = CounterfactualFuture(
                id=self.next_counterfactual_id,
                action=action[:240],
                predicted_outcome=predicted_outcome[:500],
                predicted_success=round(predicted_success, 6),
                predicted_information_gain=round(
                    predicted_information_gain,
                    6,
                ),
                predicted_uncertainty=round(predicted_uncertainty, 6),
                risk=round(risk, 6),
                utility=round(utility, 6),
                linked_workspace_cycle_id=linked_cycle_id,
                recurrence_rounds=recurrence_rounds if use_workspace else 0,
            )
            self.next_counterfactual_id += 1
            simulated.append(future)
            self.counterfactual_futures.append(future)
            if len(simulated) >= limit:
                break

        if not simulated:
            raise ValueError(
                "no reversible zero-cost bounded counterfactual future available"
            )

        if len(self.counterfactual_futures) > self.max_memory:
            self.counterfactual_futures = self.counterfactual_futures[
                -self.max_memory:
            ]
        return tuple(
            sorted(
                simulated,
                key=lambda item: (item.utility, -item.risk, -item.id),
                reverse=True,
            )
        )

    def observe_counterfactual_future(
        self,
        future_id: int,
        *,
        observed_outcome: str,
        actual_success: bool,
        actual_information_gain: float,
    ) -> CounterfactualFuture:
        """Compare a simulated future with reality and feed error to workspace."""
        future = next(
            (
                item
                for item in self.counterfactual_futures
                if item.id == future_id
            ),
            None,
        )
        if future is None:
            raise ValueError("unknown counterfactual future")
        if future.status != "simulated":
            raise ValueError("counterfactual future has already been observed")

        observed_outcome = observed_outcome.strip()
        if not observed_outcome:
            raise ValueError("observed counterfactual outcome is required")

        actual_success_value = 1.0 if actual_success else 0.0
        actual_information_gain = _clamp(float(actual_information_gain))
        success_error = abs(actual_success_value - future.predicted_success)
        information_error = abs(
            actual_information_gain - future.predicted_information_gain
        )
        outcome_error = 1.0 - _similarity(
            future.predicted_outcome,
            observed_outcome,
        )
        discrepancy = _clamp(
            (success_error * 0.40)
            + (information_error * 0.30)
            + (outcome_error * 0.30)
        )

        future.status = "observed"
        future.observed_outcome = observed_outcome[:500]
        future.actual_success = actual_success_value
        future.actual_information_gain = round(actual_information_gain, 6)
        future.discrepancy = round(discrepancy, 6)

        index = self.counterfactual_futures.index(future)
        feedback = self.stage_global_workspace_item(
            source="self_model",
            content=(
                f"counterfactual action={future.action}; "
                f"predicted_outcome={future.predicted_outcome}; "
                f"observed_outcome={future.observed_outcome}; "
                f"discrepancy={future.discrepancy:.3f}"
            ),
            salience=max(0.25, discrepancy),
            evidence_refs=(f"counterfactual:{index}",),
        )
        future.feedback_workspace_item_id = feedback.id
        return future

    def compare_counterfactual_ablation(
        self,
        candidates: list[dict[str, Any]],
        *,
        recurrence_rounds: int = 2,
    ) -> CounterfactualComparison:
        """
        Compare recurrent counterfactual selection with direct act-now choice.

        The ablated path chooses from immediate expected success and risk only.
        """
        full_engine = deepcopy(self)
        futures = full_engine.simulate_counterfactual_futures(
            candidates,
            recurrence_rounds=recurrence_rounds,
            use_workspace=True,
        )
        full = futures[0]

        viable: list[tuple[float, int, dict[str, Any]]] = []
        for index, candidate in enumerate(candidates):
            action = str(candidate.get("action") or "").strip()
            if not action:
                continue
            reversible = bool(candidate.get("reversible", True))
            external_cost = max(
                0.0,
                float(candidate.get("external_cost_usd", 0.0)),
            )
            risk = _clamp(float(candidate.get("risk", 0.0)))
            if not reversible or external_cost > 0.0 or risk > 0.50:
                continue
            expected_success = _clamp(
                float(candidate.get("expected_success", 0.5))
            )
            direct_score = expected_success - (risk * 0.25)
            viable.append((direct_score, -index, candidate))

        if not viable:
            raise ValueError("no bounded candidate available for ablation")

        _, _, ablated = max(
            viable,
            key=lambda item: (item[0], item[1]),
        )
        ablated_action = str(ablated.get("action") or "").strip()[:240]
        ablated_information_gain = _clamp(
            float(ablated.get("expected_information_gain", 0.0))
        )
        information_gain_delta = (
            full.predicted_information_gain - ablated_information_gain
        )
        choice_changed = full.action != ablated_action
        active = choice_changed and information_gain_delta > 0.05

        return CounterfactualComparison(
            full_action=full.action,
            ablated_action=ablated_action,
            full_information_gain=full.predicted_information_gain,
            ablated_information_gain=round(ablated_information_gain, 6),
            information_gain_delta=round(information_gain_delta, 6),
            choice_changed=choice_changed,
            simulation_causally_active=active,
        )


    def active_self_schema(self) -> tuple[SelfSchemaEntry, ...]:
        return tuple(
            sorted(
                (item for item in self.self_schema if item.status == "active"),
                key=lambda item: (-item.confidence, item.id),
            )
        )

    def consolidate_self_schema(
        self,
        *,
        min_evidence: int = 2,
        similarity_threshold: float = 0.28,
    ) -> tuple[SelfSchemaEntry, ...]:
        """
        Consolidate repeated autobiographical evidence into a compact self-schema.

        The schema is reconstructed from stored evidence rather than generated by
        a language model. Re-running consolidation over the same evidence is
        idempotent: entries are revised from the underlying records instead of
        double-counting them.
        """
        min_evidence = max(2, min(int(min_evidence), 12))
        similarity_threshold = _clamp(similarity_threshold, 0.10, 0.90)
        eligible = [
            (index, item)
            for index, item in enumerate(self.memory)
            if item.success is not None
        ]

        clusters: list[dict[str, Any]] = []
        for index, experience in eligible:
            signature = f"{experience.goal} {experience.action}".strip()
            best_cluster: dict[str, Any] | None = None
            best_score = 0.0
            for cluster in clusters:
                score = _similarity(signature, str(cluster["signature"]))
                if score > best_score:
                    best_score = score
                    best_cluster = cluster
            if best_cluster is not None and best_score >= similarity_threshold:
                best_cluster["items"].append((index, experience))
            else:
                clusters.append(
                    {
                        "signature": signature,
                        "items": [(index, experience)],
                    }
                )

        existing = list(self.self_schema)
        used_ids: set[int] = set()
        active: list[SelfSchemaEntry] = []

        for cluster in clusters:
            records: list[tuple[int, Experience]] = cluster["items"]
            if len(records) < min_evidence:
                continue

            pattern = str(cluster["signature"])[:400]
            successes = sum(1 for _, item in records if item.success is True)
            failures = sum(1 for _, item in records if item.success is False)
            evidence_count = successes + failures
            if evidence_count < min_evidence:
                continue

            success_rate = successes / evidence_count
            mean_reward = sum(item.reward for _, item in records) / evidence_count
            if success_rate >= 0.75:
                kind = "capability"
            elif success_rate <= 0.35:
                kind = "limitation"
            else:
                kind = "mixed"

            evidence_refs = [f"experience:{index}" for index, _ in records]
            auxiliary_refs: list[str] = []

            for index, item in enumerate(self.calibration_history):
                if _similarity(item.action, pattern) >= 0.25:
                    auxiliary_refs.append(f"calibration:{index}")

            for index, item in enumerate(self.intervention_trials):
                if (
                    item.status == "observed"
                    and _similarity(item.action, pattern) >= 0.25
                ):
                    auxiliary_refs.append(f"intervention:{index}")

            for index, item in enumerate(self.counterfactual_futures):
                if (
                    item.status == "observed"
                    and _similarity(item.action, pattern) >= 0.25
                ):
                    auxiliary_refs.append(f"counterfactual:{index}")

            for index, cycle in enumerate(self.global_workspace_cycles):
                related = False
                for item_id in cycle.selected_item_ids:
                    workspace_item = next(
                        (
                            candidate
                            for candidate in self.global_workspace_items
                            if candidate.id == item_id
                        ),
                        None,
                    )
                    if (
                        workspace_item is not None
                        and _similarity(workspace_item.content, pattern) >= 0.20
                    ):
                        related = True
                        break
                if related:
                    auxiliary_refs.append(f"workspace_cycle:{index}")

            evidence_refs = list(
                dict.fromkeys(evidence_refs + auxiliary_refs)
            )
            consistency = max(success_rate, 1.0 - success_rate)
            confidence = _clamp(
                0.25
                + min(0.45, evidence_count * 0.10)
                + min(0.18, len(auxiliary_refs) * 0.04)
                + (consistency * 0.10),
                0.0,
                0.98,
            )
            success_bias = max(
                -0.22,
                min(
                    0.22,
                    (success_rate - 0.5) * 0.44 * confidence,
                ),
            )
            risk_bias = max(
                -0.16,
                min(
                    0.16,
                    (0.5 - success_rate) * 0.32 * confidence,
                ),
            )

            match: SelfSchemaEntry | None = None
            best_match = 0.0
            for candidate in existing:
                if candidate.id in used_ids:
                    continue
                score = _similarity(pattern, candidate.pattern)
                if score > best_match:
                    best_match = score
                    match = candidate
            if match is None or best_match < 0.55:
                match = SelfSchemaEntry(
                    id=self.next_self_schema_id,
                    pattern=pattern,
                    kind=kind,
                    confidence=round(confidence, 6),
                    evidence_count=evidence_count,
                    success_count=successes,
                    failure_count=failures,
                    success_rate=round(success_rate, 6),
                    mean_reward=round(mean_reward, 6),
                    success_bias=round(success_bias, 6),
                    risk_bias=round(risk_bias, 6),
                    evidence_refs=tuple(evidence_refs),
                    last_updated_experience_count=self.state.experience_count,
                )
                self.next_self_schema_id += 1
                self.self_schema.append(match)
                existing.append(match)
            else:
                match.pattern = pattern
                match.kind = kind
                match.confidence = round(confidence, 6)
                match.evidence_count = evidence_count
                match.success_count = successes
                match.failure_count = failures
                match.success_rate = round(success_rate, 6)
                match.mean_reward = round(mean_reward, 6)
                match.success_bias = round(success_bias, 6)
                match.risk_bias = round(risk_bias, 6)
                match.evidence_refs = tuple(evidence_refs)
                match.status = "active"
                match.last_updated_experience_count = self.state.experience_count

            used_ids.add(match.id)
            active.append(match)

        for item in self.self_schema:
            if item.id not in used_ids:
                item.status = "retired"

        if len(self.self_schema) > self.max_self_schema_entries:
            keep = sorted(
                self.self_schema,
                key=lambda item: (
                    item.status == "active",
                    item.confidence,
                    item.last_updated_experience_count,
                    -item.id,
                ),
                reverse=True,
            )[: self.max_self_schema_entries]
            self.self_schema = sorted(keep, key=lambda item: item.id)

        return tuple(
            sorted(
                (item for item in self.self_schema if item.status == "active"),
                key=lambda item: (-item.confidence, item.id),
            )
        )


    def _matching_schema_experiences(
        self,
        schema: SelfSchemaEntry,
        *,
        similarity_threshold: float = 0.28,
    ) -> list[tuple[int, Experience]]:
        threshold = _clamp(similarity_threshold, 0.10, 0.90)
        matches: list[tuple[int, Experience]] = []
        for index, experience in enumerate(self.memory):
            if experience.success is None:
                continue
            signature = f"{experience.goal} {experience.action}".strip()
            if _similarity(signature, schema.pattern) >= threshold:
                matches.append((index, experience))
        return matches

    def reconcile_self_schema_contradiction(
        self,
        schema_id: int,
        *,
        min_contradictory_evidence: int = 2,
        similarity_threshold: float = 0.28,
    ) -> SelfSchemaRevision:
        """
        Revise one established self-schema when new evidence contradicts it.

        Only autobiographical experiences not already cited by the schema count as
        new contradiction evidence. The schema is then rebuilt from the complete
        evidence set, preventing selective retention of the old self-description.
        """
        target = next(
            (item for item in self.self_schema if item.id == schema_id),
            None,
        )
        if target is None:
            raise ValueError("unknown self schema")
        if target.status != "active":
            raise ValueError("self schema is not active")
        if target.kind not in {"capability", "limitation"}:
            raise ValueError("only directional self schemas can be contradicted")

        min_contradictory_evidence = max(
            1,
            min(int(min_contradictory_evidence), 12),
        )
        prior_refs = set(target.evidence_refs)
        new_matches = [
            (index, experience)
            for index, experience in self._matching_schema_experiences(
                target,
                similarity_threshold=similarity_threshold,
            )
            if f"experience:{index}" not in prior_refs
        ]
        if target.kind == "capability":
            contradictions = [
                (index, experience)
                for index, experience in new_matches
                if experience.success is False
            ]
        else:
            contradictions = [
                (index, experience)
                for index, experience in new_matches
                if experience.success is True
            ]

        contradiction_refs = tuple(
            f"experience:{index}" for index, _ in contradictions
        )
        new_evidence_count = len(new_matches)
        contradiction_ratio = (
            len(contradictions) / new_evidence_count
            if new_evidence_count
            else 0.0
        )
        prior_kind = target.kind
        prior_confidence = target.confidence
        prior_success_rate = target.success_rate

        if len(contradictions) < min_contradictory_evidence:
            revision = SelfSchemaRevision(
                id=self.next_self_schema_revision_id,
                schema_id=target.id,
                prior_kind=prior_kind,
                revised_kind=prior_kind,
                prior_confidence=prior_confidence,
                revised_confidence=prior_confidence,
                prior_success_rate=prior_success_rate,
                revised_success_rate=prior_success_rate,
                contradictory_evidence_refs=contradiction_refs,
                contradiction_ratio=round(contradiction_ratio, 6),
                status="insufficient_evidence",
                reason=(
                    "Contradictory evidence did not reach the bounded revision "
                    "threshold."
                ),
            )
            self.next_self_schema_revision_id += 1
            self.self_schema_revisions.append(revision)
            return revision

        self.consolidate_self_schema(
            min_evidence=2,
            similarity_threshold=similarity_threshold,
        )
        revised = next(
            (item for item in self.self_schema if item.id == schema_id),
            None,
        )
        if revised is None:
            raise ValueError("self schema disappeared during reconciliation")

        changed = (
            revised.kind != prior_kind
            or abs(revised.success_rate - prior_success_rate) >= 0.10
            or abs(revised.confidence - prior_confidence) >= 0.05
        )
        revision = SelfSchemaRevision(
            id=self.next_self_schema_revision_id,
            schema_id=revised.id,
            prior_kind=prior_kind,
            revised_kind=revised.kind,
            prior_confidence=prior_confidence,
            revised_confidence=revised.confidence,
            prior_success_rate=prior_success_rate,
            revised_success_rate=revised.success_rate,
            contradictory_evidence_refs=contradiction_refs,
            contradiction_ratio=round(contradiction_ratio, 6),
            status="revised" if changed else "confirmed",
            reason=(
                "New contradictory autobiographical evidence forced the schema "
                "to be recomputed from the complete evidence set."
            ),
        )
        self.next_self_schema_revision_id += 1
        self.self_schema_revisions.append(revision)
        if len(self.self_schema_revisions) > self.max_memory:
            self.self_schema_revisions = self.self_schema_revisions[-self.max_memory:]

        if changed:
            self.stage_global_workspace_item(
                source="self_schema",
                content=(
                    f"schema revision id={revision.id}; "
                    f"kind={prior_kind}->{revised.kind}; "
                    f"success_rate={prior_success_rate:.3f}"
                    f"->{revised.success_rate:.3f}; "
                    f"contradiction_ratio={contradiction_ratio:.3f}"
                ),
                salience=max(0.55, contradiction_ratio),
                evidence_refs=(
                    f"self_schema_revision:{revision.id}",
                    *contradiction_refs,
                ),
            )
        return revision

    def compare_self_schema_revision_ablation(
        self,
        *,
        schema_id: int,
        candidates: list[dict[str, Any]],
        context: str = "",
        min_contradictory_evidence: int = 2,
        similarity_threshold: float = 0.28,
    ) -> SelfSchemaRevisionComparison:
        """
        Compare a corrigible self-schema with an otherwise identical frozen one.

        Both copies contain the same new autobiographical evidence. Only the full
        copy is allowed to reconcile the stale schema before predicting actions.
        """
        if not candidates:
            raise ValueError("at least one candidate action is required")

        revised_engine = deepcopy(self)
        frozen_engine = deepcopy(self)
        revised_engine.reconcile_self_schema_contradiction(
            schema_id,
            min_contradictory_evidence=min_contradictory_evidence,
            similarity_threshold=similarity_threshold,
        )
        revised_choice = revised_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
        )
        frozen_choice = frozen_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
        )
        delta = (
            revised_choice.predicted_success
            - frozen_choice.predicted_success
        )
        choice_changed = revised_choice.action != frozen_choice.action
        active = choice_changed or abs(delta) >= 0.05
        return SelfSchemaRevisionComparison(
            revised_action=revised_choice.action,
            frozen_action=frozen_choice.action,
            revised_predicted_success=revised_choice.predicted_success,
            frozen_predicted_success=frozen_choice.predicted_success,
            predicted_success_delta=round(delta, 6),
            choice_changed=choice_changed,
            revision_causally_active=active,
        )


    def active_contextual_self_schema(
        self,
        *,
        parent_schema_id: int | None = None,
    ) -> tuple[ContextualSelfSchemaEntry, ...]:
        items = [
            item
            for item in self.contextual_self_schema
            if item.status == "active"
            and (
                parent_schema_id is None
                or item.parent_schema_id == parent_schema_id
            )
        ]
        return tuple(
            sorted(
                items,
                key=lambda item: (
                    item.parent_schema_id,
                    item.context_label,
                    item.id,
                ),
            )
        )

    def _context_rule_terms(
        self,
        context_rules: dict[str, tuple[str, ...] | list[str]],
    ) -> dict[str, tuple[str, ...]]:
        if len(context_rules) < 2:
            raise ValueError("at least two candidate contexts are required")
        normalized: dict[str, tuple[str, ...]] = {}
        for raw_label, raw_terms in context_rules.items():
            label = str(raw_label).strip().casefold()
            if not label:
                raise ValueError("context labels must be non-empty")
            if not isinstance(raw_terms, (tuple, list)):
                raise ValueError("context rules must map labels to term lists")
            terms: set[str] = set()
            for raw in raw_terms:
                terms.update(_terms(str(raw)))
            if not terms:
                raise ValueError("each context rule needs at least one term")
            normalized[label] = tuple(sorted(terms))
        if len(normalized) < 2:
            raise ValueError("context labels must be unique")
        return normalized

    def _experience_context_label(
        self,
        experience: Experience,
        context_rules: dict[str, tuple[str, ...]],
    ) -> str | None:
        observation_terms = _terms(experience.observation)
        matches = [
            label
            for label, terms in context_rules.items()
            if observation_terms.intersection(terms)
        ]
        return matches[0] if len(matches) == 1 else None

    def decompose_self_schema_context(
        self,
        schema_id: int,
        *,
        context_rules: dict[str, tuple[str, ...] | list[str]],
        min_evidence_per_context: int = 3,
        min_holdout_improvement: float = 0.10,
        similarity_threshold: float = 0.28,
    ) -> SelfSchemaDecomposition:
        """
        Test a candidate context split against held-out autobiographical outcomes.

        The split is accepted only if every context has enough evidence and its
        held-out mean absolute error beats an unsplit global predictor by the
        requested margin. Context rules are explicit hypotheses, not invented
        identity labels.
        """
        parent = next(
            (item for item in self.self_schema if item.id == schema_id),
            None,
        )
        if parent is None:
            raise ValueError("unknown self schema")
        if parent.status != "active":
            raise ValueError("self schema is not active")

        rules = self._context_rule_terms(context_rules)
        min_evidence_per_context = max(
            3,
            min(int(min_evidence_per_context), 24),
        )
        min_holdout_improvement = _clamp(
            min_holdout_improvement,
            0.01,
            0.80,
        )
        matching = self._matching_schema_experiences(
            parent,
            similarity_threshold=similarity_threshold,
        )

        by_context: dict[str, list[tuple[int, Experience]]] = {
            label: [] for label in rules
        }
        for index, experience in matching:
            label = self._experience_context_label(experience, rules)
            if label is not None:
                by_context[label].append((index, experience))

        sufficient = all(
            len(records) >= min_evidence_per_context
            for records in by_context.values()
        )
        evidence_refs = tuple(
            f"experience:{index}"
            for label in sorted(by_context)
            for index, _ in by_context[label]
        )
        if not sufficient:
            record = SelfSchemaDecomposition(
                id=self.next_self_schema_decomposition_id,
                parent_schema_id=parent.id,
                context_schema_ids=(),
                context_labels=tuple(sorted(rules)),
                global_success_rate=parent.success_rate,
                global_holdout_mae=1.0,
                contextual_holdout_mae=1.0,
                improvement=0.0,
                held_out_count=0,
                status="insufficient_evidence",
                evidence_refs=evidence_refs,
            )
            self.next_self_schema_decomposition_id += 1
            self.self_schema_decompositions.append(record)
            return record

        training_by_context: dict[str, list[tuple[int, Experience]]] = {}
        holdout: list[tuple[str, int, Experience]] = []
        for label, records in by_context.items():
            training_by_context[label] = records[:-1]
            held_index, held_experience = records[-1]
            holdout.append((label, held_index, held_experience))

        training = [
            item
            for label in sorted(training_by_context)
            for item in training_by_context[label]
        ]
        global_success_rate = sum(
            1.0 if experience.success is True else 0.0
            for _, experience in training
        ) / len(training)
        context_success_rates = {
            label: (
                sum(
                    1.0 if experience.success is True else 0.0
                    for _, experience in records
                )
                / len(records)
            )
            for label, records in training_by_context.items()
        }

        global_errors: list[float] = []
        contextual_errors: list[float] = []
        for label, _, experience in holdout:
            actual = 1.0 if experience.success is True else 0.0
            global_errors.append(abs(actual - global_success_rate))
            contextual_errors.append(
                abs(actual - context_success_rates[label])
            )
        global_mae = sum(global_errors) / len(global_errors)
        contextual_mae = sum(contextual_errors) / len(contextual_errors)
        improvement = global_mae - contextual_mae
        rate_spread = (
            max(context_success_rates.values())
            - min(context_success_rates.values())
        )
        accepted = (
            improvement >= min_holdout_improvement
            and rate_spread >= 0.25
        )

        context_schema_ids: list[int] = []
        if accepted:
            for label in sorted(rules):
                records = by_context[label]
                successes = sum(
                    1 for _, experience in records if experience.success is True
                )
                failures = sum(
                    1 for _, experience in records if experience.success is False
                )
                count = successes + failures
                success_rate = successes / count
                mean_reward = sum(
                    experience.reward for _, experience in records
                ) / count
                if success_rate >= 0.75:
                    kind = "capability"
                elif success_rate <= 0.35:
                    kind = "limitation"
                else:
                    kind = "mixed"
                consistency = max(success_rate, 1.0 - success_rate)
                confidence = _clamp(
                    0.30
                    + min(0.45, count * 0.08)
                    + (consistency * 0.15)
                    + min(0.10, improvement * 0.20),
                    0.0,
                    0.98,
                )
                success_bias = max(
                    -0.22,
                    min(
                        0.22,
                        (success_rate - 0.5) * 0.44 * confidence,
                    ),
                )
                risk_bias = max(
                    -0.16,
                    min(
                        0.16,
                        (0.5 - success_rate) * 0.32 * confidence,
                    ),
                )
                existing = next(
                    (
                        item
                        for item in self.contextual_self_schema
                        if item.parent_schema_id == parent.id
                        and item.context_label == label
                    ),
                    None,
                )
                refs = tuple(
                    f"experience:{index}" for index, _ in records
                )
                if existing is None:
                    existing = ContextualSelfSchemaEntry(
                        id=self.next_contextual_self_schema_id,
                        parent_schema_id=parent.id,
                        context_label=label,
                        context_terms=rules[label],
                        pattern=parent.pattern,
                        kind=kind,
                        confidence=round(confidence, 6),
                        evidence_count=count,
                        success_count=successes,
                        failure_count=failures,
                        success_rate=round(success_rate, 6),
                        mean_reward=round(mean_reward, 6),
                        success_bias=round(success_bias, 6),
                        risk_bias=round(risk_bias, 6),
                        evidence_refs=refs,
                    )
                    self.next_contextual_self_schema_id += 1
                    self.contextual_self_schema.append(existing)
                else:
                    existing.context_terms = rules[label]
                    existing.pattern = parent.pattern
                    existing.kind = kind
                    existing.confidence = round(confidence, 6)
                    existing.evidence_count = count
                    existing.success_count = successes
                    existing.failure_count = failures
                    existing.success_rate = round(success_rate, 6)
                    existing.mean_reward = round(mean_reward, 6)
                    existing.success_bias = round(success_bias, 6)
                    existing.risk_bias = round(risk_bias, 6)
                    existing.evidence_refs = refs
                    existing.status = "active"
                context_schema_ids.append(existing.id)

            for item in self.contextual_self_schema:
                if (
                    item.parent_schema_id == parent.id
                    and item.context_label not in rules
                ):
                    item.status = "retired"

        record = SelfSchemaDecomposition(
            id=self.next_self_schema_decomposition_id,
            parent_schema_id=parent.id,
            context_schema_ids=tuple(context_schema_ids),
            context_labels=tuple(sorted(rules)),
            global_success_rate=round(global_success_rate, 6),
            global_holdout_mae=round(global_mae, 6),
            contextual_holdout_mae=round(contextual_mae, 6),
            improvement=round(improvement, 6),
            held_out_count=len(holdout),
            status="accepted" if accepted else "rejected_no_gain",
            evidence_refs=evidence_refs,
        )
        self.next_self_schema_decomposition_id += 1
        self.self_schema_decompositions.append(record)
        if len(self.self_schema_decompositions) > self.max_memory:
            self.self_schema_decompositions = self.self_schema_decompositions[
                -self.max_memory:
            ]

        if accepted:
            self.stage_global_workspace_item(
                source="self_schema",
                content=(
                    f"context decomposition id={record.id}; "
                    f"parent_schema={parent.id}; "
                    f"contexts={','.join(record.context_labels)}; "
                    f"heldout_improvement={record.improvement:.3f}"
                ),
                salience=max(0.55, _clamp(record.improvement + 0.35)),
                evidence_refs=(
                    f"self_schema_decomposition:{record.id}",
                    *evidence_refs[-4:],
                ),
            )
        return record




    def propose_context_causality_intervention(
        self,
        hypothesis_id: int,
        *,
        from_context: str,
        to_context: str,
        controlled_signature: str,
        risk: float = 0.10,
        min_samples: int = 3,
    ) -> ContextCausalityTrial:
        """
        Plan a bounded intervention test for one selected latent context hypothesis.

        The method records a protocol only. It never performs an external action.
        """
        hypothesis = next(
            (
                item
                for item in self.latent_context_hypotheses
                if item.id == hypothesis_id
            ),
            None,
        )
        if hypothesis is None:
            raise ValueError("unknown latent context hypothesis")
        if hypothesis.validation_status != "selected":
            raise ValueError("context hypothesis must pass held-out validation")

        from_label = from_context.strip().casefold()
        to_label = to_context.strip().casefold()
        signature = controlled_signature.strip()
        if not from_label or not to_label or from_label == to_label:
            raise ValueError("distinct context labels are required")
        if not signature:
            raise ValueError("controlled environment signature is required")

        contextual = {
            item.context_label: item
            for item in self.active_contextual_self_schema(
                parent_schema_id=hypothesis.parent_schema_id
            )
        }
        if from_label not in contextual or to_label not in contextual:
            raise ValueError("intervention contexts must be validated schemas")

        baseline = contextual[from_label].success_rate
        target = contextual[to_label].success_rate
        if abs(target - baseline) < 0.25:
            raise ValueError("context outcome contrast is too small to intervene")

        trial = ContextCausalityTrial(
            id=self.next_context_causality_trial_id,
            hypothesis_id=hypothesis.id,
            from_context=from_label,
            to_context=to_label,
            controlled_signature=signature[:300],
            baseline_success_rate=baseline,
            predicted_target_success_rate=target,
            risk=round(_clamp(risk), 6),
            min_samples=max(3, min(int(min_samples), 20)),
            evidence_refs=(
                f"latent_context_hypothesis:{hypothesis.id}",
                f"self_schema_decomposition:{hypothesis.decomposition_id}",
            ),
        )
        self.next_context_causality_trial_id += 1
        self.context_causality_trials.append(trial)
        if len(self.context_causality_trials) > self.max_memory:
            self.context_causality_trials = self.context_causality_trials[
                -self.max_memory:
            ]
        return trial

    def observe_context_causality_intervention(
        self,
        trial_id: int,
        *,
        observed_target_success_rate: float,
        observed_signature: str,
        sample_count: int,
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> ContextCausalityTrial:
        """
        Evaluate whether a controlled context intervention supports causality.

        Exact controlled-signature equality is required. Confounded observations
        cannot upgrade an observational context hypothesis.
        """
        trial = next(
            (
                item
                for item in self.context_causality_trials
                if item.id == trial_id
            ),
            None,
        )
        if trial is None:
            raise ValueError("unknown context causality trial")
        if trial.status != "planned":
            raise ValueError("context causality trial has already been observed")

        observed_rate = _clamp(observed_target_success_rate)
        signature = observed_signature.strip()
        if not signature:
            raise ValueError("observed controlled signature is required")
        sample_count = max(0, int(sample_count))

        held_constant = signature == trial.controlled_signature
        trial.observed_target_success_rate = round(observed_rate, 6)
        trial.observed_signature = signature[:300]
        trial.sample_count = sample_count
        trial.competing_variables_held_constant = held_constant

        expected_delta = (
            trial.predicted_target_success_rate
            - trial.baseline_success_rate
        )
        observed_delta = observed_rate - trial.baseline_success_rate
        direction_followed = (
            observed_delta * expected_delta > 0.0
            and abs(observed_delta) >= 0.20
        )
        trial.predicted_direction_followed = direction_followed

        target_error = abs(
            observed_rate - trial.predicted_target_success_rate
        )
        sample_factor = min(1.0, sample_count / max(1, trial.min_samples))
        strength = _clamp(
            abs(observed_delta)
            * (1.0 - target_error)
            * sample_factor
        )
        trial.causal_strength = round(strength, 6)
        provided_refs = tuple(str(ref) for ref in evidence_refs if str(ref))
        trial.evidence_refs = tuple(
            dict.fromkeys(trial.evidence_refs + provided_refs)
        )

        if not held_constant:
            trial.status = "confounded"
            return trial
        if sample_count < trial.min_samples:
            trial.status = "insufficient_evidence"
            return trial

        supported = direction_followed and strength >= 0.35
        trial.status = (
            "intervention_supported"
            if supported
            else "intervention_not_supported"
        )

        updated: list[LatentContextHypothesis] = []
        for item in self.latent_context_hypotheses:
            if item.id != trial.hypothesis_id:
                updated.append(item)
                continue
            causal_refs = tuple(
                dict.fromkeys(
                    item.causal_evidence_refs
                    + (f"context_causality_trial:{trial.id}",)
                    + provided_refs
                )
            )
            updated.append(
                LatentContextHypothesis(
                    id=item.id,
                    parent_schema_id=item.parent_schema_id,
                    positive_term=item.positive_term,
                    negative_term=item.negative_term,
                    positive_support=item.positive_support,
                    negative_support=item.negative_support,
                    positive_success_rate=item.positive_success_rate,
                    negative_success_rate=item.negative_success_rate,
                    rate_contrast=item.rate_contrast,
                    validation_status=item.validation_status,
                    holdout_improvement=item.holdout_improvement,
                    decomposition_id=item.decomposition_id,
                    evidence_refs=item.evidence_refs,
                    causal_status=(
                        item.causal_status
                        if item.causal_status in {
                            "replicated_reversible",
                            "environment_invariant",
                        }
                        else "intervention_supported"
                        if supported
                        or item.causal_status == "intervention_supported"
                        else "intervention_not_supported"
                    ),
                    causal_evidence_refs=causal_refs,
                )
            )
        self.latent_context_hypotheses = updated

        if supported:
            self.stage_global_workspace_item(
                source="intervention",
                content=(
                    f"context causality trial={trial.id}; "
                    f"hypothesis={trial.hypothesis_id}; "
                    f"context={trial.from_context}->{trial.to_context}; "
                    f"strength={trial.causal_strength:.3f}"
                ),
                salience=max(0.60, trial.causal_strength or 0.0),
                evidence_refs=(
                    f"context_causality_trial:{trial.id}",
                    *provided_refs[-4:],
                ),
            )
        return trial

    def assess_context_causal_stability(
        self,
        hypothesis_id: int,
        *,
        forward_trial_ids: tuple[int, ...] | list[int],
        reverse_trial_ids: tuple[int, ...] | list[int],
        min_forward_batches: int = 2,
        min_reverse_batches: int = 1,
    ) -> ContextCausalStabilityAssessment:
        """
        Require replicated forward evidence plus a clean reversal test.

        Distinct evidence references are used as a lightweight independence gate:
        repeated observations that reuse the same external evidence batch do not
        count as independent replication.
        """
        hypothesis = next(
            (
                item
                for item in self.latent_context_hypotheses
                if item.id == hypothesis_id
            ),
            None,
        )
        if hypothesis is None:
            raise ValueError("unknown latent context hypothesis")

        forward_ids = tuple(dict.fromkeys(int(item) for item in forward_trial_ids))
        reverse_ids = tuple(dict.fromkeys(int(item) for item in reverse_trial_ids))
        if not forward_ids:
            raise ValueError("at least one forward context trial is required")

        trial_map = {item.id: item for item in self.context_causality_trials}
        requested = forward_ids + reverse_ids
        if any(item_id not in trial_map for item_id in requested):
            raise ValueError("unknown context causality trial in stability assessment")

        forward = [trial_map[item_id] for item_id in forward_ids]
        reverse = [trial_map[item_id] for item_id in reverse_ids]
        if any(item.hypothesis_id != hypothesis_id for item in forward + reverse):
            raise ValueError("all stability trials must test the same hypothesis")

        source = forward[0].from_context
        target = forward[0].to_context
        if any(
            item.from_context != source or item.to_context != target
            for item in forward
        ):
            raise ValueError("forward replication trials must share one direction")
        if any(
            item.from_context != target or item.to_context != source
            for item in reverse
        ):
            raise ValueError("reverse trials must invert the forward contexts")

        min_forward = max(2, min(int(min_forward_batches), 6))
        min_reverse = max(1, min(int(min_reverse_batches), 4))

        def supported(item: ContextCausalityTrial) -> bool:
            return (
                item.status == "intervention_supported"
                and item.competing_variables_held_constant is True
                and item.predicted_direction_followed is True
                and item.sample_count >= item.min_samples
                and (item.causal_strength or 0.0) >= 0.35
            )

        def independent_supported_count(
            trials: list[ContextCausalityTrial],
            *,
            prior_refs: set[str] | None = None,
        ) -> tuple[int, set[str]]:
            used_refs = set(prior_refs or ())
            count = 0
            for item in trials:
                if not supported(item):
                    continue
                batch_refs = {
                    ref
                    for ref in item.evidence_refs
                    if not ref.startswith("latent_context_hypothesis:")
                    and not ref.startswith("self_schema_decomposition:")
                    and not ref.startswith("context_causality_trial:")
                }
                if not batch_refs or batch_refs & used_refs:
                    continue
                used_refs.update(batch_refs)
                count += 1
            return count, used_refs

        forward_supported = sum(1 for item in forward if supported(item))
        reverse_supported = sum(1 for item in reverse if supported(item))
        independent_forward, used_batch_refs = independent_supported_count(
            forward
        )
        independent_reverse, _ = independent_supported_count(
            reverse,
            prior_refs=used_batch_refs,
        )
        forward_rate = forward_supported / max(1, len(forward))
        reverse_rate = reverse_supported / max(1, len(reverse))
        reversal_followed = bool(reverse) and all(
            supported(item) for item in reverse
        )

        strengths = [
            item.causal_strength or 0.0
            for item in forward + reverse
            if supported(item)
        ]
        mean_strength = sum(strengths) / max(1, len(strengths))
        enough_replication = (
            independent_forward >= min_forward
            and independent_reverse >= min_reverse
        )
        stable = (
            enough_replication
            and forward_rate == 1.0
            and reverse_rate == 1.0
            and reversal_followed
        )
        status = (
            "replicated_reversible"
            if stable
            else "insufficient_replication"
            if not enough_replication
            else "unstable"
        )
        confidence = _clamp(
            mean_strength
            * min(forward_rate, reverse_rate)
            * min(1.0, independent_forward / min_forward)
            * min(1.0, independent_reverse / min_reverse)
        )

        assessment = ContextCausalStabilityAssessment(
            id=self.next_context_causal_stability_assessment_id,
            hypothesis_id=hypothesis_id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=reverse_ids,
            independent_forward_batches=independent_forward,
            independent_reverse_batches=independent_reverse,
            forward_replication_rate=round(forward_rate, 6),
            reverse_replication_rate=round(reverse_rate, 6),
            mean_causal_strength=round(mean_strength, 6),
            reversal_direction_followed=reversal_followed,
            status=status,
            confidence=round(confidence, 6),
            evidence_refs=tuple(
                dict.fromkeys(
                    tuple(
                        f"context_causality_trial:{item_id}"
                        for item_id in requested
                    )
                    + tuple(
                        ref
                        for item in forward + reverse
                        for ref in item.evidence_refs
                    )
                )
            ),
        )
        self.next_context_causal_stability_assessment_id += 1
        self.context_causal_stability_assessments.append(assessment)
        if len(self.context_causal_stability_assessments) > self.max_memory:
            self.context_causal_stability_assessments = (
                self.context_causal_stability_assessments[-self.max_memory:]
            )

        updated: list[LatentContextHypothesis] = []
        for item in self.latent_context_hypotheses:
            if item.id != hypothesis_id:
                updated.append(item)
                continue
            next_status = (
                item.causal_status
                if item.causal_status == "environment_invariant"
                else "replicated_reversible"
                if stable
                else item.causal_status
            )
            updated.append(
                LatentContextHypothesis(
                    id=item.id,
                    parent_schema_id=item.parent_schema_id,
                    positive_term=item.positive_term,
                    negative_term=item.negative_term,
                    positive_support=item.positive_support,
                    negative_support=item.negative_support,
                    positive_success_rate=item.positive_success_rate,
                    negative_success_rate=item.negative_success_rate,
                    rate_contrast=item.rate_contrast,
                    validation_status=item.validation_status,
                    holdout_improvement=item.holdout_improvement,
                    decomposition_id=item.decomposition_id,
                    evidence_refs=item.evidence_refs,
                    causal_status=next_status,
                    causal_evidence_refs=tuple(
                        dict.fromkeys(
                            item.causal_evidence_refs
                            + (
                                "context_causal_stability_assessment:"
                                f"{assessment.id}",
                            )
                            + assessment.evidence_refs
                        )
                    ),
                )
            )
        self.latent_context_hypotheses = updated

        if stable:
            self.stage_global_workspace_item(
                source="intervention",
                content=(
                    f"context causal stability assessment={assessment.id}; "
                    f"hypothesis={hypothesis_id}; "
                    f"forward_batches={independent_forward}; "
                    f"reverse_batches={independent_reverse}; "
                    f"confidence={assessment.confidence:.3f}"
                ),
                salience=max(0.65, assessment.confidence),
                evidence_refs=(
                    f"context_causal_stability_assessment:{assessment.id}",
                    *assessment.evidence_refs[-4:],
                ),
            )
        return assessment

    def assess_context_causal_invariance(
        self,
        hypothesis_id: int,
        *,
        stability_assessment_ids: tuple[int, ...] | list[int],
        min_environments: int = 2,
        min_causal_strength: float = 0.35,
        max_strength_spread: float = 0.30,
    ) -> ContextCausalInvarianceAssessment:
        """
        Test whether replicated reversible causality survives environment change.

        Each supplied stability assessment must describe one controlled
        environment signature. Distinct signatures count as distinct
        environments. A failed environment becomes an explicit boundary instead
        of being silently generalized away.
        """
        hypothesis = next(
            (
                item
                for item in self.latent_context_hypotheses
                if item.id == hypothesis_id
            ),
            None,
        )
        if hypothesis is None:
            raise ValueError("unknown latent context hypothesis")

        assessment_ids = tuple(
            dict.fromkeys(int(item) for item in stability_assessment_ids)
        )
        if not assessment_ids:
            raise ValueError("at least one causal stability assessment is required")

        stability_map = {
            item.id: item for item in self.context_causal_stability_assessments
        }
        if any(item_id not in stability_map for item_id in assessment_ids):
            raise ValueError("unknown causal stability assessment")

        assessments = [stability_map[item_id] for item_id in assessment_ids]
        if any(item.hypothesis_id != hypothesis_id for item in assessments):
            raise ValueError("all invariance assessments must test one hypothesis")

        trial_map = {item.id: item for item in self.context_causality_trials}
        environment_rows: list[
            tuple[str, ContextCausalStabilityAssessment, float]
        ] = []
        boundary_signatures: list[str] = []
        evidence_refs: list[str] = []
        direction_signs: list[int] = []

        for item in assessments:
            trial_ids = item.forward_trial_ids + item.reverse_trial_ids
            trials = [trial_map.get(trial_id) for trial_id in trial_ids]
            if any(trial is None for trial in trials):
                raise ValueError("stability assessment references unknown trial")
            concrete_trials = [
                trial for trial in trials if trial is not None
            ]
            signatures = {
                trial.controlled_signature for trial in concrete_trials
            }
            if len(signatures) != 1:
                raise ValueError(
                    "one stability assessment must use one environment signature"
                )
            signature = next(iter(signatures))
            forward_trials = [
                trial_map[trial_id] for trial_id in item.forward_trial_ids
            ]
            if not forward_trials:
                raise ValueError("stability assessment has no forward trial")

            source = forward_trials[0].from_context
            target = forward_trials[0].to_context
            if any(
                trial.from_context != source or trial.to_context != target
                for trial in forward_trials
            ):
                raise ValueError("forward directions differ inside environment")

            expected_delta = (
                forward_trials[0].predicted_target_success_rate
                - forward_trials[0].baseline_success_rate
            )
            direction_signs.append(1 if expected_delta > 0.0 else -1)
            environment_rows.append(
                (signature, item, item.mean_causal_strength)
            )
            evidence_refs.append(
                f"context_causal_stability_assessment:{item.id}"
            )
            evidence_refs.extend(item.evidence_refs)
            if item.status != "replicated_reversible":
                boundary_signatures.append(signature)

        by_signature: dict[
            str,
            tuple[ContextCausalStabilityAssessment, float],
        ] = {}
        duplicated_signatures: set[str] = set()
        for signature, assessment, strength in environment_rows:
            if signature in by_signature:
                duplicated_signatures.add(signature)
                previous = by_signature[signature][0]
                if assessment.confidence > previous.confidence:
                    by_signature[signature] = (assessment, strength)
            else:
                by_signature[signature] = (assessment, strength)

        distinct_rows = [
            (signature, value[0], value[1])
            for signature, value in sorted(by_signature.items())
        ]
        distinct_count = len(distinct_rows)
        min_environments = max(2, min(int(min_environments), 8))
        strength_floor = _clamp(min_causal_strength, 0.0, 1.0)
        spread_limit = _clamp(max_strength_spread, 0.0, 1.0)

        stable_rows = [
            row
            for row in distinct_rows
            if row[1].status == "replicated_reversible"
            and row[2] >= strength_floor
        ]
        stable_count = len(stable_rows)
        strengths = [row[2] for row in distinct_rows]
        minimum_strength = min(strengths) if strengths else 0.0
        maximum_strength = max(strengths) if strengths else 0.0
        strength_spread = maximum_strength - minimum_strength
        direction_consistent = len(set(direction_signs)) <= 1

        for signature, assessment, strength in distinct_rows:
            if (
                assessment.status != "replicated_reversible"
                or strength < strength_floor
            ):
                boundary_signatures.append(signature)

        enough_environments = distinct_count >= min_environments
        invariant = (
            enough_environments
            and stable_count == distinct_count
            and direction_consistent
            and strength_spread <= spread_limit
            and not duplicated_signatures
        )
        status = (
            "environment_invariant"
            if invariant
            else "insufficient_environments"
            if not enough_environments
            else "environment_bounded"
        )
        if enough_environments and (
            not direction_consistent or strength_spread > spread_limit
        ):
            boundary_signatures.extend(
                signature for signature, _, _ in distinct_rows
            )

        coverage = min(1.0, distinct_count / min_environments)
        stability_rate = stable_count / max(1, distinct_count)
        spread_factor = max(
            0.0,
            1.0 - (strength_spread / max(spread_limit, 1e-9)),
        )
        confidence = _clamp(
            minimum_strength
            * coverage
            * stability_rate
            * spread_factor
            * (1.0 if direction_consistent else 0.0)
        )

        record = ContextCausalInvarianceAssessment(
            id=self.next_context_causal_invariance_assessment_id,
            hypothesis_id=hypothesis_id,
            stability_assessment_ids=assessment_ids,
            environment_signatures=tuple(
                signature for signature, _, _ in distinct_rows
            ),
            distinct_environment_count=distinct_count,
            stable_environment_count=stable_count,
            effect_direction_consistent=direction_consistent,
            minimum_causal_strength=round(minimum_strength, 6),
            maximum_causal_strength=round(maximum_strength, 6),
            strength_spread=round(strength_spread, 6),
            status=status,
            confidence=round(confidence, 6),
            boundary_signatures=tuple(
                sorted(set(boundary_signatures) | duplicated_signatures)
            ),
            evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        )
        self.next_context_causal_invariance_assessment_id += 1
        self.context_causal_invariance_assessments.append(record)
        if len(self.context_causal_invariance_assessments) > self.max_memory:
            self.context_causal_invariance_assessments = (
                self.context_causal_invariance_assessments[-self.max_memory:]
            )

        updated: list[LatentContextHypothesis] = []
        for item in self.latent_context_hypotheses:
            if item.id != hypothesis_id:
                updated.append(item)
                continue
            next_status = (
                "environment_invariant"
                if invariant
                else "replicated_reversible"
                if item.causal_status in {
                    "replicated_reversible",
                    "environment_invariant",
                }
                else item.causal_status
            )
            updated.append(
                LatentContextHypothesis(
                    id=item.id,
                    parent_schema_id=item.parent_schema_id,
                    positive_term=item.positive_term,
                    negative_term=item.negative_term,
                    positive_support=item.positive_support,
                    negative_support=item.negative_support,
                    positive_success_rate=item.positive_success_rate,
                    negative_success_rate=item.negative_success_rate,
                    rate_contrast=item.rate_contrast,
                    validation_status=item.validation_status,
                    holdout_improvement=item.holdout_improvement,
                    decomposition_id=item.decomposition_id,
                    evidence_refs=item.evidence_refs,
                    causal_status=next_status,
                    causal_evidence_refs=tuple(
                        dict.fromkeys(
                            item.causal_evidence_refs
                            + (
                                "context_causal_invariance_assessment:"
                                f"{record.id}",
                            )
                            + record.evidence_refs
                        )
                    ),
                )
            )
        self.latent_context_hypotheses = updated

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context causal invariance assessment={record.id}; "
                f"hypothesis={hypothesis_id}; "
                f"environments={record.distinct_environment_count}; "
                f"status={record.status}; "
                f"confidence={record.confidence:.3f}"
            ),
            salience=max(0.55, record.confidence),
            evidence_refs=(
                f"context_causal_invariance_assessment:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def plan_context_boundary_discovery(
        self,
        hypothesis_id: int,
        *,
        invariance_assessment_id: int,
        candidate_risks: dict[str, float],
        max_risk: float = 0.25,
        max_dimension_changes: int = 1,
    ) -> ContextBoundaryDiscoveryPlan:
        """
        Rank bounded environment probes by expected boundary information.

        This method only creates a plan. It never executes an intervention,
        spends money, or calls an external model.
        """
        hypothesis = next(
            (
                item
                for item in self.latent_context_hypotheses
                if item.id == hypothesis_id
            ),
            None,
        )
        if hypothesis is None:
            raise ValueError("unknown latent context hypothesis")

        invariance = next(
            (
                item
                for item in self.context_causal_invariance_assessments
                if item.id == invariance_assessment_id
            ),
            None,
        )
        if invariance is None:
            raise ValueError("unknown causal invariance assessment")
        if invariance.hypothesis_id != hypothesis_id:
            raise ValueError("invariance assessment belongs to another hypothesis")
        if not candidate_risks:
            raise ValueError("at least one candidate environment is required")

        risk_limit = _clamp(max_risk, 0.0, 1.0)
        dimension_limit = max(1, min(int(max_dimension_changes), 4))
        tested = set(invariance.environment_signatures)
        boundaries = set(invariance.boundary_signatures)
        stable = tested - boundaries
        if not stable:
            raise ValueError("boundary discovery requires a stable environment")

        def parse_signature(signature: str) -> dict[str, str]:
            parsed: dict[str, str] = {}
            for raw_part in signature.split(";"):
                part = raw_part.strip()
                if not part or "=" not in part:
                    raise ValueError("environment signature must use key=value parts")
                key, value = part.split("=", 1)
                key = key.strip().casefold()
                value = value.strip().casefold()
                if not key or not value or key in parsed:
                    raise ValueError("invalid environment signature")
                parsed[key] = value
            return parsed

        parsed_tested = {
            signature: parse_signature(signature) for signature in tested
        }

        def distance(left: dict[str, str], right: dict[str, str]) -> int:
            keys = set(left) | set(right)
            return sum(left.get(key) != right.get(key) for key in keys)

        ranked: list[
            tuple[
                float,
                float,
                str,
                int,
                int | None,
                tuple[str, ...],
            ]
        ] = []
        accepted_candidates: list[str] = []
        for raw_signature, raw_risk in candidate_risks.items():
            signature = str(raw_signature).strip()
            if not signature or signature in tested:
                continue
            risk = _clamp(float(raw_risk), 0.0, 1.0)
            if risk > risk_limit:
                continue

            parsed = parse_signature(signature)
            stable_distances = [
                (
                    distance(parsed, parsed_tested[item]),
                    item,
                )
                for item in stable
            ]
            stable_distance, nearest_stable = min(
                stable_distances,
                key=lambda item: (item[0], item[1]),
            )
            boundary_distance: int | None = None
            if boundaries:
                boundary_distance = min(
                    distance(parsed, parsed_tested[item])
                    for item in boundaries
                )

            nearest_any = stable_distance
            if boundary_distance is not None:
                nearest_any = min(nearest_any, boundary_distance)
            if nearest_any > dimension_limit:
                continue

            changed_dimensions = tuple(
                sorted(
                    key
                    for key in set(parsed) | set(parsed_tested[nearest_stable])
                    if parsed.get(key) != parsed_tested[nearest_stable].get(key)
                )
            )
            if not changed_dimensions:
                continue

            locality = 1.0 / (1.0 + nearest_any)
            if boundary_distance is None:
                balance = 0.5
                boundary_focus = 0.0
            else:
                balance = 1.0 / (
                    1.0 + abs(stable_distance - boundary_distance)
                )
                boundary_focus = 1.0 / (1.0 + boundary_distance)
            information_gain = _clamp(
                (0.45 * balance)
                + (0.35 * boundary_focus)
                + (0.20 * locality)
            )
            priority = information_gain * (1.0 - risk)
            accepted_candidates.append(signature)
            ranked.append(
                (
                    priority,
                    information_gain,
                    signature,
                    stable_distance,
                    boundary_distance,
                    changed_dimensions,
                )
            )

        if not ranked:
            raise ValueError("no bounded candidate environment passed the filters")

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1],
                -item[3],
                item[2],
            ),
            reverse=True,
        )
        (
            priority,
            information_gain,
            selected_signature,
            stable_distance,
            boundary_distance,
            changed_dimensions,
        ) = ranked[0]
        selected_risk = _clamp(float(candidate_risks[selected_signature]))

        plan = ContextBoundaryDiscoveryPlan(
            id=self.next_context_boundary_discovery_plan_id,
            hypothesis_id=hypothesis_id,
            invariance_assessment_id=invariance.id,
            candidate_signatures=tuple(sorted(accepted_candidates)),
            selected_signature=selected_signature,
            selected_risk=round(selected_risk, 6),
            selected_information_gain=round(information_gain, 6),
            selected_priority_score=round(priority, 6),
            nearest_stable_distance=stable_distance,
            nearest_boundary_distance=boundary_distance,
            changed_dimensions=changed_dimensions,
            evidence_refs=(
                f"context_causal_invariance_assessment:{invariance.id}",
                *invariance.evidence_refs[-6:],
            ),
        )
        self.next_context_boundary_discovery_plan_id += 1
        self.context_boundary_discovery_plans.append(plan)
        if len(self.context_boundary_discovery_plans) > self.max_memory:
            self.context_boundary_discovery_plans = (
                self.context_boundary_discovery_plans[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context boundary plan={plan.id}; "
                f"hypothesis={hypothesis_id}; "
                f"selected={plan.selected_signature}; "
                f"information_gain={plan.selected_information_gain:.3f}; "
                f"risk={plan.selected_risk:.3f}"
            ),
            salience=max(0.55, plan.selected_information_gain),
            evidence_refs=(
                f"context_boundary_discovery_plan:{plan.id}",
                *plan.evidence_refs[-4:],
            ),
        )
        return plan

    def observe_context_boundary_discovery(
        self,
        plan_id: int,
        *,
        stability_assessment_id: int,
    ) -> ContextBoundaryDiscoveryPlan:
        """
        Attach externally supplied causal-stability evidence to a boundary plan.

        Observation records evidence only; it does not execute the selected
        environment probe.
        """
        plan = next(
            (
                item
                for item in self.context_boundary_discovery_plans
                if item.id == plan_id
            ),
            None,
        )
        if plan is None:
            raise ValueError("unknown context boundary discovery plan")
        if plan.status != "planned":
            raise ValueError("context boundary discovery plan already resolved")

        stability = next(
            (
                item
                for item in self.context_causal_stability_assessments
                if item.id == stability_assessment_id
            ),
            None,
        )
        if stability is None:
            raise ValueError("unknown causal stability assessment")
        if stability.hypothesis_id != plan.hypothesis_id:
            raise ValueError("stability assessment belongs to another hypothesis")

        trial_map = {item.id: item for item in self.context_causality_trials}
        trial_ids = stability.forward_trial_ids + stability.reverse_trial_ids
        trials = [trial_map.get(item_id) for item_id in trial_ids]
        if not trials or any(item is None for item in trials):
            raise ValueError("stability assessment references unknown trial")
        signatures = {
            item.controlled_signature
            for item in trials
            if item is not None
        }
        if signatures != {plan.selected_signature}:
            raise ValueError("stability evidence does not match selected probe")

        expanded = stability.status == "replicated_reversible"
        plan.status = "resolved"
        plan.outcome_stability_assessment_id = stability.id
        plan.outcome_status = (
            "expanded_valid_region" if expanded else "confirmed_boundary"
        )
        evidence_weight = (
            stability.confidence if expanded else max(0.5, 1.0 - stability.confidence)
        )
        plan.uncertainty_reduction = round(
            _clamp(plan.selected_information_gain * evidence_weight),
            6,
        )
        plan.evidence_refs = tuple(
            dict.fromkeys(
                plan.evidence_refs
                + (
                    f"context_causal_stability_assessment:{stability.id}",
                )
                + stability.evidence_refs
            )
        )
        return plan

    def consolidate_context_causal_validity_map(
        self,
        hypothesis_id: int,
        *,
        max_generalization_distance: int = 1,
    ) -> ContextCausalValidityMap:
        """
        Consolidate the latest tested causal evidence into a compact validity map.

        Exact tested environments remain authoritative. The map stores no
        brute-force enumeration of unknown environments; those are classified
        lazily by distance to the current tested-valid and tested-invalid sets.
        """
        hypothesis = next(
            (
                item
                for item in self.latent_context_hypotheses
                if item.id == hypothesis_id
            ),
            None,
        )
        if hypothesis is None:
            raise ValueError("unknown latent context hypothesis")

        trial_map = {item.id: item for item in self.context_causality_trials}

        def signature_for(
            assessment: ContextCausalStabilityAssessment,
        ) -> str:
            trial_ids = assessment.forward_trial_ids + assessment.reverse_trial_ids
            trials = [trial_map.get(item_id) for item_id in trial_ids]
            if not trials or any(item is None for item in trials):
                raise ValueError("stability assessment references unknown trial")
            signatures = {
                item.controlled_signature
                for item in trials
                if item is not None
            }
            if len(signatures) != 1:
                raise ValueError(
                    "one stability assessment must use one environment signature"
                )
            return next(iter(signatures))

        latest_by_signature: dict[
            str,
            ContextCausalStabilityAssessment,
        ] = {}
        for assessment in self.context_causal_stability_assessments:
            if assessment.hypothesis_id != hypothesis_id:
                continue
            signature = signature_for(assessment)
            previous = latest_by_signature.get(signature)
            if previous is None or assessment.id > previous.id:
                latest_by_signature[signature] = assessment

        if not latest_by_signature:
            raise ValueError("causal validity map requires tested environments")

        def parse_signature(signature: str) -> dict[str, str]:
            parsed: dict[str, str] = {}
            for raw_part in signature.split(";"):
                part = raw_part.strip()
                if not part or "=" not in part:
                    raise ValueError(
                        "environment signature must use key=value parts"
                    )
                key, value = part.split("=", 1)
                key = key.strip().casefold()
                value = value.strip().casefold()
                if not key or not value or key in parsed:
                    raise ValueError("invalid environment signature")
                parsed[key] = value
            return parsed

        valid = tuple(
            sorted(
                signature
                for signature, assessment in latest_by_signature.items()
                if assessment.status == "replicated_reversible"
            )
        )
        invalid = tuple(
            sorted(
                signature
                for signature, assessment in latest_by_signature.items()
                if assessment.status != "replicated_reversible"
            )
        )
        dimensions = tuple(
            sorted(
                {
                    key
                    for signature in latest_by_signature
                    for key in parse_signature(signature)
                }
            )
        )
        signature_assessment_ids = tuple(
            sorted(
                (signature, assessment.id)
                for signature, assessment in latest_by_signature.items()
            )
        )

        invariance_ids = tuple(
            item.id
            for item in self.context_causal_invariance_assessments
            if item.hypothesis_id == hypothesis_id
        )
        boundary_plan_ids = tuple(
            item.id
            for item in self.context_boundary_discovery_plans
            if item.hypothesis_id == hypothesis_id and item.status == "resolved"
        )

        evidence_refs: list[str] = []
        confidences: list[float] = []
        for _, assessment in sorted(latest_by_signature.items()):
            evidence_refs.append(
                f"context_causal_stability_assessment:{assessment.id}"
            )
            evidence_refs.extend(assessment.evidence_refs[-4:])
            if assessment.status == "replicated_reversible":
                confidences.append(assessment.confidence)
            else:
                confidences.append(max(0.5, 1.0 - assessment.confidence))

        for item in self.context_causal_invariance_assessments:
            if item.id in invariance_ids:
                evidence_refs.append(
                    f"context_causal_invariance_assessment:{item.id}"
                )
        for item in self.context_boundary_discovery_plans:
            if item.id in boundary_plan_ids:
                evidence_refs.append(
                    f"context_boundary_discovery_plan:{item.id}"
                )

        distance_limit = max(
            0,
            min(int(max_generalization_distance), 2),
        )
        confidence = sum(confidences) / max(1, len(confidences))
        record = ContextCausalValidityMap(
            id=self.next_context_causal_validity_map_id,
            hypothesis_id=hypothesis_id,
            source_invariance_assessment_ids=invariance_ids,
            source_boundary_plan_ids=boundary_plan_ids,
            signature_assessment_ids=signature_assessment_ids,
            tested_valid_signatures=valid,
            tested_invalid_signatures=invalid,
            dimensions=dimensions,
            max_generalization_distance=distance_limit,
            confidence=round(_clamp(confidence), 6),
            evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        )
        self.next_context_causal_validity_map_id += 1
        self.context_causal_validity_maps.append(record)
        if len(self.context_causal_validity_maps) > self.max_memory:
            self.context_causal_validity_maps = (
                self.context_causal_validity_maps[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context causal validity map={record.id}; "
                f"hypothesis={hypothesis_id}; "
                f"valid={len(record.tested_valid_signatures)}; "
                f"invalid={len(record.tested_invalid_signatures)}; "
                f"distance={record.max_generalization_distance}"
            ),
            salience=max(0.55, record.confidence),
            evidence_refs=(
                f"context_causal_validity_map:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def revise_context_causal_validity_map(
        self,
        parent_map_id: int,
        *,
        calibration_ids: tuple[int, ...] | list[int] | None = None,
    ) -> ContextCausalValidityMap:
        """
        Freeze calibration evidence into a new immutable validity-map revision.

        Exact tested evidence is copied unchanged. Only inferred nearby support
        can expand or contract from calibration evidence.
        """
        parent = next(
            (
                item
                for item in self.context_causal_validity_maps
                if item.id == parent_map_id
            ),
            None,
        )
        if parent is None:
            raise ValueError("unknown parent causal validity map")

        available = [
            item
            for item in self.context_validity_region_calibrations
            if item.validity_map_id == parent.id
        ]
        if calibration_ids is None:
            selected_ids = {item.id for item in available}
        else:
            selected_ids = {int(item_id) for item_id in calibration_ids}
        selected = [item for item in available if item.id in selected_ids]
        if selected_ids and len(selected) != len(selected_ids):
            raise ValueError("unknown calibration for parent validity map")
        if not selected:
            raise ValueError("map revision requires calibration evidence")

        latest_by_signature: dict[
            str,
            ContextValidityRegionCalibration,
        ] = {}
        for item in selected:
            previous = latest_by_signature.get(item.environment_signature)
            if previous is None or item.id > previous.id:
                latest_by_signature[item.environment_signature] = item

        supported = set(parent.calibrated_supported_signatures)
        revoked = set(parent.revoked_inferred_signatures)
        reasons: list[str] = []
        evidence_refs = list(parent.evidence_refs)

        for signature, calibration in sorted(latest_by_signature.items()):
            if signature in parent.tested_valid_signatures:
                reasons.append(
                    f"preserve tested-valid {signature}; "
                    f"calibration={calibration.id}"
                )
            elif signature in parent.tested_invalid_signatures:
                reasons.append(
                    f"preserve tested-invalid {signature}; "
                    f"calibration={calibration.id}"
                )
            elif calibration.status == "nearby_support_calibrated":
                supported.add(signature)
                revoked.discard(signature)
                reasons.append(
                    f"expand inferred support {signature}; "
                    f"calibration={calibration.id}; "
                    f"advantage={calibration.gated_advantage_vs_alternative:.3f}"
                )
            elif calibration.status == "nearby_support_revoked":
                revoked.add(signature)
                supported.discard(signature)
                reasons.append(
                    f"contract inferred support {signature}; "
                    f"calibration={calibration.id}; "
                    f"advantage={calibration.gated_advantage_vs_alternative:.3f}"
                )
            else:
                reasons.append(
                    f"no inferred-region change {signature}; "
                    f"calibration={calibration.id}; status={calibration.status}"
                )
            evidence_refs.append(
                f"context_validity_region_calibration:{calibration.id}"
            )
            evidence_refs.extend(calibration.evidence_refs[-4:])

        mean_delta = sum(
            item.confidence_delta
            for item in latest_by_signature.values()
        ) / max(1, len(latest_by_signature))
        confidence = _clamp(parent.confidence + mean_delta)

        record = ContextCausalValidityMap(
            id=self.next_context_causal_validity_map_id,
            hypothesis_id=parent.hypothesis_id,
            source_invariance_assessment_ids=(
                parent.source_invariance_assessment_ids
            ),
            source_boundary_plan_ids=parent.source_boundary_plan_ids,
            signature_assessment_ids=parent.signature_assessment_ids,
            tested_valid_signatures=parent.tested_valid_signatures,
            tested_invalid_signatures=parent.tested_invalid_signatures,
            dimensions=parent.dimensions,
            max_generalization_distance=parent.max_generalization_distance,
            confidence=round(confidence, 6),
            evidence_refs=tuple(dict.fromkeys(evidence_refs)),
            parent_map_id=parent.id,
            revision_number=parent.revision_number + 1,
            source_calibration_ids=tuple(
                sorted(item.id for item in latest_by_signature.values())
            ),
            calibrated_supported_signatures=tuple(sorted(supported)),
            revoked_inferred_signatures=tuple(sorted(revoked)),
            revision_reasons=tuple(reasons),
        )
        self.next_context_causal_validity_map_id += 1
        self.context_causal_validity_maps.append(record)
        if len(self.context_causal_validity_maps) > self.max_memory:
            self.context_causal_validity_maps = (
                self.context_causal_validity_maps[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity map revision={record.id}; "
                f"parent={parent.id}; revision={record.revision_number}; "
                f"supported={len(record.calibrated_supported_signatures)}; "
                f"revoked={len(record.revoked_inferred_signatures)}"
            ),
            salience=max(0.55, record.confidence),
            evidence_refs=(
                f"context_causal_validity_map:{record.id}",
                f"context_causal_validity_map:{parent.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def _context_validity_map_lineage(
        self,
        map_id: int,
    ) -> tuple[int, ...]:
        maps = {item.id: item for item in self.context_causal_validity_maps}
        target = maps.get(map_id)
        if target is None:
            raise ValueError("unknown context causal validity map")

        hypothesis_id = target.hypothesis_id
        seen: set[int] = set()
        reverse_lineage: list[int] = []
        current = target
        while True:
            if current.id in seen:
                raise ValueError("cyclic context validity map lineage")
            seen.add(current.id)
            reverse_lineage.append(current.id)
            if current.parent_map_id is None:
                if current.revision_number != 1:
                    raise ValueError(
                        "base context validity map must be revision 1"
                    )
                break
            parent = maps.get(current.parent_map_id)
            if parent is None:
                raise ValueError("context validity map parent is missing")
            if parent.hypothesis_id != hypothesis_id:
                raise ValueError(
                    "context validity map lineage crosses hypotheses"
                )
            if current.revision_number != parent.revision_number + 1:
                raise ValueError(
                    "context validity map revision numbers are not contiguous"
                )
            current = parent

        return tuple(reversed(reverse_lineage))

    def active_context_causal_validity_map(
        self,
        hypothesis_id: int,
    ) -> ContextCausalValidityMap | None:
        map_id = self.active_context_validity_map_ids.get(hypothesis_id)
        if map_id is None:
            return None
        self._context_validity_map_lineage(map_id)
        item = next(
            (
                candidate
                for candidate in self.context_causal_validity_maps
                if candidate.id == map_id
            ),
            None,
        )
        if item is None or item.hypothesis_id != hypothesis_id:
            raise ValueError("active context validity map pointer is invalid")
        return item

    def select_context_validity_map_revision(
        self,
        hypothesis_id: int,
        *,
        map_id: int | None = None,
        reason: str = "select latest intact validity-map revision",
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> ContextValidityMapSelection:
        """
        Activate one intact validity-map lineage without deleting other revisions.

        When no map ID is supplied, the highest intact revision is selected
        deterministically. If an active pointer already exists, ordinary
        selection may only remain on it or advance along its descendant chain.
        """
        candidates = [
            item
            for item in self.context_causal_validity_maps
            if item.hypothesis_id == hypothesis_id
        ]
        if not candidates:
            raise ValueError("no validity maps exist for hypothesis")

        valid_candidates: list[
            tuple[int, int, ContextCausalValidityMap, tuple[int, ...]]
        ] = []
        for item in candidates:
            try:
                lineage = self._context_validity_map_lineage(item.id)
            except ValueError:
                continue
            valid_candidates.append(
                (item.revision_number, item.id, item, lineage)
            )
        if not valid_candidates:
            raise ValueError("no intact validity-map lineage exists")

        if map_id is None:
            _, _, selected, lineage = max(
                valid_candidates,
                key=lambda row: (row[0], row[1]),
            )
        else:
            match = next(
                (
                    row
                    for row in valid_candidates
                    if row[2].id == map_id
                ),
                None,
            )
            if match is None:
                raise ValueError(
                    "requested validity map has no intact lineage"
                )
            _, _, selected, lineage = match

        previous_map_id = self.active_context_validity_map_ids.get(
            hypothesis_id
        )
        if previous_map_id is not None and previous_map_id != selected.id:
            if previous_map_id not in lineage:
                raise ValueError(
                    "selection must advance current lineage; use rollback "
                    "for an ancestor"
                )

        if previous_map_id is not None and previous_map_id != selected.id:
            drift_resolution = next(
                (
                    item
                    for item in reversed(
                        self.context_validity_reactivation_drift_resolutions
                    )
                    if item.hypothesis_id == hypothesis_id
                    and item.decision == "rollback_review"
                    and item.rollback_selection_id is not None
                    and item.blocked_descendant_map_id == selected.id
                ),
                None,
            )
            if drift_resolution is not None:
                rollback_selection = next(
                    (
                        item
                        for item in self.context_validity_map_selection_history
                        if item.id == drift_resolution.rollback_selection_id
                    ),
                    None,
                )
                if (
                    rollback_selection is not None
                    and rollback_selection.selected_map_id == previous_map_id
                ):
                    renewed_holdout = next(
                        (
                            item
                            for item in reversed(
                                self.context_validity_renewed_holdout_validations
                            )
                            if item.drift_resolution_id == drift_resolution.id
                            and item.blocked_descendant_map_id == selected.id
                        ),
                        None,
                    )
                    if (
                        renewed_holdout is None
                        or not renewed_holdout.reactivation_allowed
                    ):
                        raise ValueError(
                            "re-advance blocked until renewed-degradation rollback "
                            "completes a new evidence cycle: fresh recovery and "
                            "independent holdout cycle required"
                        )

            accepted = next(
                (
                    item
                    for item in reversed(
                        self.context_validity_recommendation_resolutions
                    )
                    if item.hypothesis_id == hypothesis_id
                    and item.decision == "accept"
                    and item.rollback_selection_id is not None
                ),
                None,
            )
            if accepted is not None:
                rollback_selection = next(
                    (
                        item
                        for item in self.context_validity_map_selection_history
                        if item.id == accepted.rollback_selection_id
                    ),
                    None,
                )
                if (
                    rollback_selection is not None
                    and rollback_selection.selected_map_id == previous_map_id
                ):
                    holdout = next(
                        (
                            item
                            for item in reversed(
                                self.context_validity_rollback_holdout_validations
                            )
                            if item.resolution_id == accepted.id
                        ),
                        None,
                    )
                    if holdout is None or not holdout.reactivation_allowed:
                        raise ValueError(
                            "re-advance blocked until accepted rollback "
                            "passes separate recovery and holdout validation"
                        )

        clean_reason = reason.strip()[:500]
        if not clean_reason:
            raise ValueError("selection reason is required")
        refs = tuple(
            dict.fromkeys(
                str(ref).strip()
                for ref in evidence_refs
                if str(ref).strip()
            )
        )
        action = (
            "activate"
            if previous_map_id is None
            else "retain"
            if previous_map_id == selected.id
            else "advance"
        )
        record = ContextValidityMapSelection(
            id=self.next_context_validity_map_selection_id,
            hypothesis_id=hypothesis_id,
            previous_map_id=previous_map_id,
            selected_map_id=selected.id,
            action=action,
            reason=clean_reason,
            lineage=lineage,
            evidence_refs=tuple(
                dict.fromkeys(
                    (
                        f"context_causal_validity_map:{selected.id}",
                        *refs,
                    )
                )
            ),
            calibration_watermark_id=max(
                (
                    item.id
                    for item in self.context_validity_region_calibrations
                ),
                default=0,
            ),
            decision_gate_watermark_id=max(
                (
                    item.id
                    for item in self.context_validity_decision_gates
                ),
                default=0,
            ),
        )
        self.next_context_validity_map_selection_id += 1
        self.active_context_validity_map_ids[hypothesis_id] = selected.id
        self.context_validity_map_selection_history.append(record)
        if len(self.context_validity_map_selection_history) > self.max_memory:
            self.context_validity_map_selection_history = (
                self.context_validity_map_selection_history[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity selection={record.id}; "
                f"hypothesis={hypothesis_id}; action={record.action}; "
                f"active_map={record.selected_map_id}; "
                f"lineage_depth={len(record.lineage)}"
            ),
            salience=max(0.55, selected.confidence),
            evidence_refs=(
                f"context_validity_map_selection:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def rollback_context_validity_map(
        self,
        hypothesis_id: int,
        *,
        target_map_id: int,
        reason: str,
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> ContextValidityMapSelection:
        """
        Roll the active pointer back to an ancestor without deleting revisions.
        """
        current = self.active_context_causal_validity_map(hypothesis_id)
        if current is None:
            raise ValueError("no active validity map exists for hypothesis")
        current_lineage = self._context_validity_map_lineage(current.id)
        target_lineage = self._context_validity_map_lineage(target_map_id)
        target = next(
            item
            for item in self.context_causal_validity_maps
            if item.id == target_map_id
        )
        if target.hypothesis_id != hypothesis_id:
            raise ValueError("rollback target belongs to another hypothesis")
        if target.id == current.id:
            raise ValueError("rollback target is already active")
        if target.id not in current_lineage:
            raise ValueError("rollback target is not an ancestor of active map")
        if target_lineage != current_lineage[: len(target_lineage)]:
            raise ValueError("rollback target lineage does not match active map")

        clean_reason = reason.strip()[:500]
        if not clean_reason:
            raise ValueError("rollback reason is required")
        refs = tuple(
            dict.fromkeys(
                str(ref).strip()
                for ref in evidence_refs
                if str(ref).strip()
            )
        )
        record = ContextValidityMapSelection(
            id=self.next_context_validity_map_selection_id,
            hypothesis_id=hypothesis_id,
            previous_map_id=current.id,
            selected_map_id=target.id,
            action="rollback",
            reason=clean_reason,
            lineage=target_lineage,
            evidence_refs=tuple(
                dict.fromkeys(
                    (
                        f"context_causal_validity_map:{current.id}",
                        f"context_causal_validity_map:{target.id}",
                        *refs,
                    )
                )
            ),
            calibration_watermark_id=max(
                (
                    item.id
                    for item in self.context_validity_region_calibrations
                ),
                default=0,
            ),
            decision_gate_watermark_id=max(
                (
                    item.id
                    for item in self.context_validity_decision_gates
                ),
                default=0,
            ),
        )
        self.next_context_validity_map_selection_id += 1
        self.active_context_validity_map_ids[hypothesis_id] = target.id
        self.context_validity_map_selection_history.append(record)
        if len(self.context_validity_map_selection_history) > self.max_memory:
            self.context_validity_map_selection_history = (
                self.context_validity_map_selection_history[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity rollback={record.id}; "
                f"hypothesis={hypothesis_id}; from={current.id}; "
                f"to={target.id}; preserved_later_revisions=true"
            ),
            salience=max(0.60, target.confidence),
            evidence_refs=(
                f"context_validity_map_selection:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def watch_active_context_validity_degradation(
        self,
        hypothesis_id: int,
        *,
        min_samples: int = 3,
        degradation_margin: float = 0.05,
    ) -> ContextValidityDegradationWatch:
        """
        Inspect post-activation calibration and recommend, but never execute, rollback.

        Degradation must be supported by repeated observed outcomes already
        summarized in region-calibration records. The nearest intact ancestor
        is recommended only when it has favorable calibration for at least one
        degraded environment and a better mean advantage than the active map.
        """
        active = self.active_context_causal_validity_map(hypothesis_id)
        if active is None:
            raise ValueError("no active validity map exists for hypothesis")

        selection = next(
            (
                item
                for item in reversed(
                    self.context_validity_map_selection_history
                )
                if item.hypothesis_id == hypothesis_id
                and item.selected_map_id == active.id
            ),
            None,
        )
        if selection is None:
            raise ValueError("active validity map has no selection record")

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(degradation_margin, 0.01, 0.50)
        post_activation = [
            item
            for item in self.context_validity_region_calibrations
            if item.validity_map_id == active.id
            and item.id > selection.calibration_watermark_id
            and item.sample_count >= min_samples
        ]

        latest_by_signature: dict[
            str,
            ContextValidityRegionCalibration,
        ] = {}
        for item in post_activation:
            previous = latest_by_signature.get(item.environment_signature)
            if previous is None or item.id > previous.id:
                latest_by_signature[item.environment_signature] = item

        degraded = [
            item
            for item in latest_by_signature.values()
            if item.gated_advantage_vs_alternative <= -margin
        ]
        degraded.sort(key=lambda item: item.environment_signature)
        degraded_signatures = tuple(
            item.environment_signature for item in degraded
        )
        mean_active_advantage = (
            sum(
                item.gated_advantage_vs_alternative
                for item in degraded
            )
            / len(degraded)
            if degraded
            else 0.0
        )

        recommended_map: ContextCausalValidityMap | None = None
        ancestor_support_ids: tuple[int, ...] = ()
        status = (
            "insufficient_post_activation_evidence"
            if not latest_by_signature
            else "stable"
            if not degraded
            else "degradation_detected_no_supported_ancestor"
        )
        reason = (
            "no post-activation calibration meets the minimum sample threshold"
            if not latest_by_signature
            else "post-activation calibration does not show sustained degradation"
            if not degraded
            else "active revision degraded but no better-calibrated ancestor was found"
        )

        if degraded:
            lineage = self._context_validity_map_lineage(active.id)
            maps = {
                item.id: item
                for item in self.context_causal_validity_maps
            }
            for ancestor_id in reversed(lineage[:-1]):
                ancestor = maps[ancestor_id]
                favorable = [
                    item
                    for item in self.context_validity_region_calibrations
                    if item.validity_map_id == ancestor.id
                    and item.environment_signature in degraded_signatures
                    and item.sample_count >= min_samples
                    and item.gated_advantage_vs_alternative >= margin
                ]
                latest_favorable: dict[
                    str,
                    ContextValidityRegionCalibration,
                ] = {}
                for item in favorable:
                    previous = latest_favorable.get(item.environment_signature)
                    if previous is None or item.id > previous.id:
                        latest_favorable[item.environment_signature] = item
                if not latest_favorable:
                    continue
                ancestor_mean = (
                    sum(
                        item.gated_advantage_vs_alternative
                        for item in latest_favorable.values()
                    )
                    / len(latest_favorable)
                )
                if ancestor_mean <= mean_active_advantage:
                    continue
                recommended_map = ancestor
                ancestor_support_ids = tuple(
                    sorted(
                        item.id
                        for item in latest_favorable.values()
                    )
                )
                status = "rollback_recommended"
                reason = (
                    "post-activation calibration degraded and the nearest "
                    "intact ancestor retains better matched calibration support"
                )
                break

        refs = [
            f"context_causal_validity_map:{active.id}",
            f"context_validity_map_selection:{selection.id}",
        ]
        refs.extend(
            f"context_validity_region_calibration:{item.id}"
            for item in latest_by_signature.values()
        )
        refs.extend(
            f"context_validity_region_calibration:{item_id}"
            for item_id in ancestor_support_ids
        )
        if recommended_map is not None:
            refs.append(
                f"context_causal_validity_map:{recommended_map.id}"
            )

        record = ContextValidityDegradationWatch(
            id=self.next_context_validity_degradation_watch_id,
            hypothesis_id=hypothesis_id,
            active_map_id=active.id,
            activation_selection_id=selection.id,
            calibration_watermark_id=selection.calibration_watermark_id,
            observed_calibration_ids=tuple(
                sorted(item.id for item in latest_by_signature.values())
            ),
            degraded_signatures=degraded_signatures,
            mean_active_advantage=round(mean_active_advantage, 6),
            recommended_map_id=(
                recommended_map.id
                if recommended_map is not None
                else None
            ),
            recommended_revision_number=(
                recommended_map.revision_number
                if recommended_map is not None
                else None
            ),
            ancestor_support_calibration_ids=ancestor_support_ids,
            status=status,
            reason=reason,
            evidence_refs=tuple(dict.fromkeys(refs)),
        )
        self.next_context_validity_degradation_watch_id += 1
        self.context_validity_degradation_watches.append(record)
        if len(self.context_validity_degradation_watches) > self.max_memory:
            self.context_validity_degradation_watches = (
                self.context_validity_degradation_watches[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity degradation watch={record.id}; "
                f"active_map={record.active_map_id}; "
                f"status={record.status}; "
                f"recommended_map={record.recommended_map_id}"
            ),
            salience=(
                0.75
                if record.status == "rollback_recommended"
                else 0.50
            ),
            evidence_refs=(
                f"context_validity_degradation_watch:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def resolve_context_validity_degradation_watch(
        self,
        watch_id: int,
        *,
        decision: str,
        reason: str,
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> ContextValidityRecommendationResolution:
        """
        Record an explicit accept, defer, or dismiss decision for a watch.

        Accept uses the existing ancestor-only rollback operation. Defer and
        dismiss never move the active validity-map pointer.
        """
        watch = next(
            (
                item
                for item in self.context_validity_degradation_watches
                if item.id == watch_id
            ),
            None,
        )
        if watch is None:
            raise ValueError("unknown context validity degradation watch")

        normalized = decision.strip().casefold()
        if normalized not in {"accept", "defer", "dismiss"}:
            raise ValueError("resolution must be accept, defer, or dismiss")

        terminal = next(
            (
                item
                for item in reversed(
                    self.context_validity_recommendation_resolutions
                )
                if item.watch_id == watch_id
                and item.decision in {"accept", "dismiss"}
            ),
            None,
        )
        if terminal is not None:
            raise ValueError("degradation recommendation already terminally resolved")

        clean_reason = reason.strip()[:500]
        if not clean_reason:
            raise ValueError("resolution reason is required")
        refs = tuple(
            dict.fromkeys(
                str(ref).strip()
                for ref in evidence_refs
                if str(ref).strip()
            )
        )

        rollback_selection_id: int | None = None
        if normalized == "accept":
            if (
                watch.status != "rollback_recommended"
                or watch.recommended_map_id is None
            ):
                raise ValueError("watch does not contain a rollback recommendation")
            active = self.active_context_causal_validity_map(
                watch.hypothesis_id
            )
            if active is None or active.id != watch.active_map_id:
                raise ValueError(
                    "rollback recommendation is stale for the active map"
                )
            rollback = self.rollback_context_validity_map(
                watch.hypothesis_id,
                target_map_id=watch.recommended_map_id,
                reason=(
                    "accepted degradation-watch recommendation: "
                    f"{clean_reason}"
                ),
                evidence_refs=(
                    f"context_validity_degradation_watch:{watch.id}",
                    *refs,
                ),
            )
            rollback_selection_id = rollback.id

        record = ContextValidityRecommendationResolution(
            id=self.next_context_validity_recommendation_resolution_id,
            watch_id=watch.id,
            hypothesis_id=watch.hypothesis_id,
            decision=normalized,
            reason=clean_reason,
            recommended_map_id=watch.recommended_map_id,
            blocked_descendant_map_id=(
                watch.active_map_id if normalized == "accept" else None
            ),
            rollback_selection_id=rollback_selection_id,
            evidence_refs=tuple(
                dict.fromkeys(
                    (
                        f"context_validity_degradation_watch:{watch.id}",
                        *refs,
                    )
                )
            ),
        )
        self.next_context_validity_recommendation_resolution_id += 1
        self.context_validity_recommendation_resolutions.append(record)
        if len(self.context_validity_recommendation_resolutions) > self.max_memory:
            self.context_validity_recommendation_resolutions = (
                self.context_validity_recommendation_resolutions[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity recommendation resolution={record.id}; "
                f"watch={watch.id}; decision={record.decision}; "
                f"rollback_selection={record.rollback_selection_id}"
            ),
            salience=0.70 if normalized == "accept" else 0.55,
            evidence_refs=(
                f"context_validity_recommendation_resolution:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def validate_context_validity_rollback(
        self,
        resolution_id: int,
        *,
        min_samples: int = 3,
        improvement_margin: float = 0.05,
    ) -> ContextValidityRollbackValidation:
        """
        Validate an accepted rollback using only outcomes observed after rollback.

        A descendant cannot be re-advanced until a validation record shows
        positive, materially improved calibration on every degraded signature.
        """
        resolution = next(
            (
                item
                for item in self.context_validity_recommendation_resolutions
                if item.id == resolution_id
            ),
            None,
        )
        if resolution is None:
            raise ValueError("unknown degradation recommendation resolution")
        if (
            resolution.decision != "accept"
            or resolution.rollback_selection_id is None
            or resolution.blocked_descendant_map_id is None
        ):
            raise ValueError("rollback validation requires an accepted resolution")

        watch = next(
            (
                item
                for item in self.context_validity_degradation_watches
                if item.id == resolution.watch_id
            ),
            None,
        )
        rollback_selection = next(
            (
                item
                for item in self.context_validity_map_selection_history
                if item.id == resolution.rollback_selection_id
            ),
            None,
        )
        if watch is None or rollback_selection is None:
            raise ValueError("accepted rollback evidence is incomplete")

        active = self.active_context_causal_validity_map(
            resolution.hypothesis_id
        )
        if (
            active is None
            or active.id != rollback_selection.selected_map_id
        ):
            raise ValueError("rollback validation requires rollback map to remain active")

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(improvement_margin, 0.01, 0.50)
        degraded = set(watch.degraded_signatures)
        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == rollback_selection.selected_map_id
            and item.id > rollback_selection.decision_gate_watermark_id
            and item.environment_signature in degraded
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        counts: dict[str, int] = {}
        for outcome in outcomes:
            signature = gate_map[outcome.gate_id].environment_signature
            counts[signature] = counts.get(signature, 0) + 1

        enough = bool(degraded) and all(
            counts.get(signature, 0) >= min_samples
            for signature in degraded
        )
        mean_advantage = (
            sum(
                item.gated_advantage_vs_alternative
                for item in outcomes
            )
            / len(outcomes)
            if outcomes
            else 0.0
        )
        improvement = mean_advantage - watch.mean_active_advantage

        if not enough:
            status = "insufficient_post_rollback_evidence"
            recovery_passed = False
        elif (
            mean_advantage >= margin
            and improvement >= margin
        ):
            status = "rollback_recovery_passed"
            recovery_passed = True
        else:
            status = "rollback_not_improved"
            recovery_passed = False
        allowed = False

        refs = [
            f"context_validity_recommendation_resolution:{resolution.id}",
            f"context_validity_degradation_watch:{watch.id}",
            f"context_validity_map_selection:{rollback_selection.id}",
        ]
        refs.extend(
            f"context_validity_gate_outcome:{item.id}"
            for item in outcomes
        )
        record = ContextValidityRollbackValidation(
            id=self.next_context_validity_rollback_validation_id,
            resolution_id=resolution.id,
            watch_id=watch.id,
            hypothesis_id=resolution.hypothesis_id,
            rollback_selection_id=rollback_selection.id,
            rollback_map_id=rollback_selection.selected_map_id,
            blocked_descendant_map_id=resolution.blocked_descendant_map_id,
            observed_outcome_ids=tuple(sorted(item.id for item in outcomes)),
            degraded_signatures=tuple(sorted(degraded)),
            mean_rollback_advantage=round(mean_advantage, 6),
            prior_degraded_advantage=watch.mean_active_advantage,
            improvement_delta=round(improvement, 6),
            status=status,
            reactivation_allowed=allowed,
            evidence_refs=tuple(dict.fromkeys(refs)),
            holdout_gate_watermark_id=(
                max(
                    (
                        item.id
                        for item in self.context_validity_decision_gates
                    ),
                    default=0,
                )
                if recovery_passed
                else 0
            ),
        )
        self.next_context_validity_rollback_validation_id += 1
        self.context_validity_rollback_validations.append(record)
        if len(self.context_validity_rollback_validations) > self.max_memory:
            self.context_validity_rollback_validations = (
                self.context_validity_rollback_validations[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity rollback validation={record.id}; "
                f"resolution={resolution.id}; status={record.status}; "
                f"holdout_watermark={record.holdout_gate_watermark_id}; "
                f"reactivation_allowed={record.reactivation_allowed}"
            ),
            salience=0.70 if recovery_passed else 0.60,
            evidence_refs=(
                f"context_validity_rollback_validation:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def validate_context_validity_rollback_holdout(
        self,
        recovery_validation_id: int,
        *,
        min_samples: int = 3,
        confirmation_margin: float = 0.05,
        max_recovery_drop: float = 0.05,
    ) -> ContextValidityRollbackHoldoutValidation:
        """
        Confirm rollback recovery on a separate post-recovery holdout batch.

        Holdout outcomes must be generated after the recovery validation
        watermark, preventing the same evidence from justifying both recovery
        and descendant reactivation.
        """
        recovery = next(
            (
                item
                for item in self.context_validity_rollback_validations
                if item.id == recovery_validation_id
            ),
            None,
        )
        if recovery is None:
            raise ValueError("unknown rollback recovery validation")
        if (
            recovery.status != "rollback_recovery_passed"
            or recovery.holdout_gate_watermark_id <= 0
        ):
            raise ValueError("holdout requires a passed rollback recovery batch")

        resolution = next(
            (
                item
                for item in self.context_validity_recommendation_resolutions
                if item.id == recovery.resolution_id
            ),
            None,
        )
        if resolution is None:
            raise ValueError("rollback recovery resolution is missing")
        active = self.active_context_causal_validity_map(
            recovery.hypothesis_id
        )
        if active is None or active.id != recovery.rollback_map_id:
            raise ValueError("holdout validation requires rollback map to remain active")

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(confirmation_margin, 0.01, 0.50)
        max_drop = _clamp(max_recovery_drop, 0.0, 0.50)
        degraded = set(recovery.degraded_signatures)
        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == recovery.rollback_map_id
            and item.id > recovery.holdout_gate_watermark_id
            and item.environment_signature in degraded
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        counts: dict[str, int] = {}
        for outcome in outcomes:
            signature = gate_map[outcome.gate_id].environment_signature
            counts[signature] = counts.get(signature, 0) + 1

        enough = bool(degraded) and all(
            counts.get(signature, 0) >= min_samples
            for signature in degraded
        )
        mean_holdout = (
            sum(
                item.gated_advantage_vs_alternative
                for item in outcomes
            )
            / len(outcomes)
            if outcomes
            else 0.0
        )
        improvement = mean_holdout - recovery.prior_degraded_advantage
        recovery_delta = mean_holdout - recovery.mean_rollback_advantage

        if not enough:
            status = "insufficient_holdout_evidence"
            allowed = False
        elif (
            mean_holdout >= margin
            and improvement >= margin
            and recovery_delta >= -max_drop
        ):
            status = "holdout_confirmed"
            allowed = True
        else:
            status = "holdout_not_confirmed"
            allowed = False

        refs = [
            f"context_validity_rollback_validation:{recovery.id}",
            f"context_validity_recommendation_resolution:{resolution.id}",
        ]
        refs.extend(
            f"context_validity_gate_outcome:{item.id}"
            for item in outcomes
        )
        record = ContextValidityRollbackHoldoutValidation(
            id=self.next_context_validity_rollback_holdout_validation_id,
            recovery_validation_id=recovery.id,
            resolution_id=recovery.resolution_id,
            watch_id=recovery.watch_id,
            hypothesis_id=recovery.hypothesis_id,
            rollback_selection_id=recovery.rollback_selection_id,
            rollback_map_id=recovery.rollback_map_id,
            blocked_descendant_map_id=recovery.blocked_descendant_map_id,
            recovery_outcome_ids=recovery.observed_outcome_ids,
            holdout_outcome_ids=tuple(sorted(item.id for item in outcomes)),
            degraded_signatures=recovery.degraded_signatures,
            mean_recovery_advantage=recovery.mean_rollback_advantage,
            mean_holdout_advantage=round(mean_holdout, 6),
            prior_degraded_advantage=recovery.prior_degraded_advantage,
            holdout_improvement_delta=round(improvement, 6),
            recovery_to_holdout_delta=round(recovery_delta, 6),
            status=status,
            reactivation_allowed=allowed,
            evidence_refs=tuple(dict.fromkeys(refs)),
        )
        self.next_context_validity_rollback_holdout_validation_id += 1
        self.context_validity_rollback_holdout_validations.append(record)
        if len(self.context_validity_rollback_holdout_validations) > self.max_memory:
            self.context_validity_rollback_holdout_validations = (
                self.context_validity_rollback_holdout_validations[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity rollback holdout={record.id}; "
                f"recovery={recovery.id}; status={record.status}; "
                f"reactivation_allowed={record.reactivation_allowed}"
            ),
            salience=0.75 if allowed else 0.60,
            evidence_refs=(
                f"context_validity_rollback_holdout_validation:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def _latest_context_validity_reactivation_holdout(
        self,
        hypothesis_id: int,
        active_map_id: int,
    ) -> tuple[
        str,
        ContextValidityRollbackHoldoutValidation
        | ContextValidityRenewedHoldoutValidation,
    ] | None:
        """Return the newest holdout that actually authorized the active descendant."""
        renewed = next(
            (
                item
                for item in reversed(
                    self.context_validity_renewed_holdout_validations
                )
                if item.hypothesis_id == hypothesis_id
                and item.reactivation_allowed
                and item.blocked_descendant_map_id == active_map_id
            ),
            None,
        )
        if renewed is not None:
            return "renewed", renewed

        initial = next(
            (
                item
                for item in reversed(
                    self.context_validity_rollback_holdout_validations
                )
                if item.hypothesis_id == hypothesis_id
                and item.reactivation_allowed
                and item.blocked_descendant_map_id == active_map_id
            ),
            None,
        )
        if initial is not None:
            return "initial", initial
        return None

    def watch_reactivated_context_validity_drift(
        self,
        hypothesis_id: int,
        *,
        min_samples: int = 3,
        degradation_margin: float = 0.05,
        max_holdout_drop: float = 0.05,
    ) -> ContextValidityReactivationDriftWatch:
        """
        Inspect only outcomes observed after holdout-confirmed reactivation.

        Recovery and holdout evidence are excluded by the reactivation
        selection's decision-gate watermark. This method records a governance
        recommendation only and never changes the active validity map.
        """
        active = self.active_context_causal_validity_map(hypothesis_id)
        if active is None:
            raise ValueError("no active validity map exists for hypothesis")

        holdout_match = self._latest_context_validity_reactivation_holdout(
            hypothesis_id,
            active.id,
        )
        if holdout_match is None:
            raise ValueError(
                "reactivation drift watch requires a confirmed rollback holdout"
            )
        holdout_source, holdout = holdout_match

        reactivation = next(
            (
                item
                for item in reversed(
                    self.context_validity_map_selection_history
                )
                if item.hypothesis_id == hypothesis_id
                and item.selected_map_id == active.id
                and item.action == "advance"
                and item.id > holdout.rollback_selection_id
            ),
            None,
        )
        if reactivation is None:
            raise ValueError(
                "reactivation drift watch requires an explicit descendant advance"
            )

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(degradation_margin, 0.01, 0.50)
        max_drop = _clamp(max_holdout_drop, 0.0, 0.50)
        signatures = set(holdout.degraded_signatures)
        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == active.id
            and item.id > reactivation.decision_gate_watermark_id
            and item.environment_signature in signatures
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        counts: dict[str, int] = {}
        for outcome in outcomes:
            signature = gate_map[outcome.gate_id].environment_signature
            counts[signature] = counts.get(signature, 0) + 1

        enough = bool(signatures) and all(
            counts.get(signature, 0) >= min_samples
            for signature in signatures
        )
        mean_advantage = (
            sum(
                item.gated_advantage_vs_alternative
                for item in outcomes
            )
            / len(outcomes)
            if outcomes
            else 0.0
        )
        delta = mean_advantage - holdout.mean_holdout_advantage
        holdout_drop = holdout.mean_holdout_advantage - mean_advantage

        if not enough:
            status = "insufficient_post_reactivation_evidence"
            recommended_action = "observe_more"
            reason = (
                "not every previously degraded signature has enough new "
                "post-reactivation outcomes"
            )
        elif (
            mean_advantage <= -margin
            and holdout_drop >= margin
        ):
            status = "renewed_degradation_detected"
            recommended_action = "review_for_rollback"
            reason = (
                "post-reactivation outcomes show renewed negative calibration "
                "and a material drop from the confirmed holdout baseline"
            )
        elif (
            mean_advantage >= margin
            and holdout_drop <= max_drop
        ):
            status = "post_reactivation_stable"
            recommended_action = "continue_monitoring"
            reason = (
                "post-reactivation calibration remains positive and within "
                "the tolerated drop from the holdout baseline"
            )
        else:
            status = "post_reactivation_warning"
            recommended_action = "collect_more_evidence"
            reason = (
                "post-reactivation evidence is neither stably confirmed nor "
                "strong enough to establish renewed degradation"
            )

        holdout_ref = (
            f"context_validity_renewed_holdout_validation:{holdout.id}"
            if holdout_source == "renewed"
            else f"context_validity_rollback_holdout_validation:{holdout.id}"
        )
        episode_id = 1 + sum(
            1
            for item in self.context_validity_reactivation_drift_resolutions
            if item.hypothesis_id == hypothesis_id
            and item.decision == "rollback_review"
            and item.requires_new_evidence_cycle
        )
        refs = [
            holdout_ref,
            f"context_validity_map_selection:{reactivation.id}",
            f"context_causal_validity_map:{active.id}",
        ]
        refs.extend(
            f"context_validity_gate_outcome:{item.id}"
            for item in outcomes
        )
        record = ContextValidityReactivationDriftWatch(
            id=self.next_context_validity_reactivation_drift_watch_id,
            holdout_validation_id=holdout.id,
            hypothesis_id=hypothesis_id,
            reactivation_selection_id=reactivation.id,
            active_map_id=active.id,
            decision_gate_watermark_id=(
                reactivation.decision_gate_watermark_id
            ),
            observed_outcome_ids=tuple(sorted(item.id for item in outcomes)),
            degraded_signatures=tuple(sorted(signatures)),
            mean_post_reactivation_advantage=round(mean_advantage, 6),
            holdout_advantage=holdout.mean_holdout_advantage,
            advantage_delta=round(delta, 6),
            status=status,
            recommended_action=recommended_action,
            reason=reason,
            evidence_refs=tuple(dict.fromkeys(refs)),
            holdout_source=holdout_source,
            episode_id=episode_id,
        )
        self.next_context_validity_reactivation_drift_watch_id += 1
        self.context_validity_reactivation_drift_watches.append(record)
        if len(self.context_validity_reactivation_drift_watches) > self.max_memory:
            self.context_validity_reactivation_drift_watches = (
                self.context_validity_reactivation_drift_watches[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity reactivation drift={record.id}; "
                f"active_map={record.active_map_id}; "
                f"status={record.status}; "
                f"recommended_action={record.recommended_action}"
            ),
            salience=(
                0.78
                if record.status == "renewed_degradation_detected"
                else 0.55
            ),
            evidence_refs=(
                f"context_validity_reactivation_drift_watch:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def resolve_reactivated_context_validity_drift(
        self,
        drift_watch_id: int,
        *,
        decision: str,
        reason: str,
        evidence_refs: tuple[str, ...] | list[str] = (),
    ) -> ContextValidityReactivationDriftResolution:
        """
        Resolve a post-reactivation drift watch without erasing prior evidence.

        Defer leaves the recommendation open. Dismiss and rollback_review are
        terminal. A rollback review returns to the map that previously passed
        rollback recovery and requires a fresh evidence cycle before any later
        descendant re-advance.
        """
        watch = next(
            (
                item
                for item in self.context_validity_reactivation_drift_watches
                if item.id == drift_watch_id
            ),
            None,
        )
        if watch is None:
            raise ValueError("unknown context validity reactivation drift watch")

        normalized = decision.strip().casefold()
        if normalized not in {"defer", "dismiss", "rollback_review"}:
            raise ValueError(
                "drift resolution must be defer, dismiss, or rollback_review"
            )

        terminal = next(
            (
                item
                for item in reversed(
                    self.context_validity_reactivation_drift_resolutions
                )
                if item.drift_watch_id == watch.id
                and item.decision in {"dismiss", "rollback_review"}
            ),
            None,
        )
        if terminal is not None:
            raise ValueError("reactivation drift watch already terminally resolved")

        clean_reason = reason.strip()[:500]
        if not clean_reason:
            raise ValueError("drift resolution reason is required")
        refs = tuple(
            dict.fromkeys(
                str(ref).strip()
                for ref in evidence_refs
                if str(ref).strip()
            )
        )

        active = self.active_context_causal_validity_map(watch.hypothesis_id)
        if active is None:
            raise ValueError("no active validity map exists for hypothesis")
        if active.id != watch.active_map_id:
            raise ValueError("reactivation drift recommendation is stale")

        if watch.holdout_source == "renewed":
            holdout = next(
                (
                    item
                    for item in self.context_validity_renewed_holdout_validations
                    if item.id == watch.holdout_validation_id
                ),
                None,
            )
        elif watch.holdout_source == "initial":
            holdout = next(
                (
                    item
                    for item in self.context_validity_rollback_holdout_validations
                    if item.id == watch.holdout_validation_id
                ),
                None,
            )
        else:
            raise ValueError("unknown reactivation drift holdout source")
        if holdout is None or not holdout.reactivation_allowed:
            raise ValueError("reactivation drift holdout evidence is incomplete")
        holdout_ref = (
            f"context_validity_renewed_holdout_validation:{holdout.id}"
            if watch.holdout_source == "renewed"
            else f"context_validity_rollback_holdout_validation:{holdout.id}"
        )

        rollback_target_map_id: int | None = None
        rollback_selection_id: int | None = None
        blocked_descendant_map_id: int | None = None
        requires_new_evidence_cycle = False

        if normalized == "rollback_review":
            if (
                watch.status != "renewed_degradation_detected"
                or watch.recommended_action != "review_for_rollback"
            ):
                raise ValueError(
                    "drift watch does not contain a rollback-review recommendation"
                )
            rollback_target_map_id = holdout.rollback_map_id
            blocked_descendant_map_id = watch.active_map_id
            rollback = self.rollback_context_validity_map(
                watch.hypothesis_id,
                target_map_id=rollback_target_map_id,
                reason=(
                    "accepted renewed-degradation rollback review: "
                    f"{clean_reason}"
                ),
                evidence_refs=(
                    f"context_validity_reactivation_drift_watch:{watch.id}",
                    holdout_ref,
                    *refs,
                ),
            )
            rollback_selection_id = rollback.id
            requires_new_evidence_cycle = True

        episode_id = (
            watch.episode_id
            if watch.episode_id > 0
            else 1
            + sum(
                1
                for item in self.context_validity_reactivation_drift_resolutions
                if item.hypothesis_id == watch.hypothesis_id
                and item.decision == "rollback_review"
                and item.requires_new_evidence_cycle
            )
        )
        record = ContextValidityReactivationDriftResolution(
            id=self.next_context_validity_reactivation_drift_resolution_id,
            drift_watch_id=watch.id,
            holdout_validation_id=holdout.id,
            hypothesis_id=watch.hypothesis_id,
            decision=normalized,
            reason=clean_reason,
            active_map_id_before=watch.active_map_id,
            rollback_target_map_id=rollback_target_map_id,
            rollback_selection_id=rollback_selection_id,
            blocked_descendant_map_id=blocked_descendant_map_id,
            requires_new_evidence_cycle=requires_new_evidence_cycle,
            evidence_refs=tuple(
                dict.fromkeys(
                    (
                        f"context_validity_reactivation_drift_watch:{watch.id}",
                        holdout_ref,
                        *refs,
                    )
                )
            ),
            holdout_source=watch.holdout_source,
            episode_id=episode_id,
        )
        self.next_context_validity_reactivation_drift_resolution_id += 1
        self.context_validity_reactivation_drift_resolutions.append(record)
        if len(self.context_validity_reactivation_drift_resolutions) > self.max_memory:
            self.context_validity_reactivation_drift_resolutions = (
                self.context_validity_reactivation_drift_resolutions[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity reactivation drift resolution={record.id}; "
                f"watch={watch.id}; decision={record.decision}; "
                f"rollback_selection={record.rollback_selection_id}; "
                f"new_cycle={record.requires_new_evidence_cycle}"
            ),
            salience=0.78 if normalized == "rollback_review" else 0.55,
            evidence_refs=(
                f"context_validity_reactivation_drift_resolution:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record


    def _prior_context_validity_cycle_outcome_ids(
        self,
        hypothesis_id: int,
    ) -> set[int]:
        prior: set[int] = set()
        for item in self.context_validity_rollback_validations:
            if item.hypothesis_id == hypothesis_id:
                prior.update(item.observed_outcome_ids)
        for item in self.context_validity_rollback_holdout_validations:
            if item.hypothesis_id == hypothesis_id:
                prior.update(item.recovery_outcome_ids)
                prior.update(item.holdout_outcome_ids)
        for item in self.context_validity_reactivation_drift_watches:
            if item.hypothesis_id == hypothesis_id:
                prior.update(item.observed_outcome_ids)
        for item in self.context_validity_renewed_recovery_validations:
            if item.hypothesis_id == hypothesis_id:
                prior.update(item.observed_outcome_ids)
        for item in self.context_validity_renewed_holdout_validations:
            if item.hypothesis_id == hypothesis_id:
                prior.update(item.recovery_outcome_ids)
                prior.update(item.holdout_outcome_ids)
        return prior

    def validate_context_validity_renewed_rollback(
        self,
        drift_resolution_id: int,
        *,
        min_samples: int = 3,
        improvement_margin: float = 0.05,
    ) -> ContextValidityRenewedRecoveryValidation:
        """
        Validate the fresh recovery batch required after renewed degradation.

        Only outcomes created after the second rollback watermark are eligible.
        Any overlap with evidence from earlier recovery, holdout, reactivation,
        drift, or renewed-cycle episodes fails the validation closed.
        """
        resolution = next(
            (
                item
                for item in self.context_validity_reactivation_drift_resolutions
                if item.id == drift_resolution_id
            ),
            None,
        )
        if resolution is None:
            raise ValueError("unknown reactivation drift resolution")
        if (
            resolution.decision != "rollback_review"
            or not resolution.requires_new_evidence_cycle
            or resolution.rollback_selection_id is None
            or resolution.rollback_target_map_id is None
            or resolution.blocked_descendant_map_id is None
        ):
            raise ValueError(
                "renewed recovery requires a renewed-degradation rollback review"
            )

        watch = next(
            (
                item
                for item in self.context_validity_reactivation_drift_watches
                if item.id == resolution.drift_watch_id
            ),
            None,
        )
        if resolution.holdout_source == "renewed":
            prior_holdout = next(
                (
                    item
                    for item in self.context_validity_renewed_holdout_validations
                    if item.id == resolution.holdout_validation_id
                ),
                None,
            )
        elif resolution.holdout_source == "initial":
            prior_holdout = next(
                (
                    item
                    for item in self.context_validity_rollback_holdout_validations
                    if item.id == resolution.holdout_validation_id
                ),
                None,
            )
        else:
            raise ValueError("unknown renewed recovery holdout source")
        rollback_selection = next(
            (
                item
                for item in self.context_validity_map_selection_history
                if item.id == resolution.rollback_selection_id
            ),
            None,
        )
        if watch is None or prior_holdout is None or rollback_selection is None:
            raise ValueError("renewed rollback evidence is incomplete")

        active = self.active_context_causal_validity_map(
            resolution.hypothesis_id
        )
        if (
            active is None
            or active.id != resolution.rollback_target_map_id
            or rollback_selection.selected_map_id != active.id
        ):
            raise ValueError(
                "renewed recovery requires the second rollback map to remain active"
            )

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(improvement_margin, 0.01, 0.50)
        degraded = set(watch.degraded_signatures)
        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == active.id
            and item.id > rollback_selection.decision_gate_watermark_id
            and item.environment_signature in degraded
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        outcome_ids = {item.id for item in outcomes}
        prior_ids = self._prior_context_validity_cycle_outcome_ids(
            resolution.hypothesis_id
        )
        reused_ids = outcome_ids & prior_ids

        counts: dict[str, int] = {}
        for outcome in outcomes:
            signature = gate_map[outcome.gate_id].environment_signature
            counts[signature] = counts.get(signature, 0) + 1
        enough = bool(degraded) and all(
            counts.get(signature, 0) >= min_samples
            for signature in degraded
        )
        mean_advantage = (
            sum(item.gated_advantage_vs_alternative for item in outcomes)
            / len(outcomes)
            if outcomes
            else 0.0
        )
        improvement = mean_advantage - watch.mean_post_reactivation_advantage

        if reused_ids:
            status = "renewed_recovery_evidence_reused"
            recovery_passed = False
        elif not enough:
            status = "insufficient_renewed_recovery_evidence"
            recovery_passed = False
        elif mean_advantage >= margin and improvement >= margin:
            status = "renewed_recovery_passed"
            recovery_passed = True
        else:
            status = "renewed_recovery_not_improved"
            recovery_passed = False

        refs = [
            f"context_validity_reactivation_drift_resolution:{resolution.id}",
            f"context_validity_reactivation_drift_watch:{watch.id}",
            f"context_validity_map_selection:{rollback_selection.id}",
        ]
        refs.extend(
            f"context_validity_gate_outcome:{item.id}"
            for item in outcomes
        )
        record = ContextValidityRenewedRecoveryValidation(
            id=self.next_context_validity_renewed_recovery_validation_id,
            drift_resolution_id=resolution.id,
            drift_watch_id=watch.id,
            prior_holdout_validation_id=prior_holdout.id,
            hypothesis_id=resolution.hypothesis_id,
            rollback_selection_id=rollback_selection.id,
            rollback_map_id=active.id,
            blocked_descendant_map_id=resolution.blocked_descendant_map_id,
            observed_outcome_ids=tuple(sorted(outcome_ids)),
            excluded_prior_outcome_ids=tuple(sorted(prior_ids)),
            degraded_signatures=tuple(sorted(degraded)),
            mean_recovery_advantage=round(mean_advantage, 6),
            prior_degraded_advantage=watch.mean_post_reactivation_advantage,
            improvement_delta=round(improvement, 6),
            status=status,
            reactivation_allowed=False,
            evidence_refs=tuple(dict.fromkeys(refs)),
            holdout_gate_watermark_id=(
                max(
                    (item.id for item in self.context_validity_decision_gates),
                    default=0,
                )
                if recovery_passed
                else 0
            ),
            prior_holdout_source=resolution.holdout_source,
            episode_id=max(1, resolution.episode_id),
        )
        self.next_context_validity_renewed_recovery_validation_id += 1
        self.context_validity_renewed_recovery_validations.append(record)
        if len(self.context_validity_renewed_recovery_validations) > self.max_memory:
            self.context_validity_renewed_recovery_validations = (
                self.context_validity_renewed_recovery_validations[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity renewed recovery={record.id}; "
                f"resolution={resolution.id}; status={record.status}; "
                f"holdout_watermark={record.holdout_gate_watermark_id}"
            ),
            salience=0.76 if recovery_passed else 0.62,
            evidence_refs=(
                f"context_validity_renewed_recovery_validation:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def validate_context_validity_renewed_rollback_holdout(
        self,
        recovery_validation_id: int,
        *,
        min_samples: int = 3,
        confirmation_margin: float = 0.05,
        max_recovery_drop: float = 0.05,
    ) -> ContextValidityRenewedHoldoutValidation:
        """
        Confirm renewed recovery on a later independent holdout batch.

        Recovery evidence, all earlier episode evidence, and the new holdout
        evidence must be pairwise disjoint before reactivation can be allowed.
        """
        recovery = next(
            (
                item
                for item in self.context_validity_renewed_recovery_validations
                if item.id == recovery_validation_id
            ),
            None,
        )
        if recovery is None:
            raise ValueError("unknown renewed recovery validation")
        if (
            recovery.status != "renewed_recovery_passed"
            or recovery.holdout_gate_watermark_id <= 0
        ):
            raise ValueError("renewed holdout requires a passed recovery batch")

        resolution = next(
            (
                item
                for item in self.context_validity_reactivation_drift_resolutions
                if item.id == recovery.drift_resolution_id
            ),
            None,
        )
        if resolution is None:
            raise ValueError("renewed recovery resolution is missing")
        active = self.active_context_causal_validity_map(
            recovery.hypothesis_id
        )
        if active is None or active.id != recovery.rollback_map_id:
            raise ValueError(
                "renewed holdout requires rollback map to remain active"
            )

        min_samples = max(2, min(int(min_samples), 20))
        margin = _clamp(confirmation_margin, 0.01, 0.50)
        max_drop = _clamp(max_recovery_drop, 0.0, 0.50)
        degraded = set(recovery.degraded_signatures)
        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == recovery.rollback_map_id
            and item.id > recovery.holdout_gate_watermark_id
            and item.environment_signature in degraded
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        outcome_ids = {item.id for item in outcomes}
        prior_ids = set(recovery.excluded_prior_outcome_ids)
        prior_ids.update(recovery.observed_outcome_ids)
        reused_ids = outcome_ids & prior_ids

        counts: dict[str, int] = {}
        for outcome in outcomes:
            signature = gate_map[outcome.gate_id].environment_signature
            counts[signature] = counts.get(signature, 0) + 1
        enough = bool(degraded) and all(
            counts.get(signature, 0) >= min_samples
            for signature in degraded
        )
        mean_holdout = (
            sum(item.gated_advantage_vs_alternative for item in outcomes)
            / len(outcomes)
            if outcomes
            else 0.0
        )
        improvement = mean_holdout - recovery.prior_degraded_advantage
        recovery_delta = mean_holdout - recovery.mean_recovery_advantage

        if reused_ids:
            status = "renewed_holdout_evidence_reused"
            allowed = False
        elif not enough:
            status = "insufficient_renewed_holdout_evidence"
            allowed = False
        elif (
            mean_holdout >= margin
            and improvement >= margin
            and recovery_delta >= -max_drop
        ):
            status = "renewed_holdout_confirmed"
            allowed = True
        else:
            status = "renewed_holdout_not_confirmed"
            allowed = False

        refs = [
            f"context_validity_renewed_recovery_validation:{recovery.id}",
            f"context_validity_reactivation_drift_resolution:{resolution.id}",
        ]
        refs.extend(
            f"context_validity_gate_outcome:{item.id}"
            for item in outcomes
        )
        record = ContextValidityRenewedHoldoutValidation(
            id=self.next_context_validity_renewed_holdout_validation_id,
            recovery_validation_id=recovery.id,
            drift_resolution_id=recovery.drift_resolution_id,
            drift_watch_id=recovery.drift_watch_id,
            prior_holdout_validation_id=recovery.prior_holdout_validation_id,
            hypothesis_id=recovery.hypothesis_id,
            rollback_selection_id=recovery.rollback_selection_id,
            rollback_map_id=recovery.rollback_map_id,
            blocked_descendant_map_id=recovery.blocked_descendant_map_id,
            recovery_outcome_ids=recovery.observed_outcome_ids,
            holdout_outcome_ids=tuple(sorted(outcome_ids)),
            excluded_prior_outcome_ids=recovery.excluded_prior_outcome_ids,
            degraded_signatures=recovery.degraded_signatures,
            mean_recovery_advantage=recovery.mean_recovery_advantage,
            mean_holdout_advantage=round(mean_holdout, 6),
            prior_degraded_advantage=recovery.prior_degraded_advantage,
            holdout_improvement_delta=round(improvement, 6),
            recovery_to_holdout_delta=round(recovery_delta, 6),
            status=status,
            reactivation_allowed=allowed,
            evidence_refs=tuple(dict.fromkeys(refs)),
            prior_holdout_source=recovery.prior_holdout_source,
            episode_id=recovery.episode_id,
        )
        self.next_context_validity_renewed_holdout_validation_id += 1
        self.context_validity_renewed_holdout_validations.append(record)
        if len(self.context_validity_renewed_holdout_validations) > self.max_memory:
            self.context_validity_renewed_holdout_validations = (
                self.context_validity_renewed_holdout_validations[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity renewed holdout={record.id}; "
                f"recovery={recovery.id}; status={record.status}; "
                f"reactivation_allowed={record.reactivation_allowed}"
            ),
            salience=0.80 if allowed else 0.62,
            evidence_refs=(
                f"context_validity_renewed_holdout_validation:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def evaluate_active_context_validity_gated_decision(
        self,
        hypothesis_id: int,
        *,
        environment_signature: str,
        candidates: list[dict[str, Any]],
        context: str,
    ) -> ContextValidityDecisionGate:
        """Evaluate a decision through the currently active validity map."""
        active = self.active_context_causal_validity_map(hypothesis_id)
        if active is None:
            raise ValueError("no active validity map exists for hypothesis")
        return self.evaluate_context_validity_gated_decision(
            active.id,
            environment_signature=environment_signature,
            candidates=candidates,
            context=context,
        )

    def classify_context_causal_validity(
        self,
        validity_map_id: int,
        *,
        environment_signature: str,
    ) -> ContextValidityClassification:
        """
        Classify one environment without enumerating the environment space.

        Exact tested evidence wins. Untested environments are supported only
        when they are within the configured distance of valid evidence and are
        strictly closer to valid evidence than to any tested-invalid boundary.
        """
        validity_map = next(
            (
                item
                for item in self.context_causal_validity_maps
                if item.id == validity_map_id
            ),
            None,
        )
        if validity_map is None:
            raise ValueError("unknown context causal validity map")

        signature = environment_signature.strip()
        if not signature:
            raise ValueError("environment signature is required")

        def parse_signature(value: str) -> dict[str, str]:
            parsed: dict[str, str] = {}
            for raw_part in value.split(";"):
                part = raw_part.strip()
                if not part or "=" not in part:
                    raise ValueError(
                        "environment signature must use key=value parts"
                    )
                key, item_value = part.split("=", 1)
                key = key.strip().casefold()
                item_value = item_value.strip().casefold()
                if not key or not item_value or key in parsed:
                    raise ValueError("invalid environment signature")
                parsed[key] = item_value
            return parsed

        def distance(left: dict[str, str], right: dict[str, str]) -> int:
            keys = set(left) | set(right)
            return sum(left.get(key) != right.get(key) for key in keys)

        parsed = parse_signature(signature)
        parsed_valid = {
            item: parse_signature(item)
            for item in validity_map.tested_valid_signatures
        }
        parsed_invalid = {
            item: parse_signature(item)
            for item in validity_map.tested_invalid_signatures
        }
        assessment_ids = dict(validity_map.signature_assessment_ids)

        if signature in parsed_valid:
            status = "tested_valid"
            valid_distance: int | None = 0
            invalid_distance = (
                min(
                    distance(parsed, item)
                    for item in parsed_invalid.values()
                )
                if parsed_invalid
                else None
            )
            nearest_signature = signature
        elif signature in parsed_invalid:
            status = "tested_invalid"
            valid_distance = (
                min(
                    distance(parsed, item)
                    for item in parsed_valid.values()
                )
                if parsed_valid
                else None
            )
            invalid_distance = 0
            nearest_signature = signature
        else:
            valid_pairs = [
                (distance(parsed, item), candidate)
                for candidate, item in parsed_valid.items()
            ]
            invalid_pairs = [
                (distance(parsed, item), candidate)
                for candidate, item in parsed_invalid.items()
            ]
            valid_distance = (
                min(item[0] for item in valid_pairs)
                if valid_pairs
                else None
            )
            invalid_distance = (
                min(item[0] for item in invalid_pairs)
                if invalid_pairs
                else None
            )
            if signature in validity_map.revoked_inferred_signatures:
                supportable = False
                status = "unknown"
            elif signature in validity_map.calibrated_supported_signatures:
                supportable = True
                status = "supported_nearby"
            else:
                supportable = (
                    valid_distance is not None
                    and valid_distance
                    <= validity_map.max_generalization_distance
                    and (
                        invalid_distance is None
                        or valid_distance < invalid_distance
                    )
                )
                status = "supported_nearby" if supportable else "unknown"
            if supportable and valid_pairs:
                nearest_signature = min(
                    (
                        item
                        for item in valid_pairs
                        if item[0] == valid_distance
                    ),
                    key=lambda item: item[1],
                )[1]
            else:
                nearest_signature = ""

        refs = [f"context_causal_validity_map:{validity_map.id}"]
        base_confidence = validity_map.confidence
        if nearest_signature:
            assessment_id = assessment_ids.get(nearest_signature)
            if assessment_id is not None:
                refs.append(
                    f"context_causal_stability_assessment:{assessment_id}"
                )
                assessment = next(
                    (
                        item
                        for item in self.context_causal_stability_assessments
                        if item.id == assessment_id
                    ),
                    None,
                )
                if assessment is not None:
                    if status == "tested_invalid":
                        base_confidence = max(
                            0.5,
                            1.0 - assessment.confidence,
                        )
                    else:
                        base_confidence = assessment.confidence

        if status == "supported_nearby" and valid_distance is not None:
            base_confidence *= 1.0 / (1.0 + valid_distance)
        elif status == "unknown":
            base_confidence = 0.0

        calibration = None
        if validity_map.parent_map_id is None:
            calibration = next(
                (
                    item
                    for item in reversed(
                        self.context_validity_region_calibrations
                    )
                    if item.validity_map_id == validity_map.id
                    and item.environment_signature == signature
                ),
                None,
            )
        if calibration is not None:
            refs.append(
                f"context_validity_region_calibration:{calibration.id}"
            )
            if status == "supported_nearby":
                if calibration.status == "nearby_support_revoked":
                    status = "unknown"
                    base_confidence = 0.0
                elif calibration.status == "nearby_support_calibrated":
                    base_confidence = _clamp(
                        base_confidence
                        + max(0.0, calibration.confidence_delta)
                    )
            elif status == "tested_valid":
                base_confidence = _clamp(
                    base_confidence + calibration.confidence_delta
                )
        elif validity_map.parent_map_id is not None:
            calibration_ids = set(validity_map.source_calibration_ids)
            calibration = next(
                (
                    item
                    for item in reversed(
                        self.context_validity_region_calibrations
                    )
                    if item.id in calibration_ids
                    and item.environment_signature == signature
                ),
                None,
            )
            if calibration is not None:
                refs.append(
                    f"context_validity_region_calibration:{calibration.id}"
                )
                if status == "supported_nearby":
                    base_confidence = _clamp(
                        base_confidence
                        + max(0.0, calibration.confidence_delta)
                    )

        return ContextValidityClassification(
            map_id=validity_map.id,
            hypothesis_id=validity_map.hypothesis_id,
            environment_signature=signature,
            status=status,
            nearest_valid_distance=valid_distance,
            nearest_invalid_distance=invalid_distance,
            confidence=round(_clamp(base_confidence), 6),
            evidence_refs=tuple(refs),
        )

    def evaluate_context_validity_gated_decision(
        self,
        validity_map_id: int,
        *,
        environment_signature: str,
        candidates: list[dict[str, Any]],
        context: str,
    ) -> ContextValidityDecisionGate:
        """
        Gate contextual causal influence with the current validity map.

        Supported environments keep the contextual-schema/transfer path.
        Tested-invalid and unknown environments fall back to the global
        autobiographical self-schema rather than transferring causal context.
        """
        if not candidates:
            raise ValueError("at least one candidate action is required")

        classification = self.classify_context_causal_validity(
            validity_map_id,
            environment_signature=environment_signature,
        )
        causal_allowed = classification.status in {
            "tested_valid",
            "supported_nearby",
        }

        causal_enabled_engine = deepcopy(self)
        causal_enabled = causal_enabled_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=True,
            use_context_transfer=True,
        )
        causal_ablated_engine = deepcopy(self)
        causal_ablated = causal_ablated_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=False,
            use_context_transfer=False,
        )
        gated_engine = deepcopy(self)
        gated = gated_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=causal_allowed,
            use_context_transfer=causal_allowed,
        )

        expected = causal_enabled if causal_allowed else causal_ablated
        matches_expected = (
            gated.action == expected.action
            and gated.predicted_success == expected.predicted_success
            and gated.utility == expected.utility
        )
        delta_vs_ablated = (
            gated.predicted_success
            - causal_ablated.predicted_success
        )
        record = ContextValidityDecisionGate(
            id=self.next_context_validity_decision_gate_id,
            validity_map_id=validity_map_id,
            hypothesis_id=classification.hypothesis_id,
            environment_signature=classification.environment_signature,
            classification_status=classification.status,
            classification_confidence=classification.confidence,
            causal_context_allowed=causal_allowed,
            gated_action=gated.action,
            gated_predicted_success=gated.predicted_success,
            causal_enabled_action=causal_enabled.action,
            causal_enabled_predicted_success=(
                causal_enabled.predicted_success
            ),
            causal_ablated_action=causal_ablated.action,
            causal_ablated_predicted_success=(
                causal_ablated.predicted_success
            ),
            gated_matches_expected_path=matches_expected,
            choice_changed_vs_causal_enabled=(
                gated.action != causal_enabled.action
            ),
            choice_changed_vs_causal_ablated=(
                gated.action != causal_ablated.action
            ),
            predicted_success_delta_vs_ablated=round(
                delta_vs_ablated,
                6,
            ),
            evidence_refs=tuple(
                dict.fromkeys(
                    classification.evidence_refs
                    + (
                        f"context_causal_validity_map:{validity_map_id}",
                    )
                )
            ),
        )
        self.next_context_validity_decision_gate_id += 1
        self.context_validity_decision_gates.append(record)
        if len(self.context_validity_decision_gates) > self.max_memory:
            self.context_validity_decision_gates = (
                self.context_validity_decision_gates[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity decision gate={record.id}; "
                f"environment={record.environment_signature}; "
                f"classification={record.classification_status}; "
                f"causal_allowed={record.causal_context_allowed}; "
                f"action={record.gated_action}"
            ),
            salience=max(
                0.50,
                record.classification_confidence,
            ),
            evidence_refs=(
                f"context_validity_decision_gate:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def record_context_validity_gate_outcome(
        self,
        gate_id: int,
        *,
        actual_success_by_action: dict[str, bool],
        evidence_refs: tuple[str, ...] | list[str],
    ) -> ContextValidityGateOutcome:
        """
        Score a validity-gated decision against later observed action outcomes.

        Counterfactual policy calibration is accepted only when the caller
        supplies observed outcomes for every distinct action chosen by the
        gated, causal-enabled, and causal-ablated paths.
        """
        gate = next(
            (
                item
                for item in self.context_validity_decision_gates
                if item.id == gate_id
            ),
            None,
        )
        if gate is None:
            raise ValueError("unknown context validity decision gate")
        if any(
            item.gate_id == gate_id
            for item in self.context_validity_gate_outcomes
        ):
            raise ValueError("gate outcome has already been recorded")

        provided_refs = tuple(
            str(ref).strip()
            for ref in evidence_refs
            if str(ref).strip()
        )
        if not provided_refs:
            raise ValueError("observed gate outcome requires evidence references")

        required_actions = {
            gate.gated_action,
            gate.causal_enabled_action,
            gate.causal_ablated_action,
        }
        missing = required_actions - set(actual_success_by_action)
        if missing:
            raise ValueError(
                "observed outcomes are required for every policy-selected action"
            )
        if any(
            not isinstance(actual_success_by_action[action], bool)
            for action in required_actions
        ):
            raise ValueError("action outcomes must be boolean success values")

        actuals = tuple(
            sorted(
                (
                    action,
                    actual_success_by_action[action],
                )
                for action in required_actions
            )
        )

        def error(action: str, prediction: float) -> float:
            actual = 1.0 if actual_success_by_action[action] else 0.0
            return abs(actual - prediction)

        gated_error = error(
            gate.gated_action,
            gate.gated_predicted_success,
        )
        enabled_error = error(
            gate.causal_enabled_action,
            gate.causal_enabled_predicted_success,
        )
        ablated_error = error(
            gate.causal_ablated_action,
            gate.causal_ablated_predicted_success,
        )
        alternative_error = (
            ablated_error
            if gate.causal_context_allowed
            else enabled_error
        )
        advantage = alternative_error - gated_error

        outcome = ContextValidityGateOutcome(
            id=self.next_context_validity_gate_outcome_id,
            gate_id=gate.id,
            validity_map_id=gate.validity_map_id,
            environment_signature=gate.environment_signature,
            actual_success_by_action=actuals,
            gated_error=round(gated_error, 6),
            causal_enabled_error=round(enabled_error, 6),
            causal_ablated_error=round(ablated_error, 6),
            alternative_error=round(alternative_error, 6),
            gated_advantage_vs_alternative=round(advantage, 6),
            evidence_refs=tuple(dict.fromkeys(provided_refs)),
        )
        self.next_context_validity_gate_outcome_id += 1
        self.context_validity_gate_outcomes.append(outcome)
        if len(self.context_validity_gate_outcomes) > self.max_memory:
            self.context_validity_gate_outcomes = (
                self.context_validity_gate_outcomes[-self.max_memory:]
            )
        return outcome

    def calibrate_context_validity_region(
        self,
        validity_map_id: int,
        *,
        environment_signature: str,
        min_samples: int = 3,
        advantage_margin: float = 0.05,
    ) -> ContextValidityRegionCalibration:
        """
        Aggregate matched gate outcomes and calibrate one environment region.

        Nearby support can be strengthened only after repeated favorable
        calibration and is revoked after repeated underperformance. Exact
        tested-valid evidence is never relabeled by this policy-calibration step.
        """
        validity_map = next(
            (
                item
                for item in self.context_causal_validity_maps
                if item.id == validity_map_id
            ),
            None,
        )
        if validity_map is None:
            raise ValueError("unknown context causal validity map")

        signature = environment_signature.strip()
        if not signature:
            raise ValueError("environment signature is required")

        gate_map = {
            item.id: item
            for item in self.context_validity_decision_gates
            if item.validity_map_id == validity_map_id
            and item.environment_signature == signature
        }
        outcomes = [
            item
            for item in self.context_validity_gate_outcomes
            if item.gate_id in gate_map
        ]
        min_samples = max(2, min(int(min_samples), 20))
        if len(outcomes) < min_samples:
            raise ValueError("insufficient matched gate outcomes for calibration")

        margin = _clamp(advantage_margin, 0.01, 0.50)
        mean_gated = sum(item.gated_error for item in outcomes) / len(outcomes)
        mean_enabled = (
            sum(item.causal_enabled_error for item in outcomes)
            / len(outcomes)
        )
        mean_ablated = (
            sum(item.causal_ablated_error for item in outcomes)
            / len(outcomes)
        )
        mean_alternative = (
            sum(item.alternative_error for item in outcomes)
            / len(outcomes)
        )
        advantage = mean_alternative - mean_gated

        source_statuses = {
            gate_map[item.gate_id].classification_status
            for item in outcomes
        }
        source_status = (
            next(iter(source_statuses))
            if len(source_statuses) == 1
            else "mixed"
        )

        if source_status == "supported_nearby":
            status = (
                "nearby_support_calibrated"
                if advantage >= margin
                else "nearby_support_revoked"
                if advantage <= -margin
                else "nearby_support_uncertain"
            )
        elif source_status == "tested_valid":
            status = (
                "tested_valid_calibrated"
                if advantage >= margin
                else "tested_valid_policy_warning"
                if advantage <= -margin
                else "tested_valid_uncertain"
            )
        else:
            status = (
                "abstention_calibrated"
                if advantage >= margin
                else "abstention_warning"
                if advantage <= -margin
                else "abstention_uncertain"
            )

        confidence_delta = 0.0
        if status in {
            "nearby_support_calibrated",
            "tested_valid_calibrated",
            "abstention_calibrated",
        }:
            confidence_delta = min(0.20, max(0.0, advantage) * 0.50)
        elif status in {
            "nearby_support_revoked",
            "tested_valid_policy_warning",
            "abstention_warning",
        }:
            confidence_delta = -min(0.20, abs(advantage) * 0.50)

        refs = tuple(
            dict.fromkeys(
                tuple(
                    f"context_validity_gate_outcome:{item.id}"
                    for item in outcomes
                )
                + tuple(
                    ref
                    for item in outcomes
                    for ref in item.evidence_refs
                )
            )
        )
        record = ContextValidityRegionCalibration(
            id=self.next_context_validity_region_calibration_id,
            validity_map_id=validity_map_id,
            hypothesis_id=validity_map.hypothesis_id,
            environment_signature=signature,
            source_classification_status=source_status,
            outcome_ids=tuple(item.id for item in outcomes),
            sample_count=len(outcomes),
            mean_gated_error=round(mean_gated, 6),
            mean_causal_enabled_error=round(mean_enabled, 6),
            mean_causal_ablated_error=round(mean_ablated, 6),
            mean_alternative_error=round(mean_alternative, 6),
            gated_advantage_vs_alternative=round(advantage, 6),
            status=status,
            confidence_delta=round(confidence_delta, 6),
            evidence_refs=refs,
        )
        self.next_context_validity_region_calibration_id += 1
        self.context_validity_region_calibrations.append(record)
        if len(self.context_validity_region_calibrations) > self.max_memory:
            self.context_validity_region_calibrations = (
                self.context_validity_region_calibrations[-self.max_memory:]
            )

        self.stage_global_workspace_item(
            source="intervention",
            content=(
                f"context validity calibration={record.id}; "
                f"environment={signature}; "
                f"samples={record.sample_count}; "
                f"advantage={record.gated_advantage_vs_alternative:.3f}; "
                f"status={record.status}"
            ),
            salience=max(
                0.50,
                min(1.0, abs(record.gated_advantage_vs_alternative) + 0.45),
            ),
            evidence_refs=(
                f"context_validity_region_calibration:{record.id}",
                *record.evidence_refs[-4:],
            ),
        )
        return record

    def discover_latent_context_hypotheses(
        self,
        schema_id: int,
        *,
        max_candidates: int = 4,
        min_term_support: int = 3,
        min_rate_contrast: float = 0.40,
        min_holdout_improvement: float = 0.10,
        similarity_threshold: float = 0.28,
    ) -> LatentContextDiscovery:
        """
        Propose and falsify a small set of latent context hypotheses.

        Observation terms are only proposal features. A hypothesis becomes active
        context structure only when the existing held-out decomposition test
        validates it. Candidate evaluation happens on deep copies so rejected
        hypotheses cannot mutate the live self-schema.
        """
        parent = next(
            (item for item in self.self_schema if item.id == schema_id),
            None,
        )
        if parent is None:
            raise ValueError("unknown self schema")
        if parent.status != "active":
            raise ValueError("self schema is not active")

        max_candidates = max(1, min(int(max_candidates), 6))
        min_term_support = max(2, min(int(min_term_support), 24))
        min_rate_contrast = _clamp(min_rate_contrast, 0.10, 1.0)
        min_holdout_improvement = _clamp(
            min_holdout_improvement,
            0.01,
            0.80,
        )

        matching = self._matching_schema_experiences(
            parent,
            similarity_threshold=similarity_threshold,
        )
        parent_terms = _terms(parent.pattern)
        term_records: dict[str, list[tuple[int, Experience]]] = {}
        for index, experience in matching:
            for term in _terms(experience.observation) - parent_terms:
                if term.isdigit():
                    continue
                term_records.setdefault(term, []).append((index, experience))

        stats: list[tuple[str, int, float, tuple[str, ...]]] = []
        for term, records in term_records.items():
            support = len(records)
            if support < min_term_support:
                continue
            successes = sum(
                1 for _, experience in records if experience.success is True
            )
            rate = successes / support
            refs = tuple(f"experience:{index}" for index, _ in records)
            stats.append((term, support, rate, refs))

        pair_candidates: list[
            tuple[
                float,
                str,
                int,
                float,
                tuple[str, ...],
                str,
                int,
                float,
                tuple[str, ...],
            ]
        ] = []
        for left_index, left in enumerate(stats):
            for right in stats[left_index + 1:]:
                (
                    left_term,
                    left_support,
                    left_rate,
                    left_refs,
                ) = left
                (
                    right_term,
                    right_support,
                    right_rate,
                    right_refs,
                ) = right
                contrast = abs(left_rate - right_rate)
                if contrast < min_rate_contrast:
                    continue
                overlap = set(left_refs).intersection(right_refs)
                if overlap:
                    continue
                if left_rate >= right_rate:
                    positive = left
                    negative = right
                else:
                    positive = right
                    negative = left
                score = (
                    contrast
                    * min(positive[1], negative[1])
                    * min(1.0, (positive[1] + negative[1]) / 12.0)
                )
                pair_candidates.append(
                    (
                        score,
                        positive[0],
                        positive[1],
                        positive[2],
                        positive[3],
                        negative[0],
                        negative[1],
                        negative[2],
                        negative[3],
                    )
                )

        pair_candidates.sort(
            key=lambda item: (
                item[0],
                item[3] - item[7],
                item[2] + item[6],
                item[1],
                item[5],
            ),
            reverse=True,
        )
        selected_pairs = pair_candidates[:max_candidates]

        hypothesis_ids: list[int] = []
        validated: list[
            tuple[
                float,
                LatentContextHypothesis,
                SelfSchemaDecomposition,
            ]
        ] = []
        discovery_refs: list[str] = []

        for (
            _,
            positive_term,
            positive_support,
            positive_rate,
            positive_refs,
            negative_term,
            negative_support,
            negative_rate,
            negative_refs,
        ) in selected_pairs:
            trial = deepcopy(self)
            decomposition = trial.decompose_self_schema_context(
                schema_id,
                context_rules={
                    positive_term: (positive_term,),
                    negative_term: (negative_term,),
                },
                min_evidence_per_context=min_term_support,
                min_holdout_improvement=min_holdout_improvement,
                similarity_threshold=similarity_threshold,
            )
            rate_contrast = positive_rate - negative_rate
            validation_status = (
                "validated"
                if decomposition.status == "accepted"
                else "rejected_validation"
            )
            evidence_refs = tuple(
                dict.fromkeys(positive_refs + negative_refs)
            )
            hypothesis = LatentContextHypothesis(
                id=self.next_latent_context_hypothesis_id,
                parent_schema_id=schema_id,
                positive_term=positive_term,
                negative_term=negative_term,
                positive_support=positive_support,
                negative_support=negative_support,
                positive_success_rate=round(positive_rate, 6),
                negative_success_rate=round(negative_rate, 6),
                rate_contrast=round(rate_contrast, 6),
                validation_status=validation_status,
                holdout_improvement=decomposition.improvement,
                decomposition_id=None,
                evidence_refs=evidence_refs,
            )
            self.next_latent_context_hypothesis_id += 1
            self.latent_context_hypotheses.append(hypothesis)
            hypothesis_ids.append(hypothesis.id)
            discovery_refs.extend(evidence_refs)
            if decomposition.status == "accepted":
                validated.append(
                    (decomposition.improvement, hypothesis, decomposition)
                )

        selected_hypothesis_id: int | None = None
        selected_decomposition_id: int | None = None
        if validated:
            validated.sort(
                key=lambda item: (
                    item[0],
                    item[1].rate_contrast,
                    item[1].positive_support
                    + item[1].negative_support,
                ),
                reverse=True,
            )
            _, best_hypothesis, _ = validated[0]
            applied = self.decompose_self_schema_context(
                schema_id,
                context_rules={
                    best_hypothesis.positive_term: (
                        best_hypothesis.positive_term,
                    ),
                    best_hypothesis.negative_term: (
                        best_hypothesis.negative_term,
                    ),
                },
                min_evidence_per_context=min_term_support,
                min_holdout_improvement=min_holdout_improvement,
                similarity_threshold=similarity_threshold,
            )
            selected_hypothesis_id = best_hypothesis.id
            selected_decomposition_id = applied.id

            updated_hypotheses: list[LatentContextHypothesis] = []
            for item in self.latent_context_hypotheses:
                if item.id == best_hypothesis.id:
                    item = LatentContextHypothesis(
                        id=item.id,
                        parent_schema_id=item.parent_schema_id,
                        positive_term=item.positive_term,
                        negative_term=item.negative_term,
                        positive_support=item.positive_support,
                        negative_support=item.negative_support,
                        positive_success_rate=item.positive_success_rate,
                        negative_success_rate=item.negative_success_rate,
                        rate_contrast=item.rate_contrast,
                        validation_status="selected",
                        holdout_improvement=item.holdout_improvement,
                        decomposition_id=applied.id,
                        evidence_refs=item.evidence_refs,
                        causal_status=item.causal_status,
                        causal_evidence_refs=item.causal_evidence_refs,
                    )
                updated_hypotheses.append(item)
            self.latent_context_hypotheses = updated_hypotheses

        discovery = LatentContextDiscovery(
            id=self.next_latent_context_discovery_id,
            parent_schema_id=schema_id,
            hypothesis_ids=tuple(hypothesis_ids),
            proposed_count=len(hypothesis_ids),
            validated_count=len(validated),
            selected_hypothesis_id=selected_hypothesis_id,
            selected_decomposition_id=selected_decomposition_id,
            status=(
                "selected"
                if selected_hypothesis_id is not None
                else "no_validated_hypothesis"
            ),
            evidence_refs=tuple(dict.fromkeys(discovery_refs)),
        )
        self.next_latent_context_discovery_id += 1
        self.latent_context_discoveries.append(discovery)
        if len(self.latent_context_hypotheses) > self.max_memory:
            self.latent_context_hypotheses = self.latent_context_hypotheses[
                -self.max_memory:
            ]
        if len(self.latent_context_discoveries) > self.max_memory:
            self.latent_context_discoveries = self.latent_context_discoveries[
                -self.max_memory:
            ]

        if selected_hypothesis_id is not None:
            chosen = next(
                item
                for item in self.latent_context_hypotheses
                if item.id == selected_hypothesis_id
            )
            self.stage_global_workspace_item(
                source="self_schema",
                content=(
                    f"latent context discovery id={discovery.id}; "
                    f"selected={chosen.positive_term}/"
                    f"{chosen.negative_term}; "
                    f"heldout_gain={chosen.holdout_improvement:.3f}"
                ),
                salience=max(
                    0.55,
                    _clamp(chosen.holdout_improvement + 0.35),
                ),
                evidence_refs=(
                    f"latent_context_discovery:{discovery.id}",
                    f"latent_context_hypothesis:{chosen.id}",
                    *chosen.evidence_refs[-4:],
                ),
            )
        return discovery

    def active_context_transfer_boundaries(
        self,
    ) -> tuple[ContextTransferBoundary, ...]:
        return tuple(
            item
            for item in self.context_transfer_boundaries
            if item.status == "accepted"
        )

    def evaluate_context_transfer(
        self,
        source_context_schema_id: int,
        *,
        target_label: str,
        target_terms: tuple[str, ...] | list[str],
        min_target_evidence: int = 3,
        min_gain_over_global: float = 0.10,
        max_source_holdout_mae: float = 0.30,
        similarity_threshold: float = 0.28,
    ) -> ContextTransferBoundary:
        """
        Validate transfer to a new context using evidence excluded from the schemas.

        Target experiences already cited by the parent or source contextual schema
        are excluded, so the transfer test is genuinely out-of-sample relative to
        those stored self-models.
        """
        source = next(
            (
                item
                for item in self.contextual_self_schema
                if item.id == source_context_schema_id
            ),
            None,
        )
        if source is None or source.status != "active":
            raise ValueError("unknown active source contextual self schema")

        parent = next(
            (
                item
                for item in self.self_schema
                if item.id == source.parent_schema_id
            ),
            None,
        )
        if parent is None or parent.status != "active":
            raise ValueError("source contextual schema has no active parent")

        label = target_label.strip().casefold()
        if not label:
            raise ValueError("target context label is required")
        target_term_set: set[str] = set()
        for raw in target_terms:
            target_term_set.update(_terms(str(raw)))
        if not target_term_set:
            raise ValueError("target context needs at least one matching term")
        normalized_terms = tuple(sorted(target_term_set))

        min_target_evidence = max(2, min(int(min_target_evidence), 24))
        min_gain_over_global = _clamp(min_gain_over_global, 0.01, 0.80)
        max_source_holdout_mae = _clamp(max_source_holdout_mae, 0.0, 1.0)

        already_used = set(parent.evidence_refs) | set(source.evidence_refs)
        candidates: list[tuple[int, Experience]] = []
        for index, experience in self._matching_schema_experiences(
            parent,
            similarity_threshold=similarity_threshold,
        ):
            ref = f"experience:{index}"
            if ref in already_used:
                continue
            if not _terms(experience.observation).intersection(target_term_set):
                continue
            candidates.append((index, experience))

        evidence_refs = tuple(
            f"experience:{index}" for index, _ in candidates
        )
        if len(candidates) < min_target_evidence:
            boundary = ContextTransferBoundary(
                id=self.next_context_transfer_boundary_id,
                parent_schema_id=parent.id,
                source_context_schema_id=source.id,
                target_label=label,
                target_terms=normalized_terms,
                evidence_count=len(candidates),
                target_success_rate=0.0,
                source_success_rate=source.success_rate,
                global_success_rate=parent.success_rate,
                source_holdout_mae=1.0,
                global_holdout_mae=1.0,
                improvement=0.0,
                transfer_strength=0.0,
                status="insufficient_evidence",
                evidence_refs=evidence_refs,
            )
            self.next_context_transfer_boundary_id += 1
            self.context_transfer_boundaries.append(boundary)
            return boundary

        outcomes = [
            1.0 if experience.success is True else 0.0
            for _, experience in candidates
        ]
        target_success_rate = sum(outcomes) / len(outcomes)
        source_errors = [
            abs(outcome - source.success_rate) for outcome in outcomes
        ]
        global_errors = [
            abs(outcome - parent.success_rate) for outcome in outcomes
        ]
        source_mae = sum(source_errors) / len(source_errors)
        global_mae = sum(global_errors) / len(global_errors)
        improvement = global_mae - source_mae
        accepted = (
            improvement >= min_gain_over_global
            and source_mae <= max_source_holdout_mae
        )
        transfer_strength = (
            _clamp(0.55 + improvement, 0.55, 0.90)
            if accepted
            else 0.0
        )
        boundary = ContextTransferBoundary(
            id=self.next_context_transfer_boundary_id,
            parent_schema_id=parent.id,
            source_context_schema_id=source.id,
            target_label=label,
            target_terms=normalized_terms,
            evidence_count=len(candidates),
            target_success_rate=round(target_success_rate, 6),
            source_success_rate=source.success_rate,
            global_success_rate=parent.success_rate,
            source_holdout_mae=round(source_mae, 6),
            global_holdout_mae=round(global_mae, 6),
            improvement=round(improvement, 6),
            transfer_strength=round(transfer_strength, 6),
            status="accepted" if accepted else "abstained_no_gain",
            evidence_refs=evidence_refs,
        )
        self.next_context_transfer_boundary_id += 1
        self.context_transfer_boundaries.append(boundary)
        if len(self.context_transfer_boundaries) > self.max_memory:
            self.context_transfer_boundaries = self.context_transfer_boundaries[
                -self.max_memory:
            ]

        if accepted:
            self.stage_global_workspace_item(
                source="self_schema",
                content=(
                    f"context transfer id={boundary.id}; "
                    f"source={source.context_label}; target={label}; "
                    f"heldout_gain={boundary.improvement:.3f}; "
                    f"strength={boundary.transfer_strength:.3f}"
                ),
                salience=max(0.55, boundary.transfer_strength),
                evidence_refs=(
                    f"context_transfer:{boundary.id}",
                    *evidence_refs[-4:],
                ),
            )
        return boundary

    def transferred_context_adjustment(
        self,
        *,
        context: str,
        action: str,
    ) -> tuple[float, float, tuple[str, ...]]:
        context_terms = _terms(context)
        if not context_terms:
            return 0.0, 0.0, ()

        matches: list[
            tuple[float, ContextTransferBoundary, ContextualSelfSchemaEntry]
        ] = []
        for boundary in self.active_context_transfer_boundaries():
            if not context_terms.intersection(boundary.target_terms):
                continue
            source = next(
                (
                    item
                    for item in self.contextual_self_schema
                    if item.id == boundary.source_context_schema_id
                    and item.status == "active"
                ),
                None,
            )
            if source is None:
                continue
            similarity = _similarity(action, source.pattern)
            if similarity < 0.18:
                continue
            weight = (
                similarity
                * source.confidence
                * boundary.transfer_strength
            )
            matches.append((weight, boundary, source))

        if not matches:
            return 0.0, 0.0, ()

        matches.sort(
            key=lambda item: (
                item[0],
                item[1].improvement,
                item[2].confidence,
            ),
            reverse=True,
        )
        selected = matches[:3]
        total_weight = sum(weight for weight, _, _ in selected) or 1.0
        success_bias = sum(
            weight * source.success_bias * boundary.transfer_strength
            for weight, boundary, source in selected
        ) / total_weight
        risk_bias = sum(
            weight * source.risk_bias * boundary.transfer_strength
            for weight, boundary, source in selected
        ) / total_weight
        refs = tuple(
            f"context_transfer:{boundary.id}"
            for _, boundary, _ in selected
        )
        return (
            round(max(-0.20, min(0.20, success_bias)), 6),
            round(max(-0.14, min(0.14, risk_bias)), 6),
            refs,
        )

    def compare_context_transfer_ablation(
        self,
        *,
        candidates: list[dict[str, Any]],
        context: str,
    ) -> ContextTransferComparison:
        if not candidates:
            raise ValueError("at least one candidate action is required")
        transfer_engine = deepcopy(self)
        no_transfer_engine = deepcopy(self)
        transfer = transfer_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=True,
            use_context_transfer=True,
        )
        no_transfer = no_transfer_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=True,
            use_context_transfer=False,
        )
        delta = (
            transfer.predicted_success
            - no_transfer.predicted_success
        )
        choice_changed = transfer.action != no_transfer.action
        active = choice_changed or abs(delta) >= 0.05
        return ContextTransferComparison(
            transfer_action=transfer.action,
            no_transfer_action=no_transfer.action,
            transfer_predicted_success=transfer.predicted_success,
            no_transfer_predicted_success=no_transfer.predicted_success,
            predicted_success_delta=round(delta, 6),
            choice_changed=choice_changed,
            transfer_causally_active=active,
        )

    def contextual_self_schema_adjustment(
        self,
        *,
        context: str,
        action: str,
        use_context_transfer: bool = True,
    ) -> tuple[float, float, tuple[str, ...]]:
        context_terms = _terms(context)
        if not context_terms:
            return 0.0, 0.0, ()

        matches: list[tuple[float, ContextualSelfSchemaEntry]] = []
        for item in self.contextual_self_schema:
            if item.status != "active":
                continue
            if not context_terms.intersection(item.context_terms):
                continue
            similarity = _similarity(action, item.pattern)
            if similarity < 0.18:
                continue
            weight = max(0.01, similarity) * item.confidence
            matches.append((weight, item))

        if not matches:
            if use_context_transfer:
                return self.transferred_context_adjustment(
                    context=context,
                    action=action,
                )
            return 0.0, 0.0, ()

        matches.sort(key=lambda pair: (pair[0], pair[1].confidence), reverse=True)
        selected = matches[:3]
        total_weight = sum(weight for weight, _ in selected) or 1.0
        success_bias = sum(
            weight * item.success_bias for weight, item in selected
        ) / total_weight
        risk_bias = sum(
            weight * item.risk_bias for weight, item in selected
        ) / total_weight
        refs = tuple(
            f"contextual_self_schema:{item.id}" for _, item in selected
        )
        return (
            round(max(-0.22, min(0.22, success_bias)), 6),
            round(max(-0.16, min(0.16, risk_bias)), 6),
            refs,
        )

    def compare_contextual_schema_ablation(
        self,
        *,
        candidates: list[dict[str, Any]],
        context: str,
    ) -> ContextualSchemaComparison:
        if not candidates:
            raise ValueError("at least one candidate action is required")

        contextual_engine = deepcopy(self)
        global_engine = deepcopy(self)
        contextual = contextual_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=True,
        )
        global_only = global_engine.choose_predicted_action(
            candidates,
            context=context,
            use_self_schema=True,
            use_contextual_schema=False,
        )
        delta = contextual.predicted_success - global_only.predicted_success
        choice_changed = contextual.action != global_only.action
        active = choice_changed or abs(delta) >= 0.05
        return ContextualSchemaComparison(
            contextual_action=contextual.action,
            global_action=global_only.action,
            contextual_predicted_success=contextual.predicted_success,
            global_predicted_success=global_only.predicted_success,
            predicted_success_delta=round(delta, 6),
            choice_changed=choice_changed,
            contextual_schema_causally_active=active,
        )

    def self_schema_adjustment(
        self,
        *,
        context: str,
        action: str,
        use_contextual_schema: bool = True,
        use_context_transfer: bool = True,
    ) -> tuple[float, float, tuple[str, ...]]:
        """Return bounded transfer biases from related demonstrated self-schema."""
        if use_contextual_schema:
            contextual = self.contextual_self_schema_adjustment(
                context=context,
                action=action,
                use_context_transfer=use_context_transfer,
            )
            if contextual[2]:
                return contextual

        query = f"{context} {action}".strip()
        matches: list[tuple[float, SelfSchemaEntry]] = []
        for item in self.self_schema:
            if item.status != "active":
                continue
            similarity = max(
                _similarity(query, item.pattern),
                _similarity(action, item.pattern),
            )
            if similarity < 0.18:
                continue
            weight = similarity * item.confidence
            if weight > 0.0:
                matches.append((weight, item))

        if not matches:
            return 0.0, 0.0, ()

        matches.sort(key=lambda pair: (pair[0], pair[1].confidence), reverse=True)
        selected = matches[:3]
        total_weight = sum(weight for weight, _ in selected) or 1.0
        success_bias = sum(
            weight * item.success_bias for weight, item in selected
        ) / total_weight
        risk_bias = sum(
            weight * item.risk_bias for weight, item in selected
        ) / total_weight
        refs = tuple(f"self_schema:{item.id}" for _, item in selected)
        return (
            round(max(-0.22, min(0.22, success_bias)), 6),
            round(max(-0.16, min(0.16, risk_bias)), 6),
            refs,
        )

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

        if focus in {
            "context_validity_reactivation_resolution",
            "reactivation_drift_resolution",
            "renewed_degradation_resolution",
        }:
            if self.context_validity_reactivation_drift_resolutions:
                item = self.context_validity_reactivation_drift_resolutions[-1]
                add(
                    f"context_validity_reactivation_drift_resolution:{item.id}",
                    (
                        f"watch={item.drift_watch_id}; "
                        f"decision={item.decision}; "
                        f"active_before={item.active_map_id_before}; "
                        f"rollback_target={item.rollback_target_map_id}; "
                        f"rollback_selection={item.rollback_selection_id}; "
                        f"new_cycle={item.requires_new_evidence_cycle}; "
                        f"reason={item.reason!r}"
                    ),
                )
                for ref in item.evidence_refs[-8:]:
                    add(ref, "evidence retained for renewed-degradation resolution")
                summary = (
                    "Renewed-degradation resolution is explicit. A rollback "
                    "review preserves the prior audit trail and blocks stale "
                    "holdout reuse until a fresh evidence cycle is completed."
                )
            else:
                summary = (
                    "No renewed-degradation resolution has been recorded."
                )

        elif focus in {
            "context_validity_reactivation_drift",
            "reactivation_drift",
            "post_reactivation_drift",
        }:
            if self.context_validity_reactivation_drift_watches:
                item = self.context_validity_reactivation_drift_watches[-1]
                add(
                    f"context_validity_reactivation_drift_watch:{item.id}",
                    (
                        f"holdout={item.holdout_validation_id}; "
                        f"reactivation={item.reactivation_selection_id}; "
                        f"active_map={item.active_map_id}; "
                        f"outcomes={len(item.observed_outcome_ids)}; "
                        f"mean_advantage="
                        f"{item.mean_post_reactivation_advantage}; "
                        f"holdout_advantage={item.holdout_advantage}; "
                        f"delta={item.advantage_delta}; "
                        f"status={item.status}; "
                        f"recommended_action={item.recommended_action}"
                    ),
                )
                for ref in item.evidence_refs[-8:]:
                    add(ref, "post-reactivation evidence isolated by watermark")
                summary = (
                    "The reactivation drift watch uses only outcomes after "
                    "the explicit descendant re-advance and can recommend a "
                    "new governance review without automatically rolling back."
                )
            else:
                summary = "No post-reactivation drift watch has been recorded."

        elif focus in {
            "context_validity_holdout",
            "rollback_holdout",
            "holdout_validation",
        }:
            if self.context_validity_rollback_holdout_validations:
                item = self.context_validity_rollback_holdout_validations[-1]
                add(
                    f"context_validity_rollback_holdout_validation:{item.id}",
                    (
                        f"recovery={item.recovery_validation_id}; "
                        f"rollback_map={item.rollback_map_id}; "
                        f"holdout_outcomes={len(item.holdout_outcome_ids)}; "
                        f"recovery_advantage={item.mean_recovery_advantage}; "
                        f"holdout_advantage={item.mean_holdout_advantage}; "
                        f"status={item.status}; "
                        f"reactivation_allowed={item.reactivation_allowed}"
                    ),
                )
                for ref in item.evidence_refs[-8:]:
                    add(ref, "separate post-recovery holdout evidence")
                summary = (
                    "Rollback reactivation requires recovery evidence first "
                    "and a later non-overlapping holdout batch that independently "
                    "confirms the calibration improvement."
                )
            else:
                summary = "No rollback holdout validation has been recorded."

        elif focus in {
            "context_validity_resolution",
            "rollback_resolution",
            "rollback_validation",
            "recommendation_resolution",
        }:
            if self.context_validity_recommendation_resolutions:
                resolution = self.context_validity_recommendation_resolutions[-1]
                add(
                    f"context_validity_recommendation_resolution:{resolution.id}",
                    (
                        f"watch={resolution.watch_id}; "
                        f"decision={resolution.decision}; "
                        f"recommended_map={resolution.recommended_map_id}; "
                        f"rollback_selection={resolution.rollback_selection_id}; "
                        f"reason={resolution.reason!r}"
                    ),
                )
                validation = next(
                    (
                        item
                        for item in reversed(
                            self.context_validity_rollback_validations
                        )
                        if item.resolution_id == resolution.id
                    ),
                    None,
                )
                if validation is not None:
                    add(
                        f"context_validity_rollback_validation:{validation.id}",
                        (
                            f"rollback_map={validation.rollback_map_id}; "
                            f"blocked_descendant="
                            f"{validation.blocked_descendant_map_id}; "
                            f"outcomes={len(validation.observed_outcome_ids)}; "
                            f"mean_advantage="
                            f"{validation.mean_rollback_advantage}; "
                            f"improvement={validation.improvement_delta}; "
                            f"status={validation.status}; "
                            f"reactivation_allowed="
                            f"{validation.reactivation_allowed}"
                        ),
                    )
                    for ref in validation.evidence_refs[-8:]:
                        add(ref, "post-rollback evidence used for validation")
                else:
                    for ref in resolution.evidence_refs[-6:]:
                        add(ref, "evidence retained for recommendation resolution")
                summary = (
                    "Rollback recommendations require explicit resolution; "
                    "accepted rollbacks block descendant re-advance until "
                    "recovery improves and a later holdout batch confirms it."
                )
            else:
                summary = "No rollback recommendation resolution has been recorded."

        elif focus in {
            "context_validity_degradation",
            "active_revision_degradation",
            "degradation_watch",
            "rollback_recommendation",
        }:
            if self.context_validity_degradation_watches:
                item = self.context_validity_degradation_watches[-1]
                add(
                    f"context_validity_degradation_watch:{item.id}",
                    (
                        f"active_map={item.active_map_id}; "
                        f"selection={item.activation_selection_id}; "
                        f"degraded={item.degraded_signatures}; "
                        f"mean_advantage={item.mean_active_advantage}; "
                        f"recommended_map={item.recommended_map_id}; "
                        f"status={item.status}; reason={item.reason!r}"
                    ),
                )
                for ref in item.evidence_refs[-8:]:
                    add(ref, "evidence used by active-revision degradation watch")
                summary = (
                    "The active-revision degradation watch uses only "
                    "post-activation observed-outcome calibration and may "
                    "recommend an intact ancestor, but never changes the "
                    "active pointer automatically."
                )
            else:
                summary = "No active-revision degradation watch has been recorded."

        elif focus in {
            "context_validity_selection",
            "validity_map_selection",
            "active_validity_map",
            "rollback",
        }:
            if self.context_validity_map_selection_history:
                item = self.context_validity_map_selection_history[-1]
                add(
                    f"context_validity_map_selection:{item.id}",
                    (
                        f"hypothesis={item.hypothesis_id}; "
                        f"previous={item.previous_map_id}; "
                        f"selected={item.selected_map_id}; "
                        f"action={item.action}; "
                        f"lineage={item.lineage}; "
                        f"reason={item.reason!r}"
                    ),
                )
                for ref in item.evidence_refs[-6:]:
                    add(ref, "evidence retained for active-map selection")
                summary = (
                    "The active validity-map pointer changes only through "
                    "lineage-checked activation, forward selection, or "
                    "ancestor rollback; no revision or later evidence is "
                    "deleted by rollback."
                )
            else:
                summary = "No active validity-map selection has been recorded."

        elif focus in {
            "context_validity_revision",
            "validity_map_revision",
            "map_revision",
        }:
            revisions = [
                item
                for item in self.context_causal_validity_maps
                if item.parent_map_id is not None
            ]
            if revisions:
                item = revisions[-1]
                add(
                    f"context_causal_validity_map:{item.id}",
                    (
                        f"parent={item.parent_map_id}; "
                        f"revision={item.revision_number}; "
                        f"calibrated_supported="
                        f"{len(item.calibrated_supported_signatures)}; "
                        f"revoked={len(item.revoked_inferred_signatures)}; "
                        f"confidence={item.confidence}"
                    ),
                )
                if item.parent_map_id is not None:
                    add(
                        f"context_causal_validity_map:{item.parent_map_id}",
                        "immutable parent validity map",
                    )
                for reason in item.revision_reasons[-6:]:
                    add(
                        f"context_validity_revision_reason:{item.id}",
                        reason,
                    )
                summary = (
                    "The latest validity map is an immutable child revision "
                    "that preserves exact tested evidence and freezes only "
                    "calibration-backed inferred-region changes."
                )
            else:
                summary = "No calibration-aware validity-map revision exists."

        elif focus in {
            "context_validity_calibration",
            "validity_gate_calibration",
            "gate_outcome_calibration",
        }:
            if self.context_validity_region_calibrations:
                item = self.context_validity_region_calibrations[-1]
                add(
                    f"context_validity_region_calibration:{item.id}",
                    (
                        f"environment={item.environment_signature}; "
                        f"source={item.source_classification_status}; "
                        f"samples={item.sample_count}; "
                        f"gated_error={item.mean_gated_error}; "
                        f"alternative_error={item.mean_alternative_error}; "
                        f"advantage={item.gated_advantage_vs_alternative}; "
                        f"status={item.status}"
                    ),
                )
                for ref in item.evidence_refs[-6:]:
                    add(ref, "observed outcome evidence used for gate calibration")
                summary = (
                    "The latest validity-gate calibration compares matched "
                    "observed outcomes without inventing unobserved "
                    "counterfactuals and can revoke nearby support after "
                    "repeated gated-policy underperformance."
                )
            else:
                summary = "No validity-gate outcome calibration has been recorded."

        elif focus in {
            "context_validity_gate",
            "validity_gated_decision",
            "decision_gate",
        }:
            if self.context_validity_decision_gates:
                item = self.context_validity_decision_gates[-1]
                add(
                    f"context_validity_decision_gate:{item.id}",
                    (
                        f"environment={item.environment_signature}; "
                        f"classification={item.classification_status}; "
                        f"confidence={item.classification_confidence}; "
                        f"causal_allowed={item.causal_context_allowed}; "
                        f"gated_action={item.gated_action}; "
                        f"causal_enabled={item.causal_enabled_action}; "
                        f"causal_ablated={item.causal_ablated_action}"
                    ),
                )
                for ref in item.evidence_refs[-6:]:
                    add(ref, "validity evidence used to gate causal context")
                summary = (
                    "The latest validity-gated decision used contextual causal "
                    "evidence only when the environment map supported it and "
                    "otherwise fell back to the causal-context ablation path."
                )
            else:
                summary = "No validity-gated decision has been recorded."

        elif focus in {
            "context_validity_map",
            "causal_validity_map",
            "validity_map",
        }:
            if self.context_causal_validity_maps:
                item = self.context_causal_validity_maps[-1]
                add(
                    f"context_causal_validity_map:{item.id}",
                    (
                        f"hypothesis={item.hypothesis_id}; "
                        f"valid={len(item.tested_valid_signatures)}; "
                        f"invalid={len(item.tested_invalid_signatures)}; "
                        f"dimensions={','.join(item.dimensions)}; "
                        f"distance={item.max_generalization_distance}; "
                        f"confidence={item.confidence}"
                    ),
                )
                for ref in item.evidence_refs[-6:]:
                    add(ref, "evidence consolidated into the causal validity map")
                summary = (
                    "The latest causal validity map keeps exact tested-valid and "
                    "tested-invalid environments authoritative, supports only "
                    "nearby regions that remain farther from known boundaries, "
                    "and abstains elsewhere."
                )
            else:
                summary = "No causal validity map has been consolidated."

        elif focus in {
            "context_boundary_discovery",
            "boundary_discovery",
            "active_boundary",
        }:
            if self.context_boundary_discovery_plans:
                plan = self.context_boundary_discovery_plans[-1]
                add(
                    f"context_boundary_discovery_plan:{plan.id}",
                    (
                        f"hypothesis={plan.hypothesis_id}; "
                        f"status={plan.status}; "
                        f"selected={plan.selected_signature}; "
                        f"risk={plan.selected_risk}; "
                        f"information_gain={plan.selected_information_gain}; "
                        f"priority={plan.selected_priority_score}; "
                        f"outcome={plan.outcome_status}; "
                        f"uncertainty_reduction={plan.uncertainty_reduction}"
                    ),
                )
                for ref in plan.evidence_refs[-6:]:
                    add(ref, "boundary-planning or supplied outcome evidence")
                summary = (
                    "The latest active-boundary record selects a low-risk "
                    "environment probe for expected information gain without "
                    "executing it, then links any later supplied stability result."
                )
            else:
                summary = "No active context-boundary discovery plan exists."

        elif focus in {
            "context_causal_invariance",
            "causal_invariance",
            "environment_invariance",
        }:
            if self.context_causal_invariance_assessments:
                assessment = self.context_causal_invariance_assessments[-1]
                add(
                    f"context_causal_invariance_assessment:{assessment.id}",
                    (
                        f"hypothesis={assessment.hypothesis_id}; "
                        f"status={assessment.status}; "
                        f"environments={assessment.distinct_environment_count}; "
                        f"stable={assessment.stable_environment_count}; "
                        f"direction_consistent="
                        f"{assessment.effect_direction_consistent}; "
                        f"strength_spread={assessment.strength_spread}; "
                        f"confidence={assessment.confidence}"
                    ),
                )
                for ref in assessment.evidence_refs[-6:]:
                    add(ref, "environment-specific causal stability evidence")
                summary = (
                    "The latest causal-invariance assessment tests whether a "
                    "replicated reversible context relation survives predefined "
                    "environment changes and records boundaries instead of "
                    "assuming cross-environment generalization."
                )
            else:
                summary = "No cross-environment causal-invariance assessment exists."

        elif focus in {
            "context_causal_stability",
            "causal_stability",
            "replicated_context_causality",
        }:
            if self.context_causal_stability_assessments:
                assessment = self.context_causal_stability_assessments[-1]
                add(
                    f"context_causal_stability_assessment:{assessment.id}",
                    (
                        f"hypothesis={assessment.hypothesis_id}; "
                        f"status={assessment.status}; "
                        f"forward_independent="
                        f"{assessment.independent_forward_batches}; "
                        f"reverse_independent="
                        f"{assessment.independent_reverse_batches}; "
                        f"reversal_followed="
                        f"{assessment.reversal_direction_followed}; "
                        f"confidence={assessment.confidence}"
                    ),
                )
                for ref in assessment.evidence_refs[-6:]:
                    add(ref, "replication or reversal evidence")
                summary = (
                    "The latest causal-stability assessment requires independent "
                    "forward replication and a clean reverse intervention before "
                    "escalating context causality beyond single-trial support."
                )
            else:
                summary = "No replicated context-causality assessment exists."

        elif focus in {
            "context_causality",
            "context_intervention",
            "causal_context",
        }:
            if self.context_causality_trials:
                trial = self.context_causality_trials[-1]
                add(
                    f"context_causality_trial:{trial.id}",
                    (
                        f"hypothesis={trial.hypothesis_id}; "
                        f"context={trial.from_context}->{trial.to_context}; "
                        f"status={trial.status}; "
                        f"held_constant="
                        f"{trial.competing_variables_held_constant}; "
                        f"direction_followed="
                        f"{trial.predicted_direction_followed}; "
                        f"strength={trial.causal_strength}"
                    ),
                )
                add(
                    f"latent_context_hypothesis:{trial.hypothesis_id}",
                    "observational context hypothesis under intervention test",
                )
                for ref in trial.evidence_refs[-4:]:
                    add(
                        ref,
                        "evidence linked to the controlled context intervention",
                    )
                summary = (
                    "The latest context-causality assessment separates held-out "
                    "observational prediction from intervention support and "
                    "rejects causal upgrading when competing variables changed."
                )
            else:
                summary = "No context-causality intervention has been observed."

        elif focus in {
            "latent_context",
            "context_discovery",
            "latent_context_discovery",
        }:
            if self.latent_context_discoveries:
                discovery = self.latent_context_discoveries[-1]
                add(
                    f"latent_context_discovery:{discovery.id}",
                    (
                        f"parent_schema={discovery.parent_schema_id}; "
                        f"proposed={discovery.proposed_count}; "
                        f"validated={discovery.validated_count}; "
                        f"status={discovery.status}"
                    ),
                )
                for hypothesis_id in discovery.hypothesis_ids[:4]:
                    hypothesis = next(
                        (
                            item
                            for item in self.latent_context_hypotheses
                            if item.id == hypothesis_id
                        ),
                        None,
                    )
                    if hypothesis is not None:
                        add(
                            f"latent_context_hypothesis:{hypothesis.id}",
                            (
                                f"terms={hypothesis.positive_term}/"
                                f"{hypothesis.negative_term}; "
                                f"contrast={hypothesis.rate_contrast:.3f}; "
                                f"validation={hypothesis.validation_status}; "
                                f"gain={hypothesis.holdout_improvement:.3f}"
                            ),
                        )
                for ref in discovery.evidence_refs[-4:]:
                    add(
                        ref,
                        "autobiographical evidence used for candidate discovery",
                    )
                summary = (
                    "The latest latent-context discovery proposed only bounded "
                    "outcome-associated term pairs and accepted context structure "
                    "only through held-out decomposition validation."
                )
            else:
                summary = "No latent context-hypothesis discovery has been run."

        elif focus in {
            "context_transfer",
            "transfer_boundary",
            "context_generalization",
        }:
            if self.context_transfer_boundaries:
                boundary = self.context_transfer_boundaries[-1]
                add(
                    f"context_transfer:{boundary.id}",
                    (
                        f"source_schema={boundary.source_context_schema_id}; "
                        f"target={boundary.target_label}; status={boundary.status}; "
                        f"source_mae={boundary.source_holdout_mae:.3f}; "
                        f"global_mae={boundary.global_holdout_mae:.3f}; "
                        f"gain={boundary.improvement:.3f}; "
                        f"strength={boundary.transfer_strength:.3f}"
                    ),
                )
                add(
                    f"contextual_self_schema:{boundary.source_context_schema_id}",
                    "source contextual self-schema considered for transfer",
                )
                for ref in boundary.evidence_refs[-4:]:
                    add(
                        ref,
                        "new target-context evidence used to validate transfer",
                    )
                summary = (
                    "The latest context-transfer boundary is reconstructed from "
                    "a validated source context and previously unused target "
                    "evidence compared against the global fallback."
                )
            else:
                summary = "No context-transfer boundary has been evaluated."

        elif focus in {
            "contextual_schema",
            "schema_decomposition",
            "context_decomposition",
        }:
            if self.self_schema_decompositions:
                decomposition = self.self_schema_decompositions[-1]
                add(
                    f"self_schema_decomposition:{decomposition.id}",
                    (
                        f"parent_schema={decomposition.parent_schema_id}; "
                        f"contexts={','.join(decomposition.context_labels)}; "
                        f"status={decomposition.status}; "
                        f"global_mae={decomposition.global_holdout_mae:.3f}; "
                        f"contextual_mae="
                        f"{decomposition.contextual_holdout_mae:.3f}; "
                        f"improvement={decomposition.improvement:.3f}"
                    ),
                )
                for schema_id in decomposition.context_schema_ids:
                    item = next(
                        (
                            candidate
                            for candidate in self.contextual_self_schema
                            if candidate.id == schema_id
                        ),
                        None,
                    )
                    if item is not None:
                        add(
                            f"contextual_self_schema:{item.id}",
                            (
                                f"context={item.context_label}; kind={item.kind}; "
                                f"success_rate={item.success_rate:.3f}; "
                                f"confidence={item.confidence:.3f}"
                            ),
                        )
                for ref in decomposition.evidence_refs[-4:]:
                    add(
                        ref,
                        "autobiographical evidence used to validate context split",
                    )
                summary = (
                    "The latest context-sensitive self-schema decomposition is "
                    "grounded in an explicit candidate partition and held-out "
                    "prediction gain over the unsplit global schema."
                )
            else:
                summary = "No context-sensitive self-schema decomposition exists."

        elif focus in {"schema_revision", "self_schema_revision", "corrigibility"}:
            if self.self_schema_revisions:
                revision = self.self_schema_revisions[-1]
                add(
                    f"self_schema_revision:{revision.id}",
                    (
                        f"schema_id={revision.schema_id}; "
                        f"kind={revision.prior_kind}->{revision.revised_kind}; "
                        f"confidence={revision.prior_confidence:.3f}"
                        f"->{revision.revised_confidence:.3f}; "
                        f"success_rate={revision.prior_success_rate:.3f}"
                        f"->{revision.revised_success_rate:.3f}; "
                        f"status={revision.status}"
                    ),
                )
                for ref in revision.contradictory_evidence_refs:
                    add(
                        ref,
                        (
                            "new autobiographical evidence that contradicted "
                            "the prior self-schema"
                        ),
                    )
                add(
                    f"self_schema:{revision.schema_id}",
                    "current self-schema after contradiction reconciliation",
                )
                summary = (
                    "The latest self-schema revision is reconstructed from the "
                    "prior schema and the new contradictory autobiographical evidence."
                )
            else:
                summary = "No self-schema contradiction revision has been recorded."

        elif focus in {"self_schema", "schema", "identity"}:
            active = self.active_self_schema()
            if active:
                for item in active[:3]:
                    add(
                        f"self_schema:{item.id}",
                        (
                            f"kind={item.kind}; pattern='{item.pattern[:180]}'; "
                            f"confidence={item.confidence:.3f}; "
                            f"success_rate={item.success_rate:.3f}; "
                            f"success_bias={item.success_bias:+.3f}; "
                            f"risk_bias={item.risk_bias:+.3f}"
                        ),
                    )
                    for ref in item.evidence_refs[:4]:
                        add(
                            ref,
                            f"stored evidence supporting self-schema entry {item.id}",
                        )
                summary = (
                    "The autobiographical self-schema is reconstructed only from "
                    "stored outcomes and related causal records; it is compact, "
                    "revisable, and used as bounded evidence for later predictions."
                )
            else:
                summary = "No autobiographical self-schema has been consolidated."

        elif focus in {"counterfactual", "simulation", "imagination"}:
            if self.counterfactual_futures:
                item = self.counterfactual_futures[-1]
                index = len(self.counterfactual_futures) - 1
                add(
                    f"counterfactual:{index}",
                    (
                        f"action={item.action!r}; status={item.status}; "
                        f"predicted_success={item.predicted_success:.3f}; "
                        f"predicted_information_gain="
                        f"{item.predicted_information_gain:.3f}; "
                        f"discrepancy={item.discrepancy}"
                    ),
                )
                if item.linked_workspace_cycle_id is not None:
                    cycle = next(
                        (
                            candidate
                            for candidate in self.global_workspace_cycles
                            if candidate.id == item.linked_workspace_cycle_id
                        ),
                        None,
                    )
                    if cycle is not None:
                        add(
                            f"workspace_cycle:{self.global_workspace_cycles.index(cycle)}",
                            (
                                f"mode={cycle.decision_mode}; "
                                f"sources={','.join(cycle.integrated_sources)}; "
                                f"coherence={cycle.coherence_score:.3f}"
                            ),
                        )
                if item.feedback_workspace_item_id is not None:
                    feedback = next(
                        (
                            candidate
                            for candidate in self.global_workspace_items
                            if candidate.id == item.feedback_workspace_item_id
                        ),
                        None,
                    )
                    if feedback is not None:
                        add(
                            f"workspace_item:{feedback.id}",
                            (
                                f"prediction-error feedback source={feedback.source}; "
                                f"salience={feedback.salience:.3f}"
                            ),
                        )
                summary = (
                    "The latest counterfactual is traced to its predicted future, "
                    "workspace context, and any observed prediction-error feedback."
                )
            else:
                summary = "No counterfactual future has been simulated."

        elif focus in {"workspace", "global_workspace", "broadcast"}:
            if self.global_workspace_cycles:
                cycle = self.global_workspace_cycles[-1]
                add(
                    f"workspace_cycle:{len(self.global_workspace_cycles) - 1}",
                    (
                        f"mode={cycle.decision_mode}; "
                        f"sources={','.join(cycle.integrated_sources)}; "
                        f"recurrence_depth={cycle.recurrence_depth}; "
                        f"coherence={cycle.coherence_score:.3f}"
                    ),
                )
                for item_id in cycle.selected_item_ids:
                    item = next(
                        (
                            candidate
                            for candidate in self.global_workspace_items
                            if candidate.id == item_id
                        ),
                        None,
                    )
                    if item is not None:
                        add(
                            f"workspace_item:{item.id}",
                            (
                                f"source={item.source}; salience={item.salience:.3f}; "
                                f"status={item.status}; content='{item.content[:180]}'"
                            ),
                        )
                summary = (
                    "The latest global workspace cycle is reconstructed from "
                    "selected evidence, source diversity, bounded recurrence, "
                    "and the recorded broadcast targets."
                )
            else:
                summary = "No global workspace cycle has been recorded."

        elif focus in {"current_state", "state", "self"}:
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
            "global_workspace_items": [
                item.to_dict() for item in self.global_workspace_items
            ],
            "global_workspace_cycles": [
                item.to_dict() for item in self.global_workspace_cycles
            ],
            "next_workspace_item_id": self.next_workspace_item_id,
            "next_workspace_cycle_id": self.next_workspace_cycle_id,
            "workspace_recurrence_limit": self.workspace_recurrence_limit,
            "counterfactual_futures": [
                item.to_dict() for item in self.counterfactual_futures
            ],
            "next_counterfactual_id": self.next_counterfactual_id,
            "max_counterfactual_futures": self.max_counterfactual_futures,
            "self_schema": [item.to_dict() for item in self.self_schema],
            "next_self_schema_id": self.next_self_schema_id,
            "max_self_schema_entries": self.max_self_schema_entries,
            "self_schema_revisions": [
                item.to_dict() for item in self.self_schema_revisions
            ],
            "next_self_schema_revision_id": self.next_self_schema_revision_id,
            "contextual_self_schema": [
                item.to_dict() for item in self.contextual_self_schema
            ],
            "next_contextual_self_schema_id": self.next_contextual_self_schema_id,
            "self_schema_decompositions": [
                item.to_dict() for item in self.self_schema_decompositions
            ],
            "next_self_schema_decomposition_id": (
                self.next_self_schema_decomposition_id
            ),
            "context_transfer_boundaries": [
                item.to_dict() for item in self.context_transfer_boundaries
            ],
            "next_context_transfer_boundary_id": (
                self.next_context_transfer_boundary_id
            ),
            "latent_context_hypotheses": [
                item.to_dict() for item in self.latent_context_hypotheses
            ],
            "next_latent_context_hypothesis_id": (
                self.next_latent_context_hypothesis_id
            ),
            "latent_context_discoveries": [
                item.to_dict() for item in self.latent_context_discoveries
            ],
            "next_latent_context_discovery_id": (
                self.next_latent_context_discovery_id
            ),
            "context_causality_trials": [
                item.to_dict() for item in self.context_causality_trials
            ],
            "next_context_causality_trial_id": (
                self.next_context_causality_trial_id
            ),
            "context_causal_stability_assessments": [
                item.to_dict()
                for item in self.context_causal_stability_assessments
            ],
            "next_context_causal_stability_assessment_id": (
                self.next_context_causal_stability_assessment_id
            ),
            "context_causal_invariance_assessments": [
                item.to_dict()
                for item in self.context_causal_invariance_assessments
            ],
            "next_context_causal_invariance_assessment_id": (
                self.next_context_causal_invariance_assessment_id
            ),
            "context_boundary_discovery_plans": [
                item.to_dict()
                for item in self.context_boundary_discovery_plans
            ],
            "next_context_boundary_discovery_plan_id": (
                self.next_context_boundary_discovery_plan_id
            ),
            "context_causal_validity_maps": [
                item.to_dict() for item in self.context_causal_validity_maps
            ],
            "next_context_causal_validity_map_id": (
                self.next_context_causal_validity_map_id
            ),
            "context_validity_decision_gates": [
                item.to_dict()
                for item in self.context_validity_decision_gates
            ],
            "next_context_validity_decision_gate_id": (
                self.next_context_validity_decision_gate_id
            ),
            "context_validity_gate_outcomes": [
                item.to_dict()
                for item in self.context_validity_gate_outcomes
            ],
            "next_context_validity_gate_outcome_id": (
                self.next_context_validity_gate_outcome_id
            ),
            "context_validity_region_calibrations": [
                item.to_dict()
                for item in self.context_validity_region_calibrations
            ],
            "next_context_validity_region_calibration_id": (
                self.next_context_validity_region_calibration_id
            ),
            "active_context_validity_map_ids": [
                [hypothesis_id, map_id]
                for hypothesis_id, map_id
                in sorted(self.active_context_validity_map_ids.items())
            ],
            "context_validity_map_selection_history": [
                item.to_dict()
                for item in self.context_validity_map_selection_history
            ],
            "next_context_validity_map_selection_id": (
                self.next_context_validity_map_selection_id
            ),
            "context_validity_degradation_watches": [
                item.to_dict()
                for item in self.context_validity_degradation_watches
            ],
            "next_context_validity_degradation_watch_id": (
                self.next_context_validity_degradation_watch_id
            ),
            "context_validity_recommendation_resolutions": [
                item.to_dict()
                for item in self.context_validity_recommendation_resolutions
            ],
            "next_context_validity_recommendation_resolution_id": (
                self.next_context_validity_recommendation_resolution_id
            ),
            "context_validity_rollback_validations": [
                item.to_dict()
                for item in self.context_validity_rollback_validations
            ],
            "next_context_validity_rollback_validation_id": (
                self.next_context_validity_rollback_validation_id
            ),
            "context_validity_rollback_holdout_validations": [
                item.to_dict()
                for item in self.context_validity_rollback_holdout_validations
            ],
            "next_context_validity_rollback_holdout_validation_id": (
                self.next_context_validity_rollback_holdout_validation_id
            ),
            "context_validity_reactivation_drift_watches": [
                item.to_dict()
                for item in self.context_validity_reactivation_drift_watches
            ],
            "next_context_validity_reactivation_drift_watch_id": (
                self.next_context_validity_reactivation_drift_watch_id
            ),
            "context_validity_reactivation_drift_resolutions": [
                item.to_dict()
                for item in self.context_validity_reactivation_drift_resolutions
            ],
            "next_context_validity_reactivation_drift_resolution_id": (
                self.next_context_validity_reactivation_drift_resolution_id
            ),
            "context_validity_renewed_recovery_validations": [
                item.to_dict()
                for item in self.context_validity_renewed_recovery_validations
            ],
            "next_context_validity_renewed_recovery_validation_id": (
                self.next_context_validity_renewed_recovery_validation_id
            ),
            "context_validity_renewed_holdout_validations": [
                item.to_dict()
                for item in self.context_validity_renewed_holdout_validations
            ],
            "next_context_validity_renewed_holdout_validation_id": (
                self.next_context_validity_renewed_holdout_validation_id
            ),
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
        if payload.get("version") not in {
            UNARCHI_VERSION,
            *_LEGACY_UNARCHI_VERSIONS,
        }:
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
        workspace_items_payload = payload.get("global_workspace_items", [])
        workspace_cycles_payload = payload.get("global_workspace_cycles", [])
        counterfactuals_payload = payload.get("counterfactual_futures", [])
        self_schema_payload = payload.get("self_schema", [])
        self_schema_revisions_payload = payload.get("self_schema_revisions", [])
        contextual_self_schema_payload = payload.get("contextual_self_schema", [])
        self_schema_decompositions_payload = payload.get(
            "self_schema_decompositions",
            [],
        )
        context_transfer_boundaries_payload = payload.get(
            "context_transfer_boundaries",
            [],
        )
        latent_context_hypotheses_payload = payload.get(
            "latent_context_hypotheses",
            [],
        )
        latent_context_discoveries_payload = payload.get(
            "latent_context_discoveries",
            [],
        )
        context_causality_trials_payload = payload.get(
            "context_causality_trials",
            [],
        )
        context_causal_stability_assessments_payload = payload.get(
            "context_causal_stability_assessments",
            [],
        )
        context_causal_invariance_assessments_payload = payload.get(
            "context_causal_invariance_assessments",
            [],
        )
        context_boundary_discovery_plans_payload = payload.get(
            "context_boundary_discovery_plans",
            [],
        )
        context_causal_validity_maps_payload = payload.get(
            "context_causal_validity_maps",
            [],
        )
        context_validity_decision_gates_payload = payload.get(
            "context_validity_decision_gates",
            [],
        )
        context_validity_gate_outcomes_payload = payload.get(
            "context_validity_gate_outcomes",
            [],
        )
        context_validity_region_calibrations_payload = payload.get(
            "context_validity_region_calibrations",
            [],
        )
        active_context_validity_map_ids_payload = payload.get(
            "active_context_validity_map_ids",
            [],
        )
        context_validity_map_selection_history_payload = payload.get(
            "context_validity_map_selection_history",
            [],
        )
        context_validity_degradation_watches_payload = payload.get(
            "context_validity_degradation_watches",
            [],
        )
        context_validity_recommendation_resolutions_payload = payload.get(
            "context_validity_recommendation_resolutions",
            [],
        )
        context_validity_rollback_validations_payload = payload.get(
            "context_validity_rollback_validations",
            [],
        )
        context_validity_rollback_holdout_validations_payload = payload.get(
            "context_validity_rollback_holdout_validations",
            [],
        )
        context_validity_reactivation_drift_watches_payload = payload.get(
            "context_validity_reactivation_drift_watches",
            [],
        )
        context_validity_reactivation_drift_resolutions_payload = payload.get(
            "context_validity_reactivation_drift_resolutions",
            [],
        )
        context_validity_renewed_recovery_validations_payload = payload.get(
            "context_validity_renewed_recovery_validations",
            [],
        )
        context_validity_renewed_holdout_validations_payload = payload.get(
            "context_validity_renewed_holdout_validations",
            [],
        )
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
        if not isinstance(workspace_items_payload, list):
            raise ValueError("invalid UNARCHI global workspace items")
        if not isinstance(workspace_cycles_payload, list):
            raise ValueError("invalid UNARCHI global workspace cycles")
        if not isinstance(counterfactuals_payload, list):
            raise ValueError("invalid UNARCHI counterfactual futures")
        if not isinstance(self_schema_payload, list):
            raise ValueError("invalid UNARCHI self schema")
        if not isinstance(self_schema_revisions_payload, list):
            raise ValueError("invalid UNARCHI self schema revisions")
        if not isinstance(contextual_self_schema_payload, list):
            raise ValueError("invalid UNARCHI contextual self schema")
        if not isinstance(self_schema_decompositions_payload, list):
            raise ValueError("invalid UNARCHI self schema decompositions")
        if not isinstance(context_transfer_boundaries_payload, list):
            raise ValueError("invalid UNARCHI context transfer boundaries")
        if not isinstance(latent_context_hypotheses_payload, list):
            raise ValueError("invalid UNARCHI latent context hypotheses")
        if not isinstance(latent_context_discoveries_payload, list):
            raise ValueError("invalid UNARCHI latent context discoveries")
        if not isinstance(context_causality_trials_payload, list):
            raise ValueError("invalid UNARCHI context causality trials")
        if not isinstance(context_causal_stability_assessments_payload, list):
            raise ValueError("invalid UNARCHI context causal stability assessments")
        if not isinstance(context_causal_invariance_assessments_payload, list):
            raise ValueError("invalid UNARCHI context causal invariance assessments")
        if not isinstance(context_boundary_discovery_plans_payload, list):
            raise ValueError("invalid UNARCHI context boundary discovery plans")
        if not isinstance(context_causal_validity_maps_payload, list):
            raise ValueError("invalid UNARCHI context causal validity maps")
        if not isinstance(context_validity_decision_gates_payload, list):
            raise ValueError("invalid UNARCHI context validity decision gates")
        if not isinstance(context_validity_gate_outcomes_payload, list):
            raise ValueError("invalid UNARCHI context validity gate outcomes")
        if not isinstance(context_validity_region_calibrations_payload, list):
            raise ValueError(
                "invalid UNARCHI context validity region calibrations"
            )
        if not isinstance(active_context_validity_map_ids_payload, list):
            raise ValueError(
                "invalid UNARCHI active context validity map pointers"
            )
        if not isinstance(context_validity_map_selection_history_payload, list):
            raise ValueError(
                "invalid UNARCHI context validity map selection history"
            )
        if not isinstance(context_validity_degradation_watches_payload, list):
            raise ValueError(
                "invalid UNARCHI context validity degradation watches"
            )
        if not isinstance(
            context_validity_recommendation_resolutions_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity recommendation resolutions"
            )
        if not isinstance(context_validity_rollback_validations_payload, list):
            raise ValueError(
                "invalid UNARCHI context validity rollback validations"
            )
        if not isinstance(
            context_validity_rollback_holdout_validations_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity rollback holdout validations"
            )
        if not isinstance(
            context_validity_reactivation_drift_watches_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity reactivation drift watches"
            )
        if not isinstance(
            context_validity_reactivation_drift_resolutions_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity reactivation drift resolutions"
            )
        if not isinstance(
            context_validity_renewed_recovery_validations_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity renewed recovery validations"
            )
        if not isinstance(
            context_validity_renewed_holdout_validations_payload,
            list,
        ):
            raise ValueError(
                "invalid UNARCHI context validity renewed holdout validations"
            )

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

        global_workspace_items: list[GlobalWorkspaceItem] = []
        for item in workspace_items_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI global workspace item")
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            global_workspace_items.append(GlobalWorkspaceItem(**restored_item))

        global_workspace_cycles: list[GlobalWorkspaceCycle] = []
        for item in workspace_cycles_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI global workspace cycle")
            restored_item = dict(item)
            restored_item["selected_item_ids"] = tuple(
                restored_item.get("selected_item_ids", ())
            )
            restored_item["integrated_sources"] = tuple(
                restored_item.get("integrated_sources", ())
            )
            restored_item["broadcast_targets"] = tuple(
                restored_item.get("broadcast_targets", ())
            )
            global_workspace_cycles.append(GlobalWorkspaceCycle(**restored_item))

        counterfactual_futures: list[CounterfactualFuture] = []
        for item in counterfactuals_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI counterfactual future")
            counterfactual_futures.append(CounterfactualFuture(**item))

        self_schema: list[SelfSchemaEntry] = []
        for item in self_schema_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI self schema entry")
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            self_schema.append(SelfSchemaEntry(**restored_item))

        self_schema_revisions: list[SelfSchemaRevision] = []
        for item in self_schema_revisions_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI self schema revision")
            restored_item = dict(item)
            restored_item["contradictory_evidence_refs"] = tuple(
                restored_item.get("contradictory_evidence_refs", ())
            )
            self_schema_revisions.append(SelfSchemaRevision(**restored_item))

        contextual_self_schema: list[ContextualSelfSchemaEntry] = []
        for item in contextual_self_schema_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI contextual self schema entry")
            restored_item = dict(item)
            restored_item["context_terms"] = tuple(
                restored_item.get("context_terms", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            contextual_self_schema.append(
                ContextualSelfSchemaEntry(**restored_item)
            )

        self_schema_decompositions: list[SelfSchemaDecomposition] = []
        for item in self_schema_decompositions_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI self schema decomposition")
            restored_item = dict(item)
            restored_item["context_schema_ids"] = tuple(
                restored_item.get("context_schema_ids", ())
            )
            restored_item["context_labels"] = tuple(
                restored_item.get("context_labels", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            self_schema_decompositions.append(
                SelfSchemaDecomposition(**restored_item)
            )

        context_transfer_boundaries: list[ContextTransferBoundary] = []
        for item in context_transfer_boundaries_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI context transfer boundary")
            restored_item = dict(item)
            restored_item["target_terms"] = tuple(
                restored_item.get("target_terms", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_transfer_boundaries.append(
                ContextTransferBoundary(**restored_item)
            )

        latent_context_hypotheses: list[LatentContextHypothesis] = []
        for item in latent_context_hypotheses_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI latent context hypothesis")
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            restored_item["causal_evidence_refs"] = tuple(
                restored_item.get("causal_evidence_refs", ())
            )
            latent_context_hypotheses.append(
                LatentContextHypothesis(**restored_item)
            )

        latent_context_discoveries: list[LatentContextDiscovery] = []
        for item in latent_context_discoveries_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI latent context discovery")
            restored_item = dict(item)
            restored_item["hypothesis_ids"] = tuple(
                restored_item.get("hypothesis_ids", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            latent_context_discoveries.append(
                LatentContextDiscovery(**restored_item)
            )

        context_causality_trials: list[ContextCausalityTrial] = []
        for item in context_causality_trials_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI context causality trial")
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_causality_trials.append(
                ContextCausalityTrial(**restored_item)
            )

        context_causal_stability_assessments: list[
            ContextCausalStabilityAssessment
        ] = []
        for item in context_causal_stability_assessments_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context causal stability assessment"
                )
            restored_item = dict(item)
            restored_item["forward_trial_ids"] = tuple(
                restored_item.get("forward_trial_ids", ())
            )
            restored_item["reverse_trial_ids"] = tuple(
                restored_item.get("reverse_trial_ids", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_causal_stability_assessments.append(
                ContextCausalStabilityAssessment(**restored_item)
            )

        context_causal_invariance_assessments: list[
            ContextCausalInvarianceAssessment
        ] = []
        for item in context_causal_invariance_assessments_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context causal invariance assessment"
                )
            restored_item = dict(item)
            restored_item["stability_assessment_ids"] = tuple(
                restored_item.get("stability_assessment_ids", ())
            )
            restored_item["environment_signatures"] = tuple(
                restored_item.get("environment_signatures", ())
            )
            restored_item["boundary_signatures"] = tuple(
                restored_item.get("boundary_signatures", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_causal_invariance_assessments.append(
                ContextCausalInvarianceAssessment(**restored_item)
            )

        context_boundary_discovery_plans: list[
            ContextBoundaryDiscoveryPlan
        ] = []
        for item in context_boundary_discovery_plans_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context boundary discovery plan"
                )
            restored_item = dict(item)
            restored_item["candidate_signatures"] = tuple(
                restored_item.get("candidate_signatures", ())
            )
            restored_item["changed_dimensions"] = tuple(
                restored_item.get("changed_dimensions", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_boundary_discovery_plans.append(
                ContextBoundaryDiscoveryPlan(**restored_item)
            )

        context_causal_validity_maps: list[ContextCausalValidityMap] = []
        for item in context_causal_validity_maps_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI context causal validity map")
            restored_item = dict(item)
            restored_item["source_invariance_assessment_ids"] = tuple(
                restored_item.get("source_invariance_assessment_ids", ())
            )
            restored_item["source_boundary_plan_ids"] = tuple(
                restored_item.get("source_boundary_plan_ids", ())
            )
            restored_item["signature_assessment_ids"] = tuple(
                tuple(pair)
                for pair in restored_item.get(
                    "signature_assessment_ids",
                    (),
                )
            )
            restored_item["tested_valid_signatures"] = tuple(
                restored_item.get("tested_valid_signatures", ())
            )
            restored_item["tested_invalid_signatures"] = tuple(
                restored_item.get("tested_invalid_signatures", ())
            )
            restored_item["dimensions"] = tuple(
                restored_item.get("dimensions", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            restored_item["source_calibration_ids"] = tuple(
                restored_item.get("source_calibration_ids", ())
            )
            restored_item["calibrated_supported_signatures"] = tuple(
                restored_item.get("calibrated_supported_signatures", ())
            )
            restored_item["revoked_inferred_signatures"] = tuple(
                restored_item.get("revoked_inferred_signatures", ())
            )
            restored_item["revision_reasons"] = tuple(
                restored_item.get("revision_reasons", ())
            )
            context_causal_validity_maps.append(
                ContextCausalValidityMap(**restored_item)
            )

        context_validity_decision_gates: list[
            ContextValidityDecisionGate
        ] = []
        for item in context_validity_decision_gates_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity decision gate"
                )
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_decision_gates.append(
                ContextValidityDecisionGate(**restored_item)
            )

        context_validity_gate_outcomes: list[
            ContextValidityGateOutcome
        ] = []
        for item in context_validity_gate_outcomes_payload:
            if not isinstance(item, dict):
                raise ValueError("invalid UNARCHI context validity gate outcome")
            restored_item = dict(item)
            restored_item["actual_success_by_action"] = tuple(
                tuple(pair)
                for pair in restored_item.get(
                    "actual_success_by_action",
                    (),
                )
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_gate_outcomes.append(
                ContextValidityGateOutcome(**restored_item)
            )

        context_validity_region_calibrations: list[
            ContextValidityRegionCalibration
        ] = []
        for item in context_validity_region_calibrations_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity region calibration"
                )
            restored_item = dict(item)
            restored_item["outcome_ids"] = tuple(
                restored_item.get("outcome_ids", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_region_calibrations.append(
                ContextValidityRegionCalibration(**restored_item)
            )

        active_context_validity_map_ids: dict[int, int] = {}
        for item in active_context_validity_map_ids_payload:
            if (
                not isinstance(item, (list, tuple))
                or len(item) != 2
            ):
                raise ValueError(
                    "invalid UNARCHI active context validity map pointer"
                )
            hypothesis_id = int(item[0])
            map_id = int(item[1])
            active_context_validity_map_ids[hypothesis_id] = map_id

        context_validity_map_selection_history: list[
            ContextValidityMapSelection
        ] = []
        for item in context_validity_map_selection_history_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity map selection"
                )
            restored_item = dict(item)
            restored_item["lineage"] = tuple(
                restored_item.get("lineage", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_map_selection_history.append(
                ContextValidityMapSelection(**restored_item)
            )

        context_validity_degradation_watches: list[
            ContextValidityDegradationWatch
        ] = []
        for item in context_validity_degradation_watches_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity degradation watch"
                )
            restored_item = dict(item)
            restored_item["observed_calibration_ids"] = tuple(
                restored_item.get("observed_calibration_ids", ())
            )
            restored_item["degraded_signatures"] = tuple(
                restored_item.get("degraded_signatures", ())
            )
            restored_item["ancestor_support_calibration_ids"] = tuple(
                restored_item.get("ancestor_support_calibration_ids", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_degradation_watches.append(
                ContextValidityDegradationWatch(**restored_item)
            )

        context_validity_recommendation_resolutions: list[
            ContextValidityRecommendationResolution
        ] = []
        for item in context_validity_recommendation_resolutions_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity recommendation resolution"
                )
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_recommendation_resolutions.append(
                ContextValidityRecommendationResolution(**restored_item)
            )

        context_validity_rollback_validations: list[
            ContextValidityRollbackValidation
        ] = []
        for item in context_validity_rollback_validations_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity rollback validation"
                )
            restored_item = dict(item)
            restored_item["observed_outcome_ids"] = tuple(
                restored_item.get("observed_outcome_ids", ())
            )
            restored_item["degraded_signatures"] = tuple(
                restored_item.get("degraded_signatures", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_rollback_validations.append(
                ContextValidityRollbackValidation(**restored_item)
            )

        context_validity_rollback_holdout_validations: list[
            ContextValidityRollbackHoldoutValidation
        ] = []
        for item in context_validity_rollback_holdout_validations_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity rollback holdout validation"
                )
            restored_item = dict(item)
            restored_item["recovery_outcome_ids"] = tuple(
                restored_item.get("recovery_outcome_ids", ())
            )
            restored_item["holdout_outcome_ids"] = tuple(
                restored_item.get("holdout_outcome_ids", ())
            )
            restored_item["degraded_signatures"] = tuple(
                restored_item.get("degraded_signatures", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_rollback_holdout_validations.append(
                ContextValidityRollbackHoldoutValidation(**restored_item)
            )

        context_validity_reactivation_drift_watches: list[
            ContextValidityReactivationDriftWatch
        ] = []
        for item in context_validity_reactivation_drift_watches_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity reactivation drift watch"
                )
            restored_item = dict(item)
            restored_item["observed_outcome_ids"] = tuple(
                restored_item.get("observed_outcome_ids", ())
            )
            restored_item["degraded_signatures"] = tuple(
                restored_item.get("degraded_signatures", ())
            )
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_reactivation_drift_watches.append(
                ContextValidityReactivationDriftWatch(**restored_item)
            )

        context_validity_reactivation_drift_resolutions: list[
            ContextValidityReactivationDriftResolution
        ] = []
        for item in context_validity_reactivation_drift_resolutions_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity reactivation drift resolution"
                )
            restored_item = dict(item)
            restored_item["evidence_refs"] = tuple(
                restored_item.get("evidence_refs", ())
            )
            context_validity_reactivation_drift_resolutions.append(
                ContextValidityReactivationDriftResolution(**restored_item)
            )

        context_validity_renewed_recovery_validations: list[
            ContextValidityRenewedRecoveryValidation
        ] = []
        for item in context_validity_renewed_recovery_validations_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity renewed recovery validation"
                )
            restored_item = dict(item)
            for key in (
                "observed_outcome_ids",
                "excluded_prior_outcome_ids",
                "degraded_signatures",
                "evidence_refs",
            ):
                restored_item[key] = tuple(restored_item.get(key, ()))
            context_validity_renewed_recovery_validations.append(
                ContextValidityRenewedRecoveryValidation(**restored_item)
            )

        context_validity_renewed_holdout_validations: list[
            ContextValidityRenewedHoldoutValidation
        ] = []
        for item in context_validity_renewed_holdout_validations_payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "invalid UNARCHI context validity renewed holdout validation"
                )
            restored_item = dict(item)
            for key in (
                "recovery_outcome_ids",
                "holdout_outcome_ids",
                "excluded_prior_outcome_ids",
                "degraded_signatures",
                "evidence_refs",
            ):
                restored_item[key] = tuple(restored_item.get(key, ()))
            context_validity_renewed_holdout_validations.append(
                ContextValidityRenewedHoldoutValidation(**restored_item)
            )

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
            global_workspace_items=global_workspace_items[-max_memory:],
            global_workspace_cycles=global_workspace_cycles[-max_memory:],
            next_workspace_item_id=max(
                int(payload.get("next_workspace_item_id") or 1),
                max((item.id for item in global_workspace_items), default=0) + 1,
            ),
            next_workspace_cycle_id=max(
                int(payload.get("next_workspace_cycle_id") or 1),
                max((item.id for item in global_workspace_cycles), default=0) + 1,
            ),
            workspace_recurrence_limit=max(
                1,
                min(int(payload.get("workspace_recurrence_limit") or 3), 8),
            ),
            counterfactual_futures=counterfactual_futures[-max_memory:],
            next_counterfactual_id=max(
                int(payload.get("next_counterfactual_id") or 1),
                max((item.id for item in counterfactual_futures), default=0) + 1,
            ),
            max_counterfactual_futures=max(
                1,
                min(int(payload.get("max_counterfactual_futures") or 4), 8),
            ),
            self_schema=self_schema[-max_memory:],
            next_self_schema_id=max(
                int(payload.get("next_self_schema_id") or 1),
                max((item.id for item in self_schema), default=0) + 1,
            ),
            max_self_schema_entries=max(
                4,
                min(int(payload.get("max_self_schema_entries") or 32), 128),
            ),
            self_schema_revisions=self_schema_revisions[-max_memory:],
            next_self_schema_revision_id=max(
                int(payload.get("next_self_schema_revision_id") or 1),
                max((item.id for item in self_schema_revisions), default=0) + 1,
            ),
            contextual_self_schema=contextual_self_schema[-max_memory:],
            next_contextual_self_schema_id=max(
                int(payload.get("next_contextual_self_schema_id") or 1),
                max(
                    (item.id for item in contextual_self_schema),
                    default=0,
                )
                + 1,
            ),
            self_schema_decompositions=self_schema_decompositions[-max_memory:],
            next_self_schema_decomposition_id=max(
                int(payload.get("next_self_schema_decomposition_id") or 1),
                max(
                    (item.id for item in self_schema_decompositions),
                    default=0,
                )
                + 1,
            ),
            context_transfer_boundaries=context_transfer_boundaries[-max_memory:],
            next_context_transfer_boundary_id=max(
                int(payload.get("next_context_transfer_boundary_id") or 1),
                max(
                    (item.id for item in context_transfer_boundaries),
                    default=0,
                )
                + 1,
            ),
            latent_context_hypotheses=latent_context_hypotheses[-max_memory:],
            next_latent_context_hypothesis_id=max(
                int(payload.get("next_latent_context_hypothesis_id") or 1),
                max(
                    (item.id for item in latent_context_hypotheses),
                    default=0,
                )
                + 1,
            ),
            latent_context_discoveries=latent_context_discoveries[-max_memory:],
            next_latent_context_discovery_id=max(
                int(payload.get("next_latent_context_discovery_id") or 1),
                max(
                    (item.id for item in latent_context_discoveries),
                    default=0,
                )
                + 1,
            ),
            context_causality_trials=context_causality_trials[-max_memory:],
            next_context_causality_trial_id=max(
                int(payload.get("next_context_causality_trial_id") or 1),
                max(
                    (item.id for item in context_causality_trials),
                    default=0,
                )
                + 1,
            ),
            context_causal_stability_assessments=(
                context_causal_stability_assessments[-max_memory:]
            ),
            next_context_causal_stability_assessment_id=max(
                int(
                    payload.get(
                        "next_context_causal_stability_assessment_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_causal_stability_assessments
                    ),
                    default=0,
                )
                + 1,
            ),
            context_causal_invariance_assessments=(
                context_causal_invariance_assessments[-max_memory:]
            ),
            next_context_causal_invariance_assessment_id=max(
                int(
                    payload.get(
                        "next_context_causal_invariance_assessment_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_causal_invariance_assessments
                    ),
                    default=0,
                )
                + 1,
            ),
            context_boundary_discovery_plans=(
                context_boundary_discovery_plans[-max_memory:]
            ),
            next_context_boundary_discovery_plan_id=max(
                int(
                    payload.get("next_context_boundary_discovery_plan_id")
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_boundary_discovery_plans
                    ),
                    default=0,
                )
                + 1,
            ),
            context_causal_validity_maps=(
                context_causal_validity_maps[-max_memory:]
            ),
            next_context_causal_validity_map_id=max(
                int(payload.get("next_context_causal_validity_map_id") or 1),
                max(
                    (item.id for item in context_causal_validity_maps),
                    default=0,
                )
                + 1,
            ),
            context_validity_decision_gates=(
                context_validity_decision_gates[-max_memory:]
            ),
            next_context_validity_decision_gate_id=max(
                int(
                    payload.get(
                        "next_context_validity_decision_gate_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_decision_gates
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_gate_outcomes=(
                context_validity_gate_outcomes[-max_memory:]
            ),
            next_context_validity_gate_outcome_id=max(
                int(payload.get("next_context_validity_gate_outcome_id") or 1),
                max(
                    (item.id for item in context_validity_gate_outcomes),
                    default=0,
                )
                + 1,
            ),
            context_validity_region_calibrations=(
                context_validity_region_calibrations[-max_memory:]
            ),
            next_context_validity_region_calibration_id=max(
                int(
                    payload.get(
                        "next_context_validity_region_calibration_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_region_calibrations
                    ),
                    default=0,
                )
                + 1,
            ),
            active_context_validity_map_ids=active_context_validity_map_ids,
            context_validity_map_selection_history=(
                context_validity_map_selection_history[-max_memory:]
            ),
            next_context_validity_map_selection_id=max(
                int(payload.get("next_context_validity_map_selection_id") or 1),
                max(
                    (
                        item.id
                        for item in context_validity_map_selection_history
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_degradation_watches=(
                context_validity_degradation_watches[-max_memory:]
            ),
            next_context_validity_degradation_watch_id=max(
                int(
                    payload.get(
                        "next_context_validity_degradation_watch_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_degradation_watches
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_recommendation_resolutions=(
                context_validity_recommendation_resolutions[-max_memory:]
            ),
            next_context_validity_recommendation_resolution_id=max(
                int(
                    payload.get(
                        "next_context_validity_recommendation_resolution_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_recommendation_resolutions
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_rollback_validations=(
                context_validity_rollback_validations[-max_memory:]
            ),
            next_context_validity_rollback_validation_id=max(
                int(
                    payload.get(
                        "next_context_validity_rollback_validation_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_rollback_validations
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_rollback_holdout_validations=(
                context_validity_rollback_holdout_validations[-max_memory:]
            ),
            next_context_validity_rollback_holdout_validation_id=max(
                int(
                    payload.get(
                        "next_context_validity_rollback_holdout_validation_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_rollback_holdout_validations
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_reactivation_drift_watches=(
                context_validity_reactivation_drift_watches[-max_memory:]
            ),
            next_context_validity_reactivation_drift_watch_id=max(
                int(
                    payload.get(
                        "next_context_validity_reactivation_drift_watch_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_reactivation_drift_watches
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_reactivation_drift_resolutions=(
                context_validity_reactivation_drift_resolutions[-max_memory:]
            ),
            next_context_validity_reactivation_drift_resolution_id=max(
                int(
                    payload.get(
                        "next_context_validity_reactivation_drift_resolution_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_reactivation_drift_resolutions
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_renewed_recovery_validations=(
                context_validity_renewed_recovery_validations[-max_memory:]
            ),
            next_context_validity_renewed_recovery_validation_id=max(
                int(
                    payload.get(
                        "next_context_validity_renewed_recovery_validation_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_renewed_recovery_validations
                    ),
                    default=0,
                )
                + 1,
            ),
            context_validity_renewed_holdout_validations=(
                context_validity_renewed_holdout_validations[-max_memory:]
            ),
            next_context_validity_renewed_holdout_validation_id=max(
                int(
                    payload.get(
                        "next_context_validity_renewed_holdout_validation_id"
                    )
                    or 1
                ),
                max(
                    (
                        item.id
                        for item in context_validity_renewed_holdout_validations
                    ),
                    default=0,
                )
                + 1,
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
            "active_global_workspace_items": len(
                [
                    item
                    for item in self.global_workspace_items
                    if item.status == "active"
                ]
            ),
            "global_workspace_cycle_count": len(self.global_workspace_cycles),
            "counterfactual_future_count": len(self.counterfactual_futures),
            "self_schema_active_count": len(self.active_self_schema()),
            "self_schema_total_count": len(self.self_schema),
            "self_schema_revision_count": len(self.self_schema_revisions),
            "contextual_self_schema_count": len(
                self.active_contextual_self_schema()
            ),
            "self_schema_decomposition_count": len(
                self.self_schema_decompositions
            ),
            "context_transfer_boundary_count": len(
                self.context_transfer_boundaries
            ),
            "accepted_context_transfer_count": len(
                self.active_context_transfer_boundaries()
            ),
            "latent_context_hypothesis_count": len(
                self.latent_context_hypotheses
            ),
            "latent_context_discovery_count": len(
                self.latent_context_discoveries
            ),
            "context_causality_trial_count": len(
                self.context_causality_trials
            ),
            "intervention_supported_context_count": len(
                [
                    item
                    for item in self.latent_context_hypotheses
                    if item.causal_status in {
                        "intervention_supported",
                        "replicated_reversible",
                        "environment_invariant",
                    }
                ]
            ),
            "context_causal_stability_assessment_count": len(
                self.context_causal_stability_assessments
            ),
            "replicated_reversible_context_count": len(
                [
                    item
                    for item in self.latent_context_hypotheses
                    if item.causal_status in {
                        "replicated_reversible",
                        "environment_invariant",
                    }
                ]
            ),
            "context_causal_invariance_assessment_count": len(
                self.context_causal_invariance_assessments
            ),
            "environment_invariant_context_count": len(
                [
                    item
                    for item in self.latent_context_hypotheses
                    if item.causal_status == "environment_invariant"
                ]
            ),
            "context_boundary_discovery_plan_count": len(
                self.context_boundary_discovery_plans
            ),
            "resolved_boundary_discovery_count": len(
                [
                    item
                    for item in self.context_boundary_discovery_plans
                    if item.status == "resolved"
                ]
            ),
            "context_causal_validity_map_count": len(
                self.context_causal_validity_maps
            ),
            "context_causal_validity_map_revision_count": len(
                [
                    item
                    for item in self.context_causal_validity_maps
                    if item.parent_map_id is not None
                ]
            ),
            "context_validity_decision_gate_count": len(
                self.context_validity_decision_gates
            ),
            "context_validity_abstention_count": len(
                [
                    item
                    for item in self.context_validity_decision_gates
                    if not item.causal_context_allowed
                ]
            ),
            "context_validity_gate_outcome_count": len(
                self.context_validity_gate_outcomes
            ),
            "context_validity_region_calibration_count": len(
                self.context_validity_region_calibrations
            ),
            "revoked_nearby_support_count": len(
                [
                    item
                    for item in self.context_validity_region_calibrations
                    if item.status == "nearby_support_revoked"
                ]
            ),
            "active_context_validity_map_count": len(
                self.active_context_validity_map_ids
            ),
            "context_validity_map_selection_count": len(
                self.context_validity_map_selection_history
            ),
            "context_validity_map_rollback_count": len(
                [
                    item
                    for item in self.context_validity_map_selection_history
                    if item.action == "rollback"
                ]
            ),
            "context_validity_degradation_watch_count": len(
                self.context_validity_degradation_watches
            ),
            "rollback_recommendation_count": len(
                [
                    item
                    for item in self.context_validity_degradation_watches
                    if item.status == "rollback_recommended"
                ]
            ),
            "rollback_recommendation_resolution_count": len(
                self.context_validity_recommendation_resolutions
            ),
            "accepted_rollback_recommendation_count": len(
                [
                    item
                    for item in self.context_validity_recommendation_resolutions
                    if item.decision == "accept"
                ]
            ),
            "rollback_validation_count": len(
                self.context_validity_rollback_validations
            ),
            "rollback_holdout_validation_count": len(
                self.context_validity_rollback_holdout_validations
            ),
            "rollback_reactivation_allowed_count": len(
                [
                    item
                    for item in self.context_validity_rollback_holdout_validations
                    if item.reactivation_allowed
                ]
            ),
            "post_reactivation_drift_watch_count": len(
                self.context_validity_reactivation_drift_watches
            ),
            "renewed_recovery_validation_count": len(
                self.context_validity_renewed_recovery_validations
            ),
            "renewed_holdout_validation_count": len(
                self.context_validity_renewed_holdout_validations
            ),
            "renewed_reactivation_allowed_count": len(
                [
                    item
                    for item in self.context_validity_renewed_holdout_validations
                    if item.reactivation_allowed
                ]
            ),
            "renewed_episode_count": max(
                (
                    item.episode_id
                    for item in self.context_validity_renewed_holdout_validations
                ),
                default=0,
            ),
            "renewed_degradation_count": len(
                [
                    item
                    for item in self.context_validity_reactivation_drift_watches
                    if item.status == "renewed_degradation_detected"
                ]
            ),
            "reactivation_drift_resolution_count": len(
                self.context_validity_reactivation_drift_resolutions
            ),
            "reactivation_drift_rollback_review_count": len(
                [
                    item
                    for item in self.context_validity_reactivation_drift_resolutions
                    if item.decision == "rollback_review"
                ]
            ),
            "observed_counterfactual_count": len(
                [
                    item
                    for item in self.counterfactual_futures
                    if item.status == "observed"
                ]
            ),
            "claims_phenomenal_consciousness": False,
        }
