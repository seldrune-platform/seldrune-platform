from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.live_media.face_torch_training import TrainingStepResult
from services.live_media.face_training_loop import run_training_loop


def _job(max_steps=3, checkpoint_every=2):
    config = SimpleNamespace(max_steps=max_steps, checkpoint_every=checkpoint_every)
    return SimpleNamespace(config=config)


def test_training_loop_runs_to_bound_and_checkpoints(tmp_path):
    batches = [(object(), object(), object()) for _ in range(5)]
    checkpoint = SimpleNamespace(step=2)
    with (
        patch(
            "services.live_media.face_training_loop.train_step",
            return_value=TrainingStepResult(loss=0.25, device="cuda"),
        ) as step,
        patch(
            "services.live_media.face_training_loop.write_checkpoint",
            return_value=checkpoint,
        ) as write,
    ):
        result = run_training_loop(
            object(),
            object(),
            batches,
            _job(),
            device="cuda",
            output_dir=tmp_path,
        )

    assert result.completed_steps == 3
    assert result.last_loss == 0.25
    assert result.device == "cuda"
    assert len(result.checkpoints) == 2
    assert step.call_count == 3
    assert write.call_count == 2


def test_training_loop_rejects_empty_batches(tmp_path):
    with pytest.raises(ValueError, match="at least one admitted batch"):
        run_training_loop(
            object(),
            object(),
            (),
            _job(),
            device="cuda",
            output_dir=tmp_path,
        )


def test_training_loop_rejects_invalid_start_step(tmp_path):
    with pytest.raises(ValueError, match="configured training range"):
        run_training_loop(
            object(),
            object(),
            ((object(), object(), object()),),
            _job(max_steps=3),
            device="cuda",
            output_dir=tmp_path,
            start_step=3,
        )
