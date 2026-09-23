from __future__ import annotations

from typing import Any

from backend.app.services.unarchi_engine import UnarchiEngine


BENCHMARK_VERSION = "unarchi-ablation-v0.8"


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
