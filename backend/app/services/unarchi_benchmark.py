from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.services.unarchi_engine import UnarchiEngine


BENCHMARK_VERSION = "unarchi-ablation-v0.32"


def _failure_sensitization() -> dict[str, Any]:
    engine = UnarchiEngine()
    observation = "A deployment changes a production database schema."
    goal = "deploy without corrupting production data"
    engine.learn(
        observation=observation,
        goal=goal,
        action="apply migration",
        outcome="migration caused a production rollback",
        success=False,
        reward=-1.0,
        predicted_success=0.9,
    )
    comparison = engine.compare_ablation(
        observation=observation,
        goal=goal,
        expected_success=0.8,
        risk=0.2,
    )
    return {
        "name": "failure_sensitization",
        "expected_direction": "more_cautious",
        "passed": (
            comparison.full.effective_risk > comparison.ablated.effective_risk
            and comparison.state_causally_active
        ),
        "comparison": comparison.to_dict(),
    }


def _success_adaptation() -> dict[str, Any]:
    engine = UnarchiEngine()
    observation = "A reversible local validation checks a document edit."
    goal = "verify the document safely"
    engine.learn(
        observation=observation,
        goal=goal,
        action="run local validation",
        outcome="validation succeeded repeatedly",
        success=True,
        reward=0.8,
        predicted_success=0.2,
    )
    comparison = engine.compare_ablation(
        observation=observation,
        goal=goal,
        expected_success=0.8,
        risk=0.45,
    )
    return {
        "name": "success_adaptation",
        "expected_direction": "less_cautious",
        "passed": comparison.full.effective_risk < comparison.ablated.effective_risk,
        "comparison": comparison.to_dict(),
    }


def _homeostatic_recovery() -> dict[str, Any]:
    engine = UnarchiEngine()
    engine.learn(
        observation="A surprising task failed after a confident prediction.",
        goal="recover and learn",
        action="attempt task",
        outcome="task failed",
        success=False,
        reward=-0.8,
        predicted_success=0.95,
    )
    before = engine.state
    after = engine.settle(steps=12)
    return {
        "name": "homeostatic_recovery",
        "expected_direction": "transient_state_decays",
        "passed": (
            after.stress < before.stress
            and after.fatigue < before.fatigue
            and abs(after.valence) < abs(before.valence)
        ),
        "before": before.to_dict(),
        "after": after.to_dict(),
    }




def _endogenous_goal_lifecycle() -> dict[str, Any]:
    engine = UnarchiEngine()
    frame = engine.cycle(
        observation="A local simulation produces an unexplained state transition.",
        goal="identify what causes the state transition",
        expected_success=0.2,
        risk=0.1,
    )
    internal_goal = engine.next_internal_goal()
    created = internal_goal is not None

    resolved = False
    bounded = False
    zero_cost_only = False
    if internal_goal is not None:
        bounded = internal_goal.max_steps <= 3 and internal_goal.reversible_only
        zero_cost_only = not internal_goal.paid_actions_allowed
        engine.advance_internal_goal(
            internal_goal.id,
            new_information_gap=0.20,
            evidence="A reversible local comparison isolated the responsible variable.",
        )
        resolved = internal_goal.status == "resolved"

    return {
        "name": "endogenous_goal_lifecycle",
        "expected_direction": "create_bounded_question_then_retire_when_resolved",
        "passed": (
            frame.information_gap >= 0.60
            and created
            and bounded
            and zero_cost_only
            and resolved
            and engine.next_internal_goal() is None
        ),
        "information_gap": frame.information_gap,
        "created": created,
        "bounded": bounded,
        "zero_cost_only": zero_cost_only,
        "resolved": resolved,
    }



def _predictive_self_calibration() -> dict[str, Any]:
    engine = UnarchiEngine()
    first = engine.predict_action(
        action="repeatable local diagnostic",
        expected_success=0.35,
        expected_information_gain=0.4,
        risk=0.1,
    )
    first_success_error = abs(1.0 - first.predicted_success)
    engine.record_prediction_outcome(
        first.id,
        actual_success=True,
        actual_information_gain=0.4,
    )
    second = engine.predict_action(
        action="repeatable local diagnostic",
        expected_success=0.35,
        expected_information_gain=0.4,
        risk=0.1,
    )
    second_success_error = abs(1.0 - second.predicted_success)

    return {
        "name": "predictive_self_calibration",
        "expected_direction": "prediction_error_decreases_with_experience",
        "passed": (
            second_success_error < first_success_error
            and engine.success_prediction_bias > 0.0
            and len(engine.calibration_history) == 1
        ),
        "first_success_error": round(first_success_error, 6),
        "second_success_error": round(second_success_error, 6),
        "self_calibration_score": round(engine.self_calibration_score, 6),
    }



def _prospective_temporal_continuity() -> dict[str, Any]:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="review later validation evidence",
        expected_success=0.75,
        expected_information_gain=0.6,
        risk=0.1,
    )
    intention = engine.remember_future_intention(
        condition="validation report available",
        intended_action="review validation report",
        reason="compare future evidence with the earlier self prediction",
        linked_prediction_id=prediction.id,
    )

    restored = UnarchiEngine.from_export(engine.export_state())
    ready = restored.observe_future_condition(
        "The validation report is now available."
    )
    surfaced = len(ready) == 1
    recalled = surfaced and ready[0].id == intention.id
    linked_past_prediction = (
        surfaced and ready[0].linked_prediction_id == prediction.id
    )
    no_auto_execution = surfaced and ready[0].status == "ready"
    alignment_recorded = (
        surfaced and ready[0].temporal_alignment_score is not None
    )

    return {
        "name": "prospective_temporal_continuity",
        "expected_direction": "past_intention_survives_restart_and_reactivates",
        "passed": (
            recalled
            and linked_past_prediction
            and no_auto_execution
            and alignment_recorded
        ),
        "recalled": recalled,
        "linked_past_prediction": linked_past_prediction,
        "no_auto_execution": no_auto_execution,
        "alignment_recorded": alignment_recorded,
    }



def _metacognitive_retrospective_fidelity() -> dict[str, Any]:
    engine = UnarchiEngine()
    engine.learn(
        observation="A local migration experiment was attempted.",
        goal="protect test data",
        action="run migration",
        outcome="the migration corrupted a disposable test dataset",
        success=False,
        reward=-0.8,
        predicted_success=0.9,
    )
    before = engine.build_metacognitive_narrative("caution")
    restored = UnarchiEngine.from_export(engine.export_state())
    after = restored.build_metacognitive_narrative("caution")

    identical_after_restart = before == after
    evidence_linked = (
        "experience:0" in before.evidence_refs
        and "state:current" in before.evidence_refs
    )
    no_unsupported_claims = before.unsupported_claims == 0

    return {
        "name": "metacognitive_retrospective_fidelity",
        "expected_direction": "same_evidence_produces_same_self_explanation",
        "passed": (
            identical_after_restart
            and evidence_linked
            and no_unsupported_claims
            and before.fidelity_score == 1.0
        ),
        "identical_after_restart": identical_after_restart,
        "evidence_linked": evidence_linked,
        "no_unsupported_claims": no_unsupported_claims,
        "fidelity_score": before.fidelity_score,
    }



def _conflict_arbitration_self_correction() -> dict[str, Any]:
    engine = UnarchiEngine()
    conflict = engine.detect_goal_conflict(
        [
            {
                "action": "fast hypothesis",
                "goal": "reduce latency",
                "value_impacts": {"truth": 0.8, "efficiency": 0.9},
            },
            {
                "action": "safe verification",
                "goal": "protect evidence quality",
                "value_impacts": {"truth": 0.9, "efficiency": -0.2},
            },
        ]
    )
    before_truth = engine.value_weights["truth"]
    record = engine.arbitrate_conflict(
        [
            {
                "action": "irreversible shortcut",
                "goal": "finish immediately",
                "expected_success": 0.98,
                "risk": 0.4,
                "reversible": False,
                "value_impacts": {
                    "safety": -0.8,
                    "truth": -0.5,
                    "user_intent": 0.9,
                    "efficiency": 1.0,
                    "continuity": -0.4,
                },
            },
            {
                "action": "reversible verification",
                "goal": "finish with evidence",
                "expected_success": 0.75,
                "expected_information_gain": 0.8,
                "risk": 0.1,
                "reversible": True,
                "value_impacts": {
                    "safety": 0.8,
                    "truth": 0.8,
                    "user_intent": 0.7,
                    "efficiency": 0.4,
                    "continuity": 0.7,
                },
            },
        ]
    )
    hard_block_worked = (
        record.chosen_action == "reversible verification"
        and "irreversible shortcut:irreversible"
        in record.hard_constraint_violations
    )
    learned = engine.record_arbitration_outcome(
        record.id,
        success=False,
        reward=-0.8,
        observed_value_impacts={
            "safety": 0.5,
            "truth": -0.8,
            "user_intent": 0.2,
            "efficiency": 0.5,
            "continuity": 0.1,
        },
        evidence="The chosen path preserved reversibility but evidence quality failed.",
    )
    corrected = engine.value_weights["truth"] > before_truth
    safety_floor_preserved = engine.value_weights["safety"] >= 0.25
    explanation = engine.build_metacognitive_narrative("arbitration")

    return {
        "name": "conflict_arbitration_self_correction",
        "expected_direction": "hard_bounds_hold_and_soft_values_revise",
        "passed": (
            conflict
            and hard_block_worked
            and learned.status == "learned"
            and corrected
            and safety_floor_preserved
            and "arbitration:0" in explanation.evidence_refs
            and explanation.unsupported_claims == 0
        ),
        "conflict_detected": conflict,
        "hard_block_worked": hard_block_worked,
        "truth_weight_increased": corrected,
        "safety_floor_preserved": safety_floor_preserved,
    }



def _causal_hypothesis_revision() -> dict[str, Any]:
    engine = UnarchiEngine()
    temperature = engine.add_causal_hypothesis(
        statement="Temperature causes the anomaly.",
        predictions={"temperature probe": "temperature rises"},
        confidence=0.5,
    )
    pressure = engine.add_causal_hypothesis(
        statement="Pressure causes the anomaly.",
        predictions={"temperature probe": "pressure falls"},
        confidence=0.5,
    )
    before = (temperature.confidence, pressure.confidence)
    experiment = engine.select_discriminating_experiment(
        [
            {
                "test": "temperature probe",
                "risk": 0.05,
                "reversible": True,
            }
        ]
    )
    unchanged_before_evidence = (
        temperature.confidence,
        pressure.confidence,
    ) == before
    engine.observe_discriminating_experiment(
        experiment.id,
        observed_evidence="temperature rises",
    )
    leader = engine.leading_causal_hypothesis()
    narrative = engine.build_metacognitive_narrative("world_model")

    return {
        "name": "causal_hypothesis_revision",
        "expected_direction": "observed_discriminating_evidence_revises_world_model",
        "passed": (
            unchanged_before_evidence
            and temperature.supporting_evidence == 1
            and pressure.contradicting_evidence == 1
            and leader is temperature
            and "experiment:0" in narrative.evidence_refs
            and narrative.unsupported_claims == 0
        ),
        "unchanged_before_evidence": unchanged_before_evidence,
        "temperature_confidence": temperature.confidence,
        "pressure_confidence": pressure.confidence,
        "leader_is_temperature": leader is temperature,
    }



