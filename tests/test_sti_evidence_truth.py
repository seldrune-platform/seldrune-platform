"""Regression tests for truthful Owner Console milestone classification."""

from backend.app.api.routes.sti import sti_telemetry


def test_face_execution_code_is_not_reported_as_production_verified(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SELDRUNE_FACE_PRODUCTION_EVIDENCE", raising=False)
    monkeypatch.delenv("SELDRUNE_FACE_VERIFICATION_RECEIPT", raising=False)

    telemetry = sti_telemetry()
    face = telemetry["face_v01"]
    live = telemetry["liveshift"]

    assert live["face_model_loaded"] is False
    assert live["first_frame_transformed"] is False
    assert live["live_stream_returned"] is False
    assert live["webrtc_return_verified"] is False
    assert live["cuda_webrtc_return_verified"] is False
    assert live["virtual_camera_connected"] is False

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
