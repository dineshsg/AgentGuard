# Build stages

This project is built and pushed in discrete stages — one commit (and
push) per stage — so the history is reviewable incrementally rather than
as a single large drop. Each stage below lists the artifacts it produces;
check them off as they land.

Source spec for the governance layer (stages 6–20): `GOVERNANCE_BUILD_PLAN.md`
(the original design document this build follows section-by-section).

## Phase A — Base project: Multi-Agent Research Assistant

The governance plan assumed this already existed; it didn't, so it's built
first, with a real multi-provider LLM backend powering the agents.

- [x] **Stage 1 — Repo scaffold + LLM backend.** `src/llm_backend.py`
      (OpenAI / LiteLLM / Ollama / LM Studio, all config via env vars),
      `.env.example`, `requirements.txt`, `.gitignore`, base `README.md`,
      `tests/test_llm_backend.py`.
- [ ] **Stage 2 — Core data model + retriever.** `src/state.py`
      (`SubQuestion`, `SubAnswer`, `CritiqueResult`, `ResearchState`),
      `src/retriever.py` (`RetrievedDoc` + retrieval), `data/kb_docs.json`.
- [ ] **Stage 3 — Agents.** `src/agents/planner.py`, `researcher.py`,
      `writer.py`, `critic.py` — LLM-backed via `src/llm_backend.py`.
- [ ] **Stage 4 — Orchestrator + tools.** `src/orchestrator.py`
      (`AgentGraph`, `build_research_graph`, `ResearchOrchestrator`),
      `src/tools.py`.
- [ ] **Stage 5 — Eval harness + base tests + README.**
      `data/eval_set.json`, `evaluate.py`, `reports/eval_report.json`,
      `tests/*.py`, base `README.md` filled in with real eval numbers.

## Phase B — AgentGuard governance layer

Follows `GOVERNANCE_BUILD_PLAN.md` §15's build order exactly.

- [ ] **Stage 6 — Governance docs.** `governance/01_intake_form.md`,
      `02_risk_assessment.md`, `04_architecture_notes.md`.
- [ ] **Stage 7 — Lifecycle model.** `src/governance/lifecycle.py`
      (`LifecycleStage`, `LIFECYCLE_STAGES`, `CapabilityVersionRecord`).
- [ ] **Stage 8 — RBAC.** `src/governance/rbac.py`,
      `tests/governance/test_rbac.py`, `governance/03_role_matrix.md`.
- [ ] **Stage 9 — Audit log.** `src/governance/audit_log.py` (hash-chained,
      tamper-evident), `tests/governance/test_audit_log.py`.
- [ ] **Stage 10 — Injection guard (centerpiece).**
      `src/governance/injection_guard.py`, `redteam_corpus.py`,
      `tests/governance/test_injection_guard.py` — including the indirect
      clean-question/poisoned-document scenario.
- [ ] **Stage 11 — Red-team eval.** `src/governance/redteam_eval.py`,
      `reports/governance/redteam_eval_report.json` (real run).
- [ ] **Stage 12 — Human review queue.**
      `src/governance/human_review_queue.py`,
      `governance/09_uat_checklist.md`.
- [ ] **Stage 13 — Governed orchestrator.**
      `src/governance/governed_orchestrator.py`,
      `tests/governance/test_governed_orchestrator.py` (all 5 response
      paths: answered, denied, blocked, pending_human_review, rate-limited).
- [ ] **Stage 14 — Deployment + incident response.**
      `src/governance/deployment_manifest.py`, `incident_response.py`,
      `reports/governance/incident_simulation_trace.json` (real 8-step run).
- [ ] **Stage 15 — Backlog generation.** `src/governance/backlog.py`
      (local JSON + optional Jira connector), wired into the promotion
      gate and incident-response failure paths.
- [ ] **Stage 16 — Promotion gate.** `src/governance/promotion_gate.py`,
      `tests/governance/test_promotion_gate.py`,
      `reports/governance/promotion_record.json` (real run).
- [ ] **Stage 17 — KPI dashboard.** `src/governance/kpi_dashboard.py`,
      `reports/governance/governance_dashboard.json` (real run).
- [ ] **Stage 18 — Retirement.** `governance/14_retirement_runbook.md`,
      `deployment_manifest.retire()` exercised by a test.
- [ ] **Stage 19 — README governance section.** `GOVERNANCE_BUILD_PLAN.md`
      §14, written from real numbers in `reports/governance/*.json` only.
- [ ] **Stage 20 — Full regression + acceptance checklist.** Run the full
      base + governance test suite together; verify every item in
      `GOVERNANCE_BUILD_PLAN.md` §16; final commit.

## Ground rules carried through every stage

- Nothing under `src/` outside `src/governance/` is touched once Phase A
  is done — the governance layer is additive only.
- `src/governance/*` has zero LLM/network dependency (pure
  dataclasses/regex/JSON) — the LLM backend is used by the base agents
  only.
- No secret, API key, or endpoint is ever hardcoded — all via env vars,
  documented in `.env.example`.
- Every number that ends up in the README traces to a real file under
  `reports/`, not a hand-typed estimate.
- One stage = one commit = one push to `main` (direct push, no PRs — solo
  portfolio repo).
