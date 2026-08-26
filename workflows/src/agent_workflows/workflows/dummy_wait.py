"""Dummy wait workflow. Replace with a LangGraph later; keep this composition layer."""

from __future__ import annotations

from agent_trace_sdk import Tracer

from agent_workflows.nodes.wait import wait_node
from agent_workflows.types.state import WaitState
from agent_workflows.utils.tracing import ingest_endpoint


def run_dummy_wait(seconds: float = 1.0) -> WaitState:
    """Run the wait node under a traced agent run.

    Export failures (backend down) do not fail the workflow itself.
    """
    result: WaitState | None = None
    try:
        with Tracer(name="dummy_wait", endpoint=ingest_endpoint()):
            result = wait_node(WaitState(seconds=seconds))
    except Exception:
        if result is None:
            raise
    return result
