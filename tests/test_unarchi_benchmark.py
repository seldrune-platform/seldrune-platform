from backend.app.services.unarchi_benchmark import run_unarchi_ablation_benchmark


def test_unarchi_ablation_benchmark_passes_all_scenarios() -> None:
    result = run_unarchi_ablation_benchmark()

    assert result["scenario_count"] == 33
    assert result["passed_scenarios"] == 33
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


def test_unarchi_benchmark_covers_recurrent_global_workspace() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    workspace = scenarios["recurrent_global_workspace_integration"]

    assert workspace["passed"] is True
    assert workspace["workspace_causally_active"] is True
    assert workspace["broadcast_target_delta"] > 0
    assert workspace["full_mode"] == "integrated"
    assert workspace["ablated_mode"] == "local"
    assert workspace["first_recurrence_depth"] == 1
    assert workspace["second_recurrence_depth"] == 2


def test_unarchi_benchmark_covers_counterfactual_recurrent_gain() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    counterfactual = scenarios["counterfactual_recurrent_information_gain"]

    assert counterfactual["passed"] is True
    assert counterfactual["simulation_causally_active"] is True
    assert counterfactual["full_action"] == "run reversible diagnostic"
    assert counterfactual["ablated_action"] == "act immediately"
    assert (
        counterfactual["full_measured_information_gain"]
        > counterfactual["ablated_measured_information_gain"]
    )
    assert counterfactual["feedback_reentered"] is True
    assert counterfactual["prediction_discrepancy"] is not None



def test_unarchi_benchmark_covers_autobiographical_self_schema_transfer() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    schema = scenarios["autobiographical_self_schema_transfer"]

    assert schema["passed"] is True
    assert schema["with_schema_action"] == "run validated local diagnostic"
    assert schema["without_schema_action"] == "use untested shortcut"
    assert "capability" in schema["schema_kinds"]
    assert "limitation" in schema["schema_kinds"]
    assert schema["validated_success_bias"] > 0.0
    assert schema["validated_risk_bias"] < 0.0
    assert schema["schema_refs"]
    assert schema["restart_preserved"] is True
    assert schema["narrative_fidelity_score"] == 1.0



def test_unarchi_benchmark_covers_contradiction_driven_schema_revision() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    revision = scenarios["contradiction_driven_self_schema_revision"]

    assert revision["passed"] is True
    assert revision["revised_kind"] == "limitation"
    assert revision["revised_success_rate"] < revision["prior_success_rate"]
    assert revision["contradiction_ratio"] == 1.0
    assert revision["contradictory_evidence_count"] >= 3
    assert revision["frozen_action"] == "run automated release check"
    assert revision["revised_action"] == "request independent review"
    assert revision["predicted_success_delta"] < 0.0
    assert revision["revision_causally_active"] is True
    assert revision["restart_preserved"] is True



def test_unarchi_benchmark_covers_context_sensitive_schema_decomposition() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    contextual = scenarios["context_sensitive_self_schema_decomposition"]

    assert contextual["passed"] is True
    assert contextual["global_kind"] == "mixed"
    assert contextual["decomposition_status"] == "accepted"
    assert (
        contextual["contextual_holdout_mae"]
        < contextual["global_holdout_mae"]
    )
    assert contextual["heldout_improvement"] > 0.0
    assert contextual["sandbox_kind"] == "capability"
    assert contextual["production_kind"] == "limitation"
    assert contextual["global_action"] == "run automated release check"
    assert contextual["contextual_action"] == "request independent review"
    assert contextual["choice_changed"] is True
    assert contextual["contextual_schema_causally_active"] is True
    assert contextual["restart_preserved"] is True



def test_unarchi_benchmark_covers_context_transfer_boundary_learning() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    transfer = scenarios["context_transfer_boundary_learning"]

    assert transfer["passed"] is True
    assert transfer["staging_status"] == "accepted"
    assert transfer["staging_source_mae"] < transfer["staging_global_mae"]
    assert transfer["staging_gain"] > 0.0
    assert transfer["emergency_status"] == "abstained_no_gain"
    assert transfer["emergency_source_mae"] > transfer["emergency_global_mae"]
    assert transfer["transfer_action"] == "run automated release check"
    assert transfer["no_transfer_action"] == "request independent review"
    assert transfer["choice_changed"] is True
    assert transfer["transfer_causally_active"] is True
    assert transfer["restart_preserved"] is True



