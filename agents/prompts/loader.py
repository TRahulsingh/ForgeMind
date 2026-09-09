"""Loader for clean prompts dir - caches, fallback to inline if file missing."""
from functools import lru_cache
from pathlib import Path
import re

PROMPT_DIR = Path(__file__).parent

# Fallback inline mirrors graph/nodes.py original to keep workflow alive
_FALLBACK = {
    "planner": 'You are Planner agent. Decompose user request into executable subtasks.\nUser request: {user_request}\nReturn JSON: {"tasks": [{"id": int, "title": str, "description": str, "dependencies": [int]}], "architecture": str, "estimated_complexity": str}',
    "researcher": 'You are Researcher. Find best practices and context.\nUser request: {user_request}\nPlan: {plan}\nRetrieved context: {context}\nReturn JSON: {"findings": [str], "best_practices": [str], "relevant_context": str}',
    "developer": 'You are Developer. Generate implementation.\nUser request: {user_request}\nPlan: {plan}\nResearch: {research}\nArchitecture: {architecture}\nPrevious test failures (if retry): {test_results}\nReturn JSON: {"files": [{"path": str, "content": str}], "explanation": str}',
    "tester": 'You are Tester. Analyze test output.\nCode summary: {code}\nTest output: {test_output}\nReturn JSON: {"passed": bool, "summary": str, "failures": [str], "command": str}',
    "reviewer": 'You are Reviewer. Check correctness, security, maintainability.\nUser request: {user_request}\nCode: {code}\nTest results: {test_results}\nReturn JSON: {"decision": "APPROVED" or "NEEDS_CHANGES", "score": int 1-10, "issues": [str], "suggestions": [str]}',
}

@lru_cache(maxsize=5)
def load_prompt(name: str):
    p = PROMPT_DIR / f"{name}.md"
    if not p.exists():
        return _FALLBACK.get(name, ""), {}
    text = p.read_text(encoding="utf-8")
    # Strip YAML front-matter
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if m:
        meta, body = m.groups()
        # Parse minimal meta for tier/temperature if needed
        # For now just return body
        return body.strip(), {}
    return text.strip(), {}

def get_all_prompts():
    return {name: load_prompt(name)[0][:80] for name in _FALLBACK}
