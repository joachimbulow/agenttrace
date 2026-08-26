"""Traced graph nodes. Keep these thin: state in, logic call, state out."""

from __future__ import annotations

from agent_trace_sdk import trace_span

from agent_workflows.logic.wait import wait_seconds
from agent_workflows.types.state import WaitState


@trace_span(name="wait", span_type="step")
def wait_node(state: WaitState) -> WaitState:
    wait_seconds(state.seconds)
    return WaitState(seconds=state.seconds, status="done")
