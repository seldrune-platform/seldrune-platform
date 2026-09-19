from services.supreme.bootstrap import bootstrap_backlog, bootstrap_waves


def test_bootstrap_starts_agi_and_liveshift_in_parallel():
    first = set(bootstrap_waves()[0].task_ids)
    assert "agi_baseline" in first
    assert "agi_experts" in first
    assert "agi_proof" in first
    assert "agi_forge" in first
    assert "face_dataset" in first


def test_face_pipeline_preserves_real_world_dependency_order():
    waves = bootstrap_waves()
    positions = {
        task_id: index
        for index, wave in enumerate(waves)
        for task_id in wave.task_ids
    }
    assert positions["face_dataset"] < positions["face_train"]
    assert positions["face_train"] < positions["face_frame"]
    assert positions["face_frame"] < positions["face_stream"]
    assert positions["face_stream"] < positions["mobile_client"]


def test_agi_integration_waits_for_core_research_components():
    tasks = {task.task_id: task for task in bootstrap_backlog()}
    assert set(tasks["agi_integrate"].dependencies) == {
        "agi_baseline",
        "agi_experts",
        "agi_proof",
        "agi_forge",
    }