def test_unarchi_benchmark_covers_latent_context_hypothesis_discovery() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    discovery = scenarios["latent_context_hypothesis_discovery"]

    assert discovery["passed"] is True
    assert discovery["proposed_count"] <= 3
    assert discovery["validated_count"] >= 1
    assert {
        discovery["selected_positive_term"],
        discovery["selected_negative_term"],
    } == {"sandbox", "production"}
    assert discovery["selected_gain"] > 0.0
    assert discovery["contextual_kinds"]["sandbox"] == "capability"
    assert discovery["contextual_kinds"]["production"] == "limitation"
    assert discovery["noisy_status"] == "no_validated_hypothesis"
    assert discovery["noisy_proposed_count"] >= 1
    assert set(discovery["noisy_validation_statuses"]) == {
        "rejected_validation"
    }
    assert discovery["restart_preserved"] is True



def test_unarchi_benchmark_covers_context_causality_intervention() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    causal = scenarios["context_causality_intervention_support"]

    assert causal["passed"] is True
    assert causal["observational_status"] == "unverified"
    assert causal["confounded_status"] == "confounded"
    assert causal["after_confounded_status"] == "unverified"
    assert causal["clean_status"] == "intervention_supported"
    assert causal["held_constant"] is True
    assert causal["direction_followed"] is True
    assert causal["causal_strength"] >= 0.35
    assert causal["final_hypothesis_status"] == "intervention_supported"
    assert causal["restart_preserved"] is True



def test_unarchi_benchmark_covers_replicated_reversible_context_causality() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    causal = scenarios["replicated_reversible_context_causality"]

    assert causal["passed"] is True
    assert causal["status"] == "replicated_reversible"
    assert causal["independent_forward_batches"] == 2
    assert causal["independent_reverse_batches"] == 1
    assert causal["forward_replication_rate"] == 1.0
    assert causal["reverse_replication_rate"] == 1.0
    assert causal["reversal_direction_followed"] is True
    assert causal["confidence"] >= 0.35
    assert causal["final_hypothesis_status"] == "replicated_reversible"
    assert causal["restart_preserved"] is True



def test_unarchi_benchmark_covers_cross_environment_causal_invariance() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    causal = scenarios["cross_environment_causal_invariance"]

    assert causal["passed"] is True
    assert causal["status"] == "environment_invariant"
    assert causal["distinct_environment_count"] == 2
    assert causal["stable_environment_count"] == 2
    assert causal["direction_consistent"] is True
    assert causal["minimum_causal_strength"] >= 0.35
    assert causal["boundary_signatures"] == ()
    assert causal["final_hypothesis_status"] == "environment_invariant"
    assert causal["restart_preserved"] is True



def test_unarchi_benchmark_covers_active_context_boundary_discovery() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    boundary = scenarios["active_context_boundary_discovery"]

    assert boundary["passed"] is True
    assert boundary["bounded_status"] == "environment_bounded"
    assert boundary["selected_signature"] == "code=v1;load=high;data=fixed"
    assert boundary["selected_risk"] <= 0.25
    assert boundary["information_gain"] > 0.0
    assert boundary["priority"] > 0.0
    assert boundary["changed_dimensions"] == ("load",)
    assert boundary["outcome_status"] == "expanded_valid_region"
    assert boundary["uncertainty_reduction"] > 0.0
    assert boundary["no_external_execution"] is True
    assert boundary["restart_preserved"] is True



def test_unarchi_benchmark_covers_causal_validity_map_consolidation() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    validity = scenarios["causal_validity_map_consolidation"]

    assert validity["passed"] is True
    assert validity["bounded_status"] == "environment_bounded"
    assert validity["exact_valid_status"] == "tested_valid"
    assert validity["exact_invalid_status"] == "tested_invalid"
    assert validity["nearby_status"] == "supported_nearby"
    assert validity["ambiguous_status"] == "unknown"
    assert validity["map_confidence"] > 0.0
    assert validity["restart_preserved"] is True



