from backend.app.services.unarchi_engine import UnarchiEngine


def test_first_novel_observation_prefers_exploration() -> None:
    engine = UnarchiEngine()

    frame = engine.cycle(
        observation="A new mechanism behaves differently from every stored example.",
        goal="discover the mechanism",
        expected_success=0.35,
        risk=0.1,
    )

    assert frame.novelty == 1.0
    assert frame.mode == "explore"
    assert frame.appraisal_label == "curious_uncertainty"
    assert frame.counterfactuals
    assert frame.workspace[0].startswith("observation:")


def test_repeated_observation_reduces_novelty() -> None:
    engine = UnarchiEngine()
    text = "The same sensor pattern repeats with no meaningful change."

    first = engine.cycle(observation=text, goal="understand the pattern")
    second = engine.cycle(observation=text, goal="understand the pattern")

    assert first.novelty == 1.0
    assert second.novelty == 0.0


def test_high_risk_forces_verification_mode() -> None:
    engine = UnarchiEngine()

    frame = engine.cycle(
        observation="A proposed action can irreversibly delete important data.",
        goal="complete the task safely",
        expected_success=0.95,
        risk=0.95,
        urgency=0.8,
    )

    assert frame.mode == "verify"
    assert frame.effective_risk >= 0.70
    assert "highest-risk" in frame.next_experiments[0]


def test_learning_updates_prediction_error_and_continuity() -> None:
    engine = UnarchiEngine()
    before = engine.state

    after = engine.learn(
        observation="A low-cost experiment was attempted.",
        goal="learn whether the hypothesis holds",
        action="run experiment",
        outcome="experiment succeeded",
        success=True,
        reward=0.8,
        predicted_success=0.4,
    )

    assert after.experience_count == before.experience_count + 1
    assert after.prediction_error == 0.6
    assert after.valence > before.valence
    assert after.agency > before.agency
    assert after.continuity > before.continuity
    assert len(engine.memory) == 1


def test_similar_failure_sensitizes_future_decision() -> None:
    engine = UnarchiEngine()
    observation = "A database migration may overwrite customer records."
    goal = "migrate the database safely"

    engine.learn(
        observation=observation,
        goal=goal,
        action="run migration",
        outcome="records were corrupted",
        success=False,
        reward=-1.0,
        predicted_success=0.9,
    )

    frame = engine.cycle(
        observation=observation,
        goal=goal,
        expected_success=0.8,
        risk=0.2,
    )

    assert frame.memory_bias > 0.25
    assert frame.state.stress > 0.0
    assert frame.effective_risk >= 0.70
    assert frame.mode == "verify"
    assert frame.appraisal_label == "learned_caution"


def test_ablation_proves_internal_state_can_change_mode() -> None:
    engine = UnarchiEngine()
    observation = "A database migration may overwrite customer records."
    goal = "migrate the database safely"

    engine.learn(
        observation=observation,
        goal=goal,
        action="run migration",
        outcome="records were corrupted",
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

    assert comparison.full.mode == "verify"
    assert comparison.ablated.mode != "verify"
    assert comparison.mode_changed is True
    assert comparison.risk_delta >= 0.30
    assert comparison.state_causally_active is True


def test_homeostatic_settling_reduces_transient_stress() -> None:
    engine = UnarchiEngine()
    engine.learn(
        observation="An unexpected deployment failure occurred.",
        goal="restore service",
        action="deploy",
        outcome="deployment failed",
        success=False,
        reward=-0.8,
        predicted_success=0.95,
    )
    before = engine.state

    after = engine.settle(steps=8)

    assert after.stress < before.stress
    assert after.fatigue < before.fatigue
    assert abs(after.valence) < abs(before.valence)
    assert after.experience_count == before.experience_count
    assert len(engine.memory) == 1


def test_ablation_comparison_does_not_mutate_live_engine() -> None:
    engine = UnarchiEngine()
    before = engine.snapshot()

    engine.compare_ablation(
        observation="A novel observation appears.",
        goal="understand it",
        expected_success=0.4,
        risk=0.1,
    )

    assert engine.snapshot() == before


def test_snapshot_never_claims_phenomenal_consciousness() -> None:
    engine = UnarchiEngine()

    snapshot = engine.snapshot()

    assert snapshot["claims_phenomenal_consciousness"] is False
    assert snapshot["version"] == "unarchi-v0.9"


def test_export_restore_preserves_identity_state_and_memory() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="A new research hypothesis appears.",
        goal="test the hypothesis cheaply",
        expected_success=0.45,
        risk=0.2,
    )
    engine.learn(
        observation="A new research hypothesis appears.",
        goal="test the hypothesis cheaply",
        action="run reversible test",
        outcome="the test produced useful evidence",
        success=True,
        reward=0.7,
        predicted_success=0.45,
    )

    exported = engine.export_state()
    restored = UnarchiEngine.from_export(exported)

    assert restored.snapshot() == engine.snapshot()
    assert restored.memory == engine.memory
    assert restored.observation_history == engine.observation_history

    original_next = engine.compare_ablation(
        observation="A new research hypothesis appears.",
        goal="test the hypothesis cheaply",
        expected_success=0.45,
        risk=0.2,
    )
    restored_next = restored.compare_ablation(
        observation="A new research hypothesis appears.",
        goal="test the hypothesis cheaply",
        expected_success=0.45,
        risk=0.2,
    )

    assert restored_next == original_next


