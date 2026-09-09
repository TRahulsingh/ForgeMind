import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.core.config import settings
from backend.api.tasks import router as tasks_router, queues
from backend.api.evaluation import router as eval_router
from backend.core.database import get_task
from graph.workflow import run_workflow
from backend.core.llm import provider

app = FastAPI(title="ForgeMind — Autonomous AI Software Engineering Agent", version="1.0.0", description="LangGraph · Gemini · RAG · Multi-Agent Systems · Human-in-the-Loop")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(eval_router)

@app.get("/health")
async def health():
    return {"status": "ok", "mock_mode": provider.is_mock(), "version": "0.1.0"}

class GenerateRequest(BaseModel):
    prompt: str
    task_type: str = "planner"

@app.post("/api/generate")
async def generate(req: GenerateRequest):
    text = await provider.generate(req.task_type, req.prompt)
    try:
        return json.loads(text)
    except:
        return {"raw": text}

@app.get("/api/stream/{task_id}")
async def stream(task_id: str, request: Request):
    q = queues.get(task_id)
    # If no active queue, try to stream from DB state logs
    if q is None:
        row = get_task(task_id)
        if not row:
            return JSONResponse({"error": "task not found"}, status_code=404)
        try:
            state = json.loads(row["state_json"]) if row["state_json"] else {}
        except:
            state = {}
        # Static snapshot stream
        async def snapshot():
            logs = state.get("logs", [])
            for log in logs:
                yield f"data: {json.dumps({'step': 'log', 'data': log})}\n\n"
            yield f"data: {json.dumps({'step': 'done', 'data': {'status': row['status']}})}\n\n"
        return StreamingResponse(snapshot(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(q.get(), timeout=15)
            except asyncio.TimeoutError:
                yield f": keepalive\n\n"
                continue
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

@app.get("/", response_class=HTMLResponse)
async def root():
    # Minimal fallback if frontend not built - serves instruction
    frontend_dist = Path("frontend/dist/index.html")
    if frontend_dist.exists():
        return frontend_dist.read_text(encoding="utf-8")
    return """
    <html><head><title>Autonomous AI Engineer</title>
    <style>body{font-family:Inter,system-ui;padding:40px;max-width:700px;margin:0 auto;color:#0f172a;background:#f8fafc}
    .card{background:white;padding:24px;border-radius:12px;border:1px solid #e2e8f0;margin-top:20px}
    .btn{background:#0ea5e9;color:white;padding:10px 18px;border:none;border-radius:8px;cursor:pointer}
    pre{background:#1e293b;color:#e2e8f0;padding:16px;border-radius:8px;overflow:auto}
    </style></head><body>
    <h2 style="color:#0f172a">Autonomous AI Software Engineer</h2>
    <p style="color:#475569">Backend running. Frontend at <code>frontend/</code> - run <code>npm run dev</code> in frontend folder.</p>
    <div class="card">
      <h3>Try API</h3>
      <pre>POST /api/tasks
{"request": "Build REST API for employee management with FastAPI and SQLite"}</pre>
      <p><a href="/docs">Open Swagger Docs</a> &middot; <a href="/health">Health</a></p>
    </div>
    </body></html>
    """

# Serve frontend static if built
dist = Path("frontend/dist")
if dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
