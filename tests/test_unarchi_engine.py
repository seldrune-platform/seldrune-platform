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
    assert snapshot["version"] == "unarchi-v0.31"


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


def test_global_workspace_broadcast_integrates_multiple_sources() -> None:
    engine = UnarchiEngine()
    engine.stage_global_workspace_item(
        source="memory",
        content="A prior validation failure increased caution.",
        salience=0.8,
        evidence_refs=("experience:0",),
    )
    engine.stage_global_workspace_item(
        source="goal",
        content="Resolve the validation uncertainty.",
        salience=0.9,
        evidence_refs=("internal_goal:0",),
    )
    engine.stage_global_workspace_item(
        source="world_model",
        content="The leading hypothesis predicts a schema mismatch.",
        salience=0.85,
        evidence_refs=("hypothesis:0",),
    )

    cycle = engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )

    assert cycle.decision_mode == "integrated"
    assert set(cycle.integrated_sources) == {"memory", "goal", "world_model"}
    assert len(cycle.broadcast_targets) == 8
    assert cycle.coherence_score >= 0.75


def test_global_workspace_recurrence_is_bounded_and_retires_item() -> None:
    engine = UnarchiEngine(workspace_recurrence_limit=3)
    item = engine.stage_global_workspace_item(
        source="goal",
        content="An unresolved causal question remains active.",
        salience=0.9,
        evidence_refs=("internal_goal:0",),
    )

    first = engine.run_global_workspace_cycle(seed_from_engine=False)
    second = engine.run_global_workspace_cycle(seed_from_engine=False)
    third = engine.run_global_workspace_cycle(seed_from_engine=False)

    assert first.recurrence_depth == 1
    assert second.recurrence_depth == 2
    assert third.recurrence_depth == 3
    assert item.recurrence_count == 3
    assert item.status == "retired"


def test_resolved_workspace_item_does_not_rebroadcast() -> None:
    engine = UnarchiEngine()
    item = engine.stage_global_workspace_item(
        source="memory",
        content="A discrepancy needs resolution.",
        salience=0.9,
        evidence_refs=("experience:0",),
    )
    first = engine.run_global_workspace_cycle(seed_from_engine=False)
    assert item.id in first.selected_item_ids

    engine.resolve_global_workspace_item(
        item.id,
        evidence="A local comparison resolved the discrepancy.",
    )
    second = engine.run_global_workspace_cycle(seed_from_engine=False)

    assert item.id not in second.selected_item_ids
    assert item.status == "resolved"


def test_global_workspace_broadcast_ablation_changes_decision_context() -> None:
    engine = UnarchiEngine()
    for source, content in (
        ("memory", "Past failure evidence."),
        ("goal", "Current unresolved goal."),
        ("world_model", "Current causal hypothesis."),
    ):
        engine.stage_global_workspace_item(
            source=source,
            content=content,
            salience=0.8,
            evidence_refs=(f"{source}:0",),
        )

    comparison = engine.compare_global_workspace_ablation(
        max_items=3,
        seed_from_engine=False,
    )

    assert comparison.full.decision_mode == "integrated"
    assert comparison.ablated.decision_mode == "local"
    assert comparison.target_delta == 8
    assert comparison.mode_changed is True
    assert comparison.workspace_causally_active is True


def test_global_workspace_narrative_is_evidence_grounded() -> None:
    engine = UnarchiEngine()
    engine.stage_global_workspace_item(
        source="self_model",
        content="Self prediction indicates elevated uncertainty.",
        salience=0.8,
        evidence_refs=("prediction:0",),
    )
    engine.stage_global_workspace_item(
        source="world_model",
        content="World hypothesis predicts an external mismatch.",
        salience=0.8,
        evidence_refs=("hypothesis:0",),
    )
    engine.run_global_workspace_cycle(
        max_items=2,
        seed_from_engine=False,
    )

    narrative = engine.build_metacognitive_narrative("workspace")

    assert "workspace_cycle:0" in narrative.evidence_refs
    assert "workspace_item:1" in narrative.evidence_refs
    assert "workspace_item:2" in narrative.evidence_refs
    assert narrative.unsupported_claims == 0


def test_export_restore_preserves_recurrent_global_workspace() -> None:
    engine = UnarchiEngine()
    item = engine.stage_global_workspace_item(
        source="goal",
        content="Persistent unresolved goal.",
        salience=0.9,
        evidence_refs=("internal_goal:0",),
    )
    engine.run_global_workspace_cycle(seed_from_engine=False)

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.global_workspace_items == engine.global_workspace_items
    assert restored.global_workspace_cycles == engine.global_workspace_cycles
    assert restored.next_workspace_item_id == engine.next_workspace_item_id
    assert restored.next_workspace_cycle_id == engine.next_workspace_cycle_id
    assert restored.snapshot() == engine.snapshot()
    assert (
        restored.global_workspace_items[0].recurrence_count
        == item.recurrence_count
    )


def test_counterfactual_recurrence_prefers_information_rich_future() -> None:
    engine = UnarchiEngine()
    for source, content in (
        ("memory", "Past failures make verification evidence important."),
        ("goal", "Reduce uncertainty before committing."),
        ("world_model", "Two explanations remain plausible."),
    ):
        engine.stage_global_workspace_item(
            source=source,
            content=content,
            salience=0.85,
            evidence_refs=(f"{source}:0",),
        )
    engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )

    futures = engine.simulate_counterfactual_futures(
        [
            {
                "action": "fast direct action",
                "predicted_outcome": "finish quickly with little new evidence",
                "expected_success": 0.86,
                "expected_information_gain": 0.10,
                "risk": 0.10,
            },
            {
                "action": "reversible diagnostic",
                "predicted_outcome": "diagnostic isolates the uncertain variable",
                "expected_success": 0.72,
                "expected_information_gain": 0.90,
                "risk": 0.05,
            },
        ],
        recurrence_rounds=2,
    )

    assert futures[0].action == "reversible diagnostic"
    assert futures[0].recurrence_rounds == 2
    assert futures[0].linked_workspace_cycle_id == 1
    assert futures[0].predicted_information_gain > futures[1].predicted_information_gain


def test_counterfactual_ablation_changes_choice_and_information_gain() -> None:
    engine = UnarchiEngine()
    for source in ("memory", "goal", "world_model"):
        engine.stage_global_workspace_item(
            source=source,
            content=f"{source} evidence favors information gathering",
            salience=0.85,
            evidence_refs=(f"{source}:0",),
        )
    engine.run_global_workspace_cycle(
        max_items=3,
        seed_from_engine=False,
    )

    comparison = engine.compare_counterfactual_ablation(
        [
            {
                "action": "act immediately",
                "predicted_outcome": "task may finish without resolving uncertainty",
                "expected_success": 0.90,
                "expected_information_gain": 0.05,
                "risk": 0.10,
            },
            {
                "action": "run local diagnostic",
                "predicted_outcome": "diagnostic resolves the main uncertainty",
                "expected_success": 0.74,
                "expected_information_gain": 0.88,
                "risk": 0.05,
            },
        ],
        recurrence_rounds=2,
    )

    assert comparison.full_action == "run local diagnostic"
    assert comparison.ablated_action == "act immediately"
    assert comparison.choice_changed is True
    assert comparison.information_gain_delta > 0.5
    assert comparison.simulation_causally_active is True


def test_counterfactual_observation_feeds_discrepancy_back_to_workspace() -> None:
    engine = UnarchiEngine()
    future = engine.simulate_counterfactual_futures(
        [
            {
                "action": "local probe",
                "predicted_outcome": "probe confirms hypothesis alpha",
                "expected_success": 0.85,
                "expected_information_gain": 0.70,
                "risk": 0.05,
            }
        ],
        recurrence_rounds=1,
    )[0]

    observed = engine.observe_counterfactual_future(
        future.id,
        observed_outcome="probe contradicts hypothesis alpha",
        actual_success=False,
        actual_information_gain=0.40,
    )

    assert observed.status == "observed"
    assert observed.discrepancy is not None
    assert observed.discrepancy > 0.3
    assert observed.feedback_workspace_item_id is not None
    feedback = next(
        item
        for item in engine.global_workspace_items
        if item.id == observed.feedback_workspace_item_id
    )
    assert feedback.source == "self_model"
    assert f"counterfactual:{engine.counterfactual_futures.index(observed)}" in (
        feedback.evidence_refs
    )


def test_counterfactual_simulation_rejects_unsafe_or_paid_futures() -> None:
    engine = UnarchiEngine()

    try:
        engine.simulate_counterfactual_futures(
            [
                {
                    "action": "irreversible external action",
                    "predicted_outcome": "unknown",
                    "expected_success": 0.9,
                    "expected_information_gain": 0.9,
                    "risk": 0.8,
                    "reversible": False,
                    "external_cost_usd": 1.0,
                }
            ]
        )
    except ValueError as exc:
        assert "no reversible zero-cost bounded counterfactual" in str(exc)
    else:
        raise AssertionError("unsafe counterfactual must be rejected")


def test_counterfactual_outcome_cannot_be_double_counted() -> None:
    engine = UnarchiEngine()
    future = engine.simulate_counterfactual_futures(
        [
            {
                "action": "local probe",
                "predicted_outcome": "probe returns alpha",
                "expected_success": 0.7,
                "expected_information_gain": 0.6,
                "risk": 0.05,
            }
        ]
    )[0]
    engine.observe_counterfactual_future(
        future.id,
        observed_outcome="probe returns beta",
        actual_success=False,
        actual_information_gain=0.5,
    )
    before_items = len(engine.global_workspace_items)

    try:
        engine.observe_counterfactual_future(
            future.id,
            observed_outcome="probe returns beta",
            actual_success=False,
            actual_information_gain=0.5,
        )
    except ValueError as exc:
        assert "already been observed" in str(exc)
    else:
        raise AssertionError("counterfactual evidence must not be counted twice")

    assert len(engine.global_workspace_items) == before_items


