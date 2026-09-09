import json
import uuid
from typing import Dict, Any
from pathlib import Path

from langgraph.graph import StateGraph, END

from graph.state import AgentState, initial_state
from graph.nodes import planner_node, researcher_node, developer_node, tester_node, reviewer_node, human_approval_node

# Conditional routing
def should_retry(state: AgentState) -> str:
    results = state.get("test_results")
    if not results:
        return "reviewer"
    passed = results.get("passed", False)
    retry = state.get("retry_count", 0)
    max_retry = state.get("max_retries", 2)
    if not passed and retry < max_retry:
        return "developer_retry"
    return "reviewer"

def reviewer_decision(state: AgentState) -> str:
    review = state.get("review", {})
    decision = review.get("decision", "APPROVED")
    if decision == "NEEDS_CHANGES":
        return "developer_revise"
    return "human_approval"

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("developer", developer_node)
    graph.add_node("tester", tester_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("human_approval", human_approval_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "developer")
    graph.add_edge("developer", "tester")

    graph.add_conditional_edges(
        "tester",
        should_retry,
        {
            "developer_retry": "developer",
            "reviewer": "reviewer",
        }
    )
    graph.add_conditional_edges(
        "reviewer",
        reviewer_decision,
        {
            "developer_revise": "developer",
            "human_approval": "human_approval",
        }
    )
    graph.add_edge("human_approval", END)

    return graph.compile()

# Wrapper for handling retry count increment
async def developer_with_retry(state: AgentState):
    # Increment if coming from tester/review failure
    prev_retry = state.get("retry_count", 0)
    # Check if previous step was tester or reviewer with failure
    test_failed = False
    if state.get("test_results") and not (state["test_results"] or {}).get("passed", True):
        test_failed = True
    review = state.get("review") or {}
    if review.get("decision") == "NEEDS_CHANGES":
        test_failed = True
    
    # Only increment if not first call (plan exists)
    if state.get("plan") and test_failed:
        state["retry_count"] = prev_retry + 1
    return await developer_node(state)

# Rebuild with retry handling
def build_graph_with_retry():
    graph = StateGraph(AgentState)

    async def planner_wrap(s): return await planner_node(s)
    async def researcher_wrap(s): return await researcher_node(s)
    async def tester_wrap(s): return await tester_node(s)
    async def reviewer_wrap(s): return await reviewer_node(s)
    async def approval_wrap(s): return await human_approval_node(s)

    graph.add_node("planner", planner_wrap)
    graph.add_node("researcher", researcher_wrap)
    graph.add_node("developer", developer_with_retry)
    graph.add_node("tester", tester_wrap)
    graph.add_node("reviewer", reviewer_wrap)
    graph.add_node("human_approval", approval_wrap)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "developer")
    graph.add_edge("developer", "tester")

    def _should_retry(state: AgentState) -> str:
        results = state.get("test_results")
        if not results:
            return "reviewer"
        passed = results.get("passed", False)
        retry = state.get("retry_count", 0)
        max_retry = state.get("max_retries", 2)
        if not passed and retry < max_retry:
            return "developer"
        return "reviewer"

    def _reviewer_decision(state: AgentState) -> str:
        review = state.get("review", {})
        decision = review.get("decision", "APPROVED")
        retry = state.get("retry_count", 0)
        max_retry = state.get("max_retries", 2)
        if decision == "NEEDS_CHANGES" and retry < max_retry:
            return "developer"
        return "human_approval"

    graph.add_conditional_edges("tester", _should_retry, {"developer": "developer", "reviewer": "reviewer"})
    graph.add_conditional_edges("reviewer", _reviewer_decision, {"developer": "developer", "human_approval": "human_approval"})
    graph.add_edge("human_approval", END)

    # No checkpoint interrupt for now - handled via state persistence in backend
    return graph.compile()

workflow = build_graph_with_retry()

async def run_workflow(task_id: str, user_request: str, max_retries: int = 2):
    init = initial_state(task_id, user_request)
    init["max_retries"] = max_retries
    # Single invoke (removed double-run astream+ainvoke bug that doubled latency)
    result = await workflow.ainvoke(init)
    return result
