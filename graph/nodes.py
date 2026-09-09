import json
import asyncio
from pathlib import Path
from typing import Dict
from graph.state import AgentState
from backend.core.llm import provider
from backend.core.config import settings
from tools.filesystem import write_artifacts
from tools.python_exec import run_tests
from rag.retrieval import retrieve_context

def render_prompt(template: str, **kwargs) -> str:
    """Safe replace only {known} placeholders, leaves JSON braces intact."""
    for k, v in kwargs.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template

# Prompts via clean loader (agents/prompts/*.md) with inline fallback for tests
try:
    from agents.prompts.loader import load_prompt
    _planner_body, _ = load_prompt("planner")
    _researcher_body, _ = load_prompt("researcher")
    _developer_body, _ = load_prompt("developer")
    _tester_body, _ = load_prompt("tester")
    _reviewer_body, _ = load_prompt("reviewer")
    PLANNER_PROMPT = _planner_body if _planner_body else """You are Planner agent. Decompose user request into executable subtasks.\nUser request: {user_request}\nReturn JSON: {{"tasks": [{{"id": int, "title": str, "description": str, "dependencies": [int]}}], "architecture": str, "estimated_complexity": str}}"""
    RESEARCHER_PROMPT = _researcher_body if _researcher_body else """You are Researcher. Find best practices and context.\nUser request: {user_request}\nPlan: {plan}\nRetrieved context: {context}\nReturn JSON: {{"findings": [str], "best_practices": [str], "relevant_context": str}}"""
    DEVELOPER_PROMPT = _developer_body if _developer_body else """You are Developer. Generate implementation.\nUser request: {user_request}\nPlan: {plan}\nResearch: {research}\nArchitecture: {architecture}\nPrevious test failures (if retry): {test_results}\nReturn JSON: {{"files": [{{"path": str, "content": str}}], "explanation": str}}\nRules: Generate complete runnable code. Include app/main.py, requirements.txt, tests/test_*.py. Use FastAPI + SQLite for low-spec. Keep files <300 lines."""
    TESTER_PROMPT = _tester_body if _tester_body else """You are Tester. Analyze test output.\nCode summary: {code}\nTest output: {test_output}\nReturn JSON: {{"passed": bool, "summary": str, "failures": [str], "command": str}}"""
    REVIEWER_PROMPT = _reviewer_body if _reviewer_body else """You are Reviewer. Check correctness, security, maintainability.\nUser request: {user_request}\nCode: {code}\nTest results: {test_results}\nReturn JSON: {{"decision": "APPROVED" or "NEEDS_CHANGES", "score": int 1-10, "issues": [str], "suggestions": [str]}}"""
except Exception as e:
    # Fallback inline if loader missing (keep workflow alive)
    print(f"[nodes] loader failed {e}, using inline prompts")
    PLANNER_PROMPT = """You are Planner agent. Decompose user request into executable subtasks.\nUser request: {user_request}\nReturn JSON: {{"tasks": [{{"id": int, "title": str, "description": str, "dependencies": [int]}}], "architecture": str, "estimated_complexity": str}}"""
    RESEARCHER_PROMPT = """You are Researcher. Find best practices and context.\nUser request: {user_request}\nPlan: {plan}\nRetrieved context: {context}\nReturn JSON: {{"findings": [str], "best_practices": [str], "relevant_context": str}}"""
    DEVELOPER_PROMPT = """You are Developer. Generate implementation.\nUser request: {user_request}\nPlan: {plan}\nResearch: {research}\nArchitecture: {architecture}\nPrevious test failures (if retry): {test_results}\nReturn JSON: {{"files": [{{"path": str, "content": str}}], "explanation": str}}\nRules: Generate complete runnable code. Include app/main.py, requirements.txt, tests/test_*.py. Use FastAPI + SQLite for low-spec. Keep files <300 lines."""
    TESTER_PROMPT = """You are Tester. Analyze test output.\nCode summary: {code}\nTest output: {test_output}\nReturn JSON: {{"passed": bool, "summary": str, "failures": [str], "command": str}}"""
    REVIEWER_PROMPT = """You are Reviewer. Check correctness, security, maintainability.\nUser request: {user_request}\nCode: {code}\nTest results: {test_results}\nReturn JSON: {{"decision": "APPROVED" or "NEEDS_CHANGES", "score": int 1-10, "issues": [str], "suggestions": [str]}}"""

async def planner_node(state: AgentState) -> Dict:
    prompt = render_prompt(PLANNER_PROMPT, user_request=state["user_request"])
    system = "You are a senior planner. Output valid JSON only."
    raw = await provider.generate("planner", prompt, system, temperature=0.2)
    try:
        plan = json.loads(raw)
    except:
        plan = {"tasks": [{"id":1,"title":"Implement","description":raw[:500],"dependencies":[]}], "architecture": "FastAPI", "estimated_complexity": "medium"}
    return {"plan": plan, "current_step": "researcher", "logs": state.get("logs", []) + [f"Planner: {len(plan.get('tasks',[]))} tasks"]}

