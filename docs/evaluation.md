# Evaluation

## Dataset
`evaluation/dataset.json` - 15 tasks (easy/medium/hard) covering FastAPI CRUD, auth, search, pagination, etc.

## Metrics
- Task completion: review APPROVED and tests passed
- Test pass rate: pytest pass via subprocess
- Approval rate: reviewer APPROVED
- Avg latency
- File score: expected files found

## Run
```
python -m rag.ingestion
python -m evaluation.evaluator 5   # 5 tasks, ~13s each mock, ~35s with real Gemini
cat evaluation/results.json
```

Example mock results (5 tasks, 2026-09-08):
| Metric | Result |
|---|---|
| Task completion | 100.0% |
| Tests passing | 100.0% |
| Approval rate | 100.0% |
| Avg latency | 12.9s |
| Tasks | 5 |

With real GOOGLE_API_KEY, expect ~60-80% completion due to LLM variance, higher latency, and token cost. Mock mode proves orchestration without cost.

## Benchmarking
Add your own task to dataset.json and rerun. Results are deterministic in mock, but with Gemini use temperature 0.2-0.3 and max_retries 2 for reproducibility.

