from enum import StrEnum


class AgentStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_TASK_STATUSES = frozenset(
    {
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }
)

ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.QUEUED: frozenset({TaskStatus.ASSIGNED, TaskStatus.CANCELLED}),
    TaskStatus.ASSIGNED: frozenset(
        {
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}