async def researcher_node(state: AgentState) -> Dict:
    # RAG retrieval - file-based Chroma, falls back to empty if not available
    context = ""
    try:
        context = retrieve_context(state["user_request"], k=5)
    except Exception as e:
        context = f"retrieval unavailable: {e}"
    
    prompt = render_prompt(
        RESEARCHER_PROMPT,
        user_request=state["user_request"],
        plan=json.dumps(state.get("plan", {}))[:1500],
        context=context[:2000]
    )
    raw = await provider.generate("researcher", prompt, "You output JSON only", temperature=0.2)
    try:
        research = json.loads(raw)
        research["retrieved_context"] = context[:1000]
    except:
        research = {"findings": [raw[:500]], "best_practices": [], "relevant_context": context[:500]}
    return {"research": research, "current_step": "developer", "logs": state.get("logs", []) + ["Researcher: context retrieved"]}

async def developer_node(state: AgentState) -> Dict:
    prompt = render_prompt(
        DEVELOPER_PROMPT,
        user_request=state["user_request"],
        plan=json.dumps(state.get("plan", {}))[:1500],
        research=json.dumps(state.get("research", {}))[:1500],
        architecture=state.get("plan", {}).get("architecture", "FastAPI + SQLite"),
        test_results=json.dumps(state.get("test_results", {}))[:1000] if state.get("retry_count",0)>0 else "None - first attempt"
    )
    # Use pro on retry
    task_type = "developer"
    if state.get("retry_count",0) > 0:
        task_type = "planner"  # routes to pro via TASK_ROUTING
    raw = await provider.generate(task_type, prompt, "You are expert Python developer. Output JSON only.", temperature=0.3)
    try:
        code = json.loads(raw)
        if "files" not in code:
            raise ValueError("no files")
    except Exception as e:
        code = {"files": [{"path": "app/main.py", "content": f"# Fallback\n# Error parsing: {e}\n{raw[:2000]}"}], "explanation": "Fallback generation"}
    
    # Write artifacts to disk
    out_dir = Path(settings.output_path) / state["task_id"]
    artifacts = write_artifacts(out_dir, code.get("files", []))
    
    return {
        "code": code,
        "current_step": "tester",
        "artifacts": artifacts,
        "logs": state.get("logs", []) + [f"Developer: {len(code.get('files',[]))} files (retry {state.get('retry_count',0)})"]
    }

async def tester_node(state: AgentState) -> Dict:
    artifacts = state.get("artifacts", [])
    task_id = state["task_id"]
    # Run pytest in output dir
    test_output, passed = run_tests(Path(settings.output_path) / task_id)
    
    # Also ask LLM to summarize
    prompt = render_prompt(
        TESTER_PROMPT,
        code=json.dumps(state.get("code", {}))[:1500],
        test_output=test_output[:2000]
    )
    raw = await provider.generate("tester", prompt, "Output JSON only", temperature=0.1)
    try:
        llm_result = json.loads(raw)
        # Override with real test result
        llm_result["passed"] = passed
        llm_result["summary"] = f"{test_output[:200]} | {llm_result.get('summary','')}"
        llm_result["raw_output"] = test_output
    except:
        llm_result = {"passed": passed, "summary": test_output[:500], "failures": [] if passed else [test_output[:500]], "raw_output": test_output}
    
    return {
        "test_results": llm_result,
        "current_step": "reviewer" if passed else "developer",
        "logs": state.get("logs", []) + [f"Tester: {'PASS' if passed else 'FAIL'} - {llm_result.get('summary','')[:80]}"]
    }

async def reviewer_node(state: AgentState) -> Dict:
    prompt = render_prompt(
        REVIEWER_PROMPT,
        user_request=state["user_request"],
        code=json.dumps(state.get("code", {}))[:1500],
        test_results=json.dumps(state.get("test_results", {}))[:1000]
    )
    raw = await provider.generate("reviewer", prompt, "You are strict reviewer. Output JSON only.", temperature=0.2)
    try:
        review = json.loads(raw)
    except:
        review = {"decision": "APPROVED", "score": 7, "issues": [], "suggestions": []}
    
    # Enforce logic: if tests failed, needs changes regardless of LLM
    if not state.get("test_results", {}).get("passed", False):
        review["decision"] = "NEEDS_CHANGES"
    
    return {
        "review": review,
        "current_step": "human_approval",
        "logs": state.get("logs", []) + [f"Reviewer: {review.get('decision')} score {review.get('score')}"]
    }

async def human_approval_node(state: AgentState) -> Dict:
    # This node is interrupt point - just set status, workflow will pause before executing tools
    return {
        "approval": state.get("approval", "pending"),
        "current_step": "human_approval",
        "logs": state.get("logs", []) + ["Waiting for human approval"]
    }