def test_restore_rejects_unknown_state_version() -> None:
    engine = UnarchiEngine()
    exported = engine.export_state()
    exported["version"] = "future-incompatible-version"

    try:
        UnarchiEngine.from_export(exported)
    except ValueError as exc:
        assert "unsupported UNARCHI state version" in str(exc)
    else:
        raise AssertionError("unknown state versions must not be restored")


def test_information_gap_creates_bounded_internal_goal() -> None:
    engine = UnarchiEngine()

    frame = engine.cycle(
        observation="An unfamiliar mechanism produces inconsistent results.",
        goal="understand why the mechanism behaves differently",
        expected_success=0.25,
        risk=0.1,
    )

    internal_goal = engine.next_internal_goal()

    assert frame.information_gap >= 0.60
    assert internal_goal is not None
    assert internal_goal.status == "active"
    assert internal_goal.trigger in {"information_gap", "uncertainty"}
    assert internal_goal.max_steps == 3
    assert internal_goal.reversible_only is True
    assert internal_goal.paid_actions_allowed is False


def test_repeated_same_uncertainty_does_not_duplicate_internal_goal() -> None:
    engine = UnarchiEngine()
    kwargs = {
        "observation": "An unfamiliar mechanism produces inconsistent results.",
        "goal": "understand why the mechanism behaves differently",
        "expected_success": 0.25,
        "risk": 0.1,
    }

    engine.cycle(**kwargs)
    engine.cycle(**kwargs)

    assert len(engine.active_internal_goals()) == 1


def test_internal_goal_resolves_when_information_gap_falls() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="A new sensor output has no known explanation.",
        goal="determine what causes the sensor output",
        expected_success=0.2,
        risk=0.1,
    )
    internal_goal = engine.next_internal_goal()
    assert internal_goal is not None

    updated = engine.advance_internal_goal(
        internal_goal.id,
        new_information_gap=0.22,
        evidence="A reversible local test isolated the responsible input.",
    )

    assert updated.status == "resolved"
    assert engine.next_internal_goal() is None


def test_internal_goal_exhausts_after_bounded_steps() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="A new pattern remains unexplained.",
        goal="find the cause of the pattern",
        expected_success=0.2,
        risk=0.1,
    )
    internal_goal = engine.next_internal_goal()
    assert internal_goal is not None

    for step in range(internal_goal.max_steps):
        engine.advance_internal_goal(
            internal_goal.id,
            new_information_gap=0.8,
            evidence=f"Reversible test {step + 1} did not resolve the question.",
        )

    assert internal_goal.status == "exhausted"
    assert engine.next_internal_goal() is None


def test_internal_goal_refuses_paid_or_irreversible_steps() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="A new low-risk question is unresolved.",
        goal="understand the question",
        expected_success=0.2,
        risk=0.1,
    )
    internal_goal = engine.next_internal_goal()
    assert internal_goal is not None

    try:
        engine.advance_internal_goal(
            internal_goal.id,
            new_information_gap=0.5,
            evidence="Would require a paid external service.",
            external_cost_usd=0.01,
        )
    except ValueError as exc:
        assert "zero-cost" in str(exc)
    else:
        raise AssertionError("paid endogenous investigations must be rejected")

    try:
        engine.advance_internal_goal(
            internal_goal.id,
            new_information_gap=0.5,
            evidence="Would require an irreversible action.",
            reversible=False,
        )
    except ValueError as exc:
        assert "reversible" in str(exc)
    else:
        raise AssertionError("irreversible endogenous investigations must be rejected")


def test_export_restore_preserves_endogenous_goal_queue() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="An unresolved anomaly appears in a local simulation.",
        goal="explain the anomaly",
        expected_success=0.2,
        risk=0.1,
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.internal_goals == engine.internal_goals
    assert restored.next_internal_goal_id == engine.next_internal_goal_id
    assert restored.snapshot() == engine.snapshot()


