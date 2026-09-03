# RBAC Role Matrix

**Lifecycle stage:** 3 of 14 — RBAC & Access Design
**Kind:** doc + code (this document + [`src/governance/rbac.py`](../src/governance/rbac.py))
**Owner role:** `security_lead`

This is the artifact a real access-review meeting would produce and sign
off on: it mirrors `src/governance/rbac.py`'s `ROLES`/`RATE_LIMITS`/
`PolicyEngine` exactly — if this table and the code ever disagree, the
code is what actually runs, and this document is wrong and needs fixing,
not the other way around. `tests/governance/test_rbac.py` (Stage 8)
verifies the code's behavior directly; nothing here is enforced by this
markdown file on its own.

Risk context: this capability carries an overall risk tier of **Medium**
(see [`02_risk_assessment.md`](02_risk_assessment.md)), driven by a
**High** attack-surface score — indirect prompt injection via retrieved
documents. RBAC is one of the controls that Medium tier requires
(§ risk assessment, "controls this tier requires"): not every requester
should be able to ask every kind of question, and the broadest-reach
question types (cross-company synthesis) are the ones most worth
restricting to more trusted roles first.

---

## Role matrix

| Role | Rate limit (per session) | Allowed question types | Can view own audit trail? | Admin capabilities |
|---|---|---|---|---|
| `viewer` | 20 requests | `search` and `targeted` only, and only about **one company at a time** — no `aggregate`-mode questions, no cross-company comparisons | Yes, own requests only | None |
| `analyst` | 50 requests | Unrestricted — `search`, `targeted`, `aggregate`; any single company or comparison across companies | Yes, own requests only | None |
| `senior_analyst` | Unlimited | Unrestricted — same as `analyst` | Yes, own requests only | None |
| `admin` | Unlimited | Unrestricted — same as `analyst` | Yes, any requester's requests | Disable/retire a capability version (circuit breaker), resolve items in the human-review queue, manage role assignments |

## Why `viewer` is scoped this way

`viewer` is the entry-level, lowest-trust role — the one a new or
external-facing account would be granted first. Two restrictions apply,
enforced by `PolicyEngine.check_mode_permission`:

1. **No `aggregate`-mode questions.** An aggregate question needs the
   Researcher to pull a larger evidence set and the Writer to synthesize
   across it — more surface area for an ungrounded or subtly wrong
   answer to slip through, and the kind of question a lower-trust role
   is least equipped to sanity-check before acting on.
2. **No cross-company questions.** A `viewer` may still ask multiple,
   multi-hop questions about a single company (e.g. products, then
   risks, then leadership, all about the same company across separate
   requests or sub-questions) — that's still single-hop-within-one-company
   in spirit. What's blocked is any single request whose sub-questions
   collectively touch more than one company's `entity_hint`, since a
   comparison is exactly the kind of higher-context-window, higher-stakes
   question this role shouldn't get by default.

`analyst` and above are never restricted by `check_mode_permission` —
the mode/entity restriction exists specifically to bound what the
lowest-trust role can do, not as a blanket policy.

## Rate limiting: a stated, deliberate simplification

`RATE_LIMITS` is enforced by an **in-memory** per-session counter on the
`PolicyEngine` instance (`src/governance/rbac.py`). This is a
portfolio-scale simplification, not a production design: a real
deployment would back this with a shared store (Redis, a database) so
the limit holds across multiple processes and survives a restart. Stated
here plainly rather than left implicit, in keeping with this project's
"say what's real vs. simulated" convention (see the README's honesty
section once Phase B's numbers land).

**Sign-off:** Role matrix reviewed and matches `src/governance/rbac.py`'s
actual enforced behavior, verified by `tests/governance/test_rbac.py`.
Proceed to Stage 4 (Architecture & Tooling Design — already complete)
and Stage 6 (Guardrail & Prompt-Injection Defense Design).