def test_unarchi_benchmark_covers_validity_gated_decision_use() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    gate = scenarios["validity_gated_decision_use"]

    assert gate["passed"] is True
    assert gate["supported_status"] == "tested_valid"
    assert gate["supported_causal_allowed"] is True
    assert gate["supported_action"] == "request independent review"
    assert gate["invalid_status"] == "tested_invalid"
    assert gate["invalid_causal_allowed"] is False
    assert gate["invalid_action"] == "run automated release check"
    assert gate["nearby_status"] == "supported_nearby"
    assert gate["nearby_action"] == "request independent review"
    assert gate["unknown_status"] == "unknown"
    assert gate["unknown_causal_allowed"] is False
    assert gate["unknown_action"] == "run automated release check"
    assert gate["restart_preserved"] is True



def test_unarchi_benchmark_covers_validity_gate_outcome_calibration() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    calibration = scenarios["validity_gate_outcome_calibration"]

    assert calibration["passed"] is True
    assert calibration["good_before_status"] == "supported_nearby"
    assert calibration["good_after_status"] == "supported_nearby"
    assert calibration["good_confidence_delta"] > 0.0
    assert calibration["good_calibration_status"] == "nearby_support_calibrated"
    assert calibration["good_advantage"] >= 0.05
    assert calibration["bad_before_status"] == "supported_nearby"
    assert calibration["bad_after_status"] == "unknown"
    assert calibration["bad_calibration_status"] == "nearby_support_revoked"
    assert calibration["bad_advantage"] <= -0.05
    assert calibration["post_revoke_causal_allowed"] is False
    assert calibration["restart_preserved"] is True



def test_unarchi_benchmark_covers_calibration_aware_map_revision() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    revision = scenarios["calibration_aware_validity_map_revision"]

    assert revision["passed"] is True
    assert revision["revision_two_number"] == 2
    assert revision["good_v2_status"] == "supported_nearby"
    assert revision["bad_v2_status"] == "unknown"
    assert revision["reversal_status"] == "nearby_support_revoked"
    assert revision["good_v2_after_new_evidence"] == "supported_nearby"
    assert revision["revision_three_number"] == 3
    assert revision["good_v3_status"] == "unknown"
    assert revision["exact_valid_v3_status"] == "tested_valid"
    assert revision["exact_invalid_v3_status"] == "tested_invalid"
    assert revision["restart_preserved"] is True



def test_unarchi_benchmark_covers_validity_map_selection_and_rollback() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    selection = scenarios["validity_map_selection_and_rollback"]

    assert selection["passed"] is True
    assert selection["activation_action"] == "activate"
    assert len(selection["activation_lineage"]) == 3
    assert selection["latest_decision_status"] == "unknown"
    assert selection["rollback_action"] == "rollback"
    assert selection["rollback_decision_status"] == "supported_nearby"
    assert selection["later_revision_preserved"] is True
    assert selection["readvance_action"] == "advance"
    assert selection["restart_preserved"] is True



def test_unarchi_benchmark_covers_active_revision_degradation_watch() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    watch = scenarios["active_revision_degradation_watch"]

    assert watch["passed"] is True
    assert watch["initial_watch_status"] == "insufficient_post_activation_evidence"
    assert watch["negative_calibration_status"] == "nearby_support_revoked"
    assert watch["recommendation_status"] == "rollback_recommended"
    assert watch["recommended_map_id"] is not None
    assert watch["active_map_unchanged"] is True
    assert watch["automatic_rollback_count"] == 0
    assert watch["restart_preserved"] is True



def test_unarchi_benchmark_covers_rollback_recommendation_resolution() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    resolution = scenarios["rollback_recommendation_resolution"]

    assert resolution["passed"] is True
    assert resolution["defer_pointer_unchanged"] is True
    assert resolution["dismiss_pointer_unchanged"] is True
    assert resolution["accepted_map_id"] is not None
    assert resolution["reactivation_blocked_before_validation"] is True
    assert (
        resolution["initial_validation_status"]
        == "insufficient_post_rollback_evidence"
    )
    assert resolution["improved_validation_status"] == "rollback_recovery_passed"
    assert resolution["improvement_delta"] >= 0.05
    assert resolution["blocked_after_recovery"] is True
    assert resolution["holdout_status"] == "holdout_confirmed"
    assert resolution["readvance_action"] == "advance"
    assert resolution["restart_preserved"] is True