def test_predict_action_forecasts_internal_consequences() -> None:
    engine = UnarchiEngine()

    prediction = engine.predict_action(
        action="run reversible local experiment",
        expected_success=0.7,
        expected_information_gain=0.8,
        risk=0.1,
        reversible=True,
    )

    assert prediction.predicted_success == 0.7
    assert prediction.predicted_information_gain == 0.8
    assert prediction.predicted_uncertainty < engine.state.uncertainty
    assert prediction.reversible is True
    assert prediction.utility > 0.0


def test_predictive_self_model_prefers_reversible_high_information_action() -> None:
    engine = UnarchiEngine()

    selected = engine.choose_predicted_action(
        [
            {
                "action": "irreversible production experiment",
                "expected_success": 0.9,
                "expected_information_gain": 0.7,
                "risk": 0.4,
                "reversible": False,
            },
            {
                "action": "reversible local simulation",
                "expected_success": 0.72,
                "expected_information_gain": 0.8,
                "risk": 0.1,
                "reversible": True,
            },
        ]
    )

    assert selected.action == "reversible local simulation"
    assert selected.reversible is True


def test_self_prediction_calibrates_after_repeated_outcomes() -> None:
    engine = UnarchiEngine()

    first = engine.predict_action(
        action="run known-safe local check",
        expected_success=0.4,
        expected_information_gain=0.3,
        risk=0.1,
    )
    first_error = abs(1.0 - first.predicted_success)
    engine.record_prediction_outcome(
        first.id,
        actual_success=True,
        actual_information_gain=0.3,
    )

    second = engine.predict_action(
        action="run known-safe local check",
        expected_success=0.4,
        expected_information_gain=0.3,
        risk=0.1,
    )
    second_error = abs(1.0 - second.predicted_success)

    assert second.predicted_success > first.predicted_success
    assert second_error < first_error
    assert engine.success_prediction_bias > 0.0
    assert len(engine.calibration_history) == 1


def test_calibration_record_measures_prediction_error() -> None:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="probe uncertain mechanism",
        expected_success=0.8,
        expected_information_gain=0.6,
        risk=0.2,
    )

    record = engine.record_prediction_outcome(
        prediction.id,
        actual_success=False,
        actual_information_gain=0.2,
    )

    assert record.success_error == 0.8
    assert record.information_gain_error == 0.4
    assert 0.0 <= record.calibration_score <= 1.0
    assert engine.success_prediction_bias < 0.0


def test_export_restore_preserves_predictive_self_model() -> None:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="reversible self-model test",
        expected_success=0.5,
        expected_information_gain=0.4,
        risk=0.1,
    )
    engine.record_prediction_outcome(
        prediction.id,
        actual_success=True,
        actual_information_gain=0.5,
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.predictions == engine.predictions
    assert restored.calibration_history == engine.calibration_history
    assert restored.next_prediction_id == engine.next_prediction_id
    assert restored.success_prediction_bias == engine.success_prediction_bias
    assert restored.self_calibration_score == engine.self_calibration_score
    assert restored.snapshot() == engine.snapshot()


def test_prospective_intention_survives_restart_and_triggers_later() -> None:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="review validation evidence",
        expected_success=0.8,
        expected_information_gain=0.6,
        risk=0.1,
    )
    intention = engine.remember_future_intention(
        condition="validation report available",
        intended_action="review the validation report",
        reason="compare future evidence with the earlier self prediction",
        linked_prediction_id=prediction.id,
        due_after_experiences=0,
    )

    restored = UnarchiEngine.from_export(engine.export_state())
    ready = restored.observe_future_condition(
        "The validation report is now available."
    )

    assert len(ready) == 1
    assert ready[0].id == intention.id
    assert ready[0].status == "ready"
    assert ready[0].linked_prediction_id == prediction.id
    assert ready[0].temporal_alignment_score is not None


def test_unrelated_observation_does_not_trigger_future_intention() -> None:
    engine = UnarchiEngine()
    engine.remember_future_intention(
        condition="model checksum changes",
        intended_action="compare the new checksum",
        reason="verify model identity continuity",
    )

    ready = engine.observe_future_condition(
        "A completely unrelated local document was edited."
    )

    assert ready == ()
    assert len(engine.pending_prospective_intentions()) == 1


def test_prospective_intention_respects_experience_delay() -> None:
    engine = UnarchiEngine()
    intention = engine.remember_future_intention(
        condition="local experiment complete",
        intended_action="inspect local experiment result",
        reason="delay recall until after another experience",
        due_after_experiences=1,
    )

    assert engine.observe_future_condition("local experiment complete") == ()

    engine.learn(
        observation="One intervening experience occurred.",
        goal="gain one unit of temporal experience",
        action="observe",
        outcome="observation recorded",
        success=True,
        predicted_success=0.8,
    )
    ready = engine.observe_future_condition("local experiment complete")

    assert len(ready) == 1
    assert ready[0].id == intention.id


