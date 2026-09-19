import pytest

from services.supreme.experiment_runtime import (
    JobState,
    complete_job,
    queue_experiment,
)
from services.supreme.forge import next_experiment


def test_forge_experiment_targets_primary_gpu():
    job = queue_experiment(next_experiment("exp-1", "test a new reasoning router"))
    assert job.accelerator == "rtx-pro-6000-blackwell"
    assert job.state is JobState.QUEUED


def test_success_requires_evidence():
    job = queue_experiment(next_experiment("exp-2", "test memory architecture"))
    with pytest.raises(ValueError, match="evidence"):
        complete_job(job, "")


def test_success_preserves_evidence_reference():
    job = queue_experiment(next_experiment("exp-3", "test expert topology"))
    done = complete_job(job, "artifact://exp-3/benchmark.json")
    assert done.state is JobState.SUCCEEDED
    assert done.evidence_uri == "artifact://exp-3/benchmark.json"
