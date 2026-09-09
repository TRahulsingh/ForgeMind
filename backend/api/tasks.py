import uuid
import json
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from graph.state import initial_state
from graph.workflow import workflow
from backend.core.database import save_task, get_task, list_tasks
from backend.core.config import settings
from tools.github import create_github_pr

router = APIRouter(prefix="/api", tags=["tasks"])

# In-memory stream queues {task_id: asyncio.Queue}
queues = {}

class TaskCreate(BaseModel):
    request: str
    max_retries: int = 2

class ApproveRequest(BaseModel):
    decision: str  # approved | rejected
    feedback: Optional[str] = None

@router.post("/tasks")
async def create_task(payload: TaskCreate, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    save_task(task_id, payload.request, "running", {"user_request": payload.request})
    queues[task_id] = asyncio.Queue()
    
    background_tasks.add_task(run_task_background, task_id, payload.request, payload.max_retries)
    
    return {"task_id": task_id, "status": "running"}

async def run_task_background(task_id: str, user_request: str, max_retries: int):
    q = queues.get(task_id)
    async def push(step: str, data: dict):
        if q:
            await q.put(json.dumps({"step": step, "data": data}))

    try:
        init = initial_state(task_id, user_request)
        init["max_retries"] = max_retries
        
        await push("started", {"user_request": user_request})
        save_task(task_id, user_request, "running", init)

        final = None
        # Stream workflow steps
        async for event in workflow.astream(init):
            for node_name, chunk in event.items():
                # Merge into init for next context (workflow handles)
                for k, v in chunk.items():
                    init[k] = v
                await push(node_name, chunk)
                save_task(task_id, user_request, "running", init)
        
        # Final invoke result is init after streaming
        final = init
        # Determine status
        review = final.get("review", {})
        test_passed = final.get("test_results", {}).get("passed", False)
        if review.get("decision") == "NEEDS_CHANGES" or not test_passed:
            status = "needs_review"
        else:
            status = "awaiting_approval"
        
        final["current_step"] = "human_approval"
        save_task(task_id, user_request, status, final)
        await push("human_approval", {"status": status, "review": review, "artifacts": final.get("artifacts", [])})
        await push("done", {"status": status})

        if q:
            await q.put(None)  # signal end
            # Cleanup queue after done to prevent leak over 15 tasks
            queues.pop(task_id, None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        err_state = {"error": str(e)}
        save_task(task_id, user_request, "failed", err_state)
        if q:
            await q.put(json.dumps({"step": "error", "data": {"error": str(e)}}))
            await q.put(None)
            queues.pop(task_id, None)

@router.get("/tasks")
async def get_tasks():
    return list_tasks(20)

@router.get("/tasks/{task_id}")
async def get_task_by_id(task_id: str):
    row = get_task(task_id)
    if not row:
        raise HTTPException(404, "task not found")
    try:
        state = json.loads(row["state_json"]) if row["state_json"] else {}
    except:
        state = {}
    return {"task_id": row["id"], "user_request": row["user_request"], "status": row["status"], "state": state, "created_at": row["created_at"]}

@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, payload: ApproveRequest):
    row = get_task(task_id)
    if not row:
        raise HTTPException(404, "task not found")
    try:
        state = json.loads(row["state_json"]) if row["state_json"] else {}
    except:
        state = {}
    
    if payload.decision not in ["approved", "rejected"]:
        raise HTTPException(400, "decision must be approved|rejected")
    
    state["approval"] = payload.decision
    if payload.decision == "approved":
        # Trigger GitHub PR dry-run + mark complete
        artifacts_dir = Path(settings.output_path) / task_id
        pr_res = create_github_pr(task_id, row["user_request"], artifacts_dir, repo_name="")
        state["pr_result"] = pr_res
        save_task(task_id, row["user_request"], "completed", state)
        return {"status": "completed", "pr": pr_res}
    else:
        state["approval"] = "rejected"
        if payload.feedback:
            state["review"] = state.get("review") or {}
            state["review"]["feedback"] = payload.feedback
            # Store feedback for potential retry via developer
            state["retry_count"] = state.get("retry_count", 0)
        save_task(task_id, row["user_request"], "rejected", state)
        return {"status": "rejected", "feedback_stored": bool(payload.feedback)}
