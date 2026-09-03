"""Tests for src/governance/human_review_queue.py."""
from __future__ import annotations

import json

import pytest

from src.governance.human_review_queue import (
    HumanReviewItem,
    enqueue,
    list_pending,
    resolve,
)


def _item(item_id: str = "item-1", reason: str = "below_human_review_threshold") -> HumanReviewItem:
    return HumanReviewItem(
        id=item_id,
        question="What does Acme Robotics sell?",
        draft_answer="Acme Robotics sells robotic arms [acme-products].",
        reason=reason,
        groundedness=0.68,
        citation_coverage=1.0,
        status="pending",
        created_at="2026-09-03T00:00:00Z",
    )


# --- enqueue --------------------------------------------------------------

def test_enqueue_creates_new_file_with_one_item(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item(), path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["id"] == "item-1"
    assert data[0]["status"] == "pending"


def test_enqueue_appends_to_existing_queue_preserving_order(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))
    enqueue(_item("item-2"), path=str(path))
    enqueue(_item("item-3"), path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert [d["id"] for d in data] == ["item-1", "item-2", "item-3"]


def test_enqueue_raises_on_invalid_reason(tmp_path):
    path = tmp_path / "queue.json"
    bad_item = _item(reason="not_a_real_reason")

    with pytest.raises(ValueError, match="unknown reason"):
        enqueue(bad_item, path=str(path))


def test_enqueue_accepts_both_valid_reasons(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1", reason="below_human_review_threshold"), path=str(path))
    enqueue(_item("item-2", reason="max_iterations_without_full_approval"), path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2


# --- resolve ---------------------------------------------------------------

def test_resolve_updates_status_to_approved(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))

    resolved = resolve("item-1", "approved", path=str(path))

    assert resolved.status == "approved"
    assert resolved.id == "item-1"


def test_resolve_updates_status_to_rejected(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))

    resolved = resolve("item-1", "rejected", path=str(path))

    assert resolved.status == "rejected"


def test_resolve_persists_change_to_disk(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))

    resolve("item-1", "approved", path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["status"] == "approved"


def test_resolve_only_changes_the_targeted_item(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))
    enqueue(_item("item-2"), path=str(path))

    resolve("item-1", "approved", path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    statuses = {d["id"]: d["status"] for d in data}
    assert statuses == {"item-1": "approved", "item-2": "pending"}


def test_resolve_raises_on_invalid_decision(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))

    with pytest.raises(ValueError, match="decision must be one of"):
        resolve("item-1", "maybe", path=str(path))


def test_resolve_raises_on_unknown_item_id(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))

    with pytest.raises(KeyError, match="no queue item with id"):
        resolve("does-not-exist", "approved", path=str(path))


# --- list_pending -----------------------------------------------------

def test_list_pending_returns_only_pending_items(tmp_path):
    path = tmp_path / "queue.json"
    enqueue(_item("item-1"), path=str(path))
    enqueue(_item("item-2"), path=str(path))
    enqueue(_item("item-3"), path=str(path))
    resolve("item-2", "approved", path=str(path))

    pending = list_pending(path=str(path))

    assert [item.id for item in pending] == ["item-1", "item-3"]


def test_list_pending_empty_for_nonexistent_queue(tmp_path):
    path = tmp_path / "does_not_exist.json"
    assert list_pending(path=str(path)) == []


def test_queue_items_round_trip_all_fields_exactly(tmp_path):
    path = tmp_path / "queue.json"
    original = _item("item-1")
    enqueue(original, path=str(path))

    pending = list_pending(path=str(path))

    assert len(pending) == 1
    assert pending[0] == original
