"""
src/governance/audit_log.py

A hash-chained, append-only audit log: every AuditRecord's record_hash
is computed from its own fields PLUS the previous record's record_hash,
so mutating or deleting any line breaks the chain for every subsequent
record. verify_audit_chain() walks the file and recomputes each record's
hash independently to catch that deterministically -- this is what makes
the log tamper-EVIDENT, not just "append-only by convention" (a plain
text file with no verification is trivially editable and no one would
know).

payload is meant to hold event-specific details (a denial reason, a scan
result, a groundedness score) -- callers should never put full document
text in it, to keep records small and avoid duplicating the knowledge
base inside the log. This module doesn't enforce that (it has no way to
know what's "too much"); it's guidance for callers, stated here and in
GOVERNANCE_BUILD_PLAN.md.

Zero LLM/network dependency (json, hashlib, dataclasses, datetime only),
consistent with the rest of src/governance/. Single-process, no file
locking -- a real deployment fielding concurrent writers would need a
shared, coordinated store (a database, or OS-level file locking), not a
plain append-mode file open; stated plainly rather than left implicit.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.governance.rbac import Requester

GENESIS_HASH = "GENESIS"

VALID_EVENT_TYPES = {
    "request_received",
    "policy_denied",
    "injection_scan",
    "agent_trace",
    "answer_issued",
    "routed_to_human_review",
    "incident_created",
    "capability_disabled",
}


@dataclass
class AuditRecord:
    seq: int
    timestamp: str
    event_type: str
    requester_id: str
    session_id: str
    payload: dict
    prev_hash: str
    record_hash: str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_record_hash(
    seq: int,
    timestamp: str,
    event_type: str,
    requester_id: str,
    session_id: str,
    payload: dict,
    prev_hash: str,
) -> str:
    # sort_keys so the same payload always hashes the same way
    # regardless of the dict's insertion order.
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    material = (
        f"{seq}|{timestamp}|{event_type}|{requester_id}|{session_id}|"
        f"{canonical_payload}|{prev_hash}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AuditLog:
    """append() only ever adds one JSON line to the file at `path`,
    never rewrites an existing line. read_all() re-reads the file from
    disk every call rather than caching in memory, so it always
    reflects what's actually there -- including edits made outside this
    class (which is exactly what verify_audit_chain relies on to detect
    tampering)."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def append(self, event_type: str, requester: Requester, payload: dict) -> AuditRecord:
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"append: unknown event_type {event_type!r} -- must be one of "
                f"{sorted(VALID_EVENT_TYPES)}"
            )

        # Re-reads the whole log to find the next seq/prev_hash. Fine at
        # portfolio scale; a high-throughput deployment would keep the
        # tail (seq, last hash) cached instead of re-reading on every
        # append.
        existing = self.read_all()
        seq = len(existing)
        prev_hash = existing[-1].record_hash if existing else GENESIS_HASH
        timestamp = _utcnow_iso()

        record_hash = _compute_record_hash(
            seq, timestamp, event_type, requester.user_id, requester.session_id,
            payload, prev_hash,
        )
        record = AuditRecord(
            seq=seq,
            timestamp=timestamp,
            event_type=event_type,
            requester_id=requester.user_id,
            session_id=requester.session_id,
            payload=payload,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), sort_keys=True) + "\n")

        return record

    def read_all(self) -> list[AuditRecord]:
        if not self.path.exists():
            return []
        records: list[AuditRecord] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(AuditRecord(**json.loads(line)))
        return records


def verify_audit_chain(path: str) -> tuple[bool, str | None]:
    """Walks the log in order, recomputing each record's hash from its
    own stored fields plus the PRIOR record's stored hash, and compares
    it to that record's own stored record_hash. Returns (True, None) if
    every record matches; returns (False, "record at seq=N does not
    match its stored hash") at the first mismatch. An empty or
    nonexistent log is vacuously valid."""
    records = AuditLog(path).read_all()

    prev_hash = GENESIS_HASH
    for record in records:
        expected_hash = _compute_record_hash(
            record.seq, record.timestamp, record.event_type,
            record.requester_id, record.session_id, record.payload, prev_hash,
        )
        if expected_hash != record.record_hash:
            return False, f"record at seq={record.seq} does not match its stored hash"
        prev_hash = record.record_hash

    return True, None