def test_unarchi_benchmark_covers_rollback_holdout_validation() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    holdout = scenarios["rollback_holdout_validation"]

    assert holdout["passed"] is True
    assert holdout["recovery_status"] == "rollback_recovery_passed"
    assert holdout["recovery_reactivation_allowed"] is False
    assert holdout["failed_holdout_status"] == "holdout_not_confirmed"
    assert holdout["blocked_after_failed_holdout"] is True
    assert holdout["confirmed_holdout_status"] == "holdout_confirmed"
    assert holdout["confirmed_reactivation_allowed"] is True
    assert holdout["evidence_overlap"] is False
    assert holdout["readvance_action"] == "advance"
    assert holdout["restart_preserved"] is True



def test_unarchi_benchmark_covers_post_reactivation_drift_monitoring() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    drift = scenarios["post_reactivation_holdout_drift_monitoring"]

    assert drift["passed"] is True
    assert drift["initial_status"] == "insufficient_post_reactivation_evidence"
    assert drift["stable_status"] == "post_reactivation_stable"
    assert drift["stable_action"] == "continue_monitoring"
    assert drift["degraded_status"] == "renewed_degradation_detected"
    assert drift["degraded_action"] == "review_for_rollback"
    assert drift["evidence_overlap_with_holdout"] is False
    assert drift["automatic_selection_change"] is False
    assert drift["active_map_unchanged"] is True
    assert drift["restart_preserved"] is True



def test_unarchi_benchmark_covers_renewed_degradation_resolution() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    resolution = scenarios["renewed_degradation_resolution"]

    assert resolution["passed"] is True
    assert resolution["defer_pointer_unchanged"] is True
    assert resolution["dismiss_pointer_unchanged"] is True
    assert resolution["rollback_target_map_id"] is not None
    assert resolution["rollback_active_map_id"] == (
        resolution["rollback_target_map_id"]
    )
    assert resolution["requires_new_evidence_cycle"] is True
    assert resolution["stale_holdout_blocked"] is True
    assert resolution["terminal_resolution_blocked"] is True
    assert resolution["descendant_preserved"] is True
    assert resolution["restart_preserved"] is True


def test_unarchi_benchmark_covers_v031_renewed_recovery_cycle() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    cycle = scenarios["renewed_degradation_recovery_cycle"]

    assert cycle["passed"] is True
    assert cycle["initial_recovery_status"] == "rollback_recovery_passed"
    assert cycle["initial_holdout_status"] == "holdout_confirmed"
    assert cycle["renewed_recovery_status"] == "renewed_recovery_passed"
    assert cycle["renewed_holdout_status"] == "renewed_holdout_confirmed"
    assert cycle["stale_holdout_blocked"] is True
    assert cycle["recovery_only_blocked"] is True
    assert cycle["prior_evidence_reused"] is False
    assert cycle["recovery_holdout_overlap"] is False
    assert cycle["readvance_action"] == "advance"
    assert cycle["restart_preserved"] is True


def test_unarchi_benchmark_covers_v032_repeated_episode_isolation() -> None:
    result = run_unarchi_ablation_benchmark()
    scenarios = {item["name"]: item for item in result["scenarios"]}

    episode = scenarios["repeated_episode_isolation"]

    assert episode["passed"] is True
    assert episode["episode_one_id"] == 1
    assert episode["episode_two_id"] == 2
    assert episode["second_holdout_source"] == "renewed"
    assert (
        episode["second_holdout_validation_id"]
        == episode["first_renewed_holdout_id"]
    )
    assert episode["cross_episode_overlap"] is False
    assert episode["prior_episode_excluded"] is True
    assert episode["recovery_holdout_overlap"] is False
    assert episode["readvance_action"] == "advance"
    assert episode["restart_preserved"] is True
