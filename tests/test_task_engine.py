from uuid import uuid4

import pytest

from backend.app.core.tasking import TaskStatus
from backend.app.models.task import Task
from backend.app.services.task_engine import TaskTransitionError, transition_task


def make_task(status: TaskStatus, *, assigned: bool = False) -> Task:
    return Task(
        organization_id=uuid4(),
        created_by_user_id=uuid4(),
        assigned_agent_id=uuid4() if assigned else None,
        title="Research a market",
        objective="Find a measurable painful workflow",
        priority=0,
        status=status.value,
        input_data={},
    )


def test_task_must_follow_state_machine() -> None:
    task = make_task(TaskStatus.QUEUED)
    with pytest.raises(TaskTransitionError):
        transition_task(task, TaskStatus.SUCCEEDED)


def test_assigned_task_can_run_and_succeed() -> None:
    task = make_task(TaskStatus.ASSIGNED, assigned=True)
    transition_task(task, TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING.value
    assert task.started_at is not None

    transition_task(task, TaskStatus.SUCCEEDED, output_data={"score": 92})
    assert task.status == TaskStatus.SUCCEEDED.value
    assert task.output_data == {"score": 92}
    assert task.completed_at is not None


def test_failed_task_requires_error_message() -> None:
    task = make_task(TaskStatus.RUNNING, assigned=True)
    with pytest.raises(TaskTransitionError):
        transition_task(task, TaskStatus.FAILED)
