"""Tests for src/agents/planner.py."""
from __future__ import annotations

from src.agents.planner import PlannerAgent
from src.state import SubQuestion
from tests.conftest import FakeBackend


def test_plan_parses_well_formed_json_array():
    response = (
        '[{"text": "What products does Acme Robotics sell?", '
        '"mode": "targeted", "entity_hint": "Acme Robotics", '
        '"doc_type_hint": "Products"}]'
    )
    planner = PlannerAgent(backend=FakeBackend(response))
    result = planner.plan("What products does Acme Robotics sell?")

    assert result == [
        SubQuestion(
            text="What products does Acme Robotics sell?",
            mode="targeted",
            entity_hint="Acme Robotics",
            doc_type_hint="Products",
        )
    ]


def test_plan_handles_markdown_fenced_json():
    response = (
        "```json\n"
        '[{"text": "q1", "mode": "search", "entity_hint": null, "doc_type_hint": null}]\n'
        "```"
    )
    planner = PlannerAgent(backend=FakeBackend(response))
    result = planner.plan("some question")

    assert len(result) == 1
    assert result[0].text == "q1"
    assert result[0].mode == "search"


def test_plan_handles_multiple_sub_questions_for_comparison():
    response = (
        '[{"text": "What is Acme Robotics revenue?", "mode": "targeted", '
        '"entity_hint": "Acme Robotics", "doc_type_hint": "Financial Overview"}, '
        '{"text": "What is Borealis Foods revenue?", "mode": "targeted", '
        '"entity_hint": "Borealis Foods", "doc_type_hint": "Financial Overview"}]'
    )
    planner = PlannerAgent(backend=FakeBackend(response))
    result = planner.plan("Compare Acme Robotics and Borealis Foods revenue")

    assert len(result) == 2
    assert {sq.entity_hint for sq in result} == {"Acme Robotics", "Borealis Foods"}


def test_plan_falls_back_to_single_subquestion_on_unparseable_response():
    planner = PlannerAgent(backend=FakeBackend("I'm sorry, I cannot help with that."))
    result = planner.plan("What does Acme Robotics sell?")

    assert result == [SubQuestion(text="What does Acme Robotics sell?", mode="search")]


def test_plan_falls_back_on_empty_array():
    planner = PlannerAgent(backend=FakeBackend("[]"))
    result = planner.plan("q")

    assert result == [SubQuestion(text="q", mode="search")]


def test_plan_defaults_invalid_mode_to_search():
    response = '[{"text": "q", "mode": "not-a-real-mode"}]'
    planner = PlannerAgent(backend=FakeBackend(response))
    result = planner.plan("q")

    assert result[0].mode == "search"


def test_plan_skips_items_missing_text():
    response = '[{"mode": "search"}, {"text": "valid one", "mode": "search"}]'
    planner = PlannerAgent(backend=FakeBackend(response))
    result = planner.plan("q")

    assert len(result) == 1
    assert result[0].text == "valid one"


def test_plan_sends_question_as_prompt_with_a_system_prompt():
    backend = FakeBackend('[{"text": "q", "mode": "search"}]')
    planner = PlannerAgent(backend=backend)

    planner.plan("What does Acme Robotics sell?")

    assert backend.calls[0]["prompt"] == "What does Acme Robotics sell?"
    assert backend.calls[0]["system"] is not None
