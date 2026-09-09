# ForgeMind Demo & Testing Guide

> **6GB, no Docker, mock zero-cost · verify orchestration in 5 min** — for users who build and readers who verify. Companion to [`architecture.md`](./architecture.md) (user guide) and [`README.md`](../README.md) (story). No API key needed for mock.

---

## 1. Prerequisites

| Need | Version | Check | Where |
|---|---|---|---|
| **Python** | `3.11` | `python --version` | `README.md:343` |
| **Node** | `18+` (`22.11.0` verified) | `node --version` | `frontend/package.json:8` |
| **Git** | any | `git --version` | — |
| **RAM** | `~6GB` | `Vite` 400MB vs `Next.js` 1GB | `docs/decisions.md:6` |
| **GOOGLE_API_KEY** | optional | leave empty for mock `backend/core/llm.py:44` `is_mock()` checks placeholder `your_gemini_api_key_here` | `.env.example:2` `GOOGLE_API_KEY=` |
| **GITHUB_TOKEN** | optional | leave empty for dry-run `tools/github.py:10` `ai/task-{id[:8]}` | `.env.example:9` |

Env file is idempotent: `backend/core/config.py:11` `model_config env_file=.env extra=allow` + `config.py:21` `Path(output/chroma_db).mkdir(exist_ok=True)` + `backend/core/database.py:73` `init_db()` `CREATE TABLE IF NOT EXISTS` + `WAL` `database.py:21`. Pinned deps `requirements.txt:1` `fastapi==0.110.0` `langgraph==0.2.16` `chromadb==0.5.3` `pytest==8.2.2` + `pytest.ini:1` `norecursedirs = output frontend chroma_db`.

---

## 2. One-Command Quick Start (Primary)

ForgeMind’s best one-cmd checks before downloading — if all pass it goes, if not it downloads that stuff. No repeated `pip install`.

```powershell
# From project root C:\Users\rahul\Desktop\crew (or your clone)
powershell -ExecutionPolicy Bypass -File run.ps1
# Or double-click run.bat (bypasses ExecutionPolicy for you)

# What run.ps1 does (idempotent, check-before-download, never downgrades):
# 1) Env: if Test-Path .env else Copy-Item .env.example .env (.env.example:1) + warn if placeholder still
# 2) Python deps: python tools/check_pydeps.py --gte (Version(installed) < Version(required) only) -> if OK skip pip, else pip install --no-deps <missing> (never uninstall/downgrade)
# 3) Node deps: Test-Path frontend/node_modules/react + package-lock.json -> if OK skip npm, else npm ci --prefer-offline
# 4) RAG: Test-Path chroma_db/fallback.json + ingest_stats.json + chunks>0 + fallback newer than docs_seed -> if OK skip, else python -m rag.ingestion (table-aware 7 chunks)
# 5) Backend: try Invoke-RestMethod http://localhost:8000/health (backend/main.py:30) -> if running skip uvicorn, else Start-Process powershell uvicorn backend.main:app --reload --port 8000 + poll 15x2s + open http://localhost:8000/docs
# 6) Frontend: try Invoke-WebRequest http://localhost:5173 -> if running skip, else Start-Process npm run dev + open http://localhost:5173
# Flags: -NoBrowser (no browser), -NoInstall (runner only: skip 2-4) e.g. run.ps1 -NoInstall -NoBrowser
```

> Then open `http://localhost:5173` Workflow tab. `run.bat:3` forwards `%*` so `run.bat -NoInstall` works.

**Manual alternative (2 terminals, for control):** see `README.md:337` `<details>` and `docs/architecture.md:114` `Option B` — `pip install -r requirements.txt` `copy .env.example .env` `python -m rag.ingestion` `uvicorn backend.main:app --reload --port 8000` `cd frontend; npm install; npm run dev`. Quick start above is primary.

---

## 3. Quick Test — `pytest -q` (11 tests, mock, no key)