def test_counterfactual_narrative_links_workspace_and_feedback() -> None:
    engine = UnarchiEngine()
    engine.stage_global_workspace_item(
        source="goal",
        content="Resolve the uncertain variable.",
        salience=0.9,
        evidence_refs=("internal_goal:0",),
    )
    engine.run_global_workspace_cycle(seed_from_engine=False)
    future = engine.simulate_counterfactual_futures(
        [
            {
                "action": "diagnostic",
                "predicted_outcome": "diagnostic confirms alpha",
                "expected_success": 0.8,
                "expected_information_gain": 0.8,
                "risk": 0.05,
            }
        ]
    )[0]
    engine.observe_counterfactual_future(
        future.id,
        observed_outcome="diagnostic contradicts alpha",
        actual_success=False,
        actual_information_gain=0.6,
    )

    narrative = engine.build_metacognitive_narrative("counterfactual")

    assert "counterfactual:0" in narrative.evidence_refs
    assert "workspace_cycle:0" in narrative.evidence_refs
    assert f"workspace_item:{future.feedback_workspace_item_id}" in (
        narrative.evidence_refs
    )
    assert narrative.unsupported_claims == 0


def test_export_restore_preserves_counterfactual_recurrent_state() -> None:
    engine = UnarchiEngine()
    future = engine.simulate_counterfactual_futures(
        [
            {
                "action": "diagnostic",
                "predicted_outcome": "diagnostic confirms alpha",
                "expected_success": 0.8,
                "expected_information_gain": 0.8,
                "risk": 0.05,
            }
        ]
    )[0]
    engine.observe_counterfactual_future(
        future.id,
        observed_outcome="diagnostic confirms alpha",
        actual_success=True,
        actual_information_gain=0.75,
    )

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.counterfactual_futures == engine.counterfactual_futures
    assert restored.next_counterfactual_id == engine.next_counterfactual_id
    assert (
        restored.max_counterfactual_futures
        == engine.max_counterfactual_futures
    )
    assert restored.snapshot() == engine.snapshot()