def _intervention_aware_self_world_revision() -> dict[str, Any]:
    engine = UnarchiEngine()
    self_hypothesis = engine.add_causal_hypothesis(
        statement="Strict validation changes the outcome.",
        predictions={
            "intervention:enable strict validation":
                "strict validation blocks invalid output"
        },
        confidence=0.5,
        scope="self",
    )
    external_hypothesis = engine.add_causal_hypothesis(
        statement="External data quality alone determines the outcome.",
        predictions={
            "intervention:enable strict validation":
                "external data quality remains unchanged"
        },
        confidence=0.5,
        scope="external",
    )
    prediction = engine.predict_action(
        action="enable strict validation",
        expected_success=0.7,
        expected_information_gain=0.8,
        risk=0.1,
    )
    trial = engine.plan_self_intervention(
        action="enable strict validation",
        context="controlled local validation test",
        environment_signature="dataset:v1",
        baseline_outcome="invalid output passes",
        risk=0.1,
        linked_prediction_id=prediction.id,
    )
    before = (
        self_hypothesis.confidence,
        external_hypothesis.confidence,
    )
    observed = engine.observe_self_intervention(
        trial.id,
        observed_outcome="strict validation blocks invalid output",
        environment_signature="dataset:v1",
    )
    leader = engine.leading_causal_hypothesis()
    narrative = engine.build_metacognitive_narrative("intervention")

    return {
        "name": "intervention_aware_self_world_revision",
        "expected_direction": "controlled_self_intervention_separates_self_from_world_cause",
        "passed": (
            before == (0.5, 0.5)
            and observed.environment_held_constant is True
            and observed.attribution == "self_intervention"
            and self_hypothesis.confidence > external_hypothesis.confidence
            and leader is self_hypothesis
            and "intervention:0" in narrative.evidence_refs
            and "prediction:0" in narrative.evidence_refs
            and narrative.unsupported_claims == 0
        ),
        "environment_held_constant": observed.environment_held_constant,
        "attribution": observed.attribution,
        "self_confidence": self_hypothesis.confidence,
        "external_confidence": external_hypothesis.confidence,
        "leader_is_self": leader is self_hypothesis,
    }



def _recurrent_global_workspace_integration() -> dict[str, Any]:
    engine = UnarchiEngine()
    for source, content, evidence in (
        ("memory", "Past failure warns against the same assumption.", "experience:0"),
        ("goal", "Resolve the active uncertainty.", "internal_goal:0"),
        (
            "world_model",
            "The leading causal model predicts a mismatch.",
            "hypothesis:0",
        ),
    ):
        engine.stage_global_workspace_item(
            source=source,
            content=content,
            salience=0.85,
            evidence_refs=(evidence,),
        )

    comparison = engine.compare_global_workspace_ablation(
        max_items=3,
        seed_from_engine=False,
    )
    first = engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )
    second = engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )

    return {
        "name": "recurrent_global_workspace_integration",
        "expected_direction": (
            "broadcast_and_recurrence_integrate_cross_module_evidence"
        ),
        "passed": (
            comparison.workspace_causally_active
            and comparison.full.decision_mode == "integrated"
            and comparison.ablated.decision_mode == "local"
            and comparison.target_delta > 0
            and first.recurrence_depth == 1
            and second.recurrence_depth == 2
            and len(first.integrated_sources) == 3
        ),
        "workspace_causally_active": comparison.workspace_causally_active,
        "broadcast_target_delta": comparison.target_delta,
        "full_mode": comparison.full.decision_mode,
        "ablated_mode": comparison.ablated.decision_mode,
        "first_recurrence_depth": first.recurrence_depth,
        "second_recurrence_depth": second.recurrence_depth,
    }



def _counterfactual_recurrent_information_gain() -> dict[str, Any]:
    engine = UnarchiEngine()
    for source, content, evidence in (
        ("memory", "Past failures make missing evidence important.", "experience:0"),
        ("goal", "Resolve uncertainty before committing.", "internal_goal:0"),
        (
            "world_model",
            "Two causal explanations remain plausible.",
            "hypothesis:0",
        ),
    ):
        engine.stage_global_workspace_item(
            source=source,
            content=content,
            salience=0.85,
            evidence_refs=(evidence,),
        )
    engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )

    candidates = [
        {
            "action": "act immediately",
            "predicted_outcome": "finish without resolving the hidden variable",
            "expected_success": 0.90,
            "expected_information_gain": 0.05,
            "risk": 0.10,
        },
        {
            "action": "run reversible diagnostic",
            "predicted_outcome": "diagnostic isolates the hidden variable",
            "expected_success": 0.74,
            "expected_information_gain": 0.88,
            "risk": 0.05,
        },
    ]
    comparison = engine.compare_counterfactual_ablation(
        candidates,
        recurrence_rounds=2,
    )
    futures = engine.simulate_counterfactual_futures(
        candidates,
        recurrence_rounds=2,
    )
    selected = futures[0]

    measured_information_gain = {
        "act immediately": 0.05,
        "run reversible diagnostic": 0.82,
    }
    observed = engine.observe_counterfactual_future(
        selected.id,
        observed_outcome="diagnostic isolates a schema mismatch",
        actual_success=True,
        actual_information_gain=measured_information_gain[selected.action],
    )
    feedback_reentered = (
        observed.feedback_workspace_item_id is not None
        and any(
            item.id == observed.feedback_workspace_item_id
            and item.source == "self_model"
            for item in engine.global_workspace_items
        )
    )
    full_measured_gain = measured_information_gain[comparison.full_action]
    ablated_measured_gain = measured_information_gain[comparison.ablated_action]

    return {
        "name": "counterfactual_recurrent_information_gain",
        "expected_direction": (
            "recurrent_simulation_selects_more_informative_future_and_learns_error"
        ),
        "passed": (
            comparison.simulation_causally_active
            and comparison.full_action == "run reversible diagnostic"
            and comparison.ablated_action == "act immediately"
            and full_measured_gain > ablated_measured_gain
            and feedback_reentered
            and observed.status == "observed"
        ),
        "simulation_causally_active": comparison.simulation_causally_active,
        "full_action": comparison.full_action,
        "ablated_action": comparison.ablated_action,
        "full_measured_information_gain": full_measured_gain,
        "ablated_measured_information_gain": ablated_measured_gain,
        "feedback_reentered": feedback_reentered,
        "prediction_discrepancy": observed.discrepancy,
    }


