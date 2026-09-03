"""Tests for AgentGraph itself (src/orchestrator.py), kept fully generic
-- no ResearchState involved -- to verify it really is reusable over any
state type, as the module docstring claims."""
from __future__ import annotations

import pytest

from src.orchestrator import AgentGraph, GraphExecutionError


def test_linear_execution_runs_nodes_in_edge_order():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("double", lambda s: s * 2)
    graph.add_node("increment", lambda s: s + 1)
    graph.set_entry("double")
    graph.add_edge("double", "increment")

    assert graph.run(3) == 7  # (3 * 2) + 1


def test_conditional_edge_loops_until_router_returns_none():
    def increment(s: int) -> int:
        return s + 1

    def router(s: int) -> str | None:
        return "inc" if s < 5 else None

    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("inc", increment)
    graph.set_entry("inc")
    graph.add_conditional_edge("inc", router)

    assert graph.run(0) == 5


def test_terminal_node_with_no_outgoing_edge_stops_after_one_run():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("only", lambda s: s + 100)
    graph.set_entry("only")

    assert graph.run(1) == 101


def test_run_without_entry_raises():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("a", lambda s: s)

    with pytest.raises(GraphExecutionError, match="no entry node set"):
        graph.run(1)


def test_run_exceeding_max_steps_raises():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("loop", lambda s: s + 1)
    graph.set_entry("loop")
    graph.add_conditional_edge("loop", lambda s: "loop")  # never stops

    with pytest.raises(GraphExecutionError, match="exceeded max_steps"):
        graph.run(0, max_steps=10)


def test_add_edge_rejects_unknown_from_node():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("b", lambda s: s)

    with pytest.raises(GraphExecutionError, match="unknown from_node"):
        graph.add_edge("a", "b")


def test_add_edge_rejects_unknown_to_node():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("a", lambda s: s)

    with pytest.raises(GraphExecutionError, match="unknown to_node"):
        graph.add_edge("a", "nonexistent")


def test_set_entry_rejects_unknown_node():
    graph: AgentGraph[int] = AgentGraph()
    with pytest.raises(GraphExecutionError, match="unknown node"):
        graph.set_entry("nonexistent")


def test_node_cannot_have_both_unconditional_and_conditional_edge():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("a", lambda s: s)
    graph.add_node("b", lambda s: s)
    graph.add_edge("a", "b")

    with pytest.raises(GraphExecutionError, match="already has an unconditional edge"):
        graph.add_conditional_edge("a", lambda s: "b")


def test_conditional_edge_cannot_then_get_an_unconditional_edge():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("a", lambda s: s)
    graph.add_node("b", lambda s: s)
    graph.add_conditional_edge("a", lambda s: "b")

    with pytest.raises(GraphExecutionError, match="already has a conditional edge"):
        graph.add_edge("a", "b")


def test_conditional_edge_routing_to_unknown_node_raises():
    graph: AgentGraph[int] = AgentGraph()
    graph.add_node("a", lambda s: s)
    graph.set_entry("a")
    graph.add_conditional_edge("a", lambda s: "nonexistent")

    with pytest.raises(GraphExecutionError, match="unknown node 'nonexistent'"):
        graph.run(1)
