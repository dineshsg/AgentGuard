# AgentGuard

**A governed multi-agent research assistant.** A RAG-based research agent
(planner → researcher → writer → critic, iterating until its answer is
grounded) with a governance and lifecycle layer on top: RBAC, tamper-evident
audit logging, indirect prompt-injection defense, human-review escalation,
promotion gates, deployment circuit-breaking, incident response, and
KPI/backlog reporting.

This repo is built in explicit stages (see [`docs/BUILD_STAGES.md`](docs/BUILD_STAGES.md)),
each committed and pushed separately so progress is reviewable stage by
stage rather than as one large drop.

**Status:** 🚧 in progress — Stage 10 of 20 complete (Phase A, the base
research assistant, is done; Phase B, the AgentGuard governance layer,
is underway).

## Multi-provider LLM backend

Agents call an LLM through [`src/llm_backend.py`](src/llm_backend.py), which
supports four interchangeable providers, selected via the `LLM_PROVIDER`
environment variable:

| Provider | `LLM_PROVIDER` | Needs a key? | Notes |
|---|---|---|---|
| OpenAI | `openai` | Yes — `OPENAI_API_KEY` | Chat Completions API |
| LiteLLM | `litellm` | Depends on what's behind the proxy | Talks to a LiteLLM proxy over HTTP, or the `litellm` SDK directly |
| Ollama | `ollama` | No (local) | Native `/api/chat`, default provider |
| LM Studio | `lmstudio` | No (local) | OpenAI-compatible `/v1/chat/completions` |

Every credential and endpoint is read from an environment variable at call
time — **nothing is hardcoded**. Copy [`.env.example`](.env.example) to
`.env` and fill in only what you use; `.env` is gitignored.

```bash
cp .env.example .env
# edit .env, then:
pip install -r requirements.txt
python -m pytest tests/ -v
```

The `openai` and `litellm` SDKs are lazy-imported — installing
`requirements.txt` alone is enough to run everything against Ollama or LM
Studio (both plain HTTP, no extra SDK).

## Layout

```
src/
  llm_backend.py     # provider-agnostic LLM client            (stage 1)
  state.py            # research state model                    (stage 2)
  retriever.py         # TF-IDF document retrieval                (stage 2)
  agents/              # planner / researcher / writer / critic   (stage 3)
  orchestrator.py      # AgentGraph + ResearchOrchestrator        (stage 4)
  tools.py             # shared reporting helpers                  (stage 4)
  governance/          # AgentGuard governance package          (stages 6-18)
evaluate.py             # eval harness -- run against data/eval_set.json (this stage)
data/                  # knowledge base + eval set              (stages 2, 5)
governance/             # process/sign-off docs (intake, risk, RBAC, UAT, retirement)
reports/                 # real run outputs (eval, redteam, promotion, KPI, incidents)
tests/                   # base project tests + tests/governance/
```

## Base project evaluation

`evaluate.py` runs every question in [`data/eval_set.json`](data/eval_set.json)
(18 questions across all 5 companies plus 2 cross-company comparisons)
through the real pipeline and writes
[`reports/eval_report.json`](reports/eval_report.json). This run used a real
local model — **LM Studio, `qwen2.5-7b-instruct`** — not a mock:

```bash
python evaluate.py
```

| Metric | Value |
|---|---|
| Questions | 18 |
| Approval rate | 100% (18/18 approved by the Critic) |
| Groundedness | 0.961 |
| Citation coverage | 1.00 |
| Keyword recall | 0.917 |
| Mean latency | 16.2s / question |

Keyword recall is a strict, literal substring check against a small
hand-picked keyword list per question — three questions landed at 0.5
because the model's phrasing didn't reuse the exact source string (e.g.
paraphrasing a competitor's product name instead of quoting it), not
because the answer was wrong. Worth stating plainly rather than smoothing
over: one comparison question (`eval-17`, Acme Robotics vs. Borealis Foods
revenue) took 2 revision iterations and its final answer ended up citing
only one of the two companies' documents even though both were retrieved
and separately answered — a real synthesis weakness of this 7B model on a
multi-company question, not a bug in the citation-extraction logic (the
other comparison question, `eval-18`, correctly cited both companies). Full
per-question detail is in `reports/eval_report.json`.

## AgentGuard — Governance & Lifecycle Layer

Added in stages 6–19 (see `docs/BUILD_STAGES.md`). This section will be
filled in with real numbers from `reports/governance/*.json` once those
stages land — no numbers are written here ahead of an actual run.

The process side is underway: [`governance/01_intake_form.md`](governance/01_intake_form.md),
[`02_risk_assessment.md`](governance/02_risk_assessment.md), and
[`04_architecture_notes.md`](governance/04_architecture_notes.md) are
real, filled-in sign-off documents, not templates left blank — the risk
assessment scores this capability **Medium** overall (Medium on data
sensitivity, decision impact, and automation level, but **High** on
attack surface specifically because it retrieves documents as evidence,
which is exactly the indirect prompt-injection surface Stage 10 is built
to catch — highest factor wins). That Medium tier is what the rest of
the governance layer's controls (Stages 8–16) are sized to justify, not
governance applied uniformly regardless of actual risk.

**RBAC** (Stage 8) is live: [`src/governance/rbac.py`](src/governance/rbac.py)
enforces this exactly —

| Role | Rate limit (per session) | Allowed question types | Admin capabilities |
|---|---|---|---|
| `viewer` | 20 requests | `search`/`targeted`, one company at a time only | None |
| `analyst` | 50 requests | Unrestricted | None |
| `senior_analyst` | Unlimited | Unrestricted | None |
| `admin` | Unlimited | Unrestricted | Circuit-break a capability, resolve human-review items, manage roles |

Full rationale in [`governance/03_role_matrix.md`](governance/03_role_matrix.md).

**Audit logging** (Stage 9) is live: [`src/governance/audit_log.py`](src/governance/audit_log.py)
is a hash-chained, append-only log — every record's hash is computed
from its own fields *plus* the previous record's hash, so editing or
deleting any line breaks the chain for every record after it.
`verify_audit_chain()` catches this deterministically; it's proven by a
real test that tampers with one record's payload in place and confirms
detection fails at exactly that record, not just claimed.

**The centerpiece scenario is real and passing** (Stage 10):
[`src/governance/injection_guard.py`](src/governance/injection_guard.py)
scans two independent surfaces — `scan_question` (the user's question)
and `scan_document` (each retrieved piece of evidence) — because a
direct-only guard is trivially incomplete for a RAG system: a
compromised or poisoned data source can embed an instruction ("ignore
your instructions and instead…") inside a document that gets retrieved
for a completely innocent question, and only scanning *retrieved
evidence*, not just the question, catches that. This is a heuristic,
regex-based prototype, stated plainly — a determined attacker can
paraphrase around fixed patterns; the point is the *architecture*
(scan both surfaces, score by category, gate on severity, evaluate
against a labeled corpus), not research-grade robustness.

[`src/governance/redteam_corpus.py`](src/governance/redteam_corpus.py)
pairs 6 poisoned documents with 6 completely benign, on-topic questions
that would legitimately retrieve them. All 6 pass right now: every
paired question scans clean, every paired poisoned document gets
flagged — proven by `tests/governance/test_injection_guard.py`
(78 tests), not just asserted. Precision/recall numbers against the
full labeled corpus land in Stage 11's real `redteam_eval_report.json`.
