"""Control-flow ONLY -- wires the pipeline's nodes into a LangGraph
`StateGraph`, no business logic. All the actual "what does this mean"
logic lives in `agent_workflows.agents.*` and `agent_workflows.services.*`,
each exposed as an LCEL `Runnable` (see those modules). Graph nodes
(`*_node`) live next to their agent chain; this module only wires them.

Graph shape:

    gate
      |-- known --> enrich (dmr_subagent + db2_vehicle_subagent, parallel)
      |               --> diagnose (dmr / db2 / rules paths, parallel, converge)
      |                     --> judge (mocked LLM-as-judge)
      |                           --> determine_result (threshold)
      |                                 |-- correct_validate (Path A)
      |                                 |-- save_result      (Path B)
      |-- unknown --> reject (early-exit outcome, no further nodes run)

================================================================================
LangGraph/LangChain wiring notes -- non-obvious bits of *how* the graph
above is built and traced, as opposed to *what* it does:
================================================================================

1. "enrich" and "diagnose" are each ONE graph node, even though they fan
   out internally (2 and 3 parallel sub-agents respectively). The
   sub-agents still get their own nested trace span -- that comes from
   `agent_workflows.utils.tracing.leaf()`, which the sub-agent Runnables
   are wrapped in, not from adding them as separate graph nodes. Making
   them real graph nodes too would require extra fan-out/fan-in edges for
   no benefit: the parallelism is already fully expressed by each node's
   own LCEL `RunnableParallel` composition (see agents/enrich/agent.py,
   agents/diagnose/agent.py).

2. Every agent node forwards the `config` LangGraph passes it into the
   corresponding agent chain's `.ainvoke(input, config)` call. This is
   required, not cosmetic: `config` carries the callback manager that
   links a chain run to its parent in the trace tree. Drop it (e.g. call
   `.ainvoke(input)` with no config) and that sub-agent still runs
   correctly, but its span silently detaches into its own untraced root
   instead of nesting under this node.

3. Each node's `span_type` (e.g. judge's `"llm_call"`) is set via the
   `metadata` passed to `add_node` below, not on the agent chain itself --
   see `agent_workflows.utils.tracing.AgentTraceCallbackHandler` for how a
   node's Pregel-wrapper run turns into a span with that type.

KNOWN OPEN QUESTIONS / ASSUMPTIONS -- carried forward from the source spec.
Do NOT resolve these silently; confirm with the domain/source team. See also
workflows/README.md, which repeats this list for visibility.
================================================================================

1. "Diagnose/Propose: three parallel paths" -- unconfirmed whether this
   really means DMR + DB2 + rules, or something else. The rules-based third
   path in `agents/diagnose/agent.py` is an assumption made to fill out the
   count, not a confirmed requirement.

2. The real Primo CSV extract schema (columns) is not finalized.
   `services/csv_loader.py` is deliberately schema-tolerant (only requires
   `policy_id` and `task_type`) -- adjust once the real schema is known.

3. `agents/determine_result/agent.py`'s CONFIDENCE_THRESHOLD (0.75) is a
   placeholder, not calibrated against real data or SME input.

See also `agents/judge/agent.py` for a fourth, narrower implementation
choice about how "conflict" is defined between the DMR and DB2 paths.
================================================================================
"""

from __future__ import annotations

import asyncio

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
from agent_workflows.utils.tracing import agent_trace_callback_handler


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


async def _run_record(record: RawRecord) -> PipelineOutcome:
    """Run one record through the graph."""
    final_state = await _GRAPH.ainvoke(
        {"record": record},
        config={
            "callbacks": [agent_trace_callback_handler],
            "run_name": f"primo_kogen_record[{record.policy_id}]",
        },
    )
    return final_state["outcome"]


async def run_pipeline(csv_path: str) -> list[PipelineOutcome]:
    """Load `csv_path` and run every record through the pipeline.

    Records are processed concurrently (each gets its own graph run); this
    doesn't change the per-record graph shape described above, and each
    record's spans nest under its own `primo_kogen_record[<policy_id>]`
    span rather than being interleaved flat under the pipeline root.
    """
    records = load_records(csv_path)
    return await asyncio.gather(*(_run_record(record) for record in records))