```powershell
pytest -q
# -> 11 passed, 2 warnings (grpc 1.83 FutureWarning + genai deprecated backend/core/llm.py:33) in ~13s
# With pytest.ini:1 norecursedirs = output frontend chroma_db, testpaths = tests

# Focused
pytest tests/test_tabular_rag.py -v
# -> test_tabular_ingestion (detect_markdown_tables 2 rows rag/ingestion.py:25)
# -> test_csv_chunk (Columns: id, name, email + is_table True rag/ingestion.py:68)
# -> test_retrieval_preserves_table (Alice Johnson 95000 + Columns: Table rag/retrieval.py:28)
# -> test_filesystem_allows_csv (data.csv + app/main.py tools/filesystem.py:4)
# -> test_ingest_stats_table (table_chunks rag/ingestion.py:255)

pytest tests/test_workflow.py::test_minimal_workflow_mock -v
# -> mock planner 3 tasks -> developer 4 files -> tester PASS -> reviewer APPROVED (via fallback _mock_generate backend/core/llm.py:95) ~65s real (mock 4.2s)

pytest tests/test_tools.py -v
# -> test_run_tests_no_dir / empty (tools/python_exec.py:5 30s timeout + py_compile fallback)
```

CI ` .github/workflows/ci.yml.example:1` is template `ubuntu-latest python 3.11 pip install -r requirements.txt pytest -q` — copy to `ci.yml` to enable `on: [push]`.

---

## 4. RAG Tabular Demo — No Hallucination

Tabular pipeline preserves column context and row relationships with header repetition.

### 4.1 Ingest (7 chunks: 5 text, 2 table)

```powershell
python -m rag.ingestion
# -> Ingested 7 chunks (5 text, 2 table) from 6 docs into ./chroma_db/fallback.json (vector or fallback keyword) + ingest_stats.json
# Sources: docs_seed/employees.csv (10 rows), employees_table.md, fastapi_standards.md, architecture_guidelines.md, testing_strategy.md, synthetic_example.md
# Chunking: CHUNK_SIZE 500 OVERLAP 50 rag/ingestion.py:9, TABLE_ROWS_PER_CHUNK 20 header-repeat rag/ingestion.py:46, linearize_csv_row col: val rag/ingestion.py:58
```

`chunk_markdown_table` repeats `header + sep` each chunk `rag/ingestion.py:46`, `chunk_csv_file` Sniffer `rag/ingestion.py:68` `linearize_csv_row:58` `col: val | col: val` + markdown table, `embed` MiniLM 80MB `rag/embeddings.py:14` or hash `384d` fallback.

### 4.2 Verify — Exact Value Preserved (Not Hallucinated)

```powershell
python -c "from rag.retrieval import retrieve_context, get_retrieval_stats; print(get_retrieval_stats()); print(retrieve_context('Alice Johnson salary', k=2)[:1200])"
# -> {'chunks': 7, 'text_chunks': 5, 'table_chunks': 2, 'fallback_used': True}
# -> [Source: docs_seed/employees.csv [Table | Columns: id, name, email, role, department, salary | Rows: 0-9]]
#    [Table: employees.csv | Columns: id, name, email, role, department, salary | Rows 0-9 | Total rows: 10]
#    | 1 | Alice Johnson | alice@forgemind.ai | Engineering | Backend | 95000 | 2022-03-15 |
#    | ... | 95000 preserved, not invented
```

Retrieval `rag/retrieval.py:4` `k=5` preserves `2000` chars for tables vs `800` for text `retrieval.py:28` + `Columns:` header `retrieval.py:35`, fallback keyword `qwords` scoring `retrieval.py:40` `sum(1 for w in qwords if w in doc)` + header `retrieval.py:65`.

### 4.3 API RAG (no Python needed)

```bash
# Upload your own table
curl -X POST http://localhost:8000/api/rag/ingest -F "file=@docs_seed/employees.csv"
# -> {"status":"ingested","file":"employees.csv","chunks":7,"stats":{"table_chunks":2}} backend/api/evaluation.py:49 allowlist .csv/.tsv/.md/.txt/.json

# Query
curl "http://localhost:8000/api/rag/query?q=Alice%20Johnson%20salary&k=2"
# -> {"query":"...","context":"[Source: employees.csv [Table | Columns: ...]] + 95000","preserved":true} backend/api/evaluation.py:30

curl http://localhost:8000/api/rag/stats
# -> {"chunks":7,"table_chunks":2,"fallback_used":true} rag/retrieval.py:57 get_retrieval_stats()

# Frontend Benchmark tab: Upload CSV `<input accept .csv>` frontend/src/App.jsx:177 POST /rag/ingest + Test Query GET /rag/query
```

Research prompt `agents/prompts/researcher.md:27` explicitly: *Never hallucinate table values. If not in context, say not found.*