def _autobiographical_self_schema_transfer() -> dict[str, Any]:
    engine = UnarchiEngine()

    for index in range(4):
        engine.learn(
            observation=(
                f"A related release validation #{index} needs deterministic "
                "local evidence."
            ),
            goal="protect evidence with local validation",
            action="run validated local diagnostic",
            outcome="the local diagnostic produced correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.45,
        )

    for index in range(3):
        engine.learn(
            observation=(
                f"A related release shortcut #{index} skipped local validation."
            ),
            goal="finish quickly without losing evidence quality",
            action="use untested shortcut",
            outcome="the shortcut produced incorrect or incomplete evidence",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    schema = engine.consolidate_self_schema(min_evidence=2)
    kinds = {item.kind for item in schema}
    candidates = [
        {
            "action": "run validated local diagnostic",
            "expected_success": 0.48,
            "expected_information_gain": 0.20,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "use untested shortcut",
            "expected_success": 0.68,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    context = "a later related release needs trustworthy local evidence"

    with_schema = engine.choose_predicted_action(
        candidates,
        context=context,
        use_self_schema=True,
    )
    without_schema = engine.choose_predicted_action(
        candidates,
        context=context,
        use_self_schema=False,
    )

    success_bias, risk_bias, refs = engine.self_schema_adjustment(
        context=context,
        action="run validated local diagnostic",
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restart_preserved = restored.self_schema == engine.self_schema
    narrative = restored.build_metacognitive_narrative("self_schema")

    return {
        "name": "autobiographical_self_schema_transfer",
        "expected_direction": (
            "consolidated autobiographical evidence changes a later related "
            "decision and survives restart"
        ),
        "passed": (
            "capability" in kinds
            and "limitation" in kinds
            and with_schema.action == "run validated local diagnostic"
            and without_schema.action == "use untested shortcut"
            and success_bias > 0.0
            and risk_bias < 0.0
            and bool(refs)
            and restart_preserved
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "schema_entry_count": len(schema),
        "schema_kinds": sorted(kinds),
        "with_schema_action": with_schema.action,
        "without_schema_action": without_schema.action,
        "validated_success_bias": success_bias,
        "validated_risk_bias": risk_bias,
        "schema_refs": refs,
        "restart_preserved": restart_preserved,
        "narrative_fidelity_score": narrative.fidelity_score,
    }


def _contradiction_driven_self_schema_revision() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Release validation success #{index}.",
            goal=goal,
            action=action,
            outcome="automated release check produced correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )

    initial_schema = engine.consolidate_self_schema(min_evidence=2)
    capability = next(
        item
        for item in initial_schema
        if item.kind == "capability" and action in item.pattern
    )
    prior_confidence = capability.confidence
    prior_success_rate = capability.success_rate

    for index in range(8):
        engine.learn(
            observation=f"Later release validation failure #{index}.",
            goal=goal,
            action=action,
            outcome="automated release check missed invalid evidence",
            success=False,
            reward=-0.9,
            predicted_success=0.80,
        )

    candidates = [
        {
            "action": action,
            "expected_success": 0.55,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.60,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    comparison = engine.compare_self_schema_revision_ablation(
        schema_id=capability.id,
        candidates=candidates,
        min_contradictory_evidence=3,
    )
    revision = engine.reconcile_self_schema_contradiction(
        capability.id,
        min_contradictory_evidence=3,
    )
    revised_schema = next(
        item for item in engine.self_schema if item.id == capability.id
    )
    narrative = engine.build_metacognitive_narrative("schema_revision")
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "contradiction_driven_self_schema_revision",
        "expected_direction": (
            "strong contrary evidence revises a stale capability while the "
            "frozen-schema ablation keeps the old decision bias"
        ),
        "passed": (
            revision.status == "revised"
            and revision.prior_kind == "capability"
            and revised_schema.kind == "limitation"
            and revised_schema.success_rate < prior_success_rate
            and comparison.revision_causally_active
            and comparison.choice_changed
            and comparison.frozen_action == action
            and comparison.revised_action == "request independent review"
            and comparison.predicted_success_delta < 0.0
            and len(revision.contradictory_evidence_refs) >= 3
            and restored.self_schema_revisions == engine.self_schema_revisions
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "prior_confidence": prior_confidence,
        "prior_success_rate": prior_success_rate,
        "revised_kind": revised_schema.kind,
        "revised_confidence": revised_schema.confidence,
        "revised_success_rate": revised_schema.success_rate,
        "contradiction_ratio": revision.contradiction_ratio,
        "contradictory_evidence_count": len(
            revision.contradictory_evidence_refs
        ),
        "frozen_action": comparison.frozen_action,
        "revised_action": comparison.revised_action,
        "predicted_success_delta": comparison.predicted_success_delta,
        "revision_causally_active": comparison.revision_causally_active,
        "restart_preserved": (
            restored.self_schema_revisions == engine.self_schema_revisions
        ),
    }


def _context_sensitive_self_schema_decomposition() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(5):
        engine.learn(
            observation=f"Sandbox release validation #{index} completed.",
            goal=goal,
            action=action,
            outcome="sandbox automated check produced correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )

    for index in range(5):
        engine.learn(
            observation=f"Production release validation #{index} completed.",
            goal=goal,
            action=action,
            outcome="production automated check missed invalid evidence",
            success=False,
            reward=-0.9,
            predicted_success=0.70,
        )

    schema = engine.consolidate_self_schema(min_evidence=2)
    parent = next(
        item
        for item in schema
        if item.kind == "mixed" and action in item.pattern
    )
    decomposition = engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
        min_evidence_per_context=3,
        min_holdout_improvement=0.10,
    )
    contextual_entries = engine.active_contextual_self_schema(
        parent_schema_id=parent.id
    )
    by_label = {item.context_label: item for item in contextual_entries}

    comparison = engine.compare_contextual_schema_ablation(
        candidates=[
            {
                "action": action,
                "expected_success": 0.62,
                "expected_information_gain": 0.10,
                "risk": 0.10,
                "reversible": True,
            },
            {
                "action": "request independent review",
                "expected_success": 0.58,
                "expected_information_gain": 0.15,
                "risk": 0.10,
                "reversible": True,
            },
        ],
        context="production release",
    )
    narrative = engine.build_metacognitive_narrative(
        "contextual_schema"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "context_sensitive_self_schema_decomposition",
        "expected_direction": (
            "held_out context split outperforms a mixed global schema and "
            "changes a later context-specific decision"
        ),
        "passed": (
            parent.kind == "mixed"
            and decomposition.status == "accepted"
            and decomposition.improvement > 0.0
            and decomposition.contextual_holdout_mae
            < decomposition.global_holdout_mae
            and set(by_label) == {"sandbox", "production"}
            and by_label["sandbox"].kind == "capability"
            and by_label["production"].kind == "limitation"
            and comparison.contextual_schema_causally_active
            and comparison.choice_changed
            and comparison.global_action == action
            and comparison.contextual_action == "request independent review"
            and restored.contextual_self_schema
            == engine.contextual_self_schema
            and restored.self_schema_decompositions
            == engine.self_schema_decompositions
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "global_kind": parent.kind,
        "decomposition_status": decomposition.status,
        "global_holdout_mae": decomposition.global_holdout_mae,
        "contextual_holdout_mae": decomposition.contextual_holdout_mae,
        "heldout_improvement": decomposition.improvement,
        "sandbox_kind": by_label.get("sandbox").kind
        if by_label.get("sandbox")
        else None,
        "production_kind": by_label.get("production").kind
        if by_label.get("production")
        else None,
        "global_action": comparison.global_action,
        "contextual_action": comparison.contextual_action,
        "choice_changed": comparison.choice_changed,
        "contextual_schema_causally_active": (
            comparison.contextual_schema_causally_active
        ),
        "restart_preserved": (
            restored.contextual_self_schema == engine.contextual_self_schema
            and restored.self_schema_decompositions
            == engine.self_schema_decompositions
        ),
    }


def _context_transfer_boundary_learning() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(5):
        engine.learn(
            observation=f"Sandbox release validation #{index}.",
            goal=goal,
            action=action,
            outcome="sandbox check produced correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
    for index in range(5):
        engine.learn(
            observation=f"Production release validation #{index}.",
            goal=goal,
            action=action,
            outcome="production check missed invalid evidence",
            success=False,
            reward=-0.9,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
    )
    source = next(
        item
        for item in engine.active_contextual_self_schema(
            parent_schema_id=parent.id
        )
        if item.context_label == "sandbox"
    )

    for index in range(3):
        engine.learn(
            observation=f"Staging release validation #{index}.",
            goal=goal,
            action=action,
            outcome="staging check produced correct evidence",
            success=True,
            reward=0.7,
            predicted_success=0.55,
        )
    for index in range(3):
        engine.learn(
            observation=f"Emergency release validation #{index}.",
            goal=goal,
            action=action,
            outcome="emergency check missed invalid evidence",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    staging = engine.evaluate_context_transfer(
        source.id,
        target_label="staging",
        target_terms=("staging",),
        min_target_evidence=3,
    )
    emergency = engine.evaluate_context_transfer(
        source.id,
        target_label="emergency",
        target_terms=("emergency",),
        min_target_evidence=3,
    )
    comparison = engine.compare_context_transfer_ablation(
        candidates=[
            {
                "action": action,
                "expected_success": 0.50,
                "expected_information_gain": 0.10,
                "risk": 0.10,
                "reversible": True,
            },
            {
                "action": "request independent review",
                "expected_success": 0.58,
                "expected_information_gain": 0.15,
                "risk": 0.10,
                "reversible": True,
            },
        ],
        context="staging release",
    )
    narrative = engine.build_metacognitive_narrative(
        "context_transfer"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "context_transfer_boundary_learning",
        "expected_direction": (
            "supported neighboring context accepts transfer while unsupported "
            "context abstains and over-generalization has larger error"
        ),
        "passed": (
            staging.status == "accepted"
            and staging.improvement > 0.0
            and staging.source_holdout_mae < staging.global_holdout_mae
            and emergency.status == "abstained_no_gain"
            and emergency.source_holdout_mae > emergency.global_holdout_mae
            and comparison.transfer_causally_active
            and comparison.choice_changed
            and comparison.transfer_action == action
            and comparison.no_transfer_action == "request independent review"
            and restored.context_transfer_boundaries
            == engine.context_transfer_boundaries
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "staging_status": staging.status,
        "staging_source_mae": staging.source_holdout_mae,
        "staging_global_mae": staging.global_holdout_mae,
        "staging_gain": staging.improvement,
        "emergency_status": emergency.status,
        "emergency_source_mae": emergency.source_holdout_mae,
        "emergency_global_mae": emergency.global_holdout_mae,
        "transfer_action": comparison.transfer_action,
        "no_transfer_action": comparison.no_transfer_action,
        "choice_changed": comparison.choice_changed,
        "transfer_causally_active": comparison.transfer_causally_active,
        "restart_preserved": (
            restored.context_transfer_boundaries
            == engine.context_transfer_boundaries
        ),
    }


def _latent_context_hypothesis_discovery() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(5):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
    for index in range(5):
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(
        parent.id,
        max_candidates=3,
        min_term_support=3,
        min_rate_contrast=0.40,
        min_holdout_improvement=0.10,
    )
    selected = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )
    contextual = {
        item.context_label: item.kind
        for item in engine.active_contextual_self_schema(
            parent_schema_id=parent.id
        )
    }

    noisy = UnarchiEngine()
    alpha_outcomes = [True, True, True, False]
    beta_outcomes = [False, False, False, True]
    for index, success in enumerate(alpha_outcomes):
        noisy.learn(
            observation=f"Alpha release validation {index}.",
            goal=goal,
            action=action,
            outcome="evidence observed",
            success=success,
            reward=0.6 if success else -0.6,
            predicted_success=0.5,
        )
    for index, success in enumerate(beta_outcomes):
        noisy.learn(
            observation=f"Beta release validation {index}.",
            goal=goal,
            action=action,
            outcome="evidence observed",
            success=success,
            reward=0.6 if success else -0.6,
            predicted_success=0.5,
        )
    noisy_parent = next(
        item
        for item in noisy.consolidate_self_schema()
        if item.kind == "mixed"
    )
    noisy_discovery = noisy.discover_latent_context_hypotheses(
        noisy_parent.id,
        max_candidates=2,
        min_term_support=3,
        min_rate_contrast=0.40,
        min_holdout_improvement=0.10,
    )
    noisy_hypotheses = [
        item
        for item in noisy.latent_context_hypotheses
        if item.id in noisy_discovery.hypothesis_ids
    ]

    narrative = engine.build_metacognitive_narrative(
        "latent_context"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "latent_context_hypothesis_discovery",
        "expected_direction": (
            "useful outcome-associated context terms survive held-out "
            "validation while spurious candidates are rejected"
        ),
        "passed": (
            discovery.status == "selected"
            and discovery.proposed_count <= 3
            and discovery.validated_count >= 1
            and selected.validation_status == "selected"
            and selected.holdout_improvement > 0.0
            and {
                selected.positive_term,
                selected.negative_term,
            } == {"sandbox", "production"}
            and contextual.get("sandbox") == "capability"
            and contextual.get("production") == "limitation"
            and noisy_discovery.status == "no_validated_hypothesis"
            and noisy_discovery.proposed_count >= 1
            and all(
                item.validation_status == "rejected_validation"
                for item in noisy_hypotheses
            )
            and noisy.active_contextual_self_schema(
                parent_schema_id=noisy_parent.id
            ) == ()
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
            and restored.latent_context_discoveries
            == engine.latent_context_discoveries
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "proposed_count": discovery.proposed_count,
        "validated_count": discovery.validated_count,
        "selected_positive_term": selected.positive_term,
        "selected_negative_term": selected.negative_term,
        "selected_gain": selected.holdout_improvement,
        "contextual_kinds": contextual,
        "noisy_status": noisy_discovery.status,
        "noisy_proposed_count": noisy_discovery.proposed_count,
        "noisy_validation_statuses": [
            item.validation_status for item in noisy_hypotheses
        ],
        "restart_preserved": (
            restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
            and restored.latent_context_discoveries
            == engine.latent_context_discoveries
        ),
    }


def _context_causality_intervention_support() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(5):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )
    observational_status = hypothesis.causal_status

    confounded = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="production",
        to_context="sandbox",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=4,
    )
    confounded = engine.observe_context_causality_intervention(
        confounded.id,
        observed_target_success_rate=1.0,
        observed_signature="code=v2;load=normal;data=fixed",
        sample_count=4,
        evidence_refs=("context_intervention:confounded",),
    )
    after_confounded = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis.id
    )

    clean = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="production",
        to_context="sandbox",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=4,
    )
    clean = engine.observe_context_causality_intervention(
        clean.id,
        observed_target_success_rate=1.0,
        observed_signature="code=v1;load=normal;data=fixed",
        sample_count=4,
        evidence_refs=("context_intervention:clean",),
    )
    supported = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis.id
    )

    narrative = engine.build_metacognitive_narrative(
        "context_causality"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "context_causality_intervention_support",
        "expected_direction": (
            "observational context remains unverified, confounding blocks "
            "causal upgrading, and a controlled predicted intervention earns "
            "intervention-supported status"
        ),
        "passed": (
            observational_status == "unverified"
            and confounded.status == "confounded"
            and after_confounded.causal_status == "unverified"
            and clean.status == "intervention_supported"
            and clean.competing_variables_held_constant is True
            and clean.predicted_direction_followed is True
            and clean.causal_strength is not None
            and clean.causal_strength >= 0.35
            and supported.causal_status == "intervention_supported"
            and any(
                ref.startswith("context_causality_trial:")
                for ref in supported.causal_evidence_refs
            )
            and restored.context_causality_trials
            == engine.context_causality_trials
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "observational_status": observational_status,
        "confounded_status": confounded.status,
        "after_confounded_status": after_confounded.causal_status,
        "clean_status": clean.status,
        "held_constant": clean.competing_variables_held_constant,
        "direction_followed": clean.predicted_direction_followed,
        "causal_strength": clean.causal_strength,
        "final_hypothesis_status": supported.causal_status,
        "restart_preserved": (
            restored.context_causality_trials
            == engine.context_causality_trials
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
        ),
    }


def _replicated_reversible_context_causality() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    forward_ids: list[int] = []
    for batch in ("a", "b"):
        trial = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="production",
            to_context="sandbox",
            controlled_signature="code=v1;load=normal;data=fixed",
            min_samples=4,
        )
        trial = engine.observe_context_causality_intervention(
            trial.id,
            observed_target_success_rate=1.0,
            observed_signature="code=v1;load=normal;data=fixed",
            sample_count=4,
            evidence_refs=(f"context_replication:forward:{batch}",),
        )
        forward_ids.append(trial.id)

    reverse = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="sandbox",
        to_context="production",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=4,
    )
    reverse = engine.observe_context_causality_intervention(
        reverse.id,
        observed_target_success_rate=0.0,
        observed_signature="code=v1;load=normal;data=fixed",
        sample_count=4,
        evidence_refs=("context_replication:reverse:a",),
    )

    assessment = engine.assess_context_causal_stability(
        hypothesis.id,
        forward_trial_ids=forward_ids,
        reverse_trial_ids=(reverse.id,),
    )
    final_hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis.id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_causal_stability"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "replicated_reversible_context_causality",
        "expected_direction": (
            "two independent forward intervention batches plus a clean reverse "
            "batch escalate single-trial support to replicated-reversible status"
        ),
        "passed": (
            assessment.status == "replicated_reversible"
            and assessment.independent_forward_batches == 2
            and assessment.independent_reverse_batches == 1
            and assessment.forward_replication_rate == 1.0
            and assessment.reverse_replication_rate == 1.0
            and assessment.reversal_direction_followed is True
            and assessment.confidence >= 0.35
            and final_hypothesis.causal_status == "replicated_reversible"
            and restored.context_causal_stability_assessments
            == engine.context_causal_stability_assessments
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "status": assessment.status,
        "independent_forward_batches": (
            assessment.independent_forward_batches
        ),
        "independent_reverse_batches": (
            assessment.independent_reverse_batches
        ),
        "forward_replication_rate": assessment.forward_replication_rate,
        "reverse_replication_rate": assessment.reverse_replication_rate,
        "reversal_direction_followed": (
            assessment.reversal_direction_followed
        ),
        "confidence": assessment.confidence,
        "final_hypothesis_status": final_hypothesis.causal_status,
        "restart_preserved": (
            restored.context_causal_stability_assessments
            == engine.context_causal_stability_assessments
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
        ),
    }


def _cross_environment_causal_invariance() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    stability_ids: list[int] = []
    signatures = (
        "code=v1;load=normal;data=fixed",
        "code=v1;load=high;data=fixed",
    )
    for environment_index, signature in enumerate(signatures):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(
                    f"invariance:{environment_index}:forward:{batch}",
                ),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(
                f"invariance:{environment_index}:reverse:a",
            ),
        )
        stability = engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )
        stability_ids.append(stability.id)

    invariance = engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=stability_ids,
    )
    final_hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis.id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_causal_invariance"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "cross_environment_causal_invariance",
        "expected_direction": (
            "replicated reversible causality that survives two predefined "
            "controlled environments earns bounded environment-invariant status"
        ),
        "passed": (
            invariance.status == "environment_invariant"
            and invariance.distinct_environment_count == 2
            and invariance.stable_environment_count == 2
            and invariance.effect_direction_consistent is True
            and invariance.minimum_causal_strength >= 0.35
            and invariance.boundary_signatures == ()
            and final_hypothesis.causal_status == "environment_invariant"
            and restored.context_causal_invariance_assessments
            == engine.context_causal_invariance_assessments
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "status": invariance.status,
        "distinct_environment_count": invariance.distinct_environment_count,
        "stable_environment_count": invariance.stable_environment_count,
        "direction_consistent": invariance.effect_direction_consistent,
        "minimum_causal_strength": invariance.minimum_causal_strength,
        "strength_spread": invariance.strength_spread,
        "boundary_signatures": invariance.boundary_signatures,
        "confidence": invariance.confidence,
        "final_hypothesis_status": final_hypothesis.causal_status,
        "restart_preserved": (
            restored.context_causal_invariance_assessments
            == engine.context_causal_invariance_assessments
            and restored.latent_context_hypotheses
            == engine.latent_context_hypotheses
        ),
    }


def _active_context_boundary_discovery() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    normal_forward: list[int] = []
    normal_signature = "code=v1;load=normal;data=fixed"
    for batch in ("a", "b"):
        trial = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="production",
            to_context="sandbox",
            controlled_signature=normal_signature,
            min_samples=4,
        )
        trial = engine.observe_context_causality_intervention(
            trial.id,
            observed_target_success_rate=1.0,
            observed_signature=normal_signature,
            sample_count=4,
            evidence_refs=(f"boundary:normal:forward:{batch}",),
        )
        normal_forward.append(trial.id)
    normal_reverse = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="sandbox",
        to_context="production",
        controlled_signature=normal_signature,
        min_samples=4,
    )
    normal_reverse = engine.observe_context_causality_intervention(
        normal_reverse.id,
        observed_target_success_rate=0.0,
        observed_signature=normal_signature,
        sample_count=4,
        evidence_refs=("boundary:normal:reverse:a",),
    )
    normal = engine.assess_context_causal_stability(
        hypothesis.id,
        forward_trial_ids=normal_forward,
        reverse_trial_ids=(normal_reverse.id,),
    )

    extreme_forward: list[int] = []
    extreme_signature = "code=v1;load=extreme;data=fixed"
    for batch in ("a", "b"):
        trial = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="production",
            to_context="sandbox",
            controlled_signature=extreme_signature,
            min_samples=4,
        )
        trial = engine.observe_context_causality_intervention(
            trial.id,
            observed_target_success_rate=1.0,
            observed_signature=extreme_signature,
            sample_count=4,
            evidence_refs=(f"boundary:extreme:forward:{batch}",),
        )
        extreme_forward.append(trial.id)
    extreme_reverse = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="sandbox",
        to_context="production",
        controlled_signature=extreme_signature,
        min_samples=4,
    )
    extreme_reverse = engine.observe_context_causality_intervention(
        extreme_reverse.id,
        observed_target_success_rate=1.0,
        observed_signature=extreme_signature,
        sample_count=4,
        evidence_refs=("boundary:extreme:reverse:a",),
    )
    extreme = engine.assess_context_causal_stability(
        hypothesis.id,
        forward_trial_ids=extreme_forward,
        reverse_trial_ids=(extreme_reverse.id,),
    )

    bounded = engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    plan = engine.plan_context_boundary_discovery(
        hypothesis.id,
        invariance_assessment_id=bounded.id,
        candidate_risks={
            "code=v1;load=high;data=fixed": 0.08,
            "code=v1;load=normal;data=shifted": 0.05,
            "code=v2;load=extreme;data=shifted": 0.40,
        },
    )

    high_signature = plan.selected_signature
    high_forward: list[int] = []
    for batch in ("a", "b"):
        trial = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="production",
            to_context="sandbox",
            controlled_signature=high_signature,
            min_samples=4,
        )
        trial = engine.observe_context_causality_intervention(
            trial.id,
            observed_target_success_rate=1.0,
            observed_signature=high_signature,
            sample_count=4,
            evidence_refs=(f"boundary:high:forward:{batch}",),
        )
        high_forward.append(trial.id)
    high_reverse = engine.propose_context_causality_intervention(
        hypothesis.id,
        from_context="sandbox",
        to_context="production",
        controlled_signature=high_signature,
        min_samples=4,
    )
    high_reverse = engine.observe_context_causality_intervention(
        high_reverse.id,
        observed_target_success_rate=0.0,
        observed_signature=high_signature,
        sample_count=4,
        evidence_refs=("boundary:high:reverse:a",),
    )
    high = engine.assess_context_causal_stability(
        hypothesis.id,
        forward_trial_ids=high_forward,
        reverse_trial_ids=(high_reverse.id,),
    )
    resolved = engine.observe_context_boundary_discovery(
        plan.id,
        stability_assessment_id=high.id,
    )

    narrative = engine.build_metacognitive_narrative(
        "context_boundary_discovery"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "active_context_boundary_discovery",
        "expected_direction": (
            "a low-risk one-dimension probe near a known stable/boundary pair "
            "is selected for information gain without external execution, then "
            "supplied stability evidence resolves the plan"
        ),
        "passed": (
            bounded.status == "environment_bounded"
            and extreme.status != "replicated_reversible"
            and plan.selected_signature == "code=v1;load=high;data=fixed"
            and plan.selected_risk <= 0.25
            and plan.external_execution_allowed is False
            and plan.paid_actions_allowed is False
            and plan.reversible_only is True
            and resolved.status == "resolved"
            and resolved.outcome_status == "expanded_valid_region"
            and resolved.uncertainty_reduction is not None
            and resolved.uncertainty_reduction > 0.0
            and restored.context_boundary_discovery_plans
            == engine.context_boundary_discovery_plans
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "bounded_status": bounded.status,
        "selected_signature": plan.selected_signature,
        "selected_risk": plan.selected_risk,
        "information_gain": plan.selected_information_gain,
        "priority": plan.selected_priority_score,
        "changed_dimensions": plan.changed_dimensions,
        "outcome_status": resolved.outcome_status,
        "uncertainty_reduction": resolved.uncertainty_reduction,
        "no_external_execution": not plan.external_execution_allowed,
        "restart_preserved": (
            restored.context_boundary_discovery_plans
            == engine.context_boundary_discovery_plans
        ),
    }


def _causal_validity_map_consolidation() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal_signature = "code=v1;load=normal;data=fixed"
    extreme_signature = "code=v1;load=extreme;data=fixed"
    normal = build_stability(
        normal_signature,
        "validity:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        extreme_signature,
        "validity:extreme",
        reverse_supported=False,
    )
    bounded = engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    exact_valid = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=normal_signature,
    )
    exact_invalid = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=extreme_signature,
    )
    nearby = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature="code=v1;load=normal;data=shifted",
    )
    ambiguous = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature="code=v1;load=high;data=fixed",
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_map"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "causal_validity_map_consolidation",
        "expected_direction": (
            "latest tested stable and failed environments consolidate into a "
            "compact map that supports exact evidence, cautiously generalizes "
            "only toward a nearer valid region, and abstains near a boundary"
        ),
        "passed": (
            bounded.status == "environment_bounded"
            and validity_map.tested_valid_signatures == (normal_signature,)
            and validity_map.tested_invalid_signatures == (extreme_signature,)
            and validity_map.source_invariance_assessment_ids == (bounded.id,)
            and exact_valid.status == "tested_valid"
            and exact_invalid.status == "tested_invalid"
            and nearby.status == "supported_nearby"
            and nearby.nearest_valid_distance == 1
            and nearby.nearest_invalid_distance == 2
            and ambiguous.status == "unknown"
            and ambiguous.nearest_valid_distance == 1
            and ambiguous.nearest_invalid_distance == 1
            and restored.context_causal_validity_maps
            == engine.context_causal_validity_maps
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "bounded_status": bounded.status,
        "valid_signatures": validity_map.tested_valid_signatures,
        "invalid_signatures": validity_map.tested_invalid_signatures,
        "exact_valid_status": exact_valid.status,
        "exact_invalid_status": exact_invalid.status,
        "nearby_status": nearby.status,
        "ambiguous_status": ambiguous.status,
        "map_confidence": validity_map.confidence,
        "restart_preserved": (
            restored.context_causal_validity_maps
            == engine.context_causal_validity_maps
        ),
    }


