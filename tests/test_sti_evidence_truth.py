"""Regression tests for truthful Owner Console milestone classification."""

from backend.app.api.routes.sti import sti_telemetry


def test_face_execution_code_is_not_reported_as_production_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    telemetry = sti_telemetry()
    face = telemetry["face_v01"]

    assert face["single_frame_execution"] == "implemented"
    assert face["continuous_stream_execution"] == "implemented"
    assert face["onnx_cuda_backend"] == "implemented"
    assert face["liveshift_onnx_adapter"] == "implemented"
    assert face["production_evidence_recorder"] == "implemented"
    assert face["session_evidence_integration"] == "implemented"
    assert face["production_evidence_verifier"] == "implemented"
    assert face["production_live_session_verified"] is False
    assert face["mobile_hd_output_verified"] is False
    assert face["voice_hd_output_verified"] is False
    assert face["production_evidence_status"] == "pending-evidence"
    assert set(telemetry["evidence_levels"]) == {
        "verified",
        "implemented",
        "simulated",
        "planned",
    }
