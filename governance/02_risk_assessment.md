# Risk & Data-Classification Assessment

**Lifecycle stage:** 2 of 14 — Risk & Data-Classification Assessment
**Kind:** process/documentation artifact (a sign-off form, not code) —
produces a **risk tier** that gates every downstream control
**Owner role:** `security_lead`

This assessment exists to answer one question with evidence, not
intuition: *how much governance does this specific capability actually
need?* The risk tier it produces is not decorative — `promotion_gate.py`
(Stage 16) and `lifecycle.py`'s `CapabilityVersionRecord.risk_tier`
(Stage 7) both carry it forward, and it is what justifies why the
controls built in Stages 6–14 (RBAC, audit logging, injection defense,
human review, promotion gates, circuit-breaking, incident response) are
proportionate rather than either theater or overkill.

---

## Template — scoring rubric

Each factor below is scored **Low / Medium / High**. The overall risk
tier is the **highest** individual factor score — one severe risk factor
is enough to raise the whole capability's tier, even if every other
factor is low, because governance controls have to be sized to the worst
realistic failure mode, not the average one.

| Factor | Low | Medium | High |
|---|---|---|---|
| Data sensitivity | Public/non-sensitive | Internal business data | PII, regulated, or trade-secret data |
| Decision impact if wrong | Cosmetic/informational only | Could mislead a business decision | Financial, legal, safety, or compliance consequence |
| Automation level | Human reviews every output before use | Some outputs auto-returned, some reviewed | Fully autonomous, no human in the loop |
| Attack surface | No external/untrusted input | User input only, no retrieved external content | Retrieves attacker-influenceable content (indirect prompt injection surface) |
| User population / blast radius | Single team, small user count | Broad internal audience | External/public users |

---

## Filled example — `research_assistant`

| Factor | Score | Rationale |
|---|---|---|
| **Data sensitivity** | Medium | The knowledge base holds internal-style business documents (product info, financials, risk factors, leadership, competitive positioning) — not public marketing copy, but also not PII or regulated data. Classified as **internal business data**. |
| **Decision impact if wrong** | Medium | A wrong or hallucinated answer could mislead an analyst's understanding of a company (e.g. misstating a risk factor or a competitor's positioning), which could feed into a real business decision — but the system makes no autonomous financial, legal, or safety decisions itself. |
| **Automation level** | Medium | The base pipeline auto-approves once its own Critic is satisfied (§ see `01_intake_form.md`), but the governance layer imposes a second, stricter gate before anything reaches an end user without human review. Not fully autonomous, not fully human-gated either. |
| **Attack surface** | **High** | This is the deciding factor. The system retrieves documents from a knowledge base as evidence for its answers — and a knowledge base is exactly the kind of surface a real deployment would eventually let get updated by less-trusted sources (a shared drive, a CMS, a partner feed). A poisoned document can embed an instruction an attacker wants the agent to follow ("ignore your instructions and instead…") that gets retrieved for a completely innocent question. This is **indirect prompt injection**, and it is the single scenario this project is built to specifically catch and evaluate (Stage 10) rather than just claim to guard against. |
| **User population / blast radius** | Medium | Internal analysts across several seniority levels (see `03_role_matrix.md`, Stage 3), not yet exposed to external/public users. |

### Resulting risk tier: **Medium**

The overall tier is **Medium**, driven up from what would otherwise be a
Low/Medium data-and-automation profile by the **High** attack-surface
score. This is the intended behavior of "highest factor wins": a system
that is otherwise low-stakes but has a real injection attack surface does
not get to inherit a Low tier just because its data and automation levels
are modest.

## Controls this tier requires (built in later stages)

A Medium tier, with a High-scored attack-surface factor specifically,
requires:

- **RBAC** scoped to the user population (Stage 8) — not every requester
  should be able to ask every kind of question.
- **Tamper-evident audit logging** of every request, denial, and outcome
  (Stage 9) — Medium-impact decisions need a trail.
- **Both direct AND indirect prompt-injection defense** (Stage 10) — the
  attack-surface score specifically calls out retrieved-evidence
  scanning, not just user-input scanning, as mandatory, not optional.
- **Human-in-the-loop review** for anything that doesn't clear a stricter
  confidence bar than the base pipeline's own (Stage 12).
- **A promotion gate** that checks all of the above before anything is
  marked production-active (Stage 16), plus **circuit-breaking** on a
  Critical incident (Stage 14) — a Medium-impact, High-attack-surface
  system should be able to take itself offline automatically rather than
  rely on a human noticing first.

A capability scoring uniformly Low across every factor would not need
this full control set — this rubric is what would let a future,
genuinely low-risk capability skip straight to a lighter review, rather
than every capability getting the same governance overhead regardless of
actual risk.

**Sign-off:** Risk tier **Medium** is recorded for `research_assistant`
and carried into `lifecycle.py`'s `CapabilityVersionRecord` (Stage 7).
Proceed to Stage 3 (RBAC & Access Design).