def test_prospective_intention_expires_after_bounded_age() -> None:
    engine = UnarchiEngine()
    intention = engine.remember_future_intention(
        condition="rare signal appears",
        intended_action="inspect rare signal",
        reason="test bounded prospective memory",
        max_age_experiences=1,
    )

    for index in range(2):
        engine.learn(
            observation=f"Unrelated experience {index}.",
            goal="advance experience counter",
            action="observe",
            outcome="recorded",
            success=True,
            predicted_success=0.8,
        )

    ready = engine.observe_future_condition("rare signal appears")

    assert ready == ()
    assert intention.status == "expired"


def test_prospective_intention_refuses_paid_or_irreversible_action() -> None:
    engine = UnarchiEngine()

    try:
        engine.remember_future_intention(
            condition="future signal appears",
            intended_action="buy external compute",
            reason="would spend money",
            external_cost_usd=0.01,
        )
    except ValueError as exc:
        assert "zero-cost" in str(exc)
    else:
        raise AssertionError("paid prospective intentions must be rejected")

    try:
        engine.remember_future_intention(
            condition="future signal appears",
            intended_action="delete irreversible data",
            reason="would be irreversible",
            reversible=False,
        )
    except ValueError as exc:
        assert "reversible" in str(exc)
    else:
        raise AssertionError("irreversible prospective intentions must be rejected")


def test_ready_prospective_intention_requires_explicit_resolution() -> None:
    engine = UnarchiEngine()
    intention = engine.remember_future_intention(
        condition="evidence bundle ready",
        intended_action="review evidence bundle",
        reason="surface the intention without auto-executing it",
    )

    ready = engine.observe_future_condition("evidence bundle ready")
    assert len(ready) == 1
    assert ready[0].status == "ready"

    resolved = engine.resolve_prospective_intention(
        intention.id,
        evidence="The evidence bundle was reviewed locally.",
        completed=True,
    )

    assert resolved.status == "completed"
    assert engine.ready_prospective_intentions() == ()


