# Human-in-the-Loop UAT Checklist

**Lifecycle stage:** 9 of 14 — Human-in-the-Loop UAT
**Kind:** doc + code (this checklist + [`src/governance/human_review_queue.py`](../src/governance/human_review_queue.py))
**Owner role:** `product_owner`

This is the actual checklist a reviewer works through for every item in
[`src/governance/human_review_queue.py`](../src/governance/human_review_queue.py)
— not a summary of one. An item lands here for exactly one of two
reasons (`HumanReviewItem.reason`), and both mean the same thing in
practice: *the system itself isn't confident enough to hand this to the
user without a person looking at it first.*

| Reason | What it means |
|---|---|
| `below_human_review_threshold` | The base Critic approved the draft (groundedness ≥ 0.6), but it didn't clear the governance layer's stricter `HUMAN_REVIEW_GROUNDEDNESS_THRESHOLD` (0.75) — "good enough for the agent to stop revising itself" is not the same bar as "safe to show a user unsupervised." |
| `max_iterations_without_full_approval` | The Critic never approved the draft at all, and the revision budget (`MAX_ITERATIONS = 3`) ran out. |

## What the reviewer checks, in order

1. **Citation accuracy.** For every `[doc_id]` citation in the draft
   answer, open the cited document and confirm the claim next to it is
   actually supported. A citation that points at the wrong document, or
   a claim the cited document doesn't actually say, is the single most
   important thing to catch — it's what makes an answer look grounded
   without being grounded.
2. **Is the groundedness gap a real hallucination, or just a
   terse-but-correct answer?** These look identical to the automated
   Critic in one specific way (both score below 0.75) but require
   opposite actions:
   - A genuine hallucination (a claim with no support anywhere in the
     evidence) → **reject**, and the feedback should say specifically
     which claim was unsupported.
   - A correct, well-cited answer that's just short or plainly worded
     (nothing wrong with it, the Critic's language-based scoring just
     under-rewarded brevity) → **approve**. Don't reject a correct
     answer for not being verbose.
3. **Tone and framing.** Even a fully grounded answer can be phrased in
   a way that overstates confidence ("Acme Robotics will definitely...")
   where the source material only supports a weaker claim ("Acme
   Robotics' risk factors mention..."). Flag overstated framing even
   when every fact is technically correct.
4. **Scope.** Does the answer stay within what was actually asked, or
   does it wander into unrelated territory the evidence doesn't cover
   (which would itself be a sign the retrieved evidence was thin and the
   model filled gaps from its own general knowledge instead)?
5. **Injection residue.** If this item's request also triggered an
   `injection_scan` audit event anywhere in its trace (check the audit
   log for the request), treat that as a red flag regardless of what the
   draft answer itself looks like — a scan hit means something in the
   pipeline saw suspicious content, even if the guard's severity was
   only `Medium` and didn't block the request outright.

## Decision

Every review ends in exactly one call to
[`resolve(item_id, decision)`](../src/governance/human_review_queue.py)
with `decision` being `"approved"` or `"rejected"` — no third option, no
silent skip. An item a reviewer isn't sure about should be treated as
`"rejected"` with feedback explaining the uncertainty, not left pending
indefinitely.

## SLA

A real team running this capability at Medium risk tier (see
[`02_risk_assessment.md`](02_risk_assessment.md)) would target:

| Metric | Target |
|---|---|
| Time to first review | Within 4 business hours of enqueue |
| Time to resolution | Within 1 business day |
| Reviewer agreement spot-check | A second reviewer re-checks 10% of resolved items weekly; disagreement on more than 1 in 20 triggers a checklist review, not just a reviewer conversation |

Stated here as a target, not a measured number — this project has no
live traffic to measure a real SLA against; the honest label for this
number is "what a real team would target," not "what we observed."

**Sign-off:** Checklist reflects what `human_review_queue.py` actually
stores and what `resolve()` actually accepts. Proceed to Stage 10
(already complete) and Stage 11 (already complete) continuing toward
Stage 12 (Runtime Monitoring & KPI Tracking).
