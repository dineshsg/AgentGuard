# Intake & Use-Case Definition

**Lifecycle stage:** 1 of 14 — Intake & Use-Case Definition
**Kind:** process/documentation artifact (a sign-off form, not code)
**Owner role:** `product_owner`

This is the entry point for any new agentic AI capability: before any
design or code work starts, the requesting team fills this form out and a
governance reviewer signs off that the use case is understood well enough
to proceed to Stage 2 (Risk & Data-Classification Assessment). Nothing
below this line is boilerplate — every field is filled in for real for
this project's own capability, exactly as a requesting team would.

---

## Template

| Field | Description |
|---|---|
| Capability name | The short, stable identifier used everywhere downstream (lifecycle records, audit logs, deployment manifests) |
| Requesting team / sponsor | Who owns the business need |
| Business problem | What manual process or gap this replaces or augments |
| Intended users | Who queries it, and their role/access level |
| Inputs | What the system reads (data sources, user-supplied text) |
| Outputs | What the system produces, and who consumes it |
| Automation level | Does a human review every output, some outputs, or none before it's acted on? |
| Success criteria | How "working" will be measured |
| Explicitly out of scope | What this capability will NOT do, to bound scope creep |
| Known constraints | Budget, timeline, data-residency, or tooling constraints |

---

## Filled example — this project's capability

| Field | Value |
|---|---|
| **Capability name** | `research_assistant` |
| **Requesting team / sponsor** | Business Research & Analytics (fictional sponsor, for this portfolio project) |
| **Business problem** | Analysts spend significant manual time pulling facts (products, financials, risk factors, leadership, competitive position) out of scattered company documents to answer research questions. This capability answers a natural-language question by retrieving the relevant internal documents and composing a cited, grounded answer, instead of an analyst reading through documents by hand. |
| **Intended users** | Internal analysts of varying seniority (`viewer`, `analyst`, `senior_analyst`) and an `admin` role for system operators — see [`03_role_matrix.md`](03_role_matrix.md) once Stage 3 lands. |
| **Inputs** | A natural-language question from an authenticated requester, and the internal document knowledge base (`data/kb_docs.json`) it retrieves against. The system never accepts arbitrary file uploads or external URLs as input. |
| **Outputs** | A composed answer with inline citations to specific source documents, returned to the requester. Every returned answer is either auto-approved (met the groundedness bar) or routed to a human reviewer — never silently discarded. |
| **Automation level** | Partial. The base pipeline (planner → researcher → writer → critic) auto-approves an answer once its own Critic is satisfied (`GROUNDEDNESS_THRESHOLD = 0.6`). The governance layer being built on top of it applies a **stricter** bar before anything reaches an end user unsupervised (`HUMAN_REVIEW_GROUNDEDNESS_THRESHOLD = 0.75`) — anything in between is queued for human review rather than auto-returned. This two-tier design is the direct output of this intake process: it is what "the agent thinks it's done" being distinct from "safe to hand to a person with no oversight" looks like in practice. |
| **Success criteria** | (measured for real in Stage 5) keyword recall, citation coverage, groundedness, and approval rate against a held-out eval set; later, indirect-injection defense pass rate (Stage 10) and governance KPIs (Stage 12). |
| **Explicitly out of scope** | No write access to any system of record — this capability only reads and summarizes; it cannot file, send, or modify anything on a user's behalf. No PII or regulated personal data is in scope for the knowledge base. No autonomous multi-step task execution beyond answering one research question per request. |
| **Known constraints** | Zero paid third-party API dependency required to run or test the system (LLM provider is swappable — OpenAI, LiteLLM, Ollama, or LM Studio — via `LLM_PROVIDER`, see `src/llm_backend.py`); the governance layer itself must run with zero network dependency at all (pure Python), independent of which LLM backend the agents use. |

**Sign-off:** Use case is understood and bounded enough to proceed to Stage
2 (Risk & Data-Classification Assessment). See
[`02_risk_assessment.md`](02_risk_assessment.md).
