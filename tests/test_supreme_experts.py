from services.supreme.collaboration import ProjectTask
from services.supreme.experts import ExpertKind, assign_expert, assign_wave


def test_routes_verification_work():
    task = ProjectTask("agi_proof", "Implement Proof Mesh verifier")
    assert assign_expert(task).expert is ExpertKind.VERIFICATION


def test_routes_training_work():
    task = ProjectTask("face_train", "Train Seldrune-owned face model")
    assert assign_expert(task).expert is ExpertKind.TRAINING


def test_routes_media_work():
    task = ProjectTask("face_stream", "Return transformed WebRTC stream")
    assert assign_expert(task).expert is ExpertKind.MEDIA


def test_wave_keeps_all_parallel_assignments():
    tasks = (
        ProjectTask("agi_experts", "Build expert router"),
        ProjectTask("face_dataset", "Define face dataset"),
    )
    assignments = assign_wave(tasks)
    assert {item.task_id for item in assignments} == {"agi_experts", "face_dataset"}
