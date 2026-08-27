"""Control-flow ONLY -- wires the pipeline's nodes into a LangGraph
`StateGraph`, no business logic. All the actual "what does this mean"
logic lives in `agent_workflows.agents.*` and `agent_workflows.services.*`,
each exposed as an LCEL `Runnable` (see those modules).

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

2. Every node function below forwards the `config` LangGraph passes it
   into the corresponding agent chain's `.ainvoke(input, config)` call.
   This is required, not cosmetic: `config` carries the callback manager
   that links a chain run to its parent in the trace tree. Drop it (e.g.
   call `.ainvoke(input)` with no config) and that sub-agent still runs
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
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from agent_workflows.agents.correct_validate.agent import correct_validate_chain
from agent_workflows.agents.determine_result.agent import determine_result_chain
from agent_workflows.agents.diagnose.agent import diagnose_chain
from agent_workflows.agents.enrich.agent import enrich_chain
from agent_workflows.agents.gate.agent import gate_chain
from agent_workflows.agents.judge.agent import judge_chain
from agent_workflows.agents.save_result.agent import save_result_chain
from agent_workflows.models.schemas import (
    DiagnosisResult,
    EnrichmentResult,
    GateResult,
    JudgeVerdict,
    PipelineOutcome,
    RawRecord,
    ResultDecision,
)
from agent_workflows.services.csv_loader import load_records
from agent_workflows.utils.tracing import agent_trace_callback_handler


class PipelineState(TypedDict, total=False):
    """State threaded through the graph for one record. Each key is
    written by exactly one node, so no custom reducers are needed."""

    record: RawRecord
    gate: GateResult
    enrichment: EnrichmentResult
    diagnosis: DiagnosisResult
    verdict: JudgeVerdict
    decision: ResultDecision
    outcome: PipelineOutcome


async def _gate_step(state: PipelineState, config: RunnableConfig) -> dict:
    gate = await gate_chain.ainvoke(state["record"], config)
    return {"gate": gate}


def _reject_step(state: PipelineState) -> dict:
    gate = state["gate"]
    return {
        "outcome": PipelineOutcome(
            policy_id=gate.record.policy_id,
            task_type=gate.record.task_type,
            known=False,
            branch=None,
            confidence=None,
            summary=gate.reason,
        )
    }


async def _enrich_step(state: PipelineState, config: RunnableConfig) -> dict:
    enrichment = await enrich_chain.ainvoke(state["gate"], config)
    return {"enrichment": enrichment}


async def _diagnose_step(state: PipelineState, config: RunnableConfig) -> dict:
    diagnosis = await diagnose_chain.ainvoke(state["enrichment"], config)
    return {"diagnosis": diagnosis}


async def _judge_step(state: PipelineState, config: RunnableConfig) -> dict:
    verdict = await judge_chain.ainvoke(state["diagnosis"], config)
    return {"verdict": verdict}


async def _determine_result_step(state: PipelineState, config: RunnableConfig) -> dict:
    decision = await determine_result_chain.ainvoke(state["verdict"], config)
    return {"decision": decision}


async def _correct_validate_step(state: PipelineState, config: RunnableConfig) -> dict:
    outcome = await correct_validate_chain.ainvoke(state["decision"], config)
    return {"outcome": outcome}


async def _save_result_step(state: PipelineState, config: RunnableConfig) -> dict:
    outcome = await save_result_chain.ainvoke(state["decision"], config)
    return {"outcome": outcome}


def _route_known(state: PipelineState) -> str:
    return "enrich" if state["gate"].known else "reject"


def _route_branch(state: PipelineState) -> str:
    return state["decision"].branch


def _build_graph() -> StateGraph:
    builder = StateGraph(PipelineState)
    builder.add_node("gate", _gate_step, metadata={"span_type": "step"})
    builder.add_node("reject", _reject_step, metadata={"span_type": "step"})
    builder.add_node("enrich", _enrich_step, metadata={"span_type": "step"})
    builder.add_node("diagnose", _diagnose_step, metadata={"span_type": "step"})
    builder.add_node("judge", _judge_step, metadata={"span_type": "llm_call"})
    builder.add_node("determine_result", _determine_result_step, metadata={"span_type": "step"})
    builder.add_node("correct_validate", _correct_validate_step, metadata={"span_type": "step"})
    builder.add_node("save_result", _save_result_step, metadata={"span_type": "step"})

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
