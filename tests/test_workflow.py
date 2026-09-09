import pytest
import asyncio
from graph.workflow import run_workflow
from pathlib import Path

@pytest.mark.asyncio
async def test_minimal_workflow_mock():
    # Runs in mock mode without API key
    result = await run_workflow("test-123", "Build minimal FastAPI hello world with pytest", max_retries=1)
    assert result is not None
    assert "plan" in result or "code" in result
    assert result.get("artifacts") is not None or result.get("code") is not None

@pytest.mark.asyncio
async def test_llm_provider_mock():
    from backend.core.llm import provider
    text = await provider.generate("planner", "Build API")
    assert text is not None
    assert len(text) > 10

def test_filesystem_write():
    from tools.filesystem import write_artifacts
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        artifacts = write_artifacts(Path(tmp), [{"path": "app/main.py", "content": "x=1"}])
        assert len(artifacts) == 1
        assert (Path(tmp) / "app/main.py").exists()

def test_rag_retrieval_empty():
    from rag.retrieval import retrieve_context
    ctx = retrieve_context("test query", k=2)
    assert isinstance(ctx, str)