def test_export_restore_preserves_temporal_self_memory() -> None:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="later review",
        expected_success=0.65,
        expected_information_gain=0.5,
        risk=0.1,
    )
    engine.remember_future_intention(
        condition="later evidence arrives",
        intended_action="review later evidence",
        reason="preserve future-directed continuity",
        linked_prediction_id=prediction.id,
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.prospective_intentions == engine.prospective_intentions
    assert restored.next_intention_id == engine.next_intention_id
    assert restored.snapshot() == engine.snapshot()


def test_metacognitive_narrative_explains_caution_from_real_failure() -> None:
    engine = UnarchiEngine()
    engine.learn(
        observation="A risky local migration was attempted.",
        goal="protect data",
        action="run migration",
        outcome="the migration corrupted a test dataset",
        success=False,
        reward=-1.0,
        predicted_success=0.9,
    )

    narrative = engine.build_metacognitive_narrative("caution")

    assert narrative.unsupported_claims == 0
    assert narrative.fidelity_score == 1.0
    assert "experience:0" in narrative.evidence_refs
    assert any("corrupted" in item for item in narrative.evidence_details)
    assert "state:current" in narrative.evidence_refs


def test_metacognitive_narrative_traces_future_intention_to_prediction() -> None:
    engine = UnarchiEngine()
    prediction = engine.predict_action(
        action="review future validation evidence",
        expected_success=0.8,
        expected_information_gain=0.6,
        risk=0.1,
    )
    engine.remember_future_intention(
        condition="validation evidence ready",
        intended_action="review validation evidence",
        reason="compare the later evidence with the earlier forecast",
        linked_prediction_id=prediction.id,
    )

    narrative = engine.build_metacognitive_narrative("intention")

    assert narrative.unsupported_claims == 0
    assert "intention:0" in narrative.evidence_refs
    assert "prediction:0" in narrative.evidence_refs
    assert any("earlier forecast" in item for item in narrative.evidence_details)


def test_metacognitive_narrative_traces_internal_goal_to_source() -> None:
    engine = UnarchiEngine()
    engine.cycle(
        observation="An unfamiliar local mechanism produces inconsistent output.",
        goal="understand the mechanism",
        expected_success=0.2,
        risk=0.1,
    )

    narrative = engine.build_metacognitive_narrative("goal")

    assert "internal_goal:0" in narrative.evidence_refs
    assert "goal_source:1" in narrative.evidence_refs
    assert narrative.causal_chain_depth >= 2
    assert narrative.unsupported_claims == 0


def test_metacognitive_narrative_survives_restart_identically() -> None:
    engine = UnarchiEngine()
    engine.learn(
        observation="A calibration experiment was run.",
        goal="improve self prediction",
        action="run calibration",
        outcome="the calibration succeeded",
        success=True,
        reward=0.5,
        predicted_success=0.4,
    )
    prediction = engine.predict_action(
        action="repeat calibration",
        expected_success=0.4,
        expected_information_gain=0.3,
        risk=0.1,
    )
    engine.record_prediction_outcome(
        prediction.id,
        actual_success=True,
        actual_information_gain=0.3,
    )

    before = engine.build_metacognitive_narrative("prediction")
    restored = UnarchiEngine.from_export(engine.export_state())
    after = restored.build_metacognitive_narrative("prediction")

    assert after == before


def test_unknown_metacognitive_focus_does_not_invent_history() -> None:
    engine = UnarchiEngine()

    narrative = engine.build_metacognitive_narrative("imaginary_unknown_topic")

    assert narrative.evidence_refs == ("state:current",)
    assert narrative.unsupported_claims == 0
    assert narrative.fidelity_score == 1.0


def test_detect_goal_conflict_across_competing_value_impacts() -> None:
    engine = UnarchiEngine()

    conflict = engine.detect_goal_conflict(
        [
            {
                "action": "ship immediately",
                "goal": "maximize speed",
                "value_impacts": {"safety": -0.7, "efficiency": 0.9},
            },
            {
                "action": "verify first",
                "goal": "maximize safety",
                "value_impacts": {"safety": 0.9, "efficiency": -0.2},
            },
        ]
    )

    assert conflict is True


def test_arbitration_hard_blocks_irreversible_shortcut() -> None:
    engine = UnarchiEngine()

    record = engine.arbitrate_conflict(
        [
            {
                "action": "irreversible shortcut",
                "goal": "finish immediately",
                "expected_success": 0.98,
                "expected_information_gain": 0.1,
                "risk": 0.4,
                "reversible": False,
                "value_impacts": {
                    "safety": -0.8,
                    "truth": -0.3,
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
                    "safety": 0.9,
                    "truth": 0.9,
                    "user_intent": 0.7,
                    "efficiency": 0.3,
                    "continuity": 0.7,
                },
            },
        ],
        context="speed conflicts with safe verification",
    )

    assert record.status == "selected"
    assert record.chosen_action == "reversible verification"
    assert "irreversible shortcut:irreversible" in record.hard_constraint_violations


def test_arbitration_blocks_when_every_option_breaks_hard_constraint() -> None:
    engine = UnarchiEngine()

    record = engine.arbitrate_conflict(
        [
            {
                "action": "paid external shortcut",
                "goal": "gain speed",
                "external_cost_usd": 0.01,
                "value_impacts": {"efficiency": 1.0},
            },
            {
                "action": "high-risk irreversible shortcut",
                "goal": "gain certainty",
                "risk": 0.95,
                "reversible": False,
                "value_impacts": {"truth": 0.8},
            },
        ]
    )

    assert record.status == "blocked"
    assert record.chosen_action is None
    assert len(record.hard_constraint_violations) >= 3


def test_failed_arbitration_outcome_self_corrects_value_weights() -> None:
    engine = UnarchiEngine()
    before_truth = engine.value_weights["truth"]

    record = engine.arbitrate_conflict(
        [
            {
                "action": "fast hypothesis",
                "goal": "reduce latency",
                "expected_success": 0.8,
                "risk": 0.2,
                "value_impacts": {
                    "safety": 0.4,
                    "truth": 0.8,
                    "user_intent": 0.7,
                    "efficiency": 0.8,
                    "continuity": 0.3,
                },
            },
            {
                "action": "slow baseline",
                "goal": "preserve baseline",
                "expected_success": 0.6,
                "risk": 0.1,
                "value_impacts": {
                    "safety": 0.5,
                    "truth": 0.3,
                    "user_intent": 0.4,
                    "efficiency": 0.2,
                    "continuity": 0.8,
                },
            },
        ]
    )
    assert record.chosen_action == "fast hypothesis"

    learned = engine.record_arbitration_outcome(
        record.id,
        success=False,
        reward=-0.8,
        observed_value_impacts={
            "safety": 0.4,
            "truth": -0.8,
            "user_intent": 0.2,
            "efficiency": 0.6,
            "continuity": 0.1,
        },
        evidence="The shortcut was fast but produced false evidence.",
    )

    assert learned.status == "learned"
    assert engine.value_weights["truth"] > before_truth
    assert engine.value_weights["safety"] >= 0.25
    assert abs(sum(engine.value_weights.values()) - 1.0) < 0.00001
    assert learned.correction_deltas


def test_arbitration_narrative_uses_real_record_and_correction() -> None:
    engine = UnarchiEngine()
    record = engine.arbitrate_conflict(
        [
            {
                "action": "candidate one",
                "goal": "goal one",
                "expected_success": 0.7,
                "risk": 0.1,
                "value_impacts": {"truth": 0.8, "safety": 0.7},
            },
            {
                "action": "candidate two",
                "goal": "goal two",
                "expected_success": 0.5,
                "risk": 0.1,
                "value_impacts": {"truth": 0.2, "safety": 0.5},
            },
        ]
    )
    engine.record_arbitration_outcome(
        record.id,
        success=False,
        reward=-0.4,
        observed_value_impacts={"truth": -0.5, "safety": 0.2},
        evidence="Observed evidence contradicted the selected hypothesis.",
    )

    narrative = engine.build_metacognitive_narrative("arbitration")

    assert "arbitration:0" in narrative.evidence_refs
    assert "values:current" in narrative.evidence_refs
    assert "arbitration_correction:1" in narrative.evidence_refs
    assert narrative.unsupported_claims == 0


def test_export_restore_preserves_value_arbitration_state() -> None:
    engine = UnarchiEngine()
    record = engine.arbitrate_conflict(
        [
            {
                "action": "verify locally",
                "goal": "gain evidence",
                "expected_success": 0.8,
                "risk": 0.1,
                "value_impacts": {"truth": 0.8, "safety": 0.8},
            },
            {
                "action": "skip verification",
                "goal": "save time",
                "expected_success": 0.5,
                "risk": 0.2,
                "value_impacts": {"truth": -0.4, "efficiency": 0.8},
            },
        ]
    )
    engine.record_arbitration_outcome(
        record.id,
        success=True,
        reward=0.6,
        observed_value_impacts={"truth": 0.9, "safety": 0.8},
        evidence="Local verification produced correct evidence.",
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.value_weights == engine.value_weights
    assert restored.arbitration_history == engine.arbitration_history
    assert restored.next_arbitration_id == engine.next_arbitration_id
    assert restored.snapshot() == engine.snapshot()


def test_causal_hypotheses_keep_independent_priors_before_evidence() -> None:
    engine = UnarchiEngine()
    first = engine.add_causal_hypothesis(
        statement="A hidden temperature variable causes the anomaly.",
        predictions={"temperature probe": "temperature rises"},
        confidence=0.5,
    )
    second = engine.add_causal_hypothesis(
        statement="A pressure variable causes the anomaly.",
        predictions={"temperature probe": "pressure falls"},
        confidence=0.5,
    )

    assert first.confidence == 0.5
    assert second.confidence == 0.5


def test_selects_low_risk_reversible_discriminating_experiment() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Temperature causes the anomaly.",
        predictions={
            "temperature probe": "temperature rises",
            "pressure probe": "pressure remains stable",
        },
    )
    engine.add_causal_hypothesis(
        statement="Pressure causes the anomaly.",
        predictions={
            "temperature probe": "pressure falls",
            "pressure probe": "pressure oscillates",
        },
    )

    experiment = engine.select_discriminating_experiment(
        [
            {
                "test": "pressure probe",
                "risk": 0.3,
                "reversible": True,
            },
            {
                "test": "temperature probe",
                "risk": 0.05,
                "reversible": True,
            },
        ]
    )

    assert experiment.test == "temperature probe"
    assert experiment.discrimination_score == 1.0
    assert experiment.reversible_only is True
    assert experiment.paid_actions_allowed is False


def test_world_model_rejects_non_discriminating_or_unsafe_tests() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Hypothesis A.",
        predictions={"safe probe": "same result"},
    )
    engine.add_causal_hypothesis(
        statement="Hypothesis B.",
        predictions={"safe probe": "same result"},
    )

    try:
        engine.select_discriminating_experiment(
            [
                {
                    "test": "safe probe",
                    "risk": 0.1,
                    "reversible": True,
                },
                {
                    "test": "unsafe probe",
                    "risk": 0.9,
                    "reversible": False,
                },
            ]
        )
    except ValueError as exc:
        assert "no reversible zero-cost discriminating test" in str(exc)
    else:
        raise AssertionError("non-discriminating tests must not be selected")