def test_self_schema_consolidates_repeated_capability_and_limitation() -> None:
    engine = UnarchiEngine()
    for _ in range(3):
        engine.learn(
            observation="A related local validation task needs reliable evidence.",
            goal="protect evidence with local validation",
            action="run validated local diagnostic",
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
    for _ in range(3):
        engine.learn(
            observation="A related shortcut task skipped validation.",
            goal="finish quickly without losing evidence quality",
            action="use untested shortcut",
            outcome="incorrect evidence produced",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    schema = engine.consolidate_self_schema(min_evidence=2)

    assert {item.kind for item in schema} == {"capability", "limitation"}
    capability = next(item for item in schema if item.kind == "capability")
    limitation = next(item for item in schema if item.kind == "limitation")
    assert capability.success_rate == 1.0
    assert capability.success_bias > 0.0
    assert capability.risk_bias < 0.0
    assert limitation.success_rate == 0.0
    assert limitation.success_bias < 0.0
    assert limitation.risk_bias > 0.0
    assert capability.evidence_refs


def test_self_schema_changes_related_choice_and_ablation_removes_transfer() -> None:
    engine = UnarchiEngine()
    for _ in range(4):
        engine.learn(
            observation="A release validation succeeded with local diagnostics.",
            goal="protect evidence with local validation",
            action="run validated local diagnostic",
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.45,
        )
    for _ in range(3):
        engine.learn(
            observation="A release shortcut failed after skipping validation.",
            goal="finish quickly without losing evidence quality",
            action="use untested shortcut",
            outcome="incorrect evidence produced",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )
    engine.consolidate_self_schema()

    candidates = [
        {
            "action": "run validated local diagnostic",
            "expected_success": 0.48,
            "expected_information_gain": 0.20,
            "risk": 0.10,
        },
        {
            "action": "use untested shortcut",
            "expected_success": 0.68,
            "expected_information_gain": 0.10,
            "risk": 0.10,
        },
    ]
    context = "a later related release needs trustworthy local evidence"

    full = engine.choose_predicted_action(
        candidates,
        context=context,
        use_self_schema=True,
    )
    ablated = engine.choose_predicted_action(
        candidates,
        context=context,
        use_self_schema=False,
    )

    assert full.action == "run validated local diagnostic"
    assert ablated.action == "use untested shortcut"
    assert full.utility > ablated.utility or full.action != ablated.action


def test_self_schema_is_idempotent_and_survives_restart() -> None:
    engine = UnarchiEngine()
    for _ in range(3):
        engine.learn(
            observation="A deterministic local check succeeded.",
            goal="validate output locally",
            action="run deterministic local check",
            outcome="validation passed",
            success=True,
            reward=0.7,
            predicted_success=0.5,
        )

    first = engine.consolidate_self_schema()
    first_export = [item.to_dict() for item in first]
    second = engine.consolidate_self_schema()

    assert [item.to_dict() for item in second] == first_export

    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.self_schema == engine.self_schema
    assert restored.next_self_schema_id == engine.next_self_schema_id
    assert restored.snapshot() == engine.snapshot()


def test_self_schema_metacognition_and_workspace_use_real_evidence() -> None:
    engine = UnarchiEngine()
    for _ in range(3):
        engine.learn(
            observation="A local diagnostic succeeded.",
            goal="validate evidence",
            action="run local diagnostic",
            outcome="correct evidence produced",
            success=True,
            reward=0.7,
            predicted_success=0.5,
        )
    schema = engine.consolidate_self_schema()
    narrative = engine.build_metacognitive_narrative("self_schema")
    staged = engine.seed_global_workspace()

    assert schema
    assert narrative.unsupported_claims == 0
    assert any(ref.startswith("self_schema:") for ref in narrative.evidence_refs)
    assert any(item.source == "self_schema" for item in staged)



def test_schema_contradiction_requires_new_opposing_evidence() -> None:
    engine = UnarchiEngine()
    for _ in range(3):
        engine.learn(
            observation="A stable local check succeeded.",
            goal="validate release evidence",
            action="run automated release check",
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
    schema = engine.consolidate_self_schema()
    target = next(item for item in schema if item.kind == "capability")
    before = target.to_dict()

    engine.learn(
        observation="One later check failed.",
        goal="validate release evidence",
        action="run automated release check",
        outcome="invalid evidence escaped",
        success=False,
        reward=-0.8,
        predicted_success=0.8,
    )
    revision = engine.reconcile_self_schema_contradiction(
        target.id,
        min_contradictory_evidence=2,
    )

    assert revision.status == "insufficient_evidence"
    assert target.to_dict() == before
    assert revision.contradictory_evidence_refs


def test_strong_contradiction_revises_capability_to_limitation() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"
    for _ in range(4):
        engine.learn(
            observation="Earlier check succeeded.",
            goal=goal,
            action=action,
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
    target = next(
        item for item in engine.consolidate_self_schema()
        if item.kind == "capability"
    )

    for _ in range(8):
        engine.learn(
            observation="Later check failed.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.9,
            predicted_success=0.8,
        )

    revision = engine.reconcile_self_schema_contradiction(
        target.id,
        min_contradictory_evidence=3,
    )
    revised = next(item for item in engine.self_schema if item.id == target.id)

    assert revision.status == "revised"
    assert revision.prior_kind == "capability"
    assert revision.revised_kind == "limitation"
    assert revised.kind == "limitation"
    assert revised.success_rate == 0.333333
    assert revision.contradiction_ratio == 1.0
    assert len(revision.contradictory_evidence_refs) == 8


def test_schema_revision_ablation_keeps_frozen_error_visible() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"
    for _ in range(4):
        engine.learn(
            observation="Earlier check succeeded.",
            goal=goal,
            action=action,
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
    target = next(
        item for item in engine.consolidate_self_schema()
        if item.kind == "capability"
    )
    for _ in range(8):
        engine.learn(
            observation="Later check failed.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.9,
            predicted_success=0.8,
        )

    comparison = engine.compare_self_schema_revision_ablation(
        schema_id=target.id,
        candidates=[
            {
                "action": action,
                "expected_success": 0.55,
                "expected_information_gain": 0.10,
                "risk": 0.10,
            },
            {
                "action": "request independent review",
                "expected_success": 0.60,
                "expected_information_gain": 0.15,
                "risk": 0.10,
            },
        ],
        min_contradictory_evidence=3,
    )

    assert comparison.frozen_action == action
    assert comparison.revised_action == "request independent review"
    assert comparison.choice_changed is True
    assert comparison.predicted_success_delta < 0.0
    assert comparison.revision_causally_active is True


def test_schema_revision_survives_restart_and_has_grounded_narrative() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"
    for _ in range(3):
        engine.learn(
            observation="Earlier check succeeded.",
            goal=goal,
            action=action,
            outcome="correct evidence produced",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
    target = next(
        item for item in engine.consolidate_self_schema()
        if item.kind == "capability"
    )
    for _ in range(6):
        engine.learn(
            observation="Later check failed.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.9,
            predicted_success=0.8,
        )
    engine.reconcile_self_schema_contradiction(
        target.id,
        min_contradictory_evidence=2,
    )

    narrative = engine.build_metacognitive_narrative("schema_revision")
    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.self_schema_revisions == engine.self_schema_revisions
    assert restored.next_self_schema_revision_id == engine.next_self_schema_revision_id
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("self_schema_revision:")
        for ref in narrative.evidence_refs
    )
    assert any(
        ref.startswith("experience:")
        for ref in narrative.evidence_refs
    )



def test_context_split_requires_held_out_predictive_gain() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Sandbox validation {index}.",
            goal=goal,
            action=action,
            outcome="sandbox evidence correct",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production validation {index}.",
            goal=goal,
            action=action,
            outcome="production evidence incorrect",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    result = engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
        min_evidence_per_context=3,
    )

    contextual = {
        item.context_label: item
        for item in engine.active_contextual_self_schema(
            parent_schema_id=parent.id
        )
    }

    assert result.status == "accepted"
    assert result.contextual_holdout_mae < result.global_holdout_mae
    assert result.improvement > 0.0
    assert result.held_out_count == 2
    assert contextual["sandbox"].kind == "capability"
    assert contextual["sandbox"].success_rate == 1.0
    assert contextual["production"].kind == "limitation"
    assert contextual["production"].success_rate == 0.0


def test_context_split_rejects_partition_without_predictive_gain() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    outcomes = [True, False, True, False]
    for index, success in enumerate(outcomes):
        for label in ("sandbox", "production"):
            engine.learn(
                observation=f"{label} validation {index}.",
                goal=goal,
                action=action,
                outcome="evidence observed",
                success=success,
                reward=0.5 if success else -0.5,
                predicted_success=0.5,
            )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    result = engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
        min_evidence_per_context=3,
    )

    assert result.status == "rejected_no_gain"
    assert result.improvement < 0.10
    assert result.context_schema_ids == ()
    assert engine.active_contextual_self_schema(
        parent_schema_id=parent.id
    ) == ()


def test_contextual_schema_ablation_changes_production_choice() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(5):
        engine.learn(
            observation=f"Sandbox release {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.9,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
    )

    comparison = engine.compare_contextual_schema_ablation(
        candidates=[
            {
                "action": action,
                "expected_success": 0.62,
                "expected_information_gain": 0.10,
                "risk": 0.10,
            },
            {
                "action": "request independent review",
                "expected_success": 0.58,
                "expected_information_gain": 0.15,
                "risk": 0.10,
            },
        ],
        context="production release",
    )

    assert comparison.global_action == action
    assert comparison.contextual_action == "request independent review"
    assert comparison.choice_changed is True
    assert comparison.contextual_schema_causally_active is True


def test_contextual_schema_survives_restart_and_is_explainable() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Sandbox release {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    result = engine.decompose_self_schema_context(
        parent.id,
        context_rules={
            "sandbox": ("sandbox",),
            "production": ("production",),
        },
    )
    narrative = engine.build_metacognitive_narrative(
        "contextual_schema"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert result.status == "accepted"
    assert restored.contextual_self_schema == engine.contextual_self_schema
    assert (
        restored.self_schema_decompositions
        == engine.self_schema_decompositions
    )
    assert restored.next_contextual_self_schema_id == (
        engine.next_contextual_self_schema_id
    )
    assert restored.next_self_schema_decomposition_id == (
        engine.next_self_schema_decomposition_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("self_schema_decomposition:")
        for ref in narrative.evidence_refs
    )
    assert any(
        ref.startswith("contextual_self_schema:")
        for ref in narrative.evidence_refs
    )



def _build_context_transfer_test_engine() -> tuple[
    UnarchiEngine,
    int,
    int,
]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Sandbox release {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
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
    return engine, parent.id, source.id


def test_context_transfer_accepts_out_of_sample_supported_context() -> None:
    engine, _, source_id = _build_context_transfer_test_engine()

    for index in range(3):
        engine.learn(
            observation=f"Staging release {index}.",
            goal="validate release evidence",
            action="run automated release check",
            outcome="correct evidence",
            success=True,
            reward=0.7,
            predicted_success=0.5,
        )

    boundary = engine.evaluate_context_transfer(
        source_id,
        target_label="staging",
        target_terms=("staging",),
        min_target_evidence=3,
    )

    assert boundary.status == "accepted"
    assert boundary.evidence_count == 3
    assert boundary.source_holdout_mae == 0.0
    assert boundary.global_holdout_mae == 0.5
    assert boundary.improvement == 0.5
    assert boundary.transfer_strength > 0.0
    assert boundary.evidence_refs
    source = next(
        item for item in engine.contextual_self_schema if item.id == source_id
    )
    parent = next(
        item
        for item in engine.self_schema
        if item.id == source.parent_schema_id
    )
    already_used = set(source.evidence_refs) | set(parent.evidence_refs)
    assert not already_used.intersection(boundary.evidence_refs)


def test_context_transfer_abstains_when_source_generalizes_badly() -> None:
    engine, _, source_id = _build_context_transfer_test_engine()

    for index in range(3):
        engine.learn(
            observation=f"Emergency release {index}.",
            goal="validate release evidence",
            action="run automated release check",
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    boundary = engine.evaluate_context_transfer(
        source_id,
        target_label="emergency",
        target_terms=("emergency",),
        min_target_evidence=3,
    )

    assert boundary.status == "abstained_no_gain"
    assert boundary.source_holdout_mae == 1.0
    assert boundary.global_holdout_mae == 0.5
    assert boundary.improvement == -0.5
    assert boundary.transfer_strength == 0.0
    assert engine.active_context_transfer_boundaries() == ()


def test_context_transfer_ablation_changes_supported_target_choice() -> None:
    engine, _, source_id = _build_context_transfer_test_engine()

    for index in range(3):
        engine.learn(
            observation=f"Staging release {index}.",
            goal="validate release evidence",
            action="run automated release check",
            outcome="correct evidence",
            success=True,
            reward=0.7,
            predicted_success=0.5,
        )
    engine.evaluate_context_transfer(
        source_id,
        target_label="staging",
        target_terms=("staging",),
    )

    comparison = engine.compare_context_transfer_ablation(
        candidates=[
            {
                "action": "run automated release check",
                "expected_success": 0.50,
                "expected_information_gain": 0.10,
                "risk": 0.10,
            },
            {
                "action": "request independent review",
                "expected_success": 0.58,
                "expected_information_gain": 0.15,
                "risk": 0.10,
            },
        ],
        context="staging release",
    )

    assert comparison.transfer_action == "run automated release check"
    assert comparison.no_transfer_action == "request independent review"
    assert comparison.choice_changed is True
    assert comparison.transfer_causally_active is True


def test_context_transfer_persists_and_has_grounded_narrative() -> None:
    engine, _, source_id = _build_context_transfer_test_engine()

    for index in range(3):
        engine.learn(
            observation=f"Staging release {index}.",
            goal="validate release evidence",
            action="run automated release check",
            outcome="correct evidence",
            success=True,
            reward=0.7,
            predicted_success=0.5,
        )
    boundary = engine.evaluate_context_transfer(
        source_id,
        target_label="staging",
        target_terms=("staging",),
    )
    narrative = engine.build_metacognitive_narrative(
        "context_transfer"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert boundary.status == "accepted"
    assert restored.context_transfer_boundaries == (
        engine.context_transfer_boundaries
    )
    assert restored.next_context_transfer_boundary_id == (
        engine.next_context_transfer_boundary_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_transfer:")
        for ref in narrative.evidence_refs
    )
    assert any(
        ref.startswith("contextual_self_schema:")
        for ref in narrative.evidence_refs
    )



def test_latent_context_discovery_selects_predictive_terms() -> None:
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
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release validation {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    discovery = engine.discover_latent_context_hypotheses(
        parent.id,
        max_candidates=3,
    )
    selected = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )

    assert discovery.status == "selected"
    assert discovery.proposed_count <= 3
    assert discovery.validated_count >= 1
    assert selected.validation_status == "selected"
    assert {
        selected.positive_term,
        selected.negative_term,
    } == {"sandbox", "production"}
    assert selected.holdout_improvement > 0.0
    assert selected.decomposition_id == discovery.selected_decomposition_id

    contextual = {
        item.context_label: item.kind
        for item in engine.active_contextual_self_schema(
            parent_schema_id=parent.id
        )
    }
    assert contextual["sandbox"] == "capability"
    assert contextual["production"] == "limitation"


def test_latent_context_discovery_rejects_spurious_split() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    alpha_outcomes = [True, True, True, False]
    beta_outcomes = [False, False, False, True]
    for index, success in enumerate(alpha_outcomes):
        engine.learn(
            observation=f"Alpha release validation {index}.",
            goal=goal,
            action=action,
            outcome="evidence observed",
            success=success,
            reward=0.6 if success else -0.6,
            predicted_success=0.5,
        )
    for index, success in enumerate(beta_outcomes):
        engine.learn(
            observation=f"Beta release validation {index}.",
            goal=goal,
            action=action,
            outcome="evidence observed",
            success=success,
            reward=0.6 if success else -0.6,
            predicted_success=0.5,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    discovery = engine.discover_latent_context_hypotheses(
        parent.id,
        max_candidates=2,
        min_rate_contrast=0.40,
    )
    hypotheses = [
        item
        for item in engine.latent_context_hypotheses
        if item.id in discovery.hypothesis_ids
    ]

    assert discovery.status == "no_validated_hypothesis"
    assert discovery.proposed_count >= 1
    assert discovery.validated_count == 0
    assert all(
        item.validation_status == "rejected_validation"
        for item in hypotheses
    )
    assert engine.active_contextual_self_schema(
        parent_schema_id=parent.id
    ) == ()


def test_latent_context_discovery_persists_and_is_explainable() -> None:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Sandbox release {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    narrative = engine.build_metacognitive_narrative(
        "latent_context"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert discovery.status == "selected"
    assert restored.latent_context_hypotheses == (
        engine.latent_context_hypotheses
    )
    assert restored.latent_context_discoveries == (
        engine.latent_context_discoveries
    )
    assert restored.next_latent_context_hypothesis_id == (
        engine.next_latent_context_hypothesis_id
    )
    assert restored.next_latent_context_discovery_id == (
        engine.next_latent_context_discovery_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("latent_context_discovery:")
        for ref in narrative.evidence_refs
    )
    assert any(
        ref.startswith("latent_context_hypothesis:")
        for ref in narrative.evidence_refs
    )



def _build_context_causality_test_engine() -> tuple[
    UnarchiEngine,
    int,
]:
    engine = UnarchiEngine()
    goal = "validate release evidence"
    action = "run automated release check"

    for index in range(4):
        engine.learn(
            observation=f"Sandbox release {index}.",
            goal=goal,
            action=action,
            outcome="correct evidence",
            success=True,
            reward=0.8,
            predicted_success=0.5,
        )
        engine.learn(
            observation=f"Production release {index}.",
            goal=goal,
            action=action,
            outcome="invalid evidence escaped",
            success=False,
            reward=-0.8,
            predicted_success=0.7,
        )

    parent = next(
        item
        for item in engine.consolidate_self_schema()
        if item.kind == "mixed"
    )
    discovery = engine.discover_latent_context_hypotheses(parent.id)
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == discovery.selected_hypothesis_id
    )
    return engine, hypothesis.id


def test_context_causality_confounded_trial_cannot_upgrade_hypothesis() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    trial = engine.propose_context_causality_intervention(
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=3,
    )
    observed = engine.observe_context_causality_intervention(
        trial.id,
        observed_target_success_rate=1.0,
        observed_signature="code=v2;load=normal;data=fixed",
        sample_count=3,
        evidence_refs=("test:confounded",),
    )
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )

    assert observed.status == "confounded"
    assert observed.competing_variables_held_constant is False
    assert hypothesis.causal_status == "unverified"
    assert hypothesis.causal_evidence_refs == ()


def test_context_causality_clean_intervention_supports_hypothesis() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    trial = engine.propose_context_causality_intervention(
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=4,
    )
    observed = engine.observe_context_causality_intervention(
        trial.id,
        observed_target_success_rate=1.0,
        observed_signature="code=v1;load=normal;data=fixed",
        sample_count=4,
        evidence_refs=("test:clean",),
    )
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )

    assert observed.status == "intervention_supported"
    assert observed.competing_variables_held_constant is True
    assert observed.predicted_direction_followed is True
    assert observed.causal_strength is not None
    assert observed.causal_strength >= 0.35
    assert hypothesis.causal_status == "intervention_supported"
    assert f"context_causality_trial:{trial.id}" in (
        hypothesis.causal_evidence_refs
    )


def test_context_causality_persists_and_is_explainable() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    trial = engine.propose_context_causality_intervention(
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=3,
    )
    engine.observe_context_causality_intervention(
        trial.id,
        observed_target_success_rate=1.0,
        observed_signature="code=v1;load=normal;data=fixed",
        sample_count=3,
        evidence_refs=("test:causal",),
    )
    narrative = engine.build_metacognitive_narrative(
        "context_causality"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert restored.context_causality_trials == engine.context_causality_trials
    assert restored.latent_context_hypotheses == (
        engine.latent_context_hypotheses
    )
    assert restored.next_context_causality_trial_id == (
        engine.next_context_causality_trial_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_causality_trial:")
        for ref in narrative.evidence_refs
    )
    assert any(
        ref.startswith("latent_context_hypothesis:")
        for ref in narrative.evidence_refs
    )



def _observe_context_trial(
    engine: UnarchiEngine,
    hypothesis_id: int,
    *,
    from_context: str,
    to_context: str,
    observed_target_success_rate: float,
    evidence_ref: str,
):
    trial = engine.propose_context_causality_intervention(
        hypothesis_id,
        from_context=from_context,
        to_context=to_context,
        controlled_signature="code=v1;load=normal;data=fixed",
        min_samples=4,
    )
    return engine.observe_context_causality_intervention(
        trial.id,
        observed_target_success_rate=observed_target_success_rate,
        observed_signature="code=v1;load=normal;data=fixed",
        sample_count=4,
        evidence_refs=(evidence_ref,),
    )


def test_context_causal_stability_requires_replication_and_reversal() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    forward_a = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        observed_target_success_rate=1.0,
        evidence_ref="batch:forward:a",
    )
    forward_b = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        observed_target_success_rate=1.0,
        evidence_ref="batch:forward:b",
    )
    reverse = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="sandbox",
        to_context="production",
        observed_target_success_rate=0.0,
        evidence_ref="batch:reverse:a",
    )

    assessment = engine.assess_context_causal_stability(
        hypothesis_id,
        forward_trial_ids=(forward_a.id, forward_b.id),
        reverse_trial_ids=(reverse.id,),
    )
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_causal_stability"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert assessment.status == "replicated_reversible"
    assert assessment.independent_forward_batches == 2
    assert assessment.independent_reverse_batches == 1
    assert assessment.forward_replication_rate == 1.0
    assert assessment.reverse_replication_rate == 1.0
    assert assessment.reversal_direction_followed is True
    assert assessment.confidence >= 0.35
    assert hypothesis.causal_status == "replicated_reversible"
    assert restored.context_causal_stability_assessments == (
        engine.context_causal_stability_assessments
    )
    assert restored.latent_context_hypotheses == (
        engine.latent_context_hypotheses
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_causal_stability_assessment:")
        for ref in narrative.evidence_refs
    )


def test_context_causal_stability_rejects_reused_replication_evidence() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    forward_a = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        observed_target_success_rate=1.0,
        evidence_ref="batch:shared",
    )
    forward_b = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="production",
        to_context="sandbox",
        observed_target_success_rate=1.0,
        evidence_ref="batch:shared",
    )
    reverse = _observe_context_trial(
        engine,
        hypothesis_id,
        from_context="sandbox",
        to_context="production",
        observed_target_success_rate=0.0,
        evidence_ref="batch:reverse",
    )

    assessment = engine.assess_context_causal_stability(
        hypothesis_id,
        forward_trial_ids=(forward_a.id, forward_b.id),
        reverse_trial_ids=(reverse.id,),
    )
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )

    assert assessment.status == "insufficient_replication"
    assert assessment.independent_forward_batches == 1
    assert hypothesis.causal_status == "intervention_supported"
    assert engine.snapshot()["replicated_reversible_context_count"] == 0



def _build_environment_stability(
    engine: UnarchiEngine,
    hypothesis_id: int,
    *,
    signature: str,
    prefix: str,
    reverse_supported: bool = True,
):
    forward_ids: list[int] = []
    for batch in ("a", "b"):
        trial = engine.propose_context_causality_intervention(
            hypothesis_id,
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
        hypothesis_id,
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
        hypothesis_id,
        forward_trial_ids=forward_ids,
        reverse_trial_ids=(reverse.id,),
    )


def test_context_causal_invariance_across_distinct_environments() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="env:normal",
    )
    high_load = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=high;data=fixed",
        prefix="env:high",
    )

    assessment = engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, high_load.id),
    )
    hypothesis = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_causal_invariance"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert assessment.status == "environment_invariant"
    assert assessment.distinct_environment_count == 2
    assert assessment.stable_environment_count == 2
    assert assessment.effect_direction_consistent is True
    assert assessment.minimum_causal_strength >= 0.35
    assert assessment.boundary_signatures == ()
    assert hypothesis.causal_status == "environment_invariant"
    assert restored.context_causal_invariance_assessments == (
        engine.context_causal_invariance_assessments
    )
    assert restored.latent_context_hypotheses == (
        engine.latent_context_hypotheses
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_causal_invariance_assessment:")
        for ref in narrative.evidence_refs
    )


