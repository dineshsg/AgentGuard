"""Tests for evaluate.py. Never touches a live LLM: run_evaluation()
takes an injectable orchestrator, wired here to FakeBackend, so these
tests verify the aggregation math and file-writing, not model quality."""
from __future__ import annotations

import json

import evaluate
from src.agents.critic import CriticAgent
from src.agents.planner import PlannerAgent
from src.agents.researcher import ResearcherAgent
from src.agents.writer import WriterAgent
from src.orchestrator import ResearchOrchestrator
from src.state import ResearchState
from tests.conftest import FakeBackend


def _fake_orchestrator(critic_response: str) -> ResearchOrchestrator:
    plan_response = (
        '[{"text": "What does Acme Robotics sell?", "mode": "targeted", '
        '"entity_hint": "Acme Robotics", "doc_type_hint": "Products"}]'
    )
    return ResearchOrchestrator(
        planner=PlannerAgent(backend=FakeBackend(plan_response)),
        researcher=ResearcherAgent(),
        writer=WriterAgent(backend=FakeBackend("Acme Robotics sells robotic arms [acme-products].")),
        critic=CriticAgent(backend=FakeBackend(critic_response)),
    )


def _write_eval_set(tmp_path, items):
    path = tmp_path / "eval_set.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_keyword_recall_counts_case_insensitive_substring_hits():
    state = ResearchState(question="q")
    state.final_answer = "Acme Robotics sells robotic arms and warehouse automation systems."

    assert evaluate._keyword_recall(state, ["robotic arm", "WAREHOUSE automation"]) == 1.0
    assert evaluate._keyword_recall(state, ["robotic arm", "nonexistent phrase"]) == 0.5
    assert evaluate._keyword_recall(state, []) == 1.0
    assert evaluate._keyword_recall(state, ["nothing matches here"]) == 0.0


def test_run_evaluation_aggregates_across_items(tmp_path):
    eval_set_path = _write_eval_set(
        tmp_path,
        [
            {
                "id": "e1",
                "question": "What does Acme Robotics sell?",
                "expected_keywords": ["robotic arm"],
            },
            {
                "id": "e2",
                "question": "What does Acme Robotics sell?",
                "expected_keywords": ["nonexistent phrase"],
            },
        ],
    )
    orchestrator = _fake_orchestrator('{"groundedness": 0.9, "feedback": "good"}')

    report = evaluate.run_evaluation(eval_set_path=eval_set_path, orchestrator=orchestrator)

    assert report["summary"]["n_questions"] == 2
    assert report["summary"]["keyword_recall"] == 0.5  # (1.0 + 0.0) / 2
    assert report["summary"]["approval_rate"] == 1.0  # both approved (groundedness 0.9)
    assert report["summary"]["groundedness"] == 0.9
    assert report["summary"]["citation_coverage"] == 1.0
    assert len(report["results"]) == 2
    assert report["results"][0]["id"] == "e1"
    assert report["results"][0]["keyword_recall"] == 1.0
    assert report["results"][1]["keyword_recall"] == 0.0


def test_run_evaluation_approval_rate_reflects_rejections(tmp_path):
    eval_set_path = _write_eval_set(
        tmp_path,
        [{"id": "e1", "question": "What does Acme Robotics sell?", "expected_keywords": []}],
    )
    orchestrator = _fake_orchestrator('{"groundedness": 0.1, "feedback": "not enough"}')

    report = evaluate.run_evaluation(eval_set_path=eval_set_path, orchestrator=orchestrator)

    assert report["summary"]["approval_rate"] == 0.0
    assert report["results"][0]["approved"] is False


def test_run_evaluation_handles_empty_eval_set(tmp_path):
    eval_set_path = _write_eval_set(tmp_path, [])
    orchestrator = _fake_orchestrator('{"groundedness": 0.9, "feedback": "good"}')

    report = evaluate.run_evaluation(eval_set_path=eval_set_path, orchestrator=orchestrator)

    assert report["summary"]["n_questions"] == 0
    assert report["summary"]["keyword_recall"] == 0.0
    assert report["results"] == []


def test_main_writes_report_to_disk(monkeypatch, tmp_path):
    fake_report = {"summary": {"n_questions": 1, "keyword_recall": 1.0}, "results": []}
    monkeypatch.setattr(evaluate, "run_evaluation", lambda: fake_report)
    report_path = tmp_path / "eval_report.json"
    monkeypatch.setattr(evaluate, "REPORT_PATH", report_path)

    evaluate.main()

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert written == fake_report
