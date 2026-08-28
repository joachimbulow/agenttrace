from agent_workflows.pipeline.state import PipelineState

__all__ = ["PipelineState", "run_pipeline"]


def __getattr__(name: str):
    # Lazy: importing orchestrator here would re-enter agent modules that
    # themselves import PipelineState through this package.
    if name == "run_pipeline":
        from agent_workflows.pipeline.orchestrator import run_pipeline

        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