def test_context_causal_invariance_records_environment_boundary() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="env:normal",
    )
    high_load = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=high;data=fixed",
        prefix="env:high",
        reverse_supported=False,
    )

    before = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )
    assessment = engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, high_load.id),
    )
    after = next(
        item
        for item in engine.latent_context_hypotheses
        if item.id == hypothesis_id
    )

    assert normal.status == "replicated_reversible"
    assert high_load.status != "replicated_reversible"
    assert before.causal_status == "replicated_reversible"
    assert assessment.status == "environment_bounded"
    assert assessment.distinct_environment_count == 2
    assert assessment.stable_environment_count == 1
    assert "code=v1;load=high;data=fixed" in assessment.boundary_signatures
    assert after.causal_status == "replicated_reversible"
    assert engine.snapshot()["environment_invariant_context_count"] == 0



def test_active_boundary_discovery_selects_low_risk_informative_probe() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="boundary:normal",
    )
    extreme = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=extreme;data=fixed",
        prefix="boundary:extreme",
        reverse_supported=False,
    )
    bounded = engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, extreme.id),
    )

    plan = engine.plan_context_boundary_discovery(
        hypothesis_id,
        invariance_assessment_id=bounded.id,
        candidate_risks={
            "code=v1;load=high;data=fixed": 0.08,
            "code=v1;load=normal;data=shifted": 0.05,
            "code=v2;load=extreme;data=shifted": 0.40,
        },
    )

    assert bounded.status == "environment_bounded"
    assert plan.status == "planned"
    assert plan.selected_signature == "code=v1;load=high;data=fixed"
    assert plan.selected_risk == 0.08
    assert plan.selected_information_gain > 0.0
    assert plan.selected_priority_score > 0.0
    assert plan.changed_dimensions == ("load",)
    assert plan.external_execution_allowed is False
    assert plan.paid_actions_allowed is False
    assert plan.reversible_only is True
    assert "code=v2;load=extreme;data=shifted" not in plan.candidate_signatures


def test_active_boundary_discovery_resolves_from_supplied_stability_evidence() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="resolve:normal",
    )
    extreme = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=extreme;data=fixed",
        prefix="resolve:extreme",
        reverse_supported=False,
    )
    bounded = engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    plan = engine.plan_context_boundary_discovery(
        hypothesis_id,
        invariance_assessment_id=bounded.id,
        candidate_risks={
            "code=v1;load=high;data=fixed": 0.08,
            "code=v1;load=normal;data=shifted": 0.05,
        },
    )
    selected = _build_environment_stability(
        engine,
        hypothesis_id,
        signature=plan.selected_signature,
        prefix="resolve:selected",
    )

    resolved = engine.observe_context_boundary_discovery(
        plan.id,
        stability_assessment_id=selected.id,
    )
    narrative = engine.build_metacognitive_narrative(
        "context_boundary_discovery"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert resolved.status == "resolved"
    assert resolved.outcome_status == "expanded_valid_region"
    assert resolved.outcome_stability_assessment_id == selected.id
    assert resolved.uncertainty_reduction is not None
    assert resolved.uncertainty_reduction > 0.0
    assert restored.context_boundary_discovery_plans == (
        engine.context_boundary_discovery_plans
    )
    assert restored.next_context_boundary_discovery_plan_id == (
        engine.next_context_boundary_discovery_plan_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_boundary_discovery_plan:")
        for ref in narrative.evidence_refs
    )



def test_context_causal_validity_map_is_boundary_aware_and_persistent() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal_signature = "code=v1;load=normal;data=fixed"
    extreme_signature = "code=v1;load=extreme;data=fixed"
    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature=normal_signature,
        prefix="map:normal",
    )
    extreme = _build_environment_stability(
        engine,
        hypothesis_id,
        signature=extreme_signature,
        prefix="map:extreme",
        reverse_supported=False,
    )
    bounded = engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, extreme.id),
    )

    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis_id,
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
    narrative = engine.build_metacognitive_narrative("context_validity_map")
    restored = UnarchiEngine.from_export(engine.export_state())

    assert bounded.status == "environment_bounded"
    assert validity_map.tested_valid_signatures == (normal_signature,)
    assert validity_map.tested_invalid_signatures == (extreme_signature,)
    assert validity_map.source_invariance_assessment_ids == (bounded.id,)
    assert exact_valid.status == "tested_valid"
    assert exact_invalid.status == "tested_invalid"
    assert nearby.status == "supported_nearby"
    assert nearby.nearest_valid_distance == 1
    assert nearby.nearest_invalid_distance == 2
    assert ambiguous.status == "unknown"
    assert ambiguous.nearest_valid_distance == 1
    assert ambiguous.nearest_invalid_distance == 1
    assert restored.context_causal_validity_maps == (
        engine.context_causal_validity_maps
    )
    assert restored.next_context_causal_validity_map_id == (
        engine.next_context_causal_validity_map_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_causal_validity_map:")
        for ref in narrative.evidence_refs
    )


