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

**Status:** 🚧 in progress — Stage 2 of 20 complete.

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
  state.py            # research state model (this stage)
  retriever.py         # TF-IDF document retrieval (this stage)
  agents/              # planner / researcher / writer / critic (stage 3)
  orchestrator.py      # AgentGraph + ResearchOrchestrator     (stage 4)
  tools.py             # shared agent tools                    (stage 4)
  governance/          # AgentGuard governance package          (stages 6-18)
data/                  # knowledge base + eval set              (stages 2, 5)
governance/             # process/sign-off docs (intake, risk, RBAC, UAT, retirement)
reports/                 # real run outputs (eval, redteam, promotion, KPI, incidents)
tests/                   # base project tests + tests/governance/
```

## AgentGuard — Governance & Lifecycle Layer

Added in stages 6–19 (see `docs/BUILD_STAGES.md`). This section will be
filled in with real numbers from `reports/governance/*.json` once those
stages land — no numbers are written here ahead of an actual run.