---

## 5. Synthetic Data Demo — Own Tabular + Diverse Tasks

Beyond `evaluation/dataset.json:1` 15 tasks (6 easy `hello-world`, 7 medium `employee CRUD`, 2 hard `JWT`):

```powershell
python evaluation/synthetic_generator.py --count 5
# -> evaluation/synthetic_dataset.json 5 tasks (webhook, rate-limit, CSV export, cursor pagination, notification) TEMPLATES 6 random.choice evaluation/synthetic_generator.py:9
cat evaluation/synthetic_dataset.json

# With LLM paraphrase (stub, future)
python evaluation/synthetic_generator.py --count 5 --llm --output evaluation/synthetic_dataset.json
```

`docs_seed/synthetic_example.md` example, `docs_seed/employees.csv` ground truth for tabular tasks.

---

## 6. Single-Task Demo — Mock vs Real (Gemini)

### Mock (zero-cost, deterministic, same orchestration)

```powershell
python -c "import asyncio, json; from evaluation.evaluator import evaluate_task; t=json.loads(open('evaluation/dataset.json').read())[2]; print(asyncio.run(evaluate_task(t)))"
# t = task_03 hello-world, uses provider.is_mock() backend/core/llm.py:44 + _mock_generate:95 planner 3 tasks -> developer 4 files -> tester PASS -> reviewer APPROVED 8
# -> {"id":"task_03","tests_passed":true,"review_decision":"APPROVED","latency_sec":4.2,"success":true}
# artifacts: output/task_03_*/app/main.py via tools/filesystem.py:4 secure posix quota 50 files/2MB
```

### Real (with `GOOGLE_API_KEY` `application/json` structured)

Add `GOOGLE_API_KEY=your_key_here` from Google AI Studio to `.env:2` `.env.example:2`, check `curl http://localhost:8000/health` `{"mock_mode": false}` `backend/main.py:30` `provider.is_mock()` false → `TASK_ROUTING:12` `planner/pro` `MODEL_MAP:21` `gemini-flash-latest/pro-latest` `backend/core/llm.py:21`, free tier `5 RPM` `llm.py:21` → 1 task/min, retry `developer_with_retry:66` `flash→pro` on `retry_count`.

```powershell
# Single real task via API (recommended)
curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d "{\"request\":\"Build minimal FastAPI hello world with GET / and GET /health and pytest tests\",\"max_retries\":2}"
# -> {"task_id":"...","status":"running"}
curl http://localhost:8000/api/stream/{task_id}  # SSE backend/main.py:46 keepalive 15s + snapshot fallback
curl http://localhost:8000/api/tasks/{task_id}   # state + logs + artifacts
curl -X POST http://localhost:8000/api/tasks/{task_id}/approve -H "Content-Type: application/json" -d "{\"decision\":\"approved\"}"
# -> {"status":"completed","pr":{"status":"dry_run","branch":"ai/task-..."}} tools/github.py:10
```

Mock `4.2s` `100%` vs real `60-80%` `8-20s` variance `docs/evaluation.md:29` — mock proves orchestration, real proves LLM.

---

## 7. Benchmark Demo — 15 Tasks (`evaluation/results.json`)

`evaluation/dataset.json:1` 15 tasks `6 easy: task_03 hello-world, 06 calculator, 07 validation, 10 notes, 12 weather, 15 feedback` `7 medium: 01 employee CRUD, 04 task mgmt, 05 blog search, 08 inventory, 09 book, 11 contacts, 14 shortener` `2 hard: 02 JWT, 13 cart` + `synthetic_dataset.json` 5 diverse.

```powershell
# Mock benchmark (zero cost, 63s total sequential)
python -m evaluation.evaluator 5   # 5 tasks -> evaluation/results.json 100% 4.1s
python -m evaluation.evaluator 15  # full 15 -> 15/15 100% 4.2s avg sequential (63s)

# Real (1 task/min free tier)
python evaluation/synthetic_generator.py --count 5
python -m evaluation.evaluator 5  # expect 60-80% real

# View
cat evaluation/results.json  # timestamp, total, task_completion, test_pass_rate, approval_rate, avg_latency_sec, mock_mode true/false evaluator.py:72
python evaluation/metrics.py  # task_completion/test_pass/avg_latency evaluation/metrics.py:10

# UI Benchmark tab frontend/src/App.jsx:178 GET /api/evaluation/results + GET /api/rag/stats 7 chunks + GET /api/evaluation/dataset 15
# 4 cards Completion/Tests/Latency/Total + table bench.results {id, title, tests_passed, review_decision, latency_sec, success}
```