def test_context_causal_validity_map_reconsolidates_latest_evidence() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal_signature = "code=v1;load=normal;data=fixed"
    extreme_signature = "code=v1;load=extreme;data=fixed"
    _build_environment_stability(
        engine,
        hypothesis_id,
        signature=normal_signature,
        prefix="map:update:normal:stable",
    )
    _build_environment_stability(
        engine,
        hypothesis_id,
        signature=extreme_signature,
        prefix="map:update:extreme:failed",
        reverse_supported=False,
    )
    first = engine.consolidate_context_causal_validity_map(hypothesis_id)

    _build_environment_stability(
        engine,
        hypothesis_id,
        signature=extreme_signature,
        prefix="map:update:extreme:recovered",
    )
    second = engine.consolidate_context_causal_validity_map(hypothesis_id)

    _build_environment_stability(
        engine,
        hypothesis_id,
        signature=normal_signature,
        prefix="map:update:normal:failed",
        reverse_supported=False,
    )
    third = engine.consolidate_context_causal_validity_map(hypothesis_id)

    assert normal_signature in first.tested_valid_signatures
    assert extreme_signature in first.tested_invalid_signatures
    assert extreme_signature in second.tested_valid_signatures
    assert extreme_signature not in second.tested_invalid_signatures
    assert normal_signature in third.tested_invalid_signatures
    assert normal_signature not in third.tested_valid_signatures
    assert engine.snapshot()["context_causal_validity_map_count"] == 3



def _validity_gate_candidates() -> list[dict[str, object]]:
    return [
        {
            "action": "run automated release check",
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


def test_context_validity_gate_uses_causal_context_only_in_supported_regions() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal_signature = "code=v1;load=normal;data=fixed"
    extreme_signature = "code=v1;load=extreme;data=fixed"
    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature=normal_signature,
        prefix="gate:normal",
    )
    extreme = _build_environment_stability(
        engine,
        hypothesis_id,
        signature=extreme_signature,
        prefix="gate:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis_id,
        max_generalization_distance=1,
    )
    candidates = _validity_gate_candidates()

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

    assert supported.classification_status == "tested_valid"
    assert supported.causal_context_allowed is True
    assert supported.gated_action == supported.causal_enabled_action
    assert supported.gated_action == "request independent review"
    assert supported.choice_changed_vs_causal_ablated is True

    assert invalid.classification_status == "tested_invalid"
    assert invalid.causal_context_allowed is False
    assert invalid.gated_action == invalid.causal_ablated_action
    assert invalid.gated_action == "run automated release check"
    assert invalid.choice_changed_vs_causal_enabled is True

    assert nearby.classification_status == "supported_nearby"
    assert nearby.causal_context_allowed is True
    assert nearby.gated_action == nearby.causal_enabled_action

    assert unknown.classification_status == "unknown"
    assert unknown.causal_context_allowed is False
    assert unknown.gated_action == unknown.causal_ablated_action

    assert all(
        item.gated_matches_expected_path
        for item in (supported, invalid, nearby, unknown)
    )
    assert engine.snapshot()["context_validity_decision_gate_count"] == 4
    assert engine.snapshot()["context_validity_abstention_count"] == 2


def test_context_validity_gate_persists_and_is_explainable() -> None:
    engine, hypothesis_id = _build_context_causality_test_engine()

    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="gate:persist:normal",
    )
    invalid = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=extreme;data=fixed",
        prefix="gate:persist:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, invalid.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis_id
    )
    gate = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature="code=v1;load=extreme;data=fixed",
        candidates=_validity_gate_candidates(),
        context="production release",
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_gate"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert gate.causal_context_allowed is False
    assert restored.context_validity_decision_gates == (
        engine.context_validity_decision_gates
    )
    assert restored.next_context_validity_decision_gate_id == (
        engine.next_context_validity_decision_gate_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_decision_gate:")
        for ref in narrative.evidence_refs
    )



def _build_validity_calibration_engine():
    engine, hypothesis_id = _build_context_causality_test_engine()
    normal = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=normal;data=fixed",
        prefix="calibrate:normal",
    )
    extreme = _build_environment_stability(
        engine,
        hypothesis_id,
        signature="code=v1;load=extreme;data=fixed",
        prefix="calibrate:extreme",
        reverse_supported=False,
    )
    engine.assess_context_causal_invariance(
        hypothesis_id,
        stability_assessment_ids=(normal.id, extreme.id),
    )
    validity_map = engine.consolidate_context_causal_validity_map(
        hypothesis_id,
        max_generalization_distance=1,
    )
    return engine, validity_map


def test_gate_outcome_requires_matched_action_evidence() -> None:
    engine, validity_map = _build_validity_calibration_engine()
    gate = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature="code=v1;load=normal;data=shifted",
        candidates=_validity_gate_candidates(),
        context="production release",
    )

    try:
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                gate.gated_action: True,
            },
            evidence_refs=("outcome:partial",),
        )
    except ValueError as exc:
        assert "every policy-selected action" in str(exc)
    else:
        raise AssertionError("partial counterfactual evidence must be rejected")


def test_gate_calibration_can_strengthen_and_revoke_nearby_support() -> None:
    engine, validity_map = _build_validity_calibration_engine()
    candidates = _validity_gate_candidates()
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
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"outcome:good:{index}",),
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
                "run automated release check": True,
                "request independent review": False,
            },
            evidence_refs=(f"outcome:bad:{index}",),
        )

    bad_calibration = engine.calibrate_context_validity_region(
        validity_map.id,
        environment_signature=bad_signature,
    )
    bad_after = engine.classify_context_causal_validity(
        validity_map.id,
        environment_signature=bad_signature,
    )
    post_revoke = engine.evaluate_context_validity_gated_decision(
        validity_map.id,
        environment_signature=bad_signature,
        candidates=candidates,
        context="production release",
    )

    assert good_before.status == "supported_nearby"
    assert good_calibration.status == "nearby_support_calibrated"
    assert good_calibration.gated_advantage_vs_alternative >= 0.05
    assert good_after.status == "supported_nearby"
    assert good_after.confidence > good_before.confidence

    assert bad_before.status == "supported_nearby"
    assert bad_calibration.status == "nearby_support_revoked"
    assert bad_calibration.gated_advantage_vs_alternative <= -0.05
    assert bad_after.status == "unknown"
    assert bad_after.confidence == 0.0
    assert post_revoke.classification_status == "unknown"
    assert post_revoke.causal_context_allowed is False
    assert post_revoke.gated_action == post_revoke.causal_ablated_action


def test_gate_calibration_persists_and_is_explainable() -> None:
    engine, validity_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"

    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            validity_map.id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"outcome:persist:{index}",),
        )

    calibration = engine.calibrate_context_validity_region(
        validity_map.id,
        environment_signature=signature,
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_calibration"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert calibration.status == "nearby_support_calibrated"
    assert restored.context_validity_gate_outcomes == (
        engine.context_validity_gate_outcomes
    )
    assert restored.context_validity_region_calibrations == (
        engine.context_validity_region_calibrations
    )
    assert restored.next_context_validity_gate_outcome_id == (
        engine.next_context_validity_gate_outcome_id
    )
    assert restored.next_context_validity_region_calibration_id == (
        engine.next_context_validity_region_calibration_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_region_calibration:")
        for ref in narrative.evidence_refs
    )



def _calibrate_validity_signature(
    engine: UnarchiEngine,
    validity_map_id: int,
    signature: str,
    *,
    causal_path_should_win: bool,
    prefix: str,
):
    for index in range(3):
        gate = engine.evaluate_context_validity_gated_decision(
            validity_map_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": not causal_path_should_win,
                "request independent review": causal_path_should_win,
            },
            evidence_refs=(f"{prefix}:{index}",),
        )
    return engine.calibrate_context_validity_region(
        validity_map_id,
        environment_signature=signature,
    )


def test_validity_map_revision_freezes_calibrated_expansion_and_contraction() -> None:
    engine, base_map = _build_validity_calibration_engine()
    good_signature = "code=v1;load=normal;data=shifted"
    bad_signature = "code=v2;load=normal;data=fixed"

    good = _calibrate_validity_signature(
        engine,
        base_map.id,
        good_signature,
        causal_path_should_win=True,
        prefix="revision:good",
    )
    bad = _calibrate_validity_signature(
        engine,
        base_map.id,
        bad_signature,
        causal_path_should_win=False,
        prefix="revision:bad",
    )

    revised = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(good.id, bad.id),
    )
    good_status = engine.classify_context_causal_validity(
        revised.id,
        environment_signature=good_signature,
    )
    bad_status = engine.classify_context_causal_validity(
        revised.id,
        environment_signature=bad_signature,
    )

    assert revised.parent_map_id == base_map.id
    assert revised.revision_number == 2
    assert revised.tested_valid_signatures == base_map.tested_valid_signatures
    assert revised.tested_invalid_signatures == base_map.tested_invalid_signatures
    assert good_signature in revised.calibrated_supported_signatures
    assert bad_signature in revised.revoked_inferred_signatures
    assert good_status.status == "supported_nearby"
    assert bad_status.status == "unknown"
    assert any(
        reason.startswith("expand inferred support")
        for reason in revised.revision_reasons
    )
    assert any(
        reason.startswith("contract inferred support")
        for reason in revised.revision_reasons
    )


def test_validity_map_revision_is_immutable_until_child_revision() -> None:
    engine, base_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"

    positive = _calibrate_validity_signature(
        engine,
        base_map.id,
        signature,
        causal_path_should_win=True,
        prefix="revision:positive",
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    before = engine.classify_context_causal_validity(
        revision_two.id,
        environment_signature=signature,
    )

    reversal = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="revision:reversal",
    )
    unchanged = engine.classify_context_causal_validity(
        revision_two.id,
        environment_signature=signature,
    )
    revision_three = engine.revise_context_causal_validity_map(
        revision_two.id,
        calibration_ids=(reversal.id,),
    )
    changed = engine.classify_context_causal_validity(
        revision_three.id,
        environment_signature=signature,
    )

    assert before.status == "supported_nearby"
    assert reversal.status == "nearby_support_revoked"
    assert unchanged.status == "supported_nearby"
    assert revision_three.parent_map_id == revision_two.id
    assert revision_three.revision_number == 3
    assert signature in revision_three.revoked_inferred_signatures
    assert signature not in revision_three.calibrated_supported_signatures
    assert changed.status == "unknown"


