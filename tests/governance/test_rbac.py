"""Tests for src/governance/rbac.py."""
from __future__ import annotations

import pytest

from src.governance.rbac import (
    RATE_LIMITS,
    ROLES,
    PermissionDenied,
    PolicyEngine,
    Requester,
)
from src.state import SubQuestion


def _requester(role: str, session_id: str = "session-1") -> Requester:
    return Requester(user_id="u1", role=role, session_id=session_id)


# --- constants --------------------------------------------------------

def test_roles_tuple():
    assert ROLES == ("viewer", "analyst", "senior_analyst", "admin")


def test_rate_limits_values():
    assert RATE_LIMITS == {
        "viewer": 20,
        "analyst": 50,
        "senior_analyst": None,
        "admin": None,
    }


# --- check_rate_limit ---------------------------------------------------

def test_rate_limit_trips_at_exactly_the_configured_count_and_not_before():
    engine = PolicyEngine()
    requester = _requester("viewer")

    # requests 1-20 (the configured limit) must all succeed
    for _ in range(RATE_LIMITS["viewer"]):
        engine.check_rate_limit(requester)  # must not raise

    # the 21st request is over the limit
    with pytest.raises(PermissionDenied, match="rate limit exceeded"):
        engine.check_rate_limit(requester)


def test_rate_limit_uses_the_correct_role_specific_cap():
    engine = PolicyEngine()
    requester = _requester("analyst")

    for _ in range(RATE_LIMITS["analyst"]):
        engine.check_rate_limit(requester)

    with pytest.raises(PermissionDenied):
        engine.check_rate_limit(requester)


@pytest.mark.parametrize("role", ["senior_analyst", "admin"])
def test_unlimited_roles_never_trip_rate_limit(role):
    engine = PolicyEngine()
    requester = _requester(role)

    for _ in range(500):
        engine.check_rate_limit(requester)  # must never raise


def test_rate_limit_counts_are_isolated_per_session():
    engine = PolicyEngine()
    session_a = _requester("viewer", session_id="session-a")
    session_b = _requester("viewer", session_id="session-b")

    for _ in range(RATE_LIMITS["viewer"]):
        engine.check_rate_limit(session_a)

    # session_b has made zero requests so far -- must not be affected
    # by session_a's count
    engine.check_rate_limit(session_b)  # must not raise


def test_rate_limit_denial_reports_the_request_number():
    engine = PolicyEngine()
    requester = _requester("viewer")
    for _ in range(RATE_LIMITS["viewer"]):
        engine.check_rate_limit(requester)

    with pytest.raises(PermissionDenied) as exc_info:
        engine.check_rate_limit(requester)

    assert "#21" in exc_info.value.reason


def test_check_rate_limit_raises_on_unknown_role():
    engine = PolicyEngine()
    requester = _requester("superuser")

    with pytest.raises(PermissionDenied, match="unknown role"):
        engine.check_rate_limit(requester)


# --- check_mode_permission ----------------------------------------------

def test_viewer_denied_aggregate_mode_question():
    engine = PolicyEngine()
    requester = _requester("viewer")
    sub_questions = [
        SubQuestion(text="Compare revenue across companies", mode="aggregate")
    ]

    with pytest.raises(PermissionDenied, match="aggregate-mode"):
        engine.check_mode_permission(requester, sub_questions)


def test_viewer_denied_two_entity_comparison_question():
    engine = PolicyEngine()
    requester = _requester("viewer")
    sub_questions = [
        SubQuestion(text="Acme revenue", mode="targeted", entity_hint="Acme Robotics"),
        SubQuestion(text="Borealis revenue", mode="targeted", entity_hint="Borealis Foods"),
    ]

    with pytest.raises(PermissionDenied, match="spans 2 companies"):
        engine.check_mode_permission(requester, sub_questions)


def test_viewer_allowed_single_company_multi_hop_question():
    engine = PolicyEngine()
    requester = _requester("viewer")
    sub_questions = [
        SubQuestion(text="Acme products", mode="targeted", entity_hint="Acme Robotics"),
        SubQuestion(text="Acme risks", mode="targeted", entity_hint="Acme Robotics"),
    ]

    engine.check_mode_permission(requester, sub_questions)  # must not raise


def test_viewer_allowed_open_search_with_no_entity_hint():
    engine = PolicyEngine()
    requester = _requester("viewer")
    sub_questions = [SubQuestion(text="What is a robotic arm?", mode="search")]

    engine.check_mode_permission(requester, sub_questions)  # must not raise


@pytest.mark.parametrize("role", ["analyst", "senior_analyst", "admin"])
def test_higher_roles_allowed_aggregate_and_comparison_questions(role):
    engine = PolicyEngine()
    requester = _requester(role)
    sub_questions = [
        SubQuestion(text="Acme revenue", mode="targeted", entity_hint="Acme Robotics"),
        SubQuestion(text="Borealis revenue", mode="targeted", entity_hint="Borealis Foods"),
        SubQuestion(text="Compare both", mode="aggregate"),
    ]

    engine.check_mode_permission(requester, sub_questions)  # must not raise


def test_check_mode_permission_raises_on_unknown_role():
    engine = PolicyEngine()
    requester = _requester("superuser")

    with pytest.raises(PermissionDenied, match="unknown role"):
        engine.check_mode_permission(requester, [])


# --- shared PermissionDenied shape --------------------------------------

def test_every_denial_path_is_the_same_exception_type_with_a_reason():
    engine = PolicyEngine()
    viewer = _requester("viewer")

    denials = []

    for _ in range(RATE_LIMITS["viewer"]):
        engine.check_rate_limit(viewer)
    try:
        engine.check_rate_limit(viewer)
    except PermissionDenied as exc:
        denials.append(exc)

    try:
        engine.check_mode_permission(
            viewer, [SubQuestion(text="q", mode="aggregate")]
        )
    except PermissionDenied as exc:
        denials.append(exc)

    try:
        engine.check_mode_permission(
            viewer,
            [
                SubQuestion(text="q1", mode="targeted", entity_hint="Acme Robotics"),
                SubQuestion(text="q2", mode="targeted", entity_hint="Borealis Foods"),
            ],
        )
    except PermissionDenied as exc:
        denials.append(exc)

    assert len(denials) == 3
    for denial in denials:
        assert isinstance(denial, PermissionDenied)
        assert denial.reason.strip() != ""
        assert denial.requester == viewer