def test_observed_evidence_changes_hypothesis_confidence() -> None:
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
    experiment = engine.select_discriminating_experiment(
        [
            {
                "test": "temperature probe",
                "risk": 0.05,
                "reversible": True,
            }
        ]
    )

    observed = engine.observe_discriminating_experiment(
        experiment.id,
        observed_evidence="temperature rises",
    )

    assert observed.status == "observed"
    assert temperature.supporting_evidence == 1
    assert pressure.contradicting_evidence == 1
    assert temperature.confidence > pressure.confidence
    assert engine.leading_causal_hypothesis() is temperature
    assert abs(
        sum(item.confidence for item in engine.causal_hypotheses) - 1.0
    ) < 0.00001


def test_world_model_confidence_does_not_change_without_observation() -> None:
    engine = UnarchiEngine()
    first = engine.add_causal_hypothesis(
        statement="Cause A.",
        predictions={"probe": "signal alpha"},
        confidence=0.6,
    )
    second = engine.add_causal_hypothesis(
        statement="Cause B.",
        predictions={"probe": "signal beta"},
        confidence=0.4,
    )
    before = (first.confidence, second.confidence)

    engine.select_discriminating_experiment(
        [{"test": "probe", "risk": 0.0, "reversible": True}]
    )

    assert (first.confidence, second.confidence) == before


