from enum import Enum


class SpanType(Enum):
    """Type of trace span."""

    AGENT_RUN = "agent_run"
    STEP = "step"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"