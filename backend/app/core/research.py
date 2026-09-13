from enum import StrEnum


class ConnectorStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ResearchStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchSourceStatus(StrEnum):
    CAPTURED = "captured"
    INGESTED = "ingested"
    FAILED = "failed"