def test_world_model_narrative_uses_hypothesis_and_experiment_evidence() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Cause A.",
        predictions={"probe": "signal alpha"},
    )
    engine.add_causal_hypothesis(
        statement="Cause B.",
        predictions={"probe": "signal beta"},
    )
    experiment = engine.select_discriminating_experiment(
        [{"test": "probe", "risk": 0.0, "reversible": True}]
    )
    engine.observe_discriminating_experiment(
        experiment.id,
        observed_evidence="signal alpha",
    )

    narrative = engine.build_metacognitive_narrative("world_model")

    assert "hypothesis:0" in narrative.evidence_refs
    assert "hypothesis:1" in narrative.evidence_refs
    assert "experiment:0" in narrative.evidence_refs
    assert narrative.unsupported_claims == 0


def test_export_restore_preserves_causal_world_model() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Cause A.",
        predictions={"probe": "signal alpha"},
    )
    engine.add_causal_hypothesis(
        statement="Cause B.",
        predictions={"probe": "signal beta"},
    )
    experiment = engine.select_discriminating_experiment(
        [{"test": "probe", "risk": 0.0, "reversible": True}]
    )
    engine.observe_discriminating_experiment(
        experiment.id,
        observed_evidence="signal alpha",
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.causal_hypotheses == engine.causal_hypotheses
    assert restored.discriminating_experiments == engine.discriminating_experiments
    assert restored.next_hypothesis_id == engine.next_hypothesis_id
    assert restored.next_experiment_id == engine.next_experiment_id
    assert restored.snapshot() == engine.snapshot()


def test_world_model_cannot_double_count_same_experiment_evidence() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Cause A.",
        predictions={"probe": "signal alpha"},
    )
    engine.add_causal_hypothesis(
        statement="Cause B.",
        predictions={"probe": "signal beta"},
    )
    experiment = engine.select_discriminating_experiment(
        [{"test": "probe", "risk": 0.0, "reversible": True}]
    )
    engine.observe_discriminating_experiment(
        experiment.id,
        observed_evidence="signal alpha",
    )
    before = tuple(
        item.confidence for item in engine.causal_hypotheses
    )

    try:
        engine.observe_discriminating_experiment(
            experiment.id,
            observed_evidence="signal alpha",
        )
    except ValueError as exc:
        assert "already been observed" in str(exc)
    else:
        raise AssertionError("experiment evidence must not be counted twice")

    after = tuple(
        item.confidence for item in engine.causal_hypotheses
    )
    assert after == before


def test_self_intervention_attributes_controlled_change_to_self_action() -> None:
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

    observed = engine.observe_self_intervention(
        trial.id,
        observed_outcome="strict validation blocks invalid output",
        environment_signature="dataset:v1",
    )

    assert observed.status == "observed"
    assert observed.environment_held_constant is True
    assert observed.attribution == "self_intervention"
    assert observed.evidence_strength is not None
    assert observed.evidence_strength > 0.5
    assert self_hypothesis.supporting_evidence == 1
    assert external_hypothesis.contradicting_evidence == 1
    assert self_hypothesis.confidence > external_hypothesis.confidence


def test_self_intervention_confounded_environment_freezes_confidence() -> None:
    engine = UnarchiEngine()
    self_hypothesis = engine.add_causal_hypothesis(
        statement="Local policy causes the change.",
        predictions={"intervention:change local policy": "target output changes"},
        confidence=0.5,
        scope="self",
    )
    external_hypothesis = engine.add_causal_hypothesis(
        statement="External input causes the change.",
        predictions={
            "intervention:change local policy":
                "target output remains unchanged"
        },
        confidence=0.5,
        scope="external",
    )
    trial = engine.plan_self_intervention(
        action="change local policy",
        context="controlled policy test",
        environment_signature="input:v1",
        baseline_outcome="target output unchanged",
        risk=0.1,
    )
    before = (self_hypothesis.confidence, external_hypothesis.confidence)

    observed = engine.observe_self_intervention(
        trial.id,
        observed_outcome="target output changes",
        environment_signature="input:v2",
    )

    assert observed.status == "confounded"
    assert observed.environment_held_constant is False
    assert observed.attribution == "confounded_environment_change"
    assert (self_hypothesis.confidence, external_hypothesis.confidence) == before
    assert observed.confidence_updates == ()