def test_validity_map_revision_persists_and_preserves_exact_evidence() -> None:
    engine, base_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"
    calibration = _calibrate_validity_signature(
        engine,
        base_map.id,
        signature,
        causal_path_should_win=True,
        prefix="revision:persist",
    )
    revised = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(calibration.id,),
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_revision"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert revised.tested_valid_signatures == base_map.tested_valid_signatures
    assert revised.tested_invalid_signatures == base_map.tested_invalid_signatures
    assert restored.context_causal_validity_maps == engine.context_causal_validity_maps
    assert restored.next_context_causal_validity_map_id == (
        engine.next_context_causal_validity_map_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert engine.snapshot()["context_causal_validity_map_revision_count"] == 1
    assert narrative.unsupported_claims == 0
    assert any(
        ref == f"context_causal_validity_map:{revised.id}"
        for ref in narrative.evidence_refs
    )



def _build_three_revision_validity_engine():
    engine, base_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"

    positive = _calibrate_validity_signature(
        engine,
        base_map.id,
        signature,
        causal_path_should_win=True,
        prefix="selection:positive",
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    negative = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="selection:negative",
    )
    revision_three = engine.revise_context_causal_validity_map(
        revision_two.id,
        calibration_ids=(negative.id,),
    )
    return engine, base_map, revision_two, revision_three, signature


def test_validity_map_selection_activates_latest_intact_lineage() -> None:
    (
        engine,
        base_map,
        revision_two,
        revision_three,
        signature,
    ) = _build_three_revision_validity_engine()

    selection = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        reason="activate latest tested revision",
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )
    decision = engine.evaluate_active_context_validity_gated_decision(
        base_map.hypothesis_id,
        environment_signature=signature,
        candidates=_validity_gate_candidates(),
        context="production release",
    )

    assert selection.action == "activate"
    assert selection.selected_map_id == revision_three.id
    assert selection.lineage == (
        base_map.id,
        revision_two.id,
        revision_three.id,
    )
    assert active is not None
    assert active.id == revision_three.id
    assert decision.classification_status == "unknown"
    assert decision.causal_context_allowed is False


def test_validity_map_rollback_preserves_descendant_and_rejects_sibling() -> None:
    (
        engine,
        base_map,
        revision_two,
        revision_three,
        _,
    ) = _build_three_revision_validity_engine()
    engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        reason="activate latest revision",
    )

    sibling_calibration = next(
        item
        for item in engine.context_validity_region_calibrations
        if item.validity_map_id == base_map.id
    )
    sibling = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(sibling_calibration.id,),
    )

    try:
        engine.rollback_context_validity_map(
            base_map.hypothesis_id,
            target_map_id=sibling.id,
            reason="invalid sibling rollback",
        )
    except ValueError as exc:
        assert "not an ancestor" in str(exc)
    else:
        raise AssertionError("rollback to a sibling revision must be rejected")

    rollback = engine.rollback_context_validity_map(
        base_map.hypothesis_id,
        target_map_id=revision_two.id,
        reason="rollback after descendant policy warning",
        evidence_refs=("rollback:warning",),
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert rollback.action == "rollback"
    assert rollback.previous_map_id == revision_three.id
    assert rollback.selected_map_id == revision_two.id
    assert active is not None
    assert active.id == revision_two.id
    assert any(
        item.id == revision_three.id
        for item in engine.context_causal_validity_maps
    )
    assert any(
        item.id == sibling.id
        for item in engine.context_causal_validity_maps
    )


def test_validity_map_selection_persists_and_can_readvance_after_rollback() -> None:
    (
        engine,
        base_map,
        revision_two,
        revision_three,
        _,
    ) = _build_three_revision_validity_engine()
    engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        reason="activate latest revision",
    )
    engine.rollback_context_validity_map(
        base_map.hypothesis_id,
        target_map_id=revision_two.id,
        reason="temporary rollback for review",
    )
    readvance = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        reason="review complete; re-advance intact lineage",
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_selection"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert readvance.action == "advance"
    assert readvance.selected_map_id == revision_three.id
    assert restored.active_context_validity_map_ids == (
        engine.active_context_validity_map_ids
    )
    assert restored.context_validity_map_selection_history == (
        engine.context_validity_map_selection_history
    )
    assert restored.next_context_validity_map_selection_id == (
        engine.next_context_validity_map_selection_id
    )
    assert restored_active is not None
    assert restored_active.id == revision_three.id
    assert restored.snapshot() == engine.snapshot()
    assert engine.snapshot()["context_validity_map_rollback_count"] == 1
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_map_selection:")
        for ref in narrative.evidence_refs
    )



def _build_active_degradation_watch_engine():
    engine, base_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"
    positive = _calibrate_validity_signature(
        engine,
        base_map.id,
        signature,
        causal_path_should_win=True,
        prefix="degradation:base_positive",
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    selection = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        map_id=revision_two.id,
        reason="activate revision for degradation watch",
    )
    return engine, base_map, revision_two, selection, positive, signature


def test_degradation_watch_uses_only_post_activation_calibration() -> None:
    engine, base_map = _build_validity_calibration_engine()
    signature = "code=v1;load=normal;data=shifted"
    positive = _calibrate_validity_signature(
        engine,
        base_map.id,
        signature,
        causal_path_should_win=True,
        prefix="degradation:pre:positive",
    )
    revision_two = engine.revise_context_causal_validity_map(
        base_map.id,
        calibration_ids=(positive.id,),
    )
    historical_negative = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="degradation:pre:negative",
    )
    selection = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        map_id=revision_two.id,
        reason="activate after historical calibration",
    )

    watch = engine.watch_active_context_validity_degradation(
        base_map.hypothesis_id
    )

    assert historical_negative.id == selection.calibration_watermark_id
    assert watch.status == "insufficient_post_activation_evidence"
    assert watch.observed_calibration_ids == ()
    assert watch.recommended_map_id is None


def test_degradation_watch_recommends_ancestor_without_auto_rollback() -> None:
    (
        engine,
        base_map,
        revision_two,
        selection,
        positive,
        signature,
    ) = _build_active_degradation_watch_engine()

    negative = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="degradation:active:negative",
    )
    watch = engine.watch_active_context_validity_degradation(
        base_map.hypothesis_id
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert negative.id > selection.calibration_watermark_id
    assert watch.status == "rollback_recommended"
    assert watch.active_map_id == revision_two.id
    assert watch.recommended_map_id == base_map.id
    assert watch.recommended_revision_number == 1
    assert watch.degraded_signatures == (signature,)
    assert watch.mean_active_advantage <= -0.05
    assert watch.ancestor_support_calibration_ids == (positive.id,)
    assert active is not None
    assert active.id == revision_two.id
    assert engine.snapshot()["context_validity_map_rollback_count"] == 0
    assert engine.snapshot()["rollback_recommendation_count"] == 1


def test_degradation_watch_stays_stable_on_favorable_post_activation_evidence() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        _,
        signature,
    ) = _build_active_degradation_watch_engine()

    favorable = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=True,
        prefix="degradation:active:positive",
    )
    watch = engine.watch_active_context_validity_degradation(
        base_map.hypothesis_id
    )

    assert favorable.status == "nearby_support_calibrated"
    assert watch.status == "stable"
    assert watch.degraded_signatures == ()
    assert watch.recommended_map_id is None


def test_degradation_watch_persists_and_is_explainable() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        _,
        signature,
    ) = _build_active_degradation_watch_engine()
    _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="degradation:persist:negative",
    )
    watch = engine.watch_active_context_validity_degradation(
        base_map.hypothesis_id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_degradation"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert watch.status == "rollback_recommended"
    assert restored.context_validity_degradation_watches == (
        engine.context_validity_degradation_watches
    )
    assert restored.next_context_validity_degradation_watch_id == (
        engine.next_context_validity_degradation_watch_id
    )
    assert restored_active is not None
    assert restored_active.id == revision_two.id
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_degradation_watch:")
        for ref in narrative.evidence_refs
    )



def _build_resolution_recommendation_engine():
    (
        engine,
        base_map,
        revision_two,
        _,
        positive,
        signature,
    ) = _build_active_degradation_watch_engine()
    negative = _calibrate_validity_signature(
        engine,
        revision_two.id,
        signature,
        causal_path_should_win=False,
        prefix="resolution:active:negative",
    )
    watch = engine.watch_active_context_validity_degradation(
        base_map.hypothesis_id
    )
    assert watch.status == "rollback_recommended"
    return (
        engine,
        base_map,
        revision_two,
        positive,
        negative,
        watch,
        signature,
    )


def test_recommendation_defer_and_dismiss_do_not_move_active_pointer() -> None:
    (
        deferred_engine,
        deferred_base,
        deferred_revision,
        _,
        _,
        deferred_watch,
        _,
    ) = _build_resolution_recommendation_engine()
    deferred = deferred_engine.resolve_context_validity_degradation_watch(
        deferred_watch.id,
        decision="defer",
        reason="collect more evidence",
    )
    deferred_active = deferred_engine.active_context_causal_validity_map(
        deferred_base.hypothesis_id
    )

    (
        dismissed_engine,
        dismissed_base,
        dismissed_revision,
        _,
        _,
        dismissed_watch,
        _,
    ) = _build_resolution_recommendation_engine()
    dismissed = dismissed_engine.resolve_context_validity_degradation_watch(
        dismissed_watch.id,
        decision="dismiss",
        reason="operator rejects recommendation",
    )
    dismissed_active = dismissed_engine.active_context_causal_validity_map(
        dismissed_base.hypothesis_id
    )

    assert deferred.decision == "defer"
    assert deferred.rollback_selection_id is None
    assert deferred_active is not None
    assert deferred_active.id == deferred_revision.id
    assert dismissed.decision == "dismiss"
    assert dismissed.rollback_selection_id is None
    assert dismissed_active is not None
    assert dismissed_active.id == dismissed_revision.id


