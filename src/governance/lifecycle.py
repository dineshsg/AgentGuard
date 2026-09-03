"""
src/governance/lifecycle.py

The 14-stage agent lifecycle model (see GOVERNANCE_BUILD_PLAN.md, S2),
encoded as data rather than asserted in prose -- LIFECYCLE_STAGES is the
literal source of truth for what each stage produces and who owns it,
so lifecycle coverage is checkable at a glance (or in a test) rather
than argued about in a README.

CapabilityVersionRecord tracks ONE RELEASED VERSION of a capability
(e.g. "research_assistant" v1) through these 14 stages -- deliberately
distinct from src/governance/audit_log.py (a later stage), which tracks
individual runtime REQUESTS. A capability has one lifecycle record per
version; it can field thousands of audited requests against that same
version.

This module has no runtime dependency on anything else in
src/governance/ -- it's pure bookkeeping data, imported by
promotion_gate.py and deployment_manifest.py (both later stages) to
check/update stages_completed and status.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class LifecycleStage:
    number: int
    name: str
    artifact_paths: list[str]
    kind: str  # "doc" | "code" | "doc+code"
    owner_role: str  # e.g. "product_owner", "security_lead", "ml_engineer", "sre"


LIFECYCLE_STAGES: list[LifecycleStage] = [
    LifecycleStage(
        number=1,
        name="Intake & Use-Case Definition",
        artifact_paths=["governance/01_intake_form.md"],
        kind="doc",
        owner_role="product_owner",
    ),
    LifecycleStage(
        number=2,
        name="Risk & Data-Classification Assessment",
        artifact_paths=["governance/02_risk_assessment.md"],
        kind="doc",
        owner_role="security_lead",
    ),
    LifecycleStage(
        number=3,
        name="RBAC & Access Design",
        artifact_paths=["governance/03_role_matrix.md", "src/governance/rbac.py"],
        kind="doc+code",
        owner_role="security_lead",
    ),
    LifecycleStage(
        number=4,
        name="Architecture & Tooling Design",
        artifact_paths=["governance/04_architecture_notes.md"],
        kind="doc",
        owner_role="ml_engineer",
    ),
    LifecycleStage(
        number=5,
        name="Build / Implementation",
        artifact_paths=[
            "src/agents/planner.py",
            "src/agents/researcher.py",
            "src/agents/writer.py",
            "src/agents/critic.py",
            "src/orchestrator.py",
        ],
        kind="code",
        owner_role="ml_engineer",
    ),
    LifecycleStage(
        number=6,
        name="Guardrail & Prompt-Injection Defense Design",
        artifact_paths=[
            "src/governance/injection_guard.py",
            "src/governance/redteam_corpus.py",
        ],
        kind="code",
        owner_role="security_lead",
    ),
    LifecycleStage(
        number=7,
        name="Unit & Integration Testing",
        artifact_paths=["tests/governance/"],
        kind="code",
        owner_role="ml_engineer",
    ),
    LifecycleStage(
        number=8,
        name="Adversarial / Red-Team Testing",
        artifact_paths=[
            "src/governance/redteam_eval.py",
            "reports/governance/redteam_eval_report.json",
        ],
        kind="code",
        owner_role="security_lead",
    ),
    LifecycleStage(
        number=9,
        name="Human-in-the-Loop UAT",
        artifact_paths=[
            "governance/09_uat_checklist.md",
            "src/governance/human_review_queue.py",
        ],
        kind="doc+code",
        owner_role="product_owner",
    ),
    LifecycleStage(
        number=10,
        name="Staging Gate / Promotion Checks",
        artifact_paths=[
            "src/governance/promotion_gate.py",
            "reports/governance/promotion_record.json",
        ],
        kind="code",
        owner_role="sre",
    ),
    LifecycleStage(
        number=11,
        name="Production Deployment (simulated)",
        artifact_paths=[
            "src/governance/deployment_manifest.py",
            "reports/governance/deployment_manifest.json",
        ],
        kind="code",
        owner_role="sre",
    ),
    LifecycleStage(
        number=12,
        name="Runtime Monitoring & KPI Tracking",
        artifact_paths=[
            "src/governance/audit_log.py",
            "src/governance/kpi_dashboard.py",
            "reports/governance/governance_dashboard.json",
        ],
        kind="code",
        owner_role="sre",
    ),
    LifecycleStage(
        number=13,
        name="Incident Response",
        artifact_paths=[
            "src/governance/incident_response.py",
            "reports/governance/incidents.json",
        ],
        kind="code",
        owner_role="sre",
    ),
    LifecycleStage(
        number=14,
        name="Retirement / Decommission",
        artifact_paths=["governance/14_retirement_runbook.md"],
        kind="doc+code",
        owner_role="product_owner",
    ),
]


@dataclass
class CapabilityVersionRecord:
    """One record per released version of a capability -- NOT per
    query. Tracks which lifecycle stages this version has passed,
    distinct from the audit log (a later stage), which tracks
    individual runtime requests."""

    capability_name: str
    version: str
    stages_completed: list[int]
    risk_tier: str  # "Low" | "Medium" | "High" -- from Stage 2
    status: str  # "in_development" | "staging" | "production" | "retired"
    created_at: str
    promoted_at: str | None = None
    retired_at: str | None = None


def stages_remaining(record: CapabilityVersionRecord) -> list[LifecycleStage]:
    """Every LifecycleStage not yet in record.stages_completed, in
    stage-number order -- regardless of what order stages_completed
    itself lists them in."""
    completed = set(record.stages_completed)
    return [stage for stage in LIFECYCLE_STAGES if stage.number not in completed]


def mark_stage_complete(
    record: CapabilityVersionRecord, stage_number: int
) -> CapabilityVersionRecord:
    """Returns a NEW CapabilityVersionRecord with stage_number added to
    stages_completed, kept sorted; the original record is left
    untouched (callers that want to persist the change reassign their
    own reference, the pattern dataclasses.replace encourages). Raises
    ValueError for an unknown stage number. Marking an already-completed
    stage is a no-op, not a duplicate entry."""
    valid_numbers = {stage.number for stage in LIFECYCLE_STAGES}
    if stage_number not in valid_numbers:
        raise ValueError(
            f"mark_stage_complete: {stage_number!r} is not a known lifecycle "
            f"stage number (valid: 1-{len(LIFECYCLE_STAGES)})"
        )
    if stage_number in record.stages_completed:
        return replace(record)
    new_completed = sorted(record.stages_completed + [stage_number])
    return replace(record, stages_completed=new_completed)