**Example mock `evaluation/results.json:1` (15 tasks, double-run fixed `graph/workflow.py:137` single `ainvoke`):**

| Metric | Result |
|---|---|
| **Task completion** | **100.0%** |
| **Tests passing** | **100.0%** |
| **Approval rate** | **100.0%** |
| **Avg latency** | **4.2s** |
| Mock mode | true |

*Don't copy numbers — generate your own via `evaluator.py:60` sequential `for task in data`.*

---

## 8. Frontend Demo — Workflow & Benchmark Tabs

`http://localhost:5173` `frontend/src/App.jsx:12` cool tones `slate/sky/cyan/emerald` `max-w-3xl`:

**Workflow tab:**
- Textarea `App.jsx:219` default `Build REST API for employee management...` + `Start Task` `POST /api/tasks:28` `TaskCreate max_retries 2` `backend/api/tasks.py:22`
- Stepper `STEPS:3` `App.jsx:12` `Understanding → Researching + RAG k=5 → Generating → Testing → Review → Human approval` `○` idle `slate-300` → `●` pulse `cyan-500` → `✓` emerald `slate-50`
- `EventSource /api/stream/{id}:89` SSE `backend/main.py:46` `text/event-stream` keepalive `15s` + snapshot fallback `GET /tasks/{id}:50` `backend/main.py:81` if refresh
- Logs `bg-slate-900` `› Planner: 3 tasks` `› Tester: PASS`, Artifacts grid `app/main.py` (4 files `graph/nodes.py:94` `write_artifacts` `as_posix`), `Human Approval Required` modal `App.jsx:268` `Review: APPROVED score 8` → `Approve & Create PR` `POST /approve:105` dry-run `ai/task-{id[:8]}` `tools/github.py:10` else `pr_url`
- Health dot `App.jsx:169` `mock mode` amber vs `emerald` `GET /health` `backend/main.py:30`

**Benchmark tab `App.jsx:178`:**
- 4 cards `Completion/Tests/Latency/Total` `bench.task_completion` + table `bench.results` `{id, title, tests_passed, review_decision, latency_sec, success}`
- RAG upload `<input accept .csv,.tsv,.md>` `App.jsx:211` `POST /rag/ingest` `evaluation.py:49` + Test Query `GET /rag/query` `evaluation.py:30` `preserved: true`
- `fetch /health` `mock_mode` amber, `fetch /evaluation/results` + `fetch /rag/stats` `table_chunks` on mount `App.jsx:54`

---

## 9. API Demo — curl (6 endpoints)

Copy from `README.md:408` and `docs/architecture.md:135`:

```bash
# Create task
curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d "{\"request\":\"Build minimal FastAPI hello world with GET / and GET /health and pytest tests\",\"max_retries\":2}"
# -> {"task_id":"...","status":"running"}

# Stream live (SSE)
curl http://localhost:8000/api/stream/{task_id}
# data: {"step":"planner","data":{"plan":{...}}}
# data: {"step":"done","data":{"status":"awaiting_approval"}}

# Check
curl http://localhost:8000/api/tasks/{task_id}
# -> {"task_id": "...","status":"awaiting_approval","state":{"logs":[...],"artifacts":[...]}} 

# Approve (HITL gate graph/nodes.py:159 pending → POST /approve)
curl -X POST http://localhost:8000/api/tasks/{task_id}/approve -H "Content-Type: application/json" -d "{\"decision\":\"approved\"}"
# -> {"status":"completed","pr":{"status":"dry_run","branch":"ai/task-..."}}
# rejected: {"decision":"rejected","feedback":"..."} -> stored backend/api/tasks.py:124

# Tabular RAG (no hallucination)
curl -X POST http://localhost:8000/api/rag/ingest -F "file=@docs_seed/employees.csv"
# -> {"status":"ingested","file":"employees.csv","chunks":7,"stats":{"table_chunks":2}} allowlist .csv/.tsv/.md/.txt/.json backend/api/evaluation.py:50
curl "http://localhost:8000/api/rag/query?q=Alice%20Johnson%20salary&k=2"
# -> {"query":"...","context":"[Source: employees.csv [Table | Columns: id, name, email, role, salary...]] + full row 95000","preserved":true}
curl http://localhost:8000/api/rag/stats
# -> {"chunks":7,"text_chunks":5,"table_chunks":2,"fallback_used":true} rag/retrieval.py:57
curl http://localhost:8000/api/evaluation/dataset
# -> {"count":15,"tasks":[...]} evaluation.py:18
curl http://localhost:8000/api/evaluation/results
# -> evaluation/results.json 15/15 100% 4.2s
curl http://localhost:8000/health
# -> {"mock_mode": true/false, "status":"ok"} backend/main.py:30 provider.is_mock() backend/core/llm.py:44
curl http://localhost:8000/docs
# -> Swagger UI FastAPI ForgeMind 1.0.0 backend/main.py:17
```

