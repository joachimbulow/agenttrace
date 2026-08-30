from __future__ import annotations

import asyncio
from dataclasses import replace

from agent_trace_sdk import Tracer, get_current_run_id
from agent_trace_sdk.langchain import AgentTraceCallbackHandler
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent_workflows.agents.correct_validate.agent import correct_validate_node
from agent_workflows.agents.determine_result.agent import determine_result_node
from agent_workflows.agents.diagnose.agent import diagnose_node
from agent_workflows.agents.enrich.agent import enrich_node
from agent_workflows.agents.gate.agent import gate_node, reject_node
from agent_workflows.agents.judge.agent import judge_node
from agent_workflows.agents.save_result.agent import save_result_node
from agent_workflows.models.schemas import PipelineOutcome, RawRecord
from agent_workflows.pipeline.state import PipelineState
from agent_workflows.services.csv_loader import load_records


def _route_known(state: PipelineState) -> str:
    assert state.gate is not None
    return "enrich" if state.gate.known else "reject"


def _route_branch(state: PipelineState) -> str:
    assert state.decision is not None
    return state.decision.branch


def _build_graph() -> CompiledStateGraph[PipelineState]:
    builder = StateGraph(PipelineState)
    builder.add_node("gate", gate_node, metadata={"span_type": "step"})
    builder.add_node("reject", reject_node, metadata={"span_type": "step"})
    builder.add_node("enrich", enrich_node, metadata={"span_type": "step"})
    builder.add_node("diagnose", diagnose_node, metadata={"span_type": "step"})
    builder.add_node("judge", judge_node, metadata={"span_type": "llm_call"})
    builder.add_node("determine_result", determine_result_node, metadata={"span_type": "step"})
    builder.add_node("correct_validate", correct_validate_node, metadata={"span_type": "step"})
    builder.add_node("save_result", save_result_node, metadata={"span_type": "step"})

    builder.set_entry_point("gate")
    builder.add_conditional_edges("gate", _route_known, {"enrich": "enrich", "reject": "reject"})
    builder.add_edge("enrich", "diagnose")
    builder.add_edge("diagnose", "judge")
    builder.add_edge("judge", "determine_result")
    builder.add_conditional_edges(
        "determine_result",
        _route_branch,
        {"correct_validate": "correct_validate", "save_result": "save_result"},
    )
    builder.add_edge("reject", END)
    builder.add_edge("correct_validate", END)
    builder.add_edge("save_result", END)

    return builder.compile()


_GRAPH = _build_graph()


async def _run_record(
    record: RawRecord,
    handler: AgentTraceCallbackHandler,
) -> PipelineOutcome:
    """Run one record through the graph."""
    final_state = await _GRAPH.ainvoke(
        {"record": record},
        config={
            "callbacks": [handler],
            "run_name": f"primo_record[{record.record_id}]",
            "metadata": {
                "record_id": record.record_id,
                "policy_id": record.policy_id,
            },
        },
    )
    outcome = final_state["outcome"]
    return replace(outcome, run_id=get_current_run_id())


async def run_pipeline(csv_path: str, *, tracer: Tracer) -> list[PipelineOutcome]:
    """Load `csv_path` and run every record through the pipeline.

    Records are processed concurrently (each gets its own graph run); this
    doesn't change the per-record graph shape described above, and each
    record's spans nest under its own `primo_record[<record_id>]`
    span rather than being interleaved flat under the pipeline root.
    """
    handler = AgentTraceCallbackHandler(
        tracer, attribute_keys=("record_id", "policy_id")
    )
    records = load_records(csv_path)
    return await asyncio.gather(*(_run_record(record, handler) for record in records))
