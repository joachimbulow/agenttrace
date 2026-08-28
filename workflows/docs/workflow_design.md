# Agent Workflow — Enriched Design (v2)

## 0. Domain context

- **Primo**: legacy policy system at If Insurance (post Topdanmark acquisition), being migrated to **Guidewire** (policy), **TopPro** (claims) and **ArkIf** (historic claims archive).
- **DMR**: external reference register used to validate/align vehicle data (e.g. motor policies). It is the "source of truth" used to detect mismatches (wrong plate, wrong owner, stale vehicle data, etc.) in Primo records.
- **DB2**: the production database behind Primo. Access is read-only, request-based (ServiceNow), and queries against it must respect production-time restrictions ("SQL must not run in production hours"). Second reference source, alongside DMR.
- **Segmentation / Wave 2**: a daily batch job deciding which policies are candidates for migration ("Wave 2 marked") vs excluded. A related runtime locking mechanism mirrors segmentation but runs continuously.
- **HITL (human-in-the-loop)**: SMEs approve correction rules and review any low-confidence proposed change before it's applied. Hard gate for low-confidence cases, never skipped.
- **Evidence pack**: every decision (enrich → diagnose → correct) must carry rationale + a confidence score, so the whole run is auditable.
- **Staging**: cleaned/validated records move to a staging area ("ready to migrate") before actual production migration — this pipeline's job stops at staging.

This PoC operationalizes "Discover & profile → Diagnose & propose → Correct & validate → Document & handover" for a first task type referred to as `12_11` (treat as configuration, not hardcoded).

## 1. Flow, node by node

### Node 1 — Gate: "Do we know this task?"
Filter before any enrichment. Only recognized task types proceed (PoC scope: just `12_11`, but keep it as a configurable set/list, not a hardcoded single literal). Unknown task types are rejected/short-circuited early.
Input: raw row(s) from the CSV extract. Output: `known` (bool) + the classified task, or an early-exit record.

### Node 2 — Enrich (fan-out, 2 parallel sub-agents)
- **DMR Sub-agent**: looks up the record against DMR reference data (vehicle/owner details). Produces a DMR-side finding (retrieved row, or empty data if none).
- **DB2 Vehicle Sub-agent**: queries Primo's DB2 for the corresponding vehicle/policy record, produces a DB2-side finding (same shape). Comparison (match / mismatch / gap) happens in Node 3.
These run independently (implement as genuinely concurrent, e.g. asyncio.gather) and their outputs are merged before diagnosis. Assumption to confirm: sub-agents don't call live DB2/DMR in the PoC — both are mocked.

### Node 3 — Diagnose / Propose (three parallel paths converge)
1. Diagnosis driven by DMR findings
2. Diagnosis driven by DB2 findings
3. Diagnosis driven by rule/pattern checks (segmentation/locking-style business rules)
(See open question #1 above — this third path is an assumption.) Each path compares the extract to its finding (or to a rule), then proposes a correction (or "no issue found") with status, rationale, and confidence. Implement these 3 as genuinely concurrent too.

### Node 4 — LLM as a Judge
Reviews the (possibly conflicting) proposals from the three diagnostic paths and adjudicates a single recommended outcome + confidence. For this scaffold, MOCK the "LLM" call (no real LLM API call) — implement as a deterministic stub that picks the highest-confidence proposal (or flags conflict) and returns a fixed/templated rationale string, clearly marked as a placeholder for a real LLM call later.

### Node 5 — Determine Result
Consumes the Judge's verdict, decides the branch based on confidence threshold and business rules (e.g. high confidence → auto-correct; low confidence/conflict → HITL). Deterministic, no business logic beyond thresholding — the actual "what's true" decision already happened in the Judge step.

### Node 6 — Branch
- **Path A — Correct / Validate** (high confidence): (1) apply the proposed correction (mocked), (2) move record to Staging / Ready to Migrate (mocked).
- **Path B — Save Result** (low confidence/unresolved): (1) persist the result/report as-is (mocked), (2) route to HITL / Cannot-Solve queue (mocked).

## 2. Non-functional requirements
- Every step's output must be traceable: rationale + confidence, never a bare pass/fail.
- No agent should require production-hour DB2 access; mocked/staged data only for the PoC.
- HITL volume should be a deliberate, small subset (i.e. mock data / thresholds should produce a mix of both branches when run over the sample fixture, not 100% one branch).
- GDPR/compliance: no real personal data — synthetic fixtures only.

## 3. Mocking policy
Service logic is extracted out of the agents into services/*, each agent lives in its own module, all external dependencies (DMR, DB2, staging, HITL queue) are mocked as stub functions for now — they define the interface/contract with a `# MOCK` marker and a trivial deterministic return (not `pass`/`NotImplementedError`, since we need the pipeline to actually run end-to-end and produce varied, demoable trace data). This lets a follow-on agent implement one service at a time without touching orchestration.
