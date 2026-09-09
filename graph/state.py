from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages

class AgentState(TypedDict, total=False):
    # Input
    task_id: str
    user_request: str

    # Workflow outputs
    plan: Optional[Dict[str, Any]]
    research: Optional[Dict[str, Any]]
    architecture: Optional[str]
    code: Optional[Dict[str, Any]]  # {"files": [{"path":..., "content":...}]}
    test_results: Optional[Dict[str, Any]]
    review: Optional[Dict[str, Any]]

    # Control
    approval: Optional[str]  # "pending" | "approved" | "rejected"
    retry_count: int
    max_retries: int

    # Streaming / observability
    current_step: str
    logs: List[str]
    artifacts: List[str]  # file paths

    # Messages for LLM history (optional)
    messages: Annotated[List[Any], add_messages]

def initial_state(task_id: str, user_request: str) -> AgentState:
    return {
        "task_id": task_id,
        "user_request": user_request,
        "plan": None,
        "research": None,
        "architecture": None,
        "code": None,
        "test_results": None,
        "review": None,
        "approval": "pending",
        "retry_count": 0,
        "max_retries": 2,
        "current_step": "planner",
        "logs": [],
        "artifacts": [],
        "messages": [],
    }
