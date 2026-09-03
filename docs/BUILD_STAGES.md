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
- [x] **Stage 2 — Core data model + retriever.** `src/state.py`
      (`SubQuestion`, `SubAnswer`, `CritiqueResult`, `ResearchState`),
      `src/retriever.py` (`RetrievedDoc` + TF-IDF retrieval),
      `data/kb_docs.json` (25 docs: 5 fictional companies x 5 doc types).
- [x] **Stage 3 — Agents.** `src/agents/planner.py`, `researcher.py`,
      `writer.py`, `critic.py` — LLM-backed via `src/llm_backend.py`
      (researcher is the one exception: pure retrieval, no LLM call).
      Shared `src/agents/_json_util.py` for robust structured-output
      parsing (markdown fences, stray prose).
- [x] **Stage 4 — Orchestrator + tools.** `src/orchestrator.py`
      (`AgentGraph`, `build_research_graph`, `ResearchOrchestrator`),
      `src/tools.py`. `AgentGraph` is fully generic (typed over any
      State) so the governance layer's second graph (stage 13) reuses
      it unmodified, exactly as the spec requires.
- [x] **Stage 5 — Eval harness + base tests + README.**
      `data/eval_set.json` (18 questions), `evaluate.py`,
      `reports/eval_report.json` (real run against LM Studio,
      `qwen2.5-7b-instruct`: 100% approval, 0.961 groundedness, 1.00
      citation coverage, 0.917 keyword recall), `tests/test_evaluate.py`,
      base `README.md` filled in with these real numbers (including an
      honest note on eval-17's partial-citation weakness). Phase A
      (the base research assistant) is now complete.

## Phase B — AgentGuard governance layer

Follows `GOVERNANCE_BUILD_PLAN.md` §15's build order exactly.

- [x] **Stage 6 — Governance docs.** `governance/01_intake_form.md`,
      `02_risk_assessment.md` (produces risk tier **Medium** — Medium
      data sensitivity/decision-impact/automation, but High attack
      surface from indirect prompt injection, and highest factor wins),
      `04_architecture_notes.md` (references the existing pipeline,
      does not redesign it). Pure documentation, no code, as the plan
      requires for these three lifecycle stages.
- [x] **Stage 7 — Lifecycle model.** `src/governance/lifecycle.py`
      (`LifecycleStage`, `LIFECYCLE_STAGES` — all 14 rows of the plan's
      table as data, `CapabilityVersionRecord`, `stages_remaining`,
      `mark_stage_complete`). Pure bookkeeping, no dependency on the
      rest of `src/governance/`.
- [x] **Stage 8 — RBAC.** `src/governance/rbac.py` (`ROLES`,
      `RATE_LIMITS`, `Requester`, `PermissionDenied`, `PolicyEngine`
      with `check_rate_limit`/`check_mode_permission`),
      `tests/governance/test_rbac.py`, `governance/03_role_matrix.md`.
- [x] **Stage 9 — Audit log.** `src/governance/audit_log.py` (`AuditRecord`,
      `AuditLog.append`/`read_all`, `verify_audit_chain` — SHA-256
      hash-chained, tamper-evident), `tests/governance/test_audit_log.py`
      including the required corruption test (mutate one record's
      payload in place, confirm `verify_audit_chain` fails at the exact
      `seq`).
- [x] **Stage 10 — Injection guard (centerpiece).**
      `src/governance/injection_guard.py` (`scan_question`/
      `scan_document`, direct + exfil + indirect-marker categories,
      exfil requires phrase+nearby-URL as two independent signals),
      `redteam_corpus.py` (15 benign questions reused from
      `data/eval_set.json`, 13 direct-attack questions, 6 poisoned
      documents, 6 clean-question/poisoned-document pairs),
      `tests/governance/test_injection_guard.py` — 78 tests, including
      the centerpiece scenario passing for all 6 pairs and every real
      `data/kb_docs.json` document correctly staying unflagged.
- [x] **Stage 11 — Red-team eval.** `src/governance/redteam_eval.py`
      (`evaluate_direct_guard`/`evaluate_document_guard`/
      `evaluate_indirect_scenario`), `reports/governance/redteam_eval_report.json`
      — real run: 1.0 precision/recall/F1 on both direct and document
      guards, 100% (6/6) pass rate on the centerpiece indirect scenario.
- [x] **Stage 12 — Human review queue.**
      `src/governance/human_review_queue.py` (`HumanReviewItem`,
      `enqueue`/`resolve`/`list_pending`, plain JSON array on disk —
      deliberately not the hash-chained audit log format, since items
      need in-place status updates),
      `governance/09_uat_checklist.md` (what a reviewer actually
      checks, and a stated-as-target-not-measured SLA).
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
