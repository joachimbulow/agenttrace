"""Primo data cleanup pipeline. See pipeline/orchestrator.py for the
graph shape and the carried-forward open questions/assumptions.
"""

from __future__ import annotations

from agent_trace_sdk import Tracer

from agent_workflows.models.schemas import PipelineOutcome
from agent_workflows.pipeline.orchestrator import run_pipeline
from agent_workflows.utils.tracing import ingest_endpoint


async def run_primo_cleanup_pipeline(csv_path: str) -> list[PipelineOutcome]:
    """Run the pipeline under a traced agent run."""
    tracer = Tracer(name="primo_cleanup_pipeline", endpoint=ingest_endpoint())
    print(f"run_id={tracer.run_id}")
    async with tracer:
        return await run_pipeline(csv_path)
