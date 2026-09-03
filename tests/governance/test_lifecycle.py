"""Tests for src/governance/lifecycle.py."""
from __future__ import annotations

import dataclasses

import pytest

from src.governance.lifecycle import (
    LIFECYCLE_STAGES,
    CapabilityVersionRecord,
    mark_stage_complete,
    stages_remaining,
)

_EXPECTED_STAGE_NAMES = [
    "Intake & Use-Case Definition",
    "Risk & Data-Classification Assessment",
    "RBAC & Access Design",
    "Architecture & Tooling Design",
    "Build / Implementation",
    "Guardrail & Prompt-Injection Defense Design",
    "Unit & Integration Testing",
    "Adversarial / Red-Team Testing",
    "Human-in-the-Loop UAT",
    "Staging Gate / Promotion Checks",
    "Production Deployment (simulated)",
    "Runtime Monitoring & KPI Tracking",
    "Incident Response",
    "Retirement / Decommission",
]


def _new_record(stages_completed: list[int] | None = None) -> CapabilityVersionRecord:
    return CapabilityVersionRecord(
        capability_name="research_assistant",
        version="v1",
        stages_completed=stages_completed or [],
        risk_tier="Medium",
        status="in_development",
        created_at="2026-09-03T00:00:00Z",
    )


# --- LIFECYCLE_STAGES shape ------------------------------------------------

def test_has_exactly_fourteen_stages():
    assert len(LIFECYCLE_STAGES) == 14


def test_stage_numbers_are_1_through_14_in_order():
    assert [stage.number for stage in LIFECYCLE_STAGES] == list(range(1, 15))


def test_stage_names_match_the_plan_exactly():
    assert [stage.name for stage in LIFECYCLE_STAGES] == _EXPECTED_STAGE_NAMES


def test_every_stage_has_non_empty_fields():
    for stage in LIFECYCLE_STAGES:
        assert stage.name.strip() != ""
        assert len(stage.artifact_paths) > 0
        assert all(path.strip() != "" for path in stage.artifact_paths)
        assert stage.kind in {"doc", "code", "doc+code"}
        assert stage.owner_role.strip() != ""


def test_documentation_only_stages_are_kind_doc():
    # stages 1, 2, 4 are explicitly documentation-only in the plan
    doc_only_numbers = {1, 2, 4}
    for stage in LIFECYCLE_STAGES:
        if stage.number in doc_only_numbers:
            assert stage.kind == "doc"


def test_lifecycle_stage_is_frozen():
    stage = LIFECYCLE_STAGES[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        stage.number = 99  # type: ignore[misc]


# --- CapabilityVersionRecord -----------------------------------------------

def test_capability_version_record_defaults():
    record = _new_record()
    assert record.promoted_at is None
    assert record.retired_at is None
    assert record.status == "in_development"
    assert record.risk_tier == "Medium"


# --- stages_remaining --------------------------------------------------

def test_stages_remaining_returns_all_when_none_completed():
    record = _new_record()
    remaining = stages_remaining(record)
    assert [s.number for s in remaining] == list(range(1, 15))


def test_stages_remaining_excludes_completed_stages():
    record = _new_record(stages_completed=[1, 2, 4])
    remaining = stages_remaining(record)
    assert [s.number for s in remaining] == [3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def test_stages_remaining_is_stage_number_order_even_if_completed_list_is_not():
    record = _new_record(stages_completed=[4, 1, 2])
    remaining = stages_remaining(record)
    assert [s.number for s in remaining] == [3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def test_stages_remaining_empty_when_all_completed():
    record = _new_record(stages_completed=list(range(1, 15)))
    assert stages_remaining(record) == []


# --- mark_stage_complete -----------------------------------------------

def test_mark_stage_complete_adds_stage():
    record = _new_record(stages_completed=[1])
    updated = mark_stage_complete(record, 2)
    assert updated.stages_completed == [1, 2]


def test_mark_stage_complete_does_not_mutate_original_record():
    record = _new_record(stages_completed=[1])
    mark_stage_complete(record, 2)
    assert record.stages_completed == [1]  # unchanged


def test_mark_stage_complete_keeps_result_sorted_regardless_of_insertion_order():
    record = _new_record(stages_completed=[])
    record = mark_stage_complete(record, 5)
    record = mark_stage_complete(record, 1)
    record = mark_stage_complete(record, 3)
    assert record.stages_completed == [1, 3, 5]


def test_mark_stage_complete_is_idempotent():
    record = _new_record(stages_completed=[1, 2])
    updated = mark_stage_complete(record, 2)
    assert updated.stages_completed == [1, 2]  # no duplicate


def test_mark_stage_complete_raises_on_unknown_stage_number():
    record = _new_record()
    with pytest.raises(ValueError, match="not a known lifecycle stage number"):
        mark_stage_complete(record, 15)


def test_mark_stage_complete_raises_on_zero_or_negative():
    record = _new_record()
    with pytest.raises(ValueError):
        mark_stage_complete(record, 0)
    with pytest.raises(ValueError):
        mark_stage_complete(record, -1)
