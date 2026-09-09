import json
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api", tags=["evaluation"])

@router.get("/evaluation/results")
async def get_results():
    p = Path("evaluation/results.json")
    if not p.exists():
        return {"total": 0, "message": "No results yet. Run python -m evaluation.evaluator 5"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        return {"error": str(e)}

@router.get("/evaluation/dataset")
async def get_dataset():
    p = Path("evaluation/dataset.json")
    if not p.exists():
        return {"error": "dataset not found"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"count": len(data), "tasks": data}
    except Exception as e:
        return {"error": str(e)}

@router.get("/rag/query")
async def rag_query(q: str, k: int = 3):
    """Query RAG and return context - preserves tables, anti-hallucination test."""
    try:
        from rag.retrieval import retrieve_context
        ctx = retrieve_context(q, k=k)
        return {"query": q, "context": ctx, "preserved": "Table" in ctx or "Columns:" in ctx}
    except Exception as e:
        return {"error": str(e)}

@router.get("/rag/stats")
async def rag_stats():
    try:
        from rag.retrieval import get_retrieval_stats
        stats = get_retrieval_stats()
        return stats
    except Exception as e:
        return {"error": str(e), "fallback_used": True}

@router.post("/rag/ingest")
async def rag_ingest(file: UploadFile = File(...)):
    """Upload tabular data (CSV, MD, JSON) for RAG - preserves tables without hallucination."""
    try:
        from rag.ingestion import ingest
        # Save upload to docs_seed
        dest = Path("docs_seed") / file.filename
        # Security: only allow tabular/text
        allowed = {".csv", ".tsv", ".md", ".txt", ".json"}
        if dest.suffix.lower() not in allowed:
            return {"error": f"unsupported {dest.suffix}, allowed {allowed}"}
        if ".." in Path(file.filename).parts:
            return {"error": "invalid path"}
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        # Re-ingest
        count = ingest()
        from rag.retrieval import get_retrieval_stats
        stats = get_retrieval_stats()
        return {"status": "ingested", "file": file.filename, "chunks": count, "stats": stats}
    except Exception as e:
        return {"error": str(e)}
