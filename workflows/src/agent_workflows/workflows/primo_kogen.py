"""Primo/Kogen data cleanup pipeline. See pipeline/orchestrator.py for the
graph shape and the carried-forward open questions/assumptions.
"""

from __future__ import annotations

import asyncio

from agent_trace_sdk import Tracer

from agent_workflows.models.schemas import PipelineOutcome
from agent_workflows.pipeline.orchestrator import run_pipeline
from agent_workflows.utils.tracing import ingest_endpoint


async def run_primo_kogen(csv_path: str) -> list[PipelineOutcome]:
    """Run the pipeline under a traced agent run.

    Export failures (backend down) do not fail the workflow itself.
    """
    result: list[PipelineOutcome] | None = None
    try:
        with Tracer(name="primo_kogen_pipeline", endpoint=ingest_endpoint()):
            result = await run_pipeline(csv_path)
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