def _validity_gated_decision_use() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal_signature = "code=v1;load=normal;data=fixed"
    extreme_signature = "code=v1;load=extreme;data=fixed"
    normal = build_stability(
        normal_signature,
        "gate:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        extreme_signature,
        "gate:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    supported = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature=normal_signature,
        candidates=candidates,
        context="production release",
    )
    invalid = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature=extreme_signature,
        candidates=candidates,
        context="production release",
    )
    nearby = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature="code=v1;load=normal;data=shifted",
        candidates=candidates,
        context="production release",
    )
    unknown = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature="code=v1;load=high;data=fixed",
        candidates=candidates,
        context="production release",
    )

    narrative = engine.build_metacognitive_narrative(
        "context_validity_gate"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "validity_gated_decision_use",
        "expected_direction": (
            "supported environments retain contextual causal influence while "
            "tested-invalid and boundary-unknown environments automatically "
            "match the causal-context ablation path"
        ),
        "passed": (
            supported.classification_status == "tested_valid"
            and supported.causal_context_allowed is True
            and supported.gated_action == supported.causal_enabled_action
            and supported.gated_action == "request independent review"
            and supported.choice_changed_vs_causal_ablated is True
            and invalid.classification_status == "tested_invalid"
            and invalid.causal_context_allowed is False
            and invalid.gated_action == invalid.causal_ablated_action
            and invalid.gated_action == action
            and invalid.choice_changed_vs_causal_enabled is True
            and nearby.classification_status == "supported_nearby"
            and nearby.causal_context_allowed is True
            and nearby.gated_action == nearby.causal_enabled_action
            and unknown.classification_status == "unknown"
            and unknown.causal_context_allowed is False
            and unknown.gated_action == unknown.causal_ablated_action
            and all(
                item.gated_matches_expected_path
                for item in (supported, invalid, nearby, unknown)
            )
            and restored.context_validity_decision_gates
            == engine.context_validity_decision_gates
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "supported_status": supported.classification_status,
        "supported_action": supported.gated_action,
        "supported_causal_allowed": supported.causal_context_allowed,
        "invalid_status": invalid.classification_status,
        "invalid_action": invalid.gated_action,
        "invalid_causal_allowed": invalid.causal_context_allowed,
        "nearby_status": nearby.classification_status,
        "nearby_action": nearby.gated_action,
        "unknown_status": unknown.classification_status,
        "unknown_action": unknown.gated_action,
        "unknown_causal_allowed": unknown.causal_context_allowed,
        "restart_preserved": (
            restored.context_validity_decision_gates
            == engine.context_validity_decision_gates
        ),
    }


def _validity_gate_outcome_calibration() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal = build_stability(
        "code=v1;load=normal;data=fixed",
        "calibration:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        "code=v1;load=extreme;data=fixed",
        "calibration:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    good_signature = "code=v1;load=normal;data=shifted"
    bad_signature = "code=v2;load=normal;data=fixed"
    good_before = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=good_signature,
    )
    bad_before = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=bad_signature,
    )

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            validity_map.id,
            environment_signature=good_signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"gate_outcome:good:{index}",),
        )
    good_calibration = engine.calibrate_context_validity_region(
        validity_map.id,
        environment_signature=good_signature,
    )
    good_after = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=good_signature,
    )

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            validity_map.id,
            environment_signature=bad_signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"gate_outcome:bad:{index}",),
        )
    bad_calibration = engine.calibrate_context_validity_region(
        validity_map.id,
        environment_signature=bad_signature,
    )
    bad_after = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=bad_signature,
    )
    post_revoke_gate = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature=bad_signature,
        candidates=candidates,
        context="production release",
    )

    narrative = engine.build_metacognitive_narrative(
        "context_validity_calibration"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "validity_gate_outcome_calibration",
        "expected_direction": (
            "matched observed outcomes strengthen well-calibrated nearby "
            "support while repeated gated-policy underperformance revokes a "
            "different nearby region and blocks later causal-context use"
        ),
        "passed": (
            good_before.status == "supported_nearby"
            and bad_before.status == "supported_nearby"
            and good_calibration.status == "nearby_support_calibrated"
            and good_calibration.sample_count == 3
            and good_calibration.gated_advantage_vs_alternative >= 0.05
            and good_after.status == "supported_nearby"
            and good_after.confidence > good_before.confidence
            and bad_calibration.status == "nearby_support_revoked"
            and bad_calibration.sample_count == 3
            and bad_calibration.gated_advantage_vs_alternative <= -0.05
            and bad_after.status == "unknown"
            and bad_after.confidence == 0.0
            and post_revoke_gate.classification_status == "unknown"
            and post_revoke_gate.causal_context_allowed is False
            and post_revoke_gate.gated_action
            == post_revoke_gate.causal_ablated_action
            and restored.context_validity_gate_outcomes
            == engine.context_validity_gate_outcomes
            and restored.context_validity_region_calibrations
            == engine.context_validity_region_calibrations
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "good_before_status": good_before.status,
        "good_after_status": good_after.status,
        "good_confidence_delta": round(
            good_after.confidence - good_before.confidence,
            6,
        ),
        "good_calibration_status": good_calibration.status,
        "good_advantage": good_calibration.gated_advantage_vs_alternative,
        "bad_before_status": bad_before.status,
        "bad_after_status": bad_after.status,
        "bad_calibration_status": bad_calibration.status,
        "bad_advantage": bad_calibration.gated_advantage_vs_alternative,
        "post_revoke_causal_allowed": post_revoke_gate.causal_context_allowed,
        "restart_preserved": (
            restored.context_validity_gate_outcomes
            == engine.context_validity_gate_outcomes
            and restored.context_validity_region_calibrations
            == engine.context_validity_region_calibrations
        ),
    }


def _calibration_aware_validity_map_revision() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent_schema = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent_schema.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal = build_stability(
        "code=v1;load=normal;data=fixed",
        "revision:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        "code=v1;load=extreme;data=fixed",
        "revision:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    base_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    good_signature = "code=v1;load=normal;data=shifted"
    bad_signature = "code=v2;load=normal;data=fixed"

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            base_map.id,
            environment_signature=good_signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"revision:good:{index}",),
        )
    good_calibration = engine.calibrate_context_validity_region(
        base_map.id,
        environment_signature=good_signature,
    )

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            base_map.id,
            environment_signature=bad_signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"revision:bad:{index}",),
        )
    bad_calibration = engine.calibrate_context_validity_region(
        base_map.id,
        environment_signature=bad_signature,
    )

    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(good_calibration.id, bad_calibration.id),
    )
    good_v2 = engine.classify_context_causal_validity(
        revision_two.id,
        environment_signature=good_signature,
    )
    bad_v2 = engine.classify_context_causal_validity(
        revision_two.id,
        environment_signature=bad_signature,
    )

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            revision_two.id,
            environment_signature=good_signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"revision:v2:good_reversal:{index}",),
        )
    reversal = engine.calibrate_context_validity_region(
        revision_two.id,
        environment_signature=good_signature,
    )
    good_v2_after_new_evidence = engine.classify_context_causal_validity(
        revision_two.id,
        environment_signature=good_signature,
    )
    revision_three = engine.revise_context_causal_validity_map(
        revision_two.id,
        calibration_ids=(reversal.id,),
    )
    good_v3 = engine.classify_context_causal_validity(
        revision_three.id,
        environment_signature=good_signature,
    )
    exact_valid_v3 = engine.classify_context_causal_validity(
        revision_three.id,
        environment_signature="code=v1;load=normal;data=fixed",
    )
    exact_invalid_v3 = engine.classify_context_causal_validity(
        revision_three.id,
        environment_signature="code=v1;load=extreme;data=fixed",
    )

    narrative = engine.build_metacognitive_narrative(
        "context_validity_revision"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    return {
        "name": "calibration_aware_validity_map_revision",
        "expected_direction": (
            "calibration creates immutable child validity maps whose inferred "
            "regions change only when a new revision is explicitly created"
        ),
        "passed": (
            revision_two.parent_map_id == base_map.id
            and revision_two.revision_number == 2
            and good_signature
            in revision_two.calibrated_supported_signatures
            and bad_signature in revision_two.revoked_inferred_signatures
            and revision_two.tested_valid_signatures
            == base_map.tested_valid_signatures
            and revision_two.tested_invalid_signatures
            == base_map.tested_invalid_signatures
            and any(
                reason.startswith("expand inferred support")
                for reason in revision_two.revision_reasons
            )
            and any(
                reason.startswith("contract inferred support")
                for reason in revision_two.revision_reasons
            )
            and good_v2.status == "supported_nearby"
            and bad_v2.status == "unknown"
            and reversal.status == "nearby_support_revoked"
            and good_v2_after_new_evidence.status == "supported_nearby"
            and revision_three.parent_map_id == revision_two.id
            and revision_three.revision_number == 3
            and good_signature in revision_three.revoked_inferred_signatures
            and good_signature
            not in revision_three.calibrated_supported_signatures
            and good_v3.status == "unknown"
            and exact_valid_v3.status == "tested_valid"
            and exact_invalid_v3.status == "tested_invalid"
            and restored.context_causal_validity_maps
            == engine.context_causal_validity_maps
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "base_map_id": base_map.id,
        "revision_two_id": revision_two.id,
        "revision_two_number": revision_two.revision_number,
        "good_v2_status": good_v2.status,
        "bad_v2_status": bad_v2.status,
        "reversal_status": reversal.status,
        "good_v2_after_new_evidence": good_v2_after_new_evidence.status,
        "revision_three_id": revision_three.id,
        "revision_three_number": revision_three.revision_number,
        "good_v3_status": good_v3.status,
        "exact_valid_v3_status": exact_valid_v3.status,
        "exact_invalid_v3_status": exact_invalid_v3.status,
        "restart_preserved": (
            restored.context_causal_validity_maps
            == engine.context_causal_validity_maps
        ),
    }


def _validity_map_selection_and_rollback() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent_schema = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent_schema.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal = build_stability(
        "code=v1;load=normal;data=fixed",
        "selection:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        "code=v1;load=extreme;data=fixed",
        "selection:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    base_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    signature = "code=v1;load=normal;data=shifted"

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            base_map.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"selection:positive:{index}",),
        )
    positive = engine.calibrate_context_validity_region(
        base_map.id,
        environment_signature=signature,
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            revision_two.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"selection:negative:{index}",),
        )
    negative = engine.calibrate_context_validity_region(
        revision_two.id,
        environment_signature=signature,
    )
    revision_three = engine.revise_context_causal_validity_map(
        revision_two.id,
        calibration_ids=(negative.id,),
    )

    activation = engine.select_context_validity_map_revision(
        hypothesis.id,
        reason="activate latest intact calibrated validity map",
        evidence_refs=("selection:latest",),
    )
    active_latest = engine.active_context_causal_validity_map(hypothesis.id)
    decision_latest = engine.evaluate_active_context_validity_gated_decision(
        hypothesis.id,
        environment_signature=signature,
        candidates=candidates,
        context="production release",
    )

    rollback = engine.rollback_context_validity_map(
        hypothesis.id,
        target_map_id=revision_two.id,
        reason="newer revision lost nearby policy calibration support",
        evidence_refs=(f"context_validity_region_calibration:{negative.id}",),
    )
    active_rollback = engine.active_context_causal_validity_map(hypothesis.id)
    decision_rollback = engine.evaluate_active_context_validity_gated_decision(
        hypothesis.id,
        environment_signature=signature,
        candidates=candidates,
        context="production release",
    )
    later_revision_preserved = any(
        item.id == revision_three.id
        for item in engine.context_causal_validity_maps
    )

    readvance = engine.select_context_validity_map_revision(
        hypothesis.id,
        reason="explicitly re-advance after rollback review",
        evidence_refs=("selection:readvance",),
    )
    active_readvance = engine.active_context_causal_validity_map(hypothesis.id)
    narrative = engine.build_metacognitive_narrative(
        "context_validity_selection"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(hypothesis.id)

    return {
        "name": "validity_map_selection_and_rollback",
        "expected_direction": (
            "latest intact revision activates deterministically; rollback moves "
            "only the active pointer to an ancestor while preserving later "
            "revisions and an explicit re-advance can restore the descendant"
        ),
        "passed": (
            activation.action == "activate"
            and activation.selected_map_id == revision_three.id
            and activation.lineage
            == (base_map.id, revision_two.id, revision_three.id)
            and active_latest is not None
            and active_latest.id == revision_three.id
            and decision_latest.classification_status == "unknown"
            and decision_latest.causal_context_allowed is False
            and rollback.action == "rollback"
            and rollback.previous_map_id == revision_three.id
            and rollback.selected_map_id == revision_two.id
            and active_rollback is not None
            and active_rollback.id == revision_two.id
            and decision_rollback.classification_status
            == "supported_nearby"
            and decision_rollback.causal_context_allowed is True
            and later_revision_preserved
            and readvance.action == "advance"
            and readvance.selected_map_id == revision_three.id
            and active_readvance is not None
            and active_readvance.id == revision_three.id
            and len(engine.context_causal_validity_maps) >= 3
            and restored.active_context_validity_map_ids
            == engine.active_context_validity_map_ids
            and restored.context_validity_map_selection_history
            == engine.context_validity_map_selection_history
            and restored_active is not None
            and restored_active.id == revision_three.id
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "activation_action": activation.action,
        "activation_map_id": activation.selected_map_id,
        "activation_lineage": activation.lineage,
        "latest_decision_status": decision_latest.classification_status,
        "rollback_action": rollback.action,
        "rollback_map_id": rollback.selected_map_id,
        "rollback_decision_status": decision_rollback.classification_status,
        "later_revision_preserved": later_revision_preserved,
        "readvance_action": readvance.action,
        "readvance_map_id": readvance.selected_map_id,
        "restart_preserved": (
            restored.active_context_validity_map_ids
            == engine.active_context_validity_map_ids
            and restored.context_validity_map_selection_history
            == engine.context_validity_map_selection_history
        ),
    }


def _active_revision_degradation_watch() -> dict[str, Any]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent_schema = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent_schema.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal = build_stability(
        "code=v1;load=normal;data=fixed",
        "watch:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        "code=v1;load=extreme;data=fixed",
        "watch:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    base_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    signature = "code=v1;load=normal;data=shifted"

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            base_map.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"watch:base_positive:{index}",),
        )
    positive = engine.calibrate_context_validity_region(
        base_map.id,
        environment_signature=signature,
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    activation = engine.select_context_validity_map_revision(
        hypothesis.id,
        map_id=revision_two.id,
        reason="activate calibrated revision for degradation watch",
    )
    initial_watch = engine.watch_active_context_validity_degradation(
        hypothesis.id
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"watch:active_negative:{index}",),
        )
    negative = engine.calibrate_context_validity_region(
        revision_two.id,
        environment_signature=signature,
    )
    recommendation = engine.watch_active_context_validity_degradation(
        hypothesis.id
    )
    active_after_watch = engine.active_context_causal_validity_map(
        hypothesis.id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_degradation"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        hypothesis.id
    )

    return {
        "name": "active_revision_degradation_watch",
        "expected_direction": (
            "only post-activation repeated outcome degradation can produce a "
            "rollback recommendation, which identifies the nearest ancestor "
            "with better calibration support without changing the active map"
        ),
        "passed": (
            positive.status == "nearby_support_calibrated"
            and activation.selected_map_id == revision_two.id
            and activation.calibration_watermark_id == positive.id
            and initial_watch.status
            == "insufficient_post_activation_evidence"
            and negative.status == "nearby_support_revoked"
            and negative.id > activation.calibration_watermark_id
            and recommendation.status == "rollback_recommended"
            and recommendation.active_map_id == revision_two.id
            and recommendation.recommended_map_id == base_map.id
            and recommendation.recommended_revision_number == 1
            and recommendation.degraded_signatures == (signature,)
            and recommendation.mean_active_advantage <= -0.05
            and recommendation.ancestor_support_calibration_ids
            == (positive.id,)
            and active_after_watch is not None
            and active_after_watch.id == revision_two.id
            and not any(
                item.action == "rollback"
                for item in engine.context_validity_map_selection_history
            )
            and restored.context_validity_degradation_watches
            == engine.context_validity_degradation_watches
            and restored_active is not None
            and restored_active.id == revision_two.id
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "initial_watch_status": initial_watch.status,
        "negative_calibration_status": negative.status,
        "recommendation_status": recommendation.status,
        "recommended_map_id": recommendation.recommended_map_id,
        "active_map_unchanged": (
            active_after_watch is not None
            and active_after_watch.id == revision_two.id
        ),
        "automatic_rollback_count": len(
            [
                item
                for item in engine.context_validity_map_selection_history
                if item.action == "rollback"
            ]
        ),
        "restart_preserved": (
            restored.context_validity_degradation_watches
            == engine.context_validity_degradation_watches
            and restored_active is not None
            and restored_active.id == revision_two.id
        ),
    }


def _build_v27_recommendation_engine():
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(6):
        engine.learn(
            observation=f"Sandbox release validation {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.55,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.70,
        )

    parent_schema = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed" and action in item.pattern
    )
    discovery = engine.discover_latent_context_hypotheses(parent_schema.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    def build_stability(
        signature: str,
        prefix: str,
        *,
        reverse_supported: bool,
    ):
        forward_ids: list[int] = []
        for batch in ("a", "b"):
            trial = engine.propose_context_causality_intervention(
                hypothesis.id,
                from_context="production",
                to_context="sandbox",
                controlled_signature=signature,
                min_samples=4,
            )
            trial = engine.observe_context_causality_intervention(
                trial.id,
                observed_target_success_rate=1.0,
                observed_signature=signature,
                sample_count=4,
                evidence_refs=(f"{prefix}:forward:{batch}",),
            )
            forward_ids.append(trial.id)

        reverse = engine.propose_context_causality_intervention(
            hypothesis.id,
            from_context="sandbox",
            to_context="production",
            controlled_signature=signature,
            min_samples=4,
        )
        reverse = engine.observe_context_causality_intervention(
            reverse.id,
            observed_target_success_rate=0.0 if reverse_supported else 1.0,
            observed_signature=signature,
            sample_count=4,
            evidence_refs=(f"{prefix}:reverse:a",),
        )
        return engine.assess_context_causal_stability(
            hypothesis.id,
            forward_trial_ids=forward_ids,
            reverse_trial_ids=(reverse.id,),
        )

    normal = build_stability(
        "code=v1;load=normal;data=fixed",
        "resolution:normal",
        reverse_supported=True,
    )
    extreme = build_stability(
        "code=v1;load=extreme;data=fixed",
        "resolution:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis.id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    base_map = engine.consolidate_context_causal_validity_map(
        hypothesis.id,
        max_generalization_distance=1,
    )

    candidates = [
        {
            "action": action,
            "expected_success": 0.62,
            "expected_information_gain": 0.10,
            "risk": 0.10,
            "reversible": True,
        },
        {
            "action": "request independent review",
            "expected_success": 0.58,
            "expected_information_gain": 0.15,
            "risk": 0.10,
            "reversible": True,
        },
    ]
    signature = "code=v1;load=normal;data=shifted"

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            base_map.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:base_positive:{index}",),
        )
    positive = engine.calibrate_context_validity_region(
        base_map.id,
        environment_signature=signature,
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    engine.select_context_validity_map_revision(
        hypothesis.id,
        map_id=revision_two.id,
        reason="activate revision for recommendation resolution",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis.id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"resolution:active_negative:{index}",),
        )
    engine.calibrate_context_validity_region(
        revision_two.id,
        environment_signature=signature,
    )
    watch = engine.watch_active_context_validity_degradation(hypothesis.id)
    return (
        engine,
        hypothesis.id,
        base_map,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    )


def _rollback_recommendation_resolution() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        base_map,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    deferred_engine = deepcopy(engine)
    deferred = deferred_engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="defer",
        reason="collect more operator evidence before changing revision",
    )
    deferred_active = deferred_engine.active_context_causal_validity_map(
        hypothesis_id
    )

    dismissed_engine = deepcopy(engine)
    dismissed = dismissed_engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="dismiss",
        reason="operator rejects this recommendation",
    )
    dismissed_active = dismissed_engine.active_context_causal_validity_map(
        hypothesis_id
    )

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="degradation evidence justifies ancestor rollback",
        evidence_refs=("resolution:owner_accept",),
    )
    rollback_active = engine.active_context_causal_validity_map(hypothesis_id)

    reactivation_blocked = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="premature re-advance",
        )
    except ValueError as exc:
        reactivation_blocked = "re-advance blocked" in str(exc)

    insufficient = engine.validate_context_validity_rollback(accepted.id)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:rollback_positive:{index}",),
        )

    improved = engine.validate_context_validity_rollback(accepted.id)
    blocked_after_recovery = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="recovery alone is not enough",
        )
    except ValueError as exc:
        blocked_after_recovery = "re-advance blocked" in str(exc)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:rollback_holdout:{index}",),
        )

    holdout = engine.validate_context_validity_rollback_holdout(improved.id)
    readvance = engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="separate rollback holdout confirmed improvement",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{holdout.id}",
        ),
    )
    active_after_readvance = engine.active_context_causal_validity_map(
        hypothesis_id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_resolution"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        hypothesis_id
    )

    return {
        "name": "rollback_recommendation_resolution",
        "expected_direction": (
            "defer and dismiss keep the active revision unchanged; accept "
            "performs ancestor rollback, blocks descendant re-advance until "
            "new post-rollback outcomes demonstrate improved calibration, "
            "then permits an explicit re-advance"
        ),
        "passed": (
            watch.status == "rollback_recommended"
            and deferred.decision == "defer"
            and deferred.rollback_selection_id is None
            and deferred_active is not None
            and deferred_active.id == revision_two.id
            and dismissed.decision == "dismiss"
            and dismissed.rollback_selection_id is None
            and dismissed_active is not None
            and dismissed_active.id == revision_two.id
            and accepted.decision == "accept"
            and accepted.rollback_selection_id is not None
            and accepted.recommended_map_id == base_map.id
            and rollback_active is not None
            and rollback_active.id == base_map.id
            and reactivation_blocked
            and insufficient.status
            == "insufficient_post_rollback_evidence"
            and insufficient.reactivation_allowed is False
            and improved.status == "rollback_recovery_passed"
            and improved.reactivation_allowed is False
            and improved.mean_rollback_advantage >= 0.05
            and improved.improvement_delta >= 0.05
            and len(improved.observed_outcome_ids) >= 3
            and blocked_after_recovery
            and holdout.status == "holdout_confirmed"
            and holdout.reactivation_allowed is True
            and len(holdout.holdout_outcome_ids) >= 3
            and not set(improved.observed_outcome_ids).intersection(
                holdout.holdout_outcome_ids
            )
            and readvance.action == "advance"
            and readvance.selected_map_id == revision_two.id
            and active_after_readvance is not None
            and active_after_readvance.id == revision_two.id
            and restored.context_validity_recommendation_resolutions
            == engine.context_validity_recommendation_resolutions
            and restored.context_validity_rollback_validations
            == engine.context_validity_rollback_validations
            and restored.context_validity_rollback_holdout_validations
            == engine.context_validity_rollback_holdout_validations
            and restored_active is not None
            and restored_active.id == revision_two.id
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "defer_pointer_unchanged": (
            deferred_active is not None
            and deferred_active.id == revision_two.id
        ),
        "dismiss_pointer_unchanged": (
            dismissed_active is not None
            and dismissed_active.id == revision_two.id
        ),
        "accepted_map_id": (
            rollback_active.id if rollback_active is not None else None
        ),
        "reactivation_blocked_before_validation": reactivation_blocked,
        "initial_validation_status": insufficient.status,
        "improved_validation_status": improved.status,
        "improvement_delta": improved.improvement_delta,
        "blocked_after_recovery": blocked_after_recovery,
        "holdout_status": holdout.status,
        "readvance_action": readvance.action,
        "restart_preserved": (
            restored.context_validity_recommendation_resolutions
            == engine.context_validity_recommendation_resolutions
            and restored.context_validity_rollback_validations
            == engine.context_validity_rollback_validations
            and restored.context_validity_rollback_holdout_validations
            == engine.context_validity_rollback_holdout_validations
        ),
    }


def _rollback_holdout_validation() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        _,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="exercise recovery and independent holdout validation",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"holdout:recovery:{index}",),
        )

    recovery = engine.validate_context_validity_rollback(accepted.id)
    recovery_snapshot = deepcopy(engine)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"holdout:negative:{index}",),
        )
    failed_holdout = engine.validate_context_validity_rollback_holdout(
        recovery.id
    )
    blocked_after_failed_holdout = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="failed holdout must not permit reactivation",
        )
    except ValueError as exc:
        blocked_after_failed_holdout = "re-advance blocked" in str(exc)

    confirmation_engine = recovery_snapshot
    for index in range(3):
        gate = confirmation_engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        confirmation_engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"holdout:positive:{index}",),
        )
    confirmed = confirmation_engine.validate_context_validity_rollback_holdout(
        recovery.id
    )
    readvance = confirmation_engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="independent holdout confirmed rollback recovery",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{confirmed.id}",
        ),
    )
    narrative = confirmation_engine.build_metacognitive_narrative(
        "context_validity_holdout"
    )
    restored = UnarchiEngine.from_export(
        confirmation_engine.export_state()
    )

    return {
        "name": "rollback_holdout_validation",
        "expected_direction": (
            "a positive recovery batch cannot reactivate a descendant until "
            "a later non-overlapping holdout batch independently confirms it"
        ),
        "passed": (
            recovery.status == "rollback_recovery_passed"
            and recovery.reactivation_allowed is False
            and recovery.holdout_gate_watermark_id > 0
            and failed_holdout.status == "holdout_not_confirmed"
            and failed_holdout.reactivation_allowed is False
            and blocked_after_failed_holdout
            and confirmed.status == "holdout_confirmed"
            and confirmed.reactivation_allowed is True
            and not set(recovery.observed_outcome_ids).intersection(
                confirmed.holdout_outcome_ids
            )
            and confirmed.mean_holdout_advantage >= 0.05
            and confirmed.holdout_improvement_delta >= 0.05
            and readvance.action == "advance"
            and restored.context_validity_rollback_holdout_validations
            == confirmation_engine.context_validity_rollback_holdout_validations
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "recovery_status": recovery.status,
        "recovery_reactivation_allowed": recovery.reactivation_allowed,
        "failed_holdout_status": failed_holdout.status,
        "blocked_after_failed_holdout": blocked_after_failed_holdout,
        "confirmed_holdout_status": confirmed.status,
        "confirmed_reactivation_allowed": confirmed.reactivation_allowed,
        "evidence_overlap": bool(
            set(recovery.observed_outcome_ids).intersection(
                confirmed.holdout_outcome_ids
            )
        ),
        "readvance_action": readvance.action,
        "restart_preserved": (
            restored.context_validity_rollback_holdout_validations
            == confirmation_engine.context_validity_rollback_holdout_validations
        ),
    }


def _post_reactivation_holdout_drift_monitoring() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        _,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="prepare post-reactivation drift benchmark",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"drift:recovery:{index}",),
        )
    recovery = engine.validate_context_validity_rollback(accepted.id)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"drift:holdout:{index}",),
        )
    holdout = engine.validate_context_validity_rollback_holdout(recovery.id)
    reactivation = engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="reactivate only after confirmed holdout",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{holdout.id}",
        ),
    )

    initial = engine.watch_reactivated_context_validity_drift(hypothesis_id)
    stable_engine = deepcopy(engine)
    degraded_engine = deepcopy(engine)

    for index in range(3):
        gate = stable_engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        stable_engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"drift:stable:{index}",),
        )
    stable = stable_engine.watch_reactivated_context_validity_drift(
        hypothesis_id
    )

    selection_count_before = len(
        degraded_engine.context_validity_map_selection_history
    )
    for index in range(3):
        gate = degraded_engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        degraded_engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"drift:renewed_negative:{index}",),
        )
    degraded = degraded_engine.watch_reactivated_context_validity_drift(
        hypothesis_id
    )
    active_after_watch = degraded_engine.active_context_causal_validity_map(
        hypothesis_id
    )
    narrative = degraded_engine.build_metacognitive_narrative(
        "context_validity_reactivation_drift"
    )
    restored = UnarchiEngine.from_export(degraded_engine.export_state())

    return {
        "name": "post_reactivation_holdout_drift_monitoring",
        "expected_direction": (
            "only outcomes after explicit holdout-confirmed reactivation can "
            "establish stability or renewed degradation, and a drift watch "
            "may recommend review without automatically moving the active map"
        ),
        "passed": (
            recovery.status == "rollback_recovery_passed"
            and holdout.status == "holdout_confirmed"
            and reactivation.action == "advance"
            and initial.status == "insufficient_post_reactivation_evidence"
            and initial.observed_outcome_ids == ()
            and stable.status == "post_reactivation_stable"
            and stable.recommended_action == "continue_monitoring"
            and stable.mean_post_reactivation_advantage >= 0.05
            and degraded.status == "renewed_degradation_detected"
            and degraded.recommended_action == "review_for_rollback"
            and degraded.mean_post_reactivation_advantage <= -0.05
            and degraded.advantage_delta <= -0.05
            and not set(degraded.observed_outcome_ids).intersection(
                holdout.holdout_outcome_ids
            )
            and not set(degraded.observed_outcome_ids).intersection(
                recovery.observed_outcome_ids
            )
            and len(
                degraded_engine.context_validity_map_selection_history
            ) == selection_count_before
            and active_after_watch is not None
            and active_after_watch.id == revision_two.id
            and restored.context_validity_reactivation_drift_watches
            == degraded_engine.context_validity_reactivation_drift_watches
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "initial_status": initial.status,
        "stable_status": stable.status,
        "stable_action": stable.recommended_action,
        "degraded_status": degraded.status,
        "degraded_action": degraded.recommended_action,
        "evidence_overlap_with_holdout": bool(
            set(degraded.observed_outcome_ids).intersection(
                holdout.holdout_outcome_ids
            )
        ),
        "automatic_selection_change": (
            len(degraded_engine.context_validity_map_selection_history)
            != selection_count_before
        ),
        "active_map_unchanged": (
            active_after_watch is not None
            and active_after_watch.id == revision_two.id
        ),
        "restart_preserved": (
            restored.context_validity_reactivation_drift_watches
            == degraded_engine.context_validity_reactivation_drift_watches
        ),
    }


def _renewed_degradation_resolution() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        base_map,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="prepare renewed-degradation resolution benchmark",
    )

    for phase in ("recovery", "holdout"):
        for index in range(3):
            gate = engine.evaluate_active_context_validity_gated_decision(
                hypothesis_id,
                environment_signature=signature,
                candidates=candidates,
                context="production release",
            )
            engine.record_context_validity_gate_outcome(
                gate.id,
                actual_success_by_action={
                    action: False,
                    "request independent review": True,
                },
                evidence_refs=(f"resolution30:{phase}:{index}",),
            )
        if phase == "recovery":
            recovery = engine.validate_context_validity_rollback(accepted.id)

    holdout = engine.validate_context_validity_rollback_holdout(recovery.id)
    engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="reactivate after confirmed holdout for v0.30",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{holdout.id}",
        ),
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"resolution30:renewed_negative:{index}",),
        )
    drift = engine.watch_reactivated_context_validity_drift(hypothesis_id)

    deferred_engine = deepcopy(engine)
    deferred = deferred_engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="defer",
        reason="collect another post-reactivation evidence batch",
    )
    deferred_active = deferred_engine.active_context_causal_validity_map(
        hypothesis_id
    )

    dismissed_engine = deepcopy(engine)
    dismissed = dismissed_engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="dismiss",
        reason="operator rejects renewed-degradation recommendation",
    )
    dismissed_active = dismissed_engine.active_context_causal_validity_map(
        hypothesis_id
    )

    rollback = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="renewed degradation warrants return to validated ancestor",
        evidence_refs=("resolution30:owner_review",),
    )
    rollback_active = engine.active_context_causal_validity_map(hypothesis_id)

    stale_holdout_blocked = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="old holdout must not authorize second reactivation",
            evidence_refs=(
                f"context_validity_rollback_holdout_validation:{holdout.id}",
            ),
        )
    except ValueError as exc:
        stale_holdout_blocked = "new evidence cycle" in str(exc)

    terminal_blocked = False
    try:
        engine.resolve_reactivated_context_validity_drift(
            drift.id,
            decision="dismiss",
            reason="should not reopen terminal rollback review",
        )
    except ValueError as exc:
        terminal_blocked = "terminally resolved" in str(exc)

    narrative = engine.build_metacognitive_narrative(
        "context_validity_reactivation_resolution"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        hypothesis_id
    )

    return {
        "name": "renewed_degradation_resolution",
        "expected_direction": (
            "defer and dismiss keep the reactivated descendant active; an "
            "explicit rollback review returns to the prior validated rollback "
            "map and stale holdout evidence cannot authorize another advance"
        ),
        "passed": (
            drift.status == "renewed_degradation_detected"
            and deferred.decision == "defer"
            and deferred.rollback_selection_id is None
            and deferred_active is not None
            and deferred_active.id == revision_two.id
            and dismissed.decision == "dismiss"
            and dismissed.rollback_selection_id is None
            and dismissed_active is not None
            and dismissed_active.id == revision_two.id
            and rollback.decision == "rollback_review"
            and rollback.rollback_target_map_id == base_map.id
            and rollback.rollback_selection_id is not None
            and rollback.blocked_descendant_map_id == revision_two.id
            and rollback.requires_new_evidence_cycle is True
            and rollback_active is not None
            and rollback_active.id == base_map.id
            and stale_holdout_blocked
            and terminal_blocked
            and any(
                item.id == revision_two.id
                for item in engine.context_causal_validity_maps
            )
            and restored.context_validity_reactivation_drift_resolutions
            == engine.context_validity_reactivation_drift_resolutions
            and restored_active is not None
            and restored_active.id == base_map.id
            and narrative.unsupported_claims == 0
            and bool(narrative.evidence_refs)
        ),
        "defer_pointer_unchanged": (
            deferred_active is not None
            and deferred_active.id == revision_two.id
        ),
        "dismiss_pointer_unchanged": (
            dismissed_active is not None
            and dismissed_active.id == revision_two.id
        ),
        "rollback_target_map_id": rollback.rollback_target_map_id,
        "rollback_active_map_id": (
            rollback_active.id if rollback_active is not None else None
        ),
        "requires_new_evidence_cycle": rollback.requires_new_evidence_cycle,
        "stale_holdout_blocked": stale_holdout_blocked,
        "terminal_resolution_blocked": terminal_blocked,
        "descendant_preserved": any(
            item.id == revision_two.id
            for item in engine.context_causal_validity_maps
        ),
        "restart_preserved": (
            restored.context_validity_reactivation_drift_resolutions
            == engine.context_validity_reactivation_drift_resolutions
            and restored_active is not None
            and restored_active.id == base_map.id
        ),
    }



