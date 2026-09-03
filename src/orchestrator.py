"""
src/orchestrator.py

AgentGraph is a small, generic node/edge state-machine runner: it knows
nothing about ResearchState, SubQuestion, or any research-specific type
-- it's typed over State via a TypeVar, and every "node" is just a
Callable[[State], State]. This genericness is deliberate: the AgentGuard
governance layer (a much later stage) builds a second AgentGraph over a
different state type (GovernedResearchState) by reusing this exact class
unmodified, rather than needing its own graph runner.

build_research_graph wires the four base agents (planner, researcher,
writer, critic) into the concrete research pipeline:

    plan -> research -> write -> critique -[conditional]-> research | stop

The "research" node does BOTH retrieval and sub-answer writing for each
sub-question (not just retrieval) -- so that by the time "critique" (or,
later, the governance layer's "scan_evidence" node) runs, every
SubAnswer already carries its own grounded text, citations, and
evidence. This is what lets a later governance stage inspect
state.sub_answers immediately after "research" without needing a
separate evidence-only field on ResearchState.

ResearchOrchestrator is the thin, convenient front door: construct once
with the four agents, then call .run(question) per request.
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from src.agents.critic import CriticAgent
from src.agents.planner import PlannerAgent
from src.agents.researcher import ResearcherAgent
from src.agents.writer import WriterAgent
from src.state import MAX_ITERATIONS, ResearchState

State = TypeVar("State")

NodeFn = Callable[[State], State]
RouterFn = Callable[[State], "str | None"]


class GraphExecutionError(RuntimeError):
    """Raised when the graph can't proceed: no entry point set, an edge
    points at a node that was never added, a node was given both an
    unconditional and a conditional edge, or a run hits max_steps
    without reaching a stop (almost always a routing bug -- a
    conditional edge that never returns None -- not expected normal
    termination)."""


class AgentGraph(Generic[State]):
    """A minimal directed graph runner over an arbitrary State type.

    Each node is a plain function State -> State. A node has at most one
    outgoing edge, which is either:
      - unconditional (add_edge): always go to the same next node, or
      - conditional (add_conditional_edge): a router function computes
        the next node name from the current state, or returns None to
        stop the run.
    A node with neither is treated as terminal: it runs once and the
    graph stops.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, RouterFn] = {}
        self._entry: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> None:
        self._nodes[name] = fn

    def set_entry(self, name: str) -> None:
        if name not in self._nodes:
            raise GraphExecutionError(f"set_entry: unknown node {name!r}")
        self._entry = name

    def add_edge(self, from_node: str, to_node: str) -> None:
        if from_node not in self._nodes:
            raise GraphExecutionError(f"add_edge: unknown from_node {from_node!r}")
        if to_node not in self._nodes:
            raise GraphExecutionError(f"add_edge: unknown to_node {to_node!r}")
        if from_node in self._conditional_edges:
            raise GraphExecutionError(
                f"add_edge: {from_node!r} already has a conditional edge; "
                "a node may not have both"
            )
        self._edges[from_node] = to_node

    def add_conditional_edge(self, from_node: str, router: RouterFn) -> None:
        if from_node not in self._nodes:
            raise GraphExecutionError(f"add_conditional_edge: unknown from_node {from_node!r}")
        if from_node in self._edges:
            raise GraphExecutionError(
                f"add_conditional_edge: {from_node!r} already has an unconditional "
                "edge; a node may not have both"
            )
        self._conditional_edges[from_node] = router

    def run(self, state: State, max_steps: int = 25) -> State:
        if self._entry is None:
            raise GraphExecutionError("run: no entry node set (call set_entry first)")

        current = self._entry
        for _ in range(max_steps):
            node_fn = self._nodes.get(current)
            if node_fn is None:
                raise GraphExecutionError(f"run: unknown node {current!r}")
            state = node_fn(state)

            if current in self._conditional_edges:
                next_node = self._conditional_edges[current](state)
                if next_node is None:
                    return state
                if next_node not in self._nodes:
                    raise GraphExecutionError(
                        f"run: conditional edge from {current!r} routed to "
                        f"unknown node {next_node!r}"
                    )
                current = next_node
            elif current in self._edges:
                current = self._edges[current]
            else:
                return state  # terminal node: ran it, no outgoing edge

        raise GraphExecutionError(
            f"run: exceeded max_steps={max_steps} without reaching a stop -- "
            "likely a routing bug (a conditional edge that never returns None)"
        )