def test_accepted_recommendation_blocks_readvance_until_rollback_improves() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="accept evidence-backed rollback",
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert active is not None
    assert active.id == base_map.id
    assert accepted.rollback_selection_id is not None

    try:
        engine.select_context_validity_map_revision(
            base_map.hypothesis_id,
            map_id=revision_two.id,
            reason="premature re-advance",
        )
    except ValueError as exc:
        assert "re-advance blocked" in str(exc)
    else:
        raise AssertionError("descendant re-advance must be blocked")

    initial = engine.validate_context_validity_rollback(accepted.id)
    assert initial.status == "insufficient_post_rollback_evidence"
    assert initial.reactivation_allowed is False

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:rollback:positive:{index}",),
        )

    improved = engine.validate_context_validity_rollback(accepted.id)

    try:
        engine.select_context_validity_map_revision(
            base_map.hypothesis_id,
            map_id=revision_two.id,
            reason="recovery alone must not permit re-advance",
        )
    except ValueError as exc:
        assert "re-advance blocked" in str(exc)
    else:
        raise AssertionError("recovery batch must still require holdout")

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:rollback:holdout:{index}",),
        )

    holdout = engine.validate_context_validity_rollback_holdout(improved.id)
    readvance = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        map_id=revision_two.id,
        reason="separate holdout permits re-advance",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{holdout.id}",
        ),
    )

    assert improved.status == "rollback_recovery_passed"
    assert improved.reactivation_allowed is False
    assert improved.mean_rollback_advantage >= 0.05
    assert improved.improvement_delta >= 0.05
    assert len(improved.observed_outcome_ids) >= 3
    assert holdout.status == "holdout_confirmed"
    assert holdout.reactivation_allowed is True
    assert not set(improved.observed_outcome_ids).intersection(
        holdout.holdout_outcome_ids
    )
    assert readvance.action == "advance"
    assert readvance.selected_map_id == revision_two.id


def test_dismiss_is_terminal_but_defer_can_be_superseded() -> None:
    (
        defer_engine,
        _,
        _,
        _,
        _,
        defer_watch,
        _,
    ) = _build_resolution_recommendation_engine()
    defer_engine.resolve_context_validity_degradation_watch(
        defer_watch.id,
        decision="defer",
        reason="defer first",
    )
    accepted = defer_engine.resolve_context_validity_degradation_watch(
        defer_watch.id,
        decision="accept",
        reason="later evidence review accepts rollback",
    )
    assert accepted.decision == "accept"

    (
        dismiss_engine,
        _,
        _,
        _,
        _,
        dismiss_watch,
        _,
    ) = _build_resolution_recommendation_engine()
    dismiss_engine.resolve_context_validity_degradation_watch(
        dismiss_watch.id,
        decision="dismiss",
        reason="terminal dismissal",
    )
    try:
        dismiss_engine.resolve_context_validity_degradation_watch(
            dismiss_watch.id,
            decision="accept",
            reason="should not reopen dismissal",
        )
    except ValueError as exc:
        assert "terminally resolved" in str(exc)
    else:
        raise AssertionError("dismissed recommendation must remain terminal")


def test_rollback_resolution_and_validation_persist() -> None:
    (
        engine,
        base_map,
        _,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="accept rollback for persistence test",
    )
    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:persist:{index}",),
        )
    validation = engine.validate_context_validity_rollback(accepted.id)
    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"resolution:persist:holdout:{index}",),
        )
    holdout = engine.validate_context_validity_rollback_holdout(validation.id)
    narrative = engine.build_metacognitive_narrative(
        "context_validity_holdout"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert validation.status == "rollback_recovery_passed"
    assert holdout.status == "holdout_confirmed"
    assert restored.context_validity_recommendation_resolutions == (
        engine.context_validity_recommendation_resolutions
    )
    assert restored.context_validity_rollback_validations == (
        engine.context_validity_rollback_validations
    )
    assert restored.context_validity_rollback_holdout_validations == (
        engine.context_validity_rollback_holdout_validations
    )
    assert restored.next_context_validity_recommendation_resolution_id == (
        engine.next_context_validity_recommendation_resolution_id
    )
    assert restored.next_context_validity_rollback_validation_id == (
        engine.next_context_validity_rollback_validation_id
    )
    assert restored.next_context_validity_rollback_holdout_validation_id == (
        engine.next_context_validity_rollback_holdout_validation_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_recommendation_resolution:")
        for ref in narrative.evidence_refs
    )



def test_rollback_holdout_failure_keeps_descendant_blocked() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="test failed holdout protection",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"holdout:test:recovery:{index}",),
        )
    recovery = engine.validate_context_validity_rollback(accepted.id)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": True,
                "request independent review": False,
            },
            evidence_refs=(f"holdout:test:negative:{index}",),
        )
    holdout = engine.validate_context_validity_rollback_holdout(recovery.id)

    assert recovery.status == "rollback_recovery_passed"
    assert recovery.reactivation_allowed is False
    assert holdout.status == "holdout_not_confirmed"
    assert holdout.reactivation_allowed is False
    assert not set(recovery.observed_outcome_ids).intersection(
        holdout.holdout_outcome_ids
    )

    try:
        engine.select_context_validity_map_revision(
            base_map.hypothesis_id,
            map_id=revision_two.id,
            reason="failed holdout cannot reactivate descendant",
        )
    except ValueError as exc:
        assert "re-advance blocked" in str(exc)
    else:
        raise AssertionError("failed holdout must keep re-advance blocked")


def test_rollback_holdout_uses_only_post_recovery_outcomes() -> None:
    (
        engine,
        base_map,
        _,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="test holdout watermark",
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"holdout:watermark:recovery:{index}",),
        )
    recovery = engine.validate_context_validity_rollback(accepted.id)
    assert recovery.holdout_gate_watermark_id > 0

    insufficient = engine.validate_context_validity_rollback_holdout(
        recovery.id
    )
    assert insufficient.status == "insufficient_holdout_evidence"
    assert insufficient.holdout_outcome_ids == ()

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        assert gate.id > recovery.holdout_gate_watermark_id
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"holdout:watermark:holdout:{index}",),
        )

    confirmed = engine.validate_context_validity_rollback_holdout(
        recovery.id
    )
    assert confirmed.status == "holdout_confirmed"
    assert confirmed.reactivation_allowed is True
    assert len(confirmed.holdout_outcome_ids) == 3
    assert not set(recovery.observed_outcome_ids).intersection(
        confirmed.holdout_outcome_ids
    )


def test_rollback_holdout_validation_persists_and_is_explainable() -> None:
    (
        engine,
        base_map,
        _,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="persist holdout evidence",
    )

    for phase in ("recovery", "holdout"):
        for index in range(3):
            gate = engine.evaluate_active_context_validity_gated_decision(
                base_map.hypothesis_id,
                environment_signature=signature,
                candidates=_validity_gate_candidates(),
                context="production release",
            )
            engine.record_context_validity_gate_outcome(
                gate.id,
                actual_success_by_action={
                    "run automated release check": False,
                    "request independent review": True,
                },
                evidence_refs=(f"holdout:persist:{phase}:{index}",),
            )
        if phase == "recovery":
            recovery = engine.validate_context_validity_rollback(accepted.id)

    holdout = engine.validate_context_validity_rollback_holdout(recovery.id)
    narrative = engine.build_metacognitive_narrative(
        "context_validity_holdout"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert holdout.status == "holdout_confirmed"
    assert restored.context_validity_rollback_holdout_validations == (
        engine.context_validity_rollback_holdout_validations
    )
    assert restored.next_context_validity_rollback_holdout_validation_id == (
        engine.next_context_validity_rollback_holdout_validation_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_rollback_holdout_validation:")
        for ref in narrative.evidence_refs
    )



def _build_reactivated_holdout_engine():
    (
        engine,
        base_map,
        revision_two,
        _,
        _,
        watch,
        signature,
    ) = _build_resolution_recommendation_engine()
    accepted = engine.resolve_context_validity_degradation_watch(
        watch.id,
        decision="accept",
        reason="prepare reactivation drift tests",
    )

    for phase in ("recovery", "holdout"):
        for index in range(3):
            gate = engine.evaluate_active_context_validity_gated_decision(
                base_map.hypothesis_id,
                environment_signature=signature,
                candidates=_validity_gate_candidates(),
                context="production release",
            )
            engine.record_context_validity_gate_outcome(
                gate.id,
                actual_success_by_action={
                    "run automated release check": False,
                    "request independent review": True,
                },
                evidence_refs=(f"reactivation:{phase}:{index}",),
            )
        if phase == "recovery":
            recovery = engine.validate_context_validity_rollback(accepted.id)

    holdout = engine.validate_context_validity_rollback_holdout(recovery.id)
    reactivation = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        map_id=revision_two.id,
        reason="confirmed holdout permits reactivation",
        evidence_refs=(
            f"context_validity_rollback_holdout_validation:{holdout.id}",
        ),
    )
    return (
        engine,
        base_map,
        revision_two,
        signature,
        recovery,
        holdout,
        reactivation,
    )


def test_reactivation_drift_watch_uses_only_post_reactivation_outcomes() -> None:
    (
        engine,
        base_map,
        _,
        signature,
        recovery,
        holdout,
        reactivation,
    ) = _build_reactivated_holdout_engine()

    initial = engine.watch_reactivated_context_validity_drift(
        base_map.hypothesis_id
    )
    assert initial.status == "insufficient_post_reactivation_evidence"
    assert initial.observed_outcome_ids == ()
    assert initial.decision_gate_watermark_id == (
        reactivation.decision_gate_watermark_id
    )

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        assert gate.id > reactivation.decision_gate_watermark_id
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"reactivation:stable:{index}",),
        )

    stable = engine.watch_reactivated_context_validity_drift(
        base_map.hypothesis_id
    )

    assert stable.status == "post_reactivation_stable"
    assert stable.recommended_action == "continue_monitoring"
    assert stable.mean_post_reactivation_advantage >= 0.05
    assert not set(stable.observed_outcome_ids).intersection(
        recovery.observed_outcome_ids
    )
    assert not set(stable.observed_outcome_ids).intersection(
        holdout.holdout_outcome_ids
    )


