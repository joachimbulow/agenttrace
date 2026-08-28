"""Primo data cleanup pipeline. See pipeline/orchestrator.py for the
graph shape and the carried-forward open questions/assumptions.
"""

from __future__ import annotations

import asyncio

from agent_trace_sdk import Tracer, set_current_span

from agent_workflows.models.schemas import PipelineOutcome
from agent_workflows.pipeline.orchestrator import run_pipeline
from agent_workflows.utils.tracing import ingest_endpoint


async def run_primo_cleanup_pipeline(csv_path: str) -> list[PipelineOutcome]:
    """Run the pipeline under a traced agent run.

    Export failures (backend down) do not fail the workflow itself.
    """
    result: list[PipelineOutcome] | None = None
    try:
        # `Tracer.__enter__` creates the root span but doesn't push it as the
        # ambient "current span"; pushing it explicitly via `set_current_span`
        # (rather than entering the `Span` context manager a second time,
        # which would end/export it twice) is what lets
        # AgentTraceCallbackHandler's fallback (see utils/tracing.py) resolve
        # each record's graph run as a child of this root instead of an
        # orphaned top-level span.
        with Tracer(name="primo_kogen_pipeline", endpoint=ingest_endpoint()) as root_span:
            set_current_span(root_span)
            try:
                result = await run_pipeline(csv_path)
            finally:
                set_current_span(None)
        # The SDK schedules span export (and the final flush on __exit__) as
        # fire-and-forget tasks on the running loop rather than awaiting
        # them -- fine in a long-lived server, but in a short-lived CLI
        # process like this one the event loop can close before those tasks
        # run. Give them a beat to finish so traces actually reach the
        # backend; failures here still don't fail the workflow.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    except Exception:
        if result is None:
            raise
    return result