def route_after_critique(state: ResearchState) -> str | None:
    """Loop back to "research" (revise) while the latest critique isn't
    approved and there's revision budget left; otherwise stop, whether
    that's because the critic approved or because MAX_ITERATIONS was
    reached without approval -- either way the caller gets back
    whatever the last composed draft was, with state.approved reflecting
    which case it was."""
    result = state.critique_history[-1]
    if result.approved:
        state.approved = True
        return None
    if state.iteration < MAX_ITERATIONS - 1:
        state.iteration += 1
        state.log(f"critique not approved, revising (iteration={state.iteration})")
        return "research"
    state.log("critique not approved, out of revision budget -- returning best draft")
    return None


def _make_node_plan(planner: PlannerAgent) -> NodeFn:
    def node_plan(state: ResearchState) -> ResearchState:
        state.sub_questions = planner.plan(state.question)
        state.log(f"planned {len(state.sub_questions)} sub-question(s)")
        return state

    return node_plan


def _make_node_research(
    researcher: ResearcherAgent, writer: WriterAgent, base_k: int
) -> NodeFn:
    def node_research(state: ResearchState) -> ResearchState:
        sub_answers = []
        for sub_question in state.sub_questions:
            # an aggregate question needs to synthesize across several
            # documents, so it gets a larger retrieval budget than a
            # single-fact targeted/search question.
            k = base_k * 2 if sub_question.mode == "aggregate" else base_k
            evidence = researcher.research(sub_question, k=k)
            sub_answers.append(writer.write_sub_answer(sub_question, evidence))
        state.sub_answers = sub_answers
        state.log(
            f"researched {len(sub_answers)} sub-answer(s) (iteration={state.iteration})"
        )
        return state

    return node_research


def _make_node_write(writer: WriterAgent) -> NodeFn:
    def node_write(state: ResearchState) -> ResearchState:
        final_answer, citations = writer.compose_final_answer(
            state.question, state.sub_answers
        )
        state.final_answer = final_answer
        state.citations = citations
        state.log("composed final answer")
        return state

    return node_write


def _make_node_critique(critic: CriticAgent) -> NodeFn:
    def node_critique(state: ResearchState) -> ResearchState:
        result = critic.critique(state.sub_answers, state.final_answer, state.citations)
        state.critique_history.append(result)
        state.log(
            f"critique: approved={result.approved} "
            f"groundedness={result.groundedness:.2f} "
            f"citation_coverage={result.citation_coverage:.2f}"
        )
        return state

    return node_critique


def build_research_graph(
    planner: PlannerAgent,
    researcher: ResearcherAgent,
    writer: WriterAgent,
    critic: CriticAgent,
    base_k: int = 3,
) -> AgentGraph[ResearchState]:
    graph: AgentGraph[ResearchState] = AgentGraph()

    graph.add_node("plan", _make_node_plan(planner))
    graph.add_node("research", _make_node_research(researcher, writer, base_k))
    graph.add_node("write", _make_node_write(writer))
    graph.add_node("critique", _make_node_critique(critic))

    graph.set_entry("plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "critique")
    graph.add_conditional_edge("critique", route_after_critique)

    return graph


class ResearchOrchestrator:
    """Thin front door over build_research_graph: construct once with
    the four agents, then call .run(question) per request. Callers that
    need the graph itself -- e.g. to reuse these same agents in a second,
    differently-wired graph, as the governance layer does in a later
    stage -- should call build_research_graph directly instead."""

    def __init__(
        self,
        planner: PlannerAgent,
        researcher: ResearcherAgent,
        writer: WriterAgent,
        critic: CriticAgent,
        base_k: int = 3,
    ) -> None:
        self.graph = build_research_graph(planner, researcher, writer, critic, base_k=base_k)

    def run(self, question: str) -> ResearchState:
        state = ResearchState(question=question)
        return self.graph.run(state)
