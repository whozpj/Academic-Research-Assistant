from langgraph.graph import StateGraph, END

from state import ResearchState
from nodes import (
    search_node,
    critic_node,
    snowball_node,
    synthesis_node,
    hypothesis_node,
    advocate_node,
    experiment_node,
)


def _should_refine_hypotheses(state: ResearchState) -> str:
    if state.get("error"):
        return "end"
    critiques = state.get("hypothesis_critiques", [])
    iteration = state.get("hypothesis_iteration", 0)
    if iteration >= 2:
        return "proceed"
    min_viability = min((c.get("viability_score", 10) for c in critiques), default=10)
    if min_viability < 6:
        return "refine"
    return "proceed"


def _should_retry(state: ResearchState) -> str:
    if state.get("error"):
        return "end"
    relevant = state.get("relevant_papers", [])
    retry_count = state.get("retry_count", 0)
    if len(relevant) < 5 and retry_count < 2:
        return "retry"
    return "proceed"


def build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("search_node", search_node)
    graph.add_node("critic_node", critic_node)
    graph.add_node("snowball_node", snowball_node)
    graph.add_node("synthesis_node", synthesis_node)
    graph.add_node("hypothesis_node", hypothesis_node)
    graph.add_node("advocate_node", advocate_node)
    graph.add_node("experiment_node", experiment_node)

    graph.set_entry_point("search_node")
    graph.add_edge("search_node", "critic_node")

    graph.add_conditional_edges(
        "critic_node",
        _should_retry,
        {
            "retry": "search_node",
            "proceed": "snowball_node",
            "end": END,
        },
    )

    graph.add_edge("snowball_node", "synthesis_node")
    graph.add_edge("synthesis_node", "hypothesis_node")
    graph.add_edge("hypothesis_node", "advocate_node")

    graph.add_conditional_edges(
        "advocate_node",
        _should_refine_hypotheses,
        {
            "refine": "hypothesis_node",
            "proceed": "experiment_node",
            "end": END,
        },
    )
    graph.add_edge("experiment_node", END)

    return graph.compile()
