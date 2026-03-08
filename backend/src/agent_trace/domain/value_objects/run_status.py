from enum import Enum


class RunStatus(Enum):
    """Status of an agent run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"