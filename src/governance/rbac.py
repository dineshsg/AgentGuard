"""
src/governance/rbac.py

Role-based access control for the research_assistant capability: rate
limiting and question-mode restrictions, applied in the exact two-phase
order the governed orchestrator (a later stage) needs:

  1. check_rate_limit(requester)                       -- before planning
  2. check_mode_permission(requester, sub_questions)     -- after planning

check_rate_limit runs first because it's the cheapest possible check --
there's no reason to run the Planner (an LLM call) for a request that's
already over quota. check_mode_permission necessarily runs after
planning, since it needs the Planner's classified SubQuestion.mode/
entity_hint values, which don't exist until the Planner has run.

Every PermissionDenied is meant to be caught by the governed orchestrator
and turned into an audit-logged denial, never left as an unhandled
exception.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.state import SubQuestion

ROLES = ("viewer", "analyst", "senior_analyst", "admin")

RATE_LIMITS: dict[str, int | None] = {
    "viewer": 20,
    "analyst": 50,
    "senior_analyst": None,
    "admin": None,
}
# None = unlimited. Counted per Requester.session_id, in an in-memory
# dict on the PolicyEngine instance, reset whenever the process
# restarts. This is a portfolio-scale simplification, stated plainly
# rather than left implicit: a real deployment would back this with a
# shared store (Redis, a database) so the limit holds across processes
# and survives a restart, not an in-memory dict scoped to one instance.


@dataclass
class Requester:
    """A minimal identity: who is asking, what role they hold, and
    which session their requests are being rate-limited under. Plain
    data on purpose -- role validity is checked where it matters
    (PolicyEngine), not here."""

    user_id: str
    role: str  # must be in ROLES -- validated by PolicyEngine, not here
    session_id: str


class PermissionDenied(Exception):
    """Raised by every PolicyEngine check that fails. `reason` is a
    specific, human-readable string naming exactly why -- never a bare
    exception with no explanation, since the governed orchestrator (a
    later stage) audit-logs this string verbatim."""

    def __init__(self, reason: str, requester: Requester) -> None:
        self.reason = reason
        self.requester = requester
        super().__init__(
            f"{reason} (user_id={requester.user_id!r}, role={requester.role!r})"
        )


def _validate_role(requester: Requester) -> None:
    if requester.role not in ROLES:
        raise PermissionDenied(
            f"unknown role {requester.role!r} -- must be one of {ROLES}",
            requester,
        )


class PolicyEngine:
    """Stateful only in the narrow, documented sense above: an
    in-memory per-session request counter for check_rate_limit. Every
    other check is stateless."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def check_rate_limit(self, requester: Requester) -> None:
        """Raises PermissionDenied once a session has made MORE than
        its role's limit of requests -- the Nth request within the
        limit succeeds, the (N+1)th is denied. A None limit
        (senior_analyst, admin) never denies."""
        _validate_role(requester)
        limit = RATE_LIMITS[requester.role]

        count = self._counts.get(requester.session_id, 0) + 1
        self._counts[requester.session_id] = count

        if limit is not None and count > limit:
            raise PermissionDenied(
                f"rate limit exceeded: role {requester.role!r} is limited to "
                f"{limit} request(s) per session (this is request #{count})",
                requester,
            )

    def check_mode_permission(
        self, requester: Requester, sub_questions: list[SubQuestion]
    ) -> None:
        """Only the viewer role is restricted here:
          - denied if ANY sub_question.mode == "aggregate"
          - denied if the distinct set of non-null entity_hint values
            across sub_questions has length > 1 (any cross-company
            comparison or multi-company synthesis question)
        analyst/senior_analyst/admin are never restricted by this
        check -- they may ask anything the Planner is willing to plan."""
        _validate_role(requester)
        if requester.role != "viewer":
            return

        if any(sq.mode == "aggregate" for sq in sub_questions):
            raise PermissionDenied(
                "viewer role may not ask aggregate-mode questions "
                "(cross-document synthesis) -- upgrade to analyst or above",
                requester,
            )

        distinct_entities = {sq.entity_hint for sq in sub_questions if sq.entity_hint}
        if len(distinct_entities) > 1:
            raise PermissionDenied(
                "viewer role is restricted to single-company questions; this "
                f"request spans {len(distinct_entities)} companies "
                f"({', '.join(sorted(distinct_entities))}) -- upgrade to "
                "analyst or above",
                requester,
            )