All outputs in `output/{task_id}/` `backend/core/config.py:11` `OUTPUT_PATH=./output` `gitignored:15` `output/*` `!output/.gitkeep` + `GET /api/tasks` list `backend/api/tasks.py:90`.

---

## 10. Troubleshooting (6GB common fails)

| Symptom | Cause | Fix | File |
|---|---|---|---|
| `pip install` fails `regex 2024.11.6` | `transformers` needs `regex>=2026.9.3` | `pip install --upgrade regex` already did `2026.9.3` vs `2024.11.6` | `README.md:384` |
| `Chroma ingest failed: No module named 'chromadb'` | `chromadb==0.5.3` not installed on fresh `pip` | fallback `chroma_db/fallback.json` keyword retrieval works (shows 7 chunks), same API `rag/retrieval.py:40` `qwords` scoring | `rag/ingestion.py:259` |
| `google-generativeai` deprecated `FutureWarning` | `google-generativeai 0.7.2` deprecated `ModelService` | Still works `gemini-flash-latest OK` `list_models` `gemini-flash-latest`, migrate to `google.genai` later `backend/core/llm.py:33` | `README.md:386` |
| `database is locked` | `SQLite WAL` contention `backend/core/database.py:9` `PRAGMA journal_mode=WAL` `timeout=10` handles sequential 15 tasks | Concurrent `>10` needs `Postgres` `docs/upgrade.md:20` | `backend/core/database.py:9` |
| `5 RPM` `You exceeded quota` `429` | `gemini-flash-latest/pro-latest` `backend/core/llm.py:21` `MODEL_MAP` free tier `5 RPM` | `mock fallback` `backend/core/llm.py:95` `planner 3 tasks` or wait `20s` between real tasks | `README.md:389` |
| `ExecutionPolicy` blocked `run.ps1` | `Restricted` | `powershell -ExecutionPolicy Bypass -File run.ps1` or `run.bat` (primary `README.md:320`) | `run.ps1:1` `run.bat:3` |
| `Port 8000/5173 busy` | `Get-NetTCPConnection` | `run.ps1:68` `Test-PortFree` check before `Start-Process` | `run.ps1:58` |
| `pytest` collects `output/*/tests` duplicates | `output/` leftovers | `pytest.ini:1` `norecursedirs = output frontend chroma_db .git` `testpaths = tests` — `pytest -q` `11 passed` | `pytest.ini:1` |
| `ModuleNotFoundError: app` | `pytest` run from `output/{id}` `cwd` `tools/python_exec.py:30` | `rglob` `test_*.py` check `python_exec.py:14` | `tools/python_exec.py:5` |

`run.ps1:39` re-ingests only if `chroma_db/fallback.json` missing or `docs_seed` newer than `fallback.json` — otherwise skips.

---

## 11. What to Show in Demo Video (3-min script for recruiter)

**0:00-0:20 — One-cmd + health**

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
# Check idempotent: Python deps OK -- skip pip, RAG OK 7 chunks -- skip ingest, Backend healthy mock=true
```
Show `http://localhost:5173` Workflow tab `cool tones` + `http://localhost:8000/health` `{"mock_mode":true}` + `http://localhost:8000/docs` Swagger `ForgeMind 1.0.0`.

**0:20-0:50 — Tests + RAG no hallucination**

```powershell
pytest -q # 11 passed
python -c "from rag.retrieval import retrieve_context; print(retrieve_context('Alice Johnson salary', k=2)[:800])"
# -> [Table | Columns: id, name, email, role, salary] + 95000 preserved
```

