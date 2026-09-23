from backend.app.services.unarchi_benchmark import run_unarchi_ablation_benchmark


def test_unarchi_ablation_benchmark_passes_all_scenarios() -> None:
    result = run_unarchi_ablation_benchmark()

    assert result["scenario_count"] == 10
    assert result["passed_scenarios"] == 10
    assert result["pass_rate"] == 1.0
    assert result["claims_phenomenal_consciousness"] is False


def test_unarchi_benchmark_contains_causal_comparisons() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    failure = scenarios["failure_sensitization"]
    success = scenarios["success_adaptation"]

    assert failure["comparison"]["state_causally_active"] is True
    assert failure["comparison"]["risk_delta"] > 0
    assert success["comparison"]["risk_delta"] < 0


def test_unarchi_benchmark_covers_endogenous_goal_lifecycle() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    endogenous = scenarios["endogenous_goal_lifecycle"]

    assert endogenous["created"] is True
    assert endogenous["bounded"] is True
    assert endogenous["zero_cost_only"] is True
    assert endogenous["resolved"] is True
    assert endogenous["passed"] is True


def test_unarchi_benchmark_covers_predictive_self_calibration() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    calibration = scenarios["predictive_self_calibration"]

    assert calibration["passed"] is True
    assert (
        calibration["second_success_error"]
        < calibration["first_success_error"]
    )
    assert 0.0 <= calibration["self_calibration_score"] <= 1.0


def test_unarchi_benchmark_covers_temporal_prospective_continuity() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    temporal = scenarios["prospective_temporal_continuity"]

    assert temporal["passed"] is True
    assert temporal["recalled"] is True
    assert temporal["linked_past_prediction"] is True
    assert temporal["no_auto_execution"] is True
    assert temporal["alignment_recorded"] is True


def test_unarchi_benchmark_covers_metacognitive_fidelity() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    narrative = scenarios["metacognitive_retrospective_fidelity"]

    assert narrative["passed"] is True
    assert narrative["identical_after_restart"] is True
    assert narrative["evidence_linked"] is True
    assert narrative["no_unsupported_claims"] is True
    assert narrative["fidelity_score"] == 1.0


def test_unarchi_benchmark_covers_conflict_arbitration_self_correction() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    arbitration = scenarios["conflict_arbitration_self_correction"]

    assert arbitration["passed"] is True
    assert arbitration["conflict_detected"] is True
    assert arbitration["hard_block_worked"] is True
    assert arbitration["truth_weight_increased"] is True
    assert arbitration["safety_floor_preserved"] is True


def test_unarchi_benchmark_covers_causal_hypothesis_revision() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    world_model = scenarios["causal_hypothesis_revision"]

    assert world_model["passed"] is True
    assert world_model["unchanged_before_evidence"] is True
    assert world_model["leader_is_temperature"] is True
    assert (
        world_model["temperature_confidence"]
        > world_model["pressure_confidence"]
    )


def test_unarchi_benchmark_covers_intervention_aware_self_world_revision() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    intervention = scenarios["intervention_aware_self_world_revision"]

    assert intervention["passed"] is True
    assert intervention["environment_held_constant"] is True
    assert intervention["attribution"] == "self_intervention"
    assert intervention["leader_is_self"] is True
    assert (
        intervention["self_confidence"]
        > intervention["external_confidence"]
    )
