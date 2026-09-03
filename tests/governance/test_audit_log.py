"""Tests for src/governance/audit_log.py."""
from __future__ import annotations

import json

import pytest

from src.governance.audit_log import AuditLog, verify_audit_chain
from src.governance.rbac import Requester


def _requester() -> Requester:
    return Requester(user_id="u1", role="analyst", session_id="s1")


# --- basic append/read --------------------------------------------------

def test_append_returns_first_record_chained_to_genesis(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    record = log.append("request_received", _requester(), {"question": "q1"})

    assert record.seq == 0
    assert record.prev_hash == "GENESIS"
    assert record.record_hash != ""
    assert record.requester_id == "u1"
    assert record.session_id == "s1"


def test_records_are_linked_by_hash_in_order(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    requester = _requester()

    r0 = log.append("request_received", requester, {"i": 0})
    r1 = log.append("agent_trace", requester, {"i": 1})
    r2 = log.append("answer_issued", requester, {"i": 2})

    assert r1.prev_hash == r0.record_hash
    assert r2.prev_hash == r1.record_hash
    assert len({r0.record_hash, r1.record_hash, r2.record_hash}) == 3  # all distinct


def test_read_all_round_trips_payload_exactly(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    payload = {"question": "What does Acme Robotics sell?", "score": 0.9, "flagged": False}
    log.append("request_received", _requester(), payload)

    records = log.read_all()

    assert records[0].payload == payload


def test_read_all_returns_empty_list_for_nonexistent_file(tmp_path):
    log = AuditLog(str(tmp_path / "does_not_exist.jsonl"))
    assert log.read_all() == []


def test_append_raises_on_unknown_event_type(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    with pytest.raises(ValueError, match="unknown event_type"):
        log.append("not_a_real_event", _requester(), {})


# --- log growth / sequencing --------------------------------------------

def test_log_file_grows_by_exactly_one_line_per_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()

    for i in range(1, 6):
        log.append("request_received", requester, {"i": i})
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == i


def test_sequential_rapid_appends_produce_a_valid_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()

    for i in range(50):
        log.append("agent_trace", requester, {"i": i})

    ok, reason = verify_audit_chain(str(path))
    assert ok is True
    assert reason is None

    records = log.read_all()
    assert [r.seq for r in records] == list(range(50))


# --- verify_audit_chain --------------------------------------------------

def test_verify_audit_chain_clean_on_untouched_log(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()
    for i in range(5):
        log.append("request_received", requester, {"i": i})

    ok, reason = verify_audit_chain(str(path))

    assert ok is True
    assert reason is None


def test_verify_audit_chain_on_empty_or_missing_log_is_vacuously_valid(tmp_path):
    ok, reason = verify_audit_chain(str(tmp_path / "never_written.jsonl"))
    assert ok is True
    assert reason is None


def test_verify_audit_chain_detects_tampered_payload(tmp_path):
    """The required corruption test: mutate exactly one record's
    payload in place (leaving its stored record_hash untouched -- what
    an attacker editing the file directly would do) and confirm
    verify_audit_chain fails at exactly that seq."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()

    log.append("request_received", requester, {"question": "q1"})
    log.append("answer_issued", requester, {"citations": ["doc-1"]})
    log.append("agent_trace", requester, {"iterations": 1})

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["payload"] = {"citations": ["doc-999-fabricated"]}
    lines[1] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, reason = verify_audit_chain(str(path))

    assert ok is False
    assert reason == "record at seq=1 does not match its stored hash"


def test_verify_audit_chain_detects_a_deleted_middle_record(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()
    for i in range(4):
        log.append("request_received", requester, {"i": i})

    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # remove the seq=1 record entirely
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, reason = verify_audit_chain(str(path))

    assert ok is False
    assert "seq=2" in reason  # the record right after the gap no longer chains


def test_verify_audit_chain_stops_at_the_first_mismatch(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    requester = _requester()
    for i in range(5):
        log.append("request_received", requester, {"i": i})

    lines = path.read_text(encoding="utf-8").splitlines()
    for idx in (1, 3):  # tamper with two records
        tampered = json.loads(lines[idx])
        tampered["payload"] = {"i": "tampered"}
        lines[idx] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, reason = verify_audit_chain(str(path))

    assert ok is False
    assert reason == "record at seq=1 does not match its stored hash"  # the FIRST one
