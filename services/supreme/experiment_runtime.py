"""Bounded experiment runtime for Seldrune SUPREME.

Turns Forge hypotheses into auditable jobs. It never promotes a candidate
automatically; evaluation and owner-controlled promotion remain separate gates.
"""

from dataclasses import dataclass
from enum import StrEnum

from .forge import Experiment


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ExperimentJob:
    experiment_id: str
    hypothesis: str
    state: JobState
    accelerator: str
    evidence_uri: str | None = None


def queue_experiment(
    experiment: Experiment,
    accelerator: str = "rtx-pro-6000-blackwell",
) -> ExperimentJob:
    if not accelerator.strip():
        raise ValueError("accelerator is required")
    return ExperimentJob(
        experiment_id=experiment.experiment_id,
        hypothesis=experiment.hypothesis,
        state=JobState.QUEUED,
        accelerator=accelerator,
    )


def complete_job(job: ExperimentJob, evidence_uri: str) -> ExperimentJob:
    if job.state not in {JobState.QUEUED, JobState.RUNNING}:
        raise ValueError("only active jobs can complete")
    if not evidence_uri.strip():
        raise ValueError("successful experiments require evidence")
    return ExperimentJob(
        experiment_id=job.experiment_id,
        hypothesis=job.hypothesis,
        state=JobState.SUCCEEDED,
        accelerator=job.accelerator,
        evidence_uri=evidence_uri,
    )
