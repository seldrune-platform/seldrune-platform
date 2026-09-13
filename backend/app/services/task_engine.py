from datetime import datetime, timezone

from backend.app.core.tasking import (
    ALLOWED_TASK_TRANSITIONS,
    TERMINAL_TASK_STATUSES,
    TaskStatus,
)
from backend.app.models.task import Task


class TaskTransitionError(ValueError):
    pass


def transition_task(
    task: Task,
    target_status: TaskStatus | str,
    *,
    output_data: dict | None = None,
    error_message: str | None = None,
) -> Task:
    current_status = TaskStatus(task.status)
    target = TaskStatus(target_status)

    if target not in ALLOWED_TASK_TRANSITIONS[current_status]:
        raise TaskTransitionError(
            f"Cannot transition task from {current_status.value} to {target.value}"
        )

    if target in {TaskStatus.ASSIGNED, TaskStatus.RUNNING} and task.assigned_agent_id is None:
        raise TaskTransitionError("Task must have an assigned agent")

    if target is TaskStatus.FAILED and not error_message:
        raise TaskTransitionError("Failed tasks require an error message")

    now = datetime.now(timezone.utc)
    task.status = target.value

    if target is TaskStatus.QUEUED:
        task.assigned_agent_id = None
        task.started_at = None
        task.completed_at = None
        task.output_data = None
        task.error_message = None

    if target is TaskStatus.RUNNING and task.started_at is None:
        task.started_at = now

    if target is TaskStatus.SUCCEEDED:
        task.output_data = output_data or {}
        task.error_message = None

    if target is TaskStatus.FAILED:
        task.error_message = error_message

    if target in TERMINAL_TASK_STATUSES:
        task.completed_at = now

    return task