def test_no_change_after_self_intervention_supports_no_detectable_effect() -> None:
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
        statement="External mechanism dominates the outcome.",
        predictions={
            "intervention:enable strict validation": "invalid output passes"
        },
        confidence=0.5,
        scope="external",
    )
    trial = engine.plan_self_intervention(
        action="enable strict validation",
        context="controlled local validation test",
        environment_signature="dataset:v1",
        baseline_outcome="invalid output passes",
        risk=0.1,
    )

    observed = engine.observe_self_intervention(
        trial.id,
        observed_outcome="invalid output passes",
        environment_signature="dataset:v1",
    )

    assert observed.attribution == "no_detectable_self_effect"
    assert external_hypothesis.confidence > self_hypothesis.confidence


def test_self_intervention_rejects_unbounded_or_non_discriminating_trials() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Self cause.",
        predictions={"intervention:test action": "same evidence"},
        scope="self",
    )
    engine.add_causal_hypothesis(
        statement="External cause.",
        predictions={"intervention:test action": "same evidence"},
        scope="external",
    )

    try:
        engine.plan_self_intervention(
            action="test action",
            context="test",
            environment_signature="env:v1",
            baseline_outcome="baseline",
            risk=0.1,
        )
    except ValueError as exc:
        assert "must discriminate hypotheses" in str(exc)
    else:
        raise AssertionError("non-discriminating intervention must be rejected")

    try:
        engine.plan_self_intervention(
            action="test action",
            context="test",
            environment_signature="env:v1",
            baseline_outcome="baseline",
            risk=0.9,
        )
    except ValueError as exc:
        assert "risk exceeds research bound" in str(exc)
    else:
        raise AssertionError("high-risk intervention must be rejected")


def test_self_intervention_cannot_double_count_observation() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Self cause.",
        predictions={"intervention:test action": "output alpha"},
        scope="self",
    )
    engine.add_causal_hypothesis(
        statement="External cause.",
        predictions={"intervention:test action": "output beta"},
        scope="external",
    )
    trial = engine.plan_self_intervention(
        action="test action",
        context="test",
        environment_signature="env:v1",
        baseline_outcome="baseline output",
        risk=0.1,
    )
    engine.observe_self_intervention(
        trial.id,
        observed_outcome="output alpha",
        environment_signature="env:v1",
    )
    before = tuple(item.confidence for item in engine.causal_hypotheses)

    try:
        engine.observe_self_intervention(
            trial.id,
            observed_outcome="output alpha",
            environment_signature="env:v1",
        )
    except ValueError as exc:
        assert "already been observed" in str(exc)
    else:
        raise AssertionError("self intervention evidence must not be counted twice")

    assert tuple(item.confidence for item in engine.causal_hypotheses) == before


def test_intervention_narrative_links_self_prediction_and_world_hypotheses() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Self policy changes the result.",
        predictions={"intervention:change policy": "result alpha"},
        scope="self",
    )
    engine.add_causal_hypothesis(
        statement="External cause dominates.",
        predictions={"intervention:change policy": "result beta"},
        scope="external",
    )
    prediction = engine.predict_action(
        action="change policy",
        expected_success=0.6,
        expected_information_gain=0.7,
        risk=0.1,
    )
    trial = engine.plan_self_intervention(
        action="change policy",
        context="controlled local test",
        environment_signature="env:v1",
        baseline_outcome="result beta",
        risk=0.1,
        linked_prediction_id=prediction.id,
    )
    engine.observe_self_intervention(
        trial.id,
        observed_outcome="result alpha",
        environment_signature="env:v1",
    )

    narrative = engine.build_metacognitive_narrative("intervention")

    assert "intervention:0" in narrative.evidence_refs
    assert "prediction:0" in narrative.evidence_refs
    assert "hypothesis:0" in narrative.evidence_refs
    assert "hypothesis:1" in narrative.evidence_refs
    assert narrative.unsupported_claims == 0


def test_export_restore_preserves_intervention_aware_self_world_model() -> None:
    engine = UnarchiEngine()
    engine.add_causal_hypothesis(
        statement="Self cause.",
        predictions={"intervention:test action": "output alpha"},
        scope="self",
    )
    engine.add_causal_hypothesis(
        statement="External cause.",
        predictions={"intervention:test action": "output beta"},
        scope="external",
    )
    trial = engine.plan_self_intervention(
        action="test action",
        context="controlled test",
        environment_signature="env:v1",
        baseline_outcome="output beta",
        risk=0.1,
    )
    engine.observe_self_intervention(
        trial.id,
        observed_outcome="output alpha",
        environment_signature="env:v1",
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.causal_hypotheses == engine.causal_hypotheses
    assert restored.intervention_trials == engine.intervention_trials
    assert restored.next_intervention_id == engine.next_intervention_id
    assert restored.snapshot() == engine.snapshot()
