"""
src/governance/human_review_queue.py

The escalation path for anything the governed orchestrator (a later
stage) doesn't consider safe to auto-return: a draft answer whose
groundedness cleared the base Critic's own bar
(src/agents/critic.py::GROUNDEDNESS_THRESHOLD = 0.6) but not the
governance layer's stricter HUMAN_REVIEW_GROUNDEDNESS_THRESHOLD (0.75),
or one that ran out of revision budget without ever being fully
approved. Both land here as a HumanReviewItem instead of being silently
returned to the user.

Stored as a plain JSON array on disk -- deliberately NOT
audit_log.py's hash-chained format. This queue's items get their
`status` changed in place as a reviewer works through them, which
audit_log.py's append-only design intentionally does not allow; the
audit log separately records a "routed_to_human_review" event for the
same request, so each concern gets the storage shape it actually needs.

Zero LLM/network dependency (json, dataclasses only), consistent with
the rest of src/governance/.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_QUEUE_PATH = "reports/governance/human_review_queue.json"

VALID_REASONS = {"below_human_review_threshold", "max_iterations_without_full_approval"}
VALID_DECISIONS = {"approved", "rejected"}


@dataclass
class HumanReviewItem:
    id: str
    question: str
    draft_answer: str
    reason: str  # "below_human_review_threshold" | "max_iterations_without_full_approval"
    groundedness: float
    citation_coverage: float
    status: str  # "pending" | "approved" | "rejected"
    created_at: str


def _read_queue(path: str) -> list[dict]:
    queue_path = Path(path)
    if not queue_path.exists():
        return []
    return json.loads(queue_path.read_text(encoding="utf-8"))


def _write_queue(path: str, items: list[dict]) -> None:
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def enqueue(item: HumanReviewItem, path: str = DEFAULT_QUEUE_PATH) -> None:
    if item.reason not in VALID_REASONS:
        raise ValueError(
            f"enqueue: unknown reason {item.reason!r} -- must be one of "
            f"{sorted(VALID_REASONS)}"
        )
    items = _read_queue(path)
    items.append(asdict(item))
    _write_queue(path, items)


def resolve(item_id: str, decision: str, path: str = DEFAULT_QUEUE_PATH) -> HumanReviewItem:
    """Finds the item with `item_id`, sets its status to `decision`, and
    persists the change. Raises ValueError for an invalid decision, or
    KeyError if no item with that id exists in the queue at `path`."""
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"resolve: decision must be one of {sorted(VALID_DECISIONS)}, got {decision!r}"
        )

    items = _read_queue(path)
    for raw in items:
        if raw["id"] == item_id:
            raw["status"] = decision
            _write_queue(path, items)
            return HumanReviewItem(**raw)

    raise KeyError(f"resolve: no queue item with id={item_id!r} found at {path!r}")


def list_pending(path: str = DEFAULT_QUEUE_PATH) -> list[HumanReviewItem]:
    """Every item still awaiting a decision, in the order they were
    enqueued -- what a reviewer's worklist would actually show."""
    return [HumanReviewItem(**raw) for raw in _read_queue(path) if raw["status"] == "pending"]