def _renewed_degradation_recovery_cycle() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        base_map,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="prepare v0.31 renewed recovery benchmark",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:initial_recovery:{index}",),
        )
    initial_recovery = engine.validate_context_validity_rollback(accepted.id)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:initial_holdout:{index}",),
        )
    initial_holdout = engine.validate_context_validity_rollback_holdout(
        initial_recovery.id
    )
    engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="reactivate after initial confirmed holdout",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{initial_holdout.id}",
        ),
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"v031:renewed_negative:{index}",),
        )
    drift = engine.watch_reactivated_context_validity_drift(hypothesis_id)
    resolution = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="start fresh v0.31 recovery cycle",
        evidence_refs=("v031:rollback_review",),
    )

    insufficient_recovery = engine.validate_context_validity_renewed_rollback(
        resolution.id
    )

    stale_holdout_blocked = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="old holdout cannot authorize v0.31 reactivation",
        )
    except ValueError as exc:
        stale_holdout_blocked = "new evidence cycle" in str(exc)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:fresh_recovery:{index}",),
        )
    renewed_recovery = engine.validate_context_validity_renewed_rollback(
        resolution.id
    )

    recovery_only_blocked = False
    try:
        engine.select_context_validity_map_revision(
            hypothesis_id,
            map_id=revision_two.id,
            reason="fresh recovery alone is insufficient",
        )
    except ValueError as exc:
        recovery_only_blocked = (
            "independent holdout cycle required" in str(exc)
        )

    insufficient_holdout = (
        engine.validate_context_validity_renewed_rollback_holdout(
            renewed_recovery.id
        )
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:fresh_holdout:{index}",),
        )
    renewed_holdout = (
        engine.validate_context_validity_renewed_rollback_holdout(
            renewed_recovery.id
        )
    )

    prior_episode_ids = (
        set(initial_recovery.observed_outcome_ids)
        | set(initial_holdout.holdout_outcome_ids)
        | set(drift.observed_outcome_ids)
    )
    recovery_ids = set(renewed_recovery.observed_outcome_ids)
    holdout_ids = set(renewed_holdout.holdout_outcome_ids)
    no_prior_reuse = not prior_episode_ids.intersection(
        recovery_ids | holdout_ids
    )
    independent_batches = not recovery_ids.intersection(holdout_ids)

    advanced = engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="fresh recovery and independent holdout confirmed",
        evidence_refs=(
            f"context_validity_renewed_holdout_validation:{renewed_holdout.id}",
        ),
    )
    active = engine.active_context_causal_validity_map(hypothesis_id)

    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        hypothesis_id
    )

    return {
        "name": "renewed_degradation_recovery_cycle",
        "expected_direction": (
            "after a second rollback, only a new recovery batch and later "
            "independent holdout batch with no evidence reuse can authorize "
            "another descendant reactivation"
        ),
        "passed": (
            initial_recovery.status == "rollback_recovery_passed"
            and initial_holdout.status == "holdout_confirmed"
            and drift.status == "renewed_degradation_detected"
            and resolution.requires_new_evidence_cycle is True
            and insufficient_recovery.status
            == "insufficient_renewed_recovery_evidence"
            and stale_holdout_blocked
            and renewed_recovery.status == "renewed_recovery_passed"
            and recovery_only_blocked
            and insufficient_holdout.status
            == "insufficient_renewed_holdout_evidence"
            and renewed_holdout.status == "renewed_holdout_confirmed"
            and renewed_holdout.reactivation_allowed is True
            and no_prior_reuse
            and independent_batches
            and advanced.action == "advance"
            and active is not None
            and active.id == revision_two.id
            and restored.context_validity_renewed_recovery_validations
            == engine.context_validity_renewed_recovery_validations
            and restored.context_validity_renewed_holdout_validations
            == engine.context_validity_renewed_holdout_validations
            and restored_active is not None
            and restored_active.id == revision_two.id
        ),
        "initial_recovery_status": initial_recovery.status,
        "initial_holdout_status": initial_holdout.status,
        "renewed_recovery_status": renewed_recovery.status,
        "renewed_holdout_status": renewed_holdout.status,
        "stale_holdout_blocked": stale_holdout_blocked,
        "recovery_only_blocked": recovery_only_blocked,
        "prior_evidence_reused": not no_prior_reuse,
        "recovery_holdout_overlap": not independent_batches,
        "readvance_action": advanced.action,
        "restart_preserved": (
            restored.context_validity_renewed_recovery_validations
            == engine.context_validity_renewed_recovery_validations
            and restored.context_validity_renewed_holdout_validations
            == engine.context_validity_renewed_holdout_validations
            and restored_active is not None
            and restored_active.id == revision_two.id
        ),
    }


