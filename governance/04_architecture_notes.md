# Architecture & Tooling Design

**Lifecycle stage:** 4 of 14 — Architecture & Tooling Design
**Kind:** design document (references existing code, does not redesign it)
**Owner role:** `ml_engineer`

This document describes the architecture the governance layer (Stages
6–18) attaches to. It does not propose changes to `src/state.py`,
`src/orchestrator.py`, `src/agents/*.py`, `src/retriever.py`, or
`src/tools.py` — those already exist (built in Stages 1–5) and are
treated here as a fixed foundation. The governance layer is additive:
new code in a new `src/governance/` package, plus one new CLI entry
point, that wraps and observes this foundation without modifying it.

---

## The existing base pipeline (Stages 1–5, already built)

```
                    ┌──────────────────────────────────────────┐
                    │              AgentGraph                    │
                    │   (src/orchestrator.py, generic runner)    │
                    └──────────────────────────────────────────┘

   question
      │
      ▼
   ┌──────┐   sub_questions   ┌───────────┐   sub_answers    ┌───────┐
   │ plan │ ────────────────▶ │  research  │ ───────────────▶ │ write │
   └──────┘                   └───────────┘                   └───────┘
   PlannerAgent.plan()        ResearcherAgent.research()      WriterAgent
                               + WriterAgent.write_sub_answer() .compose_final_answer()
                               (retrieval AND sub-answer                │
                                writing happen together here)           ▼
                                                                   ┌──────────┐
                                                     ┌───────────▶ │ critique │
                                                     │ revise      └──────────┘
                                                     │ (loop back      │  CriticAgent.critique()
                                                     │  to research)   │
                                                     └─────────────────┤
                                                                       │ approved, or
                                                                       │ out of revisions
                                                                       ▼
                                                                  final answer
                                                                  + citations
```

Every node is a plain function over `ResearchState` (`src/state.py`).
`AgentGraph` itself (`src/orchestrator.py`) is **generic** — typed over
any state, not just `ResearchState` — specifically so the governed
pipeline below can reuse it unmodified rather than needing its own graph
runner.

Each of the four agents (`src/agents/{planner,researcher,writer,critic}.py`)
calls an LLM through `src/llm_backend.py`, a provider-agnostic client
supporting OpenAI, LiteLLM, Ollama, and LM Studio, selected via
`LLM_PROVIDER` and configured entirely through environment variables (see
`.env.example`) — no key or endpoint is ever hardcoded. `ResearcherAgent`
is the one exception: it makes no LLM call at all, just a deterministic
TF-IDF lookup (`src/retriever.py`) over `data/kb_docs.json`.

`evaluate.py` (Stage 5) is the one script in the base project that makes
real, un-mocked calls against whatever backend is configured — every
agent's own test suite fakes the LLM entirely (`tests/conftest.py::FakeBackend`),
by design, so the test suite never depends on a live model being
reachable.

## Where the governance layer attaches

The governance layer does **not** edit `build_research_graph` or
`ResearchOrchestrator`. Instead, `src/governance/governed_orchestrator.py`
(Stage 13) builds a **second** `AgentGraph` instance, over a new
`GovernedResearchState` wrapper (`core: ResearchState` plus governance
fields), by reusing the same four agent objects' methods in new node
closures — a deliberate, small, explicitly-justified duplication (four
thin node closures, one line different each) traded for keeping the base
pipeline's code and tests completely untouched. The new graph adds one
new node the base graph doesn't have:

```
"plan" -> "research" -> "scan_evidence" -[conditional]-> "write" (or stop if blocked)
"write" -> "critique" -[conditional]-> "research" (revise)
                                       | stop (auto-return)
                                       | stop (routed to human review)
```

`scan_evidence` is why the base pipeline's "research" node was designed
(Stage 4) to populate each `SubAnswer.evidence` immediately, in the same
node that does retrieval — it lets this new node inspect every retrieved
document for injected instructions **before** any of them are shown to
the Writer agent, which is what actually stops an indirect-injection
payload from ever reaching a prompt, rather than just detecting it after
the fact.

## New tooling introduced by the governance layer

No new third-party dependency. Everything under `src/governance/` is
pure Python (dataclasses, `re`, `hashlib`, `json`) — deliberately zero
LLM/network dependency, independent of whichever LLM backend the base
agents are configured to use. This mirrors the base project's own
environment commitment and keeps the governance layer testable and
demonstrable with no API key and no running model at all.

New modules, each a thin, single-responsibility layer over the base
pipeline (full detail in each stage's own section of
`GOVERNANCE_BUILD_PLAN.md`):

| Module | Responsibility |
|---|---|
| `lifecycle.py` | The 14-stage model itself + per-version tracking |
| `rbac.py` | Role-based rate limits and mode permissions |
| `injection_guard.py` + `redteam_corpus.py` | Direct + indirect prompt-injection detection and its labeled eval corpus |
| `audit_log.py` | Hash-chained, tamper-evident request logging |
| `human_review_queue.py` | The escalation path for anything below the stricter confidence bar |
| `governed_orchestrator.py` | The second graph wiring all of the above together |
| `deployment_manifest.py` + `incident_response.py` | Production status, circuit-breaking, incident records |
| `backlog.py` | Turns gate failures and incidents into tracked work items |
| `promotion_gate.py` | The one place all of the above's pass/fail thresholds are checked together |
| `kpi_dashboard.py` | Technical + governance + business-framing KPIs, computed from the real reports above |

**Sign-off:** Architecture is understood, references the existing
pipeline without redesigning it, and identifies exactly where and how
the governance layer attaches. Proceed to Stage 5 (already complete) and
Stage 6 (Guardrail & Prompt-Injection Defense Design).
