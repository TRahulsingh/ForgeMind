"""
LLMProvider abstraction - core AI engineering decision.
Supports Gemini Pro (complex reasoning) vs Flash (fast/cheap) with mock fallback.
This allows evaluation without API key and easy model swapping.
"""
import os
import json
from typing import Optional, Dict, Any, List
from backend.core.config import settings

# Task type routing
TASK_ROUTING = {
    "planner": "pro",      # complex reasoning
    "architect": "pro",
    "reviewer": "pro",
    "researcher": "flash", # fast
    "developer": "flash",  # will use pro if retry
    "tester": "flash",
}

MODEL_MAP = {
    "pro": "gemini-pro-latest",
    "flash": "gemini-flash-latest",
}

class LLMProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client = None
        self._langchain_models = {}
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
            except Exception as e:
                print(f"[LLMProvider] genai init failed, using mock: {e}")
                self._client = None

    def get_model_name(self, task_type: str) -> str:
        tier = TASK_ROUTING.get(task_type, "flash")
        return MODEL_MAP[tier]

    def is_mock(self) -> bool:
        if not self.api_key or self.api_key.strip() in ["", "your_gemini_api_key_here", "test"]:
            return True
        if self.api_key and "your" in self.api_key.lower():
            return True
        return self._client is None

    async def generate(
        self,
        task_type: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate with structured output support. Falls back to mock if no key."""
        if self.is_mock():
            return self._mock_generate(task_type, prompt, response_schema)

        model_name = self.get_model_name(task_type)
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json" if response_schema else "text/plain",
                ),
            )
            full_prompt = prompt
            if response_schema:
                full_prompt += f"\n\nRespond with valid JSON matching schema: {json.dumps(response_schema)}"
            
            response = await model.generate_content_async(full_prompt)
            text = response.text
            # Validate JSON if schema expected
            if response_schema:
                try:
                    json.loads(text)
                except:
                    # try to extract json block
                    import re
                    m = re.search(r"\{.*\}", text, re.DOTALL)
                    if m:
                        text = m.group(0)
            return text
        except Exception as e:
            print(f"[LLMProvider] generate failed ({model_name}): {e}, fallback to mock")
            return self._mock_generate(task_type, prompt, response_schema)

    def _mock_generate(self, task_type: str, prompt: str, schema: Optional[Dict]) -> str:
        """Deterministic mocks for local dev without API key - showcases orchestration."""
        prompt_lower = prompt.lower()[:500]
        if task_type == "planner":
            return json.dumps({
                "tasks": [
                    {"id": 1, "title": "Design API structure", "description": "Define endpoints and models", "dependencies": []},
                    {"id": 2, "title": "Implement core logic", "description": "Write FastAPI routes", "dependencies": [1]},
                    {"id": 3, "title": "Add tests", "description": "pytest coverage", "dependencies": [2]},
                ],
                "architecture": "FastAPI + SQLite + JWT",
                "estimated_complexity": "medium"
            })
        elif task_type == "researcher":
            return json.dumps({
                "findings": ["Use FastAPI dependency injection for auth", "SQLAlchemy async recommended", "pytest fixtures for DB"],
                "best_practices": ["Follow REST conventions", "Use Pydantic v2"],
                "relevant_context": prompt_lower[:200]
            })
        elif task_type == "developer":
            # Minimal FastAPI app mock
            return json.dumps({
                "files": [
                    {"path": "app/main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef root():\n    return {'status': 'ok'}"},
                    {"path": "app/models.py", "content": "from pydantic import BaseModel\nclass Employee(BaseModel):\n    name: str\n    role: str"},
                    {"path": "requirements.txt", "content": "fastapi\nuvicorn\npytest"},
                    {"path": "tests/test_main.py", "content": "from fastapi.testclient import TestClient\nfrom app.main import app\nclient = TestClient(app)\ndef test_root():\n    assert client.get('/').status_code == 200"},
                ],
                "explanation": "Generated minimal FastAPI service with CRUD placeholder"
            })
        elif task_type == "tester":
            return json.dumps({
                "passed": True,
                "summary": "All mock tests passed (3/3)",
                "failures": [],
                "command": "pytest -q"
            })
        elif task_type == "reviewer":
            return json.dumps({
                "decision": "APPROVED",
                "score": 8,
                "issues": [],
                "suggestions": ["Add input validation", "Add auth"]
            })
        else:
            return json.dumps({"result": f"mock for {task_type}", "prompt_snippet": prompt_lower[:100]})

# Singleton
provider = LLMProvider()