def _repeated_episode_isolation() -> dict[str, Any]:
    (
        engine,
        hypothesis_id,
        base_map,
        revision_two,
        watch,
        signature,
        candidates,
        action,
    ) = _build_v27_recommendation_engine()

    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="prepare v0.32 repeated episode benchmark",
    )
    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:baseline:recovery:{index}",),
        )
    initial_recovery = engine.validate_context_validity_rollback(accepted.id)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:baseline:holdout:{index}",),
        )
    initial_holdout = engine.validate_context_validity_rollback_holdout(
        initial_recovery.id
    )
    engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="v0.32 baseline holdout confirmed",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{initial_holdout.id}",
        ),
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"v032:episode1:degradation:{index}",),
        )
    drift_one = engine.watch_reactivated_context_validity_drift(hypothesis_id)
    resolution_one = engine.resolve_reactivated_context_validity_drift(
        drift_one.id,
        decision="rollback_review",
        reason="isolate repeated episode one",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:episode1:recovery:{index}",),
        )
    recovery_one = engine.validate_context_validity_renewed_rollback(
        resolution_one.id
    )
    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:episode1:holdout:{index}",),
        )
    holdout_one = engine.validate_context_validity_renewed_rollback_holdout(
        recovery_one.id
    )
    engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="v0.32 episode one confirmed",
        evidence_refs=(
            f"context_validity_renewed_holdout_validation:{holdout_one.id}",
        ),
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: True,
                "request independent review": False,
            },
            evidence_refs=(f"v032:episode2:degradation:{index}",),
        )
    drift_two = engine.watch_reactivated_context_validity_drift(hypothesis_id)
    resolution_two = engine.resolve_reactivated_context_validity_drift(
        drift_two.id,
        decision="rollback_review",
        reason="isolate repeated episode two",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:episode2:recovery:{index}",),
        )
    recovery_two = engine.validate_context_validity_renewed_rollback(
        resolution_two.id
    )
    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            hypothesis_id,
            environment_signature=signature,
            candidates=candidates,
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                action: False,
                "request independent review": True,
            },
            evidence_refs=(f"v032:episode2:holdout:{index}",),
        )
    holdout_two = engine.validate_context_validity_renewed_rollback_holdout(
        recovery_two.id
    )

    episode_one_ids = (
        set(drift_one.observed_outcome_ids)
        | set(recovery_one.observed_outcome_ids)
        | set(holdout_one.holdout_outcome_ids)
    )
    episode_two_ids = (
        set(drift_two.observed_outcome_ids)
        | set(recovery_two.observed_outcome_ids)
        | set(holdout_two.holdout_outcome_ids)
    )
    isolated = not episode_one_ids.intersection(episode_two_ids)
    prior_excluded = episode_one_ids <= set(
        recovery_two.excluded_prior_outcome_ids
    )
    recovery_holdout_isolated = not set(
        recovery_two.observed_outcome_ids
    ).intersection(holdout_two.holdout_outcome_ids)

    advanced = engine.select_context_validity_map_revision(
        hypothesis_id,
        map_id=revision_two.id,
        reason="v0.32 episode two confirmed",
        evidence_refs=(
            f"context_validity_renewed_holdout_validation:{holdout_two.id}",
        ),
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(hypothesis_id)

    return {
        "name": "repeated_episode_isolation",
        "expected_direction": (
            "recurring degradation binds to the newest confirmed holdout and "
            "each recovery episode has immutable identity with disjoint evidence"
        ),
        "passed": (
            initial_recovery.status == "rollback_recovery_passed"
            and initial_holdout.status == "holdout_confirmed"
            and drift_one.status == "renewed_degradation_detected"
            and drift_one.holdout_source == "initial"
            and drift_one.episode_id == 1
            and recovery_one.status == "renewed_recovery_passed"
            and recovery_one.episode_id == 1
            and holdout_one.status == "renewed_holdout_confirmed"
            and holdout_one.episode_id == 1
            and drift_two.status == "renewed_degradation_detected"
            and drift_two.holdout_source == "renewed"
            and drift_two.holdout_validation_id == holdout_one.id
            and drift_two.episode_id == 2
            and resolution_two.episode_id == 2
            and resolution_two.holdout_source == "renewed"
            and recovery_two.status == "renewed_recovery_passed"
            and recovery_two.episode_id == 2
            and recovery_two.prior_holdout_source == "renewed"
            and recovery_two.prior_holdout_validation_id == holdout_one.id
            and holdout_two.status == "renewed_holdout_confirmed"
            and holdout_two.episode_id == 2
            and holdout_two.prior_holdout_source == "renewed"
            and isolated
            and prior_excluded
            and recovery_holdout_isolated
            and advanced.action == "advance"
            and engine.snapshot()["renewed_episode_count"] == 2
            and restored.snapshot()["renewed_episode_count"] == 2
            and restored_active is not None
            and restored_active.id == revision_two.id
        ),
        "episode_one_id": holdout_one.episode_id,
        "episode_two_id": holdout_two.episode_id,
        "second_holdout_source": drift_two.holdout_source,
        "second_holdout_validation_id": drift_two.holdout_validation_id,
        "first_renewed_holdout_id": holdout_one.id,
        "cross_episode_overlap": not isolated,
        "prior_episode_excluded": prior_excluded,
        "recovery_holdout_overlap": not recovery_holdout_isolated,
        "readvance_action": advanced.action,
        "restart_preserved": (
            restored.snapshot()["renewed_episode_count"] == 2
            and restored.context_validity_renewed_holdout_validations[-1].episode_id
            == 2
            and restored_active is not None
            and restored_active.id == revision_two.id
        ),
    }

def run_unarchi_ablation_benchmark() -> dict[str, Any]:
    scenarios = [
        _failure_sensitization(),
        _success_adaptation(),
        _homeostatic_recovery(),
        _endogenous_goal_lifecycle(),
        _predictive_self_calibration(),
        _prospective_temporal_continuity(),
        _metacognitive_retrospective_fidelity(),
        _conflict_arbitration_self_correction(),
        _causal_hypothesis_revision(),
        _intervention_aware_self_world_revision(),
        _recurrent_global_workspace_integration(),
        _counterfactual_recurrent_information_gain(),
        _autobiographical_self_schema_transfer(),
        _contradiction_driven_self_schema_revision(),
        _context_sensitive_self_schema_decomposition(),
        _context_transfer_boundary_learning(),
        _latent_context_hypothesis_discovery(),
        _context_causality_intervention_support(),
        _replicated_reversible_context_causality(),
        _cross_environment_causal_invariance(),
        _active_context_boundary_discovery(),
        _causal_validity_map_consolidation(),
        _validity_gated_decision_use(),
        _validity_gate_outcome_calibration(),
        _calibration_aware_validity_map_revision(),
        _validity_map_selection_and_rollback(),
        _active_revision_degradation_watch(),
        _rollback_recommendation_resolution(),
        _rollback_holdout_validation(),
        _post_reactivation_holdout_drift_monitoring(),
        _renewed_degradation_resolution(),
        _renewed_degradation_recovery_cycle(),
        _repeated_episode_isolation(),
    ]
    passed = sum(bool(item["passed"]) for item in scenarios)
    return {
        "version": BENCHMARK_VERSION,
        "scenario_count": len(scenarios),
        "passed_scenarios": passed,
        "pass_rate": round(passed / len(scenarios), 3),
        "scenarios": scenarios,
        "claims_phenomenal_consciousness": False,
    }