def test_reactivation_drift_recommends_review_without_auto_rollback() -> None:
    (
        engine,
        base_map,
        revision_two,
        signature,
        recovery,
        holdout,
        _,
    ) = _build_reactivated_holdout_engine()
    selection_count = len(engine.context_validity_map_selection_history)

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": True,
                "request independent review": False,
            },
            evidence_refs=(f"reactivation:negative:{index}",),
        )

    drift = engine.watch_reactivated_context_validity_drift(
        base_map.hypothesis_id
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert drift.status == "renewed_degradation_detected"
    assert drift.recommended_action == "review_for_rollback"
    assert drift.mean_post_reactivation_advantage <= -0.05
    assert drift.advantage_delta <= -0.05
    assert not set(drift.observed_outcome_ids).intersection(
        recovery.observed_outcome_ids
    )
    assert not set(drift.observed_outcome_ids).intersection(
        holdout.holdout_outcome_ids
    )
    assert len(engine.context_validity_map_selection_history) == selection_count
    assert active is not None
    assert active.id == revision_two.id


def test_reactivation_drift_watch_persists_and_is_explainable() -> None:
    (
        engine,
        base_map,
        _,
        signature,
        _,
        _,
        _,
    ) = _build_reactivated_holdout_engine()

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": True,
                "request independent review": False,
            },
            evidence_refs=(f"reactivation:persist:{index}",),
        )

    drift = engine.watch_reactivated_context_validity_drift(
        base_map.hypothesis_id
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_reactivation_drift"
    )
    restored = UnarchiEngine.from_export(engine.export_state())

    assert drift.status == "renewed_degradation_detected"
    assert restored.context_validity_reactivation_drift_watches == (
        engine.context_validity_reactivation_drift_watches
    )
    assert restored.next_context_validity_reactivation_drift_watch_id == (
        engine.next_context_validity_reactivation_drift_watch_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert engine.snapshot()["post_reactivation_drift_watch_count"] == 1
    assert engine.snapshot()["renewed_degradation_count"] == 1
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_reactivation_drift_watch:")
        for ref in narrative.evidence_refs
    )



def _build_renewed_degradation_resolution_engine():
    (
        engine,
        base_map,
        revision_two,
        signature,
        recovery,
        holdout,
        _,
    ) = _build_reactivated_holdout_engine()

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=signature,
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": True,
                "request independent review": False,
            },
            evidence_refs=(f"resolution30:test:negative:{index}",),
        )

    drift = engine.watch_reactivated_context_validity_drift(
        base_map.hypothesis_id
    )
    assert drift.status == "renewed_degradation_detected"
    return (
        engine,
        base_map,
        revision_two,
        recovery,
        holdout,
        drift,
    )


def test_renewed_degradation_defer_and_dismiss_keep_active_pointer() -> None:
    (
        defer_engine,
        defer_base,
        defer_revision,
        _,
        _,
        defer_drift,
    ) = _build_renewed_degradation_resolution_engine()
    deferred = defer_engine.resolve_reactivated_context_validity_drift(
        defer_drift.id,
        decision="defer",
        reason="collect more post-reactivation evidence",
    )
    deferred_active = defer_engine.active_context_causal_validity_map(
        defer_base.hypothesis_id
    )

    (
        dismiss_engine,
        dismiss_base,
        dismiss_revision,
        _,
        _,
        dismiss_drift,
    ) = _build_renewed_degradation_resolution_engine()
    dismissed = dismiss_engine.resolve_reactivated_context_validity_drift(
        dismiss_drift.id,
        decision="dismiss",
        reason="operator rejects drift recommendation",
    )
    dismissed_active = dismiss_engine.active_context_causal_validity_map(
        dismiss_base.hypothesis_id
    )

    assert deferred.decision == "defer"
    assert deferred.rollback_selection_id is None
    assert deferred.requires_new_evidence_cycle is False
    assert deferred_active is not None
    assert deferred_active.id == defer_revision.id

    assert dismissed.decision == "dismiss"
    assert dismissed.rollback_selection_id is None
    assert dismissed.requires_new_evidence_cycle is False
    assert dismissed_active is not None
    assert dismissed_active.id == dismiss_revision.id


def test_renewed_degradation_rollback_invalidates_old_holdout() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        holdout,
        drift,
    ) = _build_renewed_degradation_resolution_engine()

    resolution = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="renewed degradation requires ancestor review",
        evidence_refs=("resolution30:test:owner_review",),
    )
    active = engine.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert resolution.decision == "rollback_review"
    assert resolution.rollback_target_map_id == base_map.id
    assert resolution.rollback_selection_id is not None
    assert resolution.blocked_descendant_map_id == revision_two.id
    assert resolution.requires_new_evidence_cycle is True
    assert active is not None
    assert active.id == base_map.id
    assert any(
        item.id == revision_two.id
        for item in engine.context_causal_validity_maps
    )

    try:
        engine.select_context_validity_map_revision(
            base_map.hypothesis_id,
            map_id=revision_two.id,
            reason="stale holdout must not authorize second advance",
            evidence_refs=(
                f"context_validity_rollback_holdout_validation:{holdout.id}",
            ),
        )
    except ValueError as exc:
        assert "new evidence cycle" in str(exc)
    else:
        raise AssertionError("stale holdout must not authorize re-advance")



def test_v031_renewed_recovery_requires_fresh_independent_holdout() -> None:
    (
        engine,
        base_map,
        revision_two,
        _,
        old_holdout,
        drift,
    ) = _build_renewed_degradation_resolution_engine()

    resolution = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="start a fresh v0.31 evidence cycle",
        evidence_refs=("v031:test:second_rollback",),
    )

    insufficient = engine.validate_context_validity_renewed_rollback(
        resolution.id
    )
    assert insufficient.status == "insufficient_renewed_recovery_evidence"
    assert insufficient.reactivation_allowed is False
    assert insufficient.observed_outcome_ids == ()

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=drift.degraded_signatures[0],
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:test:renewed_recovery:{index}",),
        )

    recovery = engine.validate_context_validity_renewed_rollback(
        resolution.id
    )
    assert recovery.status == "renewed_recovery_passed"
    assert recovery.reactivation_allowed is False
    assert len(recovery.observed_outcome_ids) == 3
    old_episode_ids = (
        set(old_holdout.recovery_outcome_ids)
        | set(old_holdout.holdout_outcome_ids)
        | set(drift.observed_outcome_ids)
    )
    assert not old_episode_ids.intersection(recovery.observed_outcome_ids)
    assert old_episode_ids <= set(recovery.excluded_prior_outcome_ids)

    try:
        engine.select_context_validity_map_revision(
            base_map.hypothesis_id,
            map_id=revision_two.id,
            reason="recovery alone must not authorize v0.31 re-advance",
        )
    except ValueError as exc:
        assert "fresh recovery and independent holdout cycle" in str(exc)
    else:
        raise AssertionError("renewed recovery alone must not authorize re-advance")

    insufficient_holdout = (
        engine.validate_context_validity_renewed_rollback_holdout(
            recovery.id
        )
    )
    assert (
        insufficient_holdout.status
        == "insufficient_renewed_holdout_evidence"
    )
    assert insufficient_holdout.holdout_outcome_ids == ()

    for index in range(3):
        gate = engine.evaluate_active_context_validity_gated_decision(
            base_map.hypothesis_id,
            environment_signature=drift.degraded_signatures[0],
            candidates=_validity_gate_candidates(),
            context="production release",
        )
        assert gate.id > recovery.holdout_gate_watermark_id
        engine.record_context_validity_gate_outcome(
            gate.id,
            actual_success_by_action={
                "run automated release check": False,
                "request independent review": True,
            },
            evidence_refs=(f"v031:test:renewed_holdout:{index}",),
        )

    holdout = engine.validate_context_validity_renewed_rollback_holdout(
        recovery.id
    )
    assert holdout.status == "renewed_holdout_confirmed"
    assert holdout.reactivation_allowed is True
    assert len(holdout.holdout_outcome_ids) == 3
    assert not set(recovery.observed_outcome_ids).intersection(
        holdout.holdout_outcome_ids
    )
    assert not old_episode_ids.intersection(holdout.holdout_outcome_ids)

    advanced = engine.select_context_validity_map_revision(
        base_map.hypothesis_id,
        map_id=revision_two.id,
        reason="fresh v0.31 recovery and holdout confirmed",
        evidence_refs=(
            f"context_validity_renewed_holdout_validation:{holdout.id}",
        ),
    )
    assert advanced.action == "advance"
    assert advanced.selected_map_id == revision_two.id

    restored = UnarchiEngine.from_export(engine.export_state())
    assert restored.context_validity_renewed_recovery_validations == (
        engine.context_validity_renewed_recovery_validations
    )
    assert restored.context_validity_renewed_holdout_validations == (
        engine.context_validity_renewed_holdout_validations
    )
    assert restored.active_context_causal_validity_map(
        base_map.hypothesis_id
    ).id == revision_two.id


def test_renewed_degradation_resolution_terminal_rules() -> None:
    (
        engine,
        _,
        _,
        _,
        _,
        drift,
    ) = _build_renewed_degradation_resolution_engine()

    engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="defer",
        reason="defer once",
    )
    rollback = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="later review accepts rollback",
    )
    assert rollback.decision == "rollback_review"

    try:
        engine.resolve_reactivated_context_validity_drift(
            drift.id,
            decision="dismiss",
            reason="should not reopen terminal resolution",
        )
    except ValueError as exc:
        assert "terminally resolved" in str(exc)
    else:
        raise AssertionError("terminal drift resolution must remain terminal")


def test_renewed_degradation_resolution_persists_and_is_explainable() -> None:
    (
        engine,
        base_map,
        _,
        _,
        _,
        drift,
    ) = _build_renewed_degradation_resolution_engine()
    resolution = engine.resolve_reactivated_context_validity_drift(
        drift.id,
        decision="rollback_review",
        reason="persist renewed-degradation rollback review",
    )
    narrative = engine.build_metacognitive_narrative(
        "context_validity_reactivation_resolution"
    )
    restored = UnarchiEngine.from_export(engine.export_state())
    restored_active = restored.active_context_causal_validity_map(
        base_map.hypothesis_id
    )

    assert resolution.requires_new_evidence_cycle is True
    assert restored.context_validity_reactivation_drift_resolutions == (
        engine.context_validity_reactivation_drift_resolutions
    )
    assert restored.next_context_validity_reactivation_drift_resolution_id == (
        engine.next_context_validity_reactivation_drift_resolution_id
    )
    assert restored.snapshot() == engine.snapshot()
    assert restored_active is not None
    assert restored_active.id == base_map.id
    assert engine.snapshot()["reactivation_drift_resolution_count"] == 1
    assert engine.snapshot()["reactivation_drift_rollback_review_count"] == 1
    assert narrative.unsupported_claims == 0
    assert any(
        ref.startswith("context_validity_reactivation_drift_resolution:")
        for ref in narrative.evidence_refs
    )
