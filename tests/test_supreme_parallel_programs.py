from services.supreme.parallel_programs import (
    combined_execution_waves,
    parallel_programs,
)


def test_sti_and_liveshift_are_separate_parallel_programs():
    programs = parallel_programs()
    assert tuple(program.name for program in programs) == (
        "seldrune-sti",
        "liveshift",
    )


def test_first_wave_contains_both_programs():
    first = set(combined_execution_waves()[0].task_ids)
    assert any(task.startswith("agi_") for task in first)
    assert "face_dataset" in first


def test_mobile_waits_for_face_stream():
    waves = combined_execution_waves()
    positions = {
        task_id: index
        for index, wave in enumerate(waves)
        for task_id in wave.task_ids
    }
    assert positions["face_stream"] < positions["mobile_client"]