**0:50-1:30 — Workflow single task (mock)**

Frontend `Build minimal FastAPI hello world with GET / and GET /health and pytest tests` `frontend/src/App.jsx:219` → `Start Task` → live stepper pulse `cyan` `App.jsx:12` → Logs `bg-slate-900` `Planner: 3 tasks` → Artifacts `app/main.py` 4 files → `Review: APPROVED 8` → Approve → `dry_run` branch `ai/task-xxxx` `output/{id}` `app/main.py` `tests/test_main.py`.

**1:30-2:00 — Benchmark + RAG upload**

`python -m evaluation.evaluator 5` `evaluation/evaluator.py:60` `100% 4.2s` → Benchmark tab `App.jsx:178` 4 cards + table `bench.results` + `GET /api/rag/stats` `7 chunks` `2 table`, upload `data.csv` `POST /rag/ingest` `App.jsx:211` → `table_chunks 2 → 3` → `Test Query` `GET /rag/query?q=...&k=2` `preserved: true`.

**2:00-2:40 — API SSE**

```bash
curl -X POST http://localhost:8000/api/tasks -d '{"request":"Build ...","max_retries":2}' # → task_id
curl http://localhost:8000/api/stream/{task_id} # data: {"step":"planner"}
curl http://localhost:8000/api/tasks/{task_id} # state logs artifacts
curl "http://localhost:8000/api/rag/query?q=Alice%20Johnson%20salary&k=2" # preserved true
```

**2:40-3:00 — Architecture + Scale**

Show `docs/architecture.md:18` mermaid `User→Vite→LangGraph→5 agents→Tools→RAG 7 chunks` + `docs/upgrade.md:38` upgraded `Next.js→...→pgvector→MCP→OTEL` flowchart `One env-var + One file` swap `backend/core/config.py:11` `CHROMA_PATH=postgres://` — close with `Forge the mind. Forge the code.`

---

## Appendix — Scripts Reference & File Map

| Script | What it does | Where | Example |
|---|---|---|---|
| `python -m rag.ingestion` | Ingest `docs_seed/` (CSV/md tables header-repeat) → `chroma_db/fallback.json` 7 chunks (5 text, 2 table) | `rag/ingestion.py:1` `CHUNK_SIZE 500/50` `TABLE_ROWS_PER_CHUNK 20` | `Ingested 7 chunks (5 text, 2 table)` |
| `python evaluation/synthetic_generator.py --count 5` | Generate diverse tasks → `evaluation/synthetic_dataset.json` | `evaluation/synthetic_generator.py:1` | `--count 5` |
| `uvicorn backend.main:app --reload --port 8000` | Start API `http://localhost:8000/docs` | `backend/main.py:1` | `uvicorn ...` |
| `cd frontend; npm run dev` | Start Vite `http://localhost:5173` | `frontend/package.json:8` | `npm run dev` |
| `cd frontend; npm run build` | Build `frontend/dist` 158kB | `frontend/vite.config.js:1` | `npm run build` |
| `pytest -q` | Run 11 tests | `tests/` | `11 passed` |
| `python -m evaluation.evaluator 5/15` | Benchmark 5/15 → `evaluation/results.json` | `evaluation/evaluator.py:1` | `5` 4.1s `15` 63s |
| `python -c "from rag.retrieval import retrieve_context; ..."` | Test RAG `Alice 95000` | `rag/retrieval.py:4` | `retrieve_context('Alice', k=2)` |
| `python -m evaluation.metrics` | Print metrics | `evaluation/metrics.py:1` | `metrics` |
| `curl -X POST /api/rag/ingest -F "file=@employees.csv"` | Upload tabular | `backend/api/evaluation.py:49` | `curl -F ...` |

**Prompt editing:** `agents/prompts/*.md:1` front-matter `tier: pro/flash` `temperature` `loader.py:17` `@lru_cache` `graph/nodes.py:21` `render_prompt` safe braces.

**Structure:** See `README.md` `Detailed Project Structure` 50-line tree `ForgeMind/` `agents/prompts/` `graph/` `rag/` `backend/` `tools/` `frontend/` `evaluation/` `docs/` `tests/` `output/` — full in `docs/architecture.md:155`.

---

*For users who want the story, see `README.md` (Why ForgeMind). For users who build, see `docs/architecture.md` (how it works, how to use). For growth, see `docs/upgrade.md` (file→server recipes).*
