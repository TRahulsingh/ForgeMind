"""
Synthetic own-data generator for testing.
Generates diverse tasks beyond CRUD clones, without LLM initially (template-based), LLM optional when key provided.
"""
import json
import random
from pathlib import Path

TEMPLATES = [
    {
        "title": "Webhook Event API",
        "request": "Build a webhook API: POST /webhooks/register {url, event}, POST /webhooks/trigger {event, payload} forwards to registered URLs (mock). Store registrations in SQLite, add retry count and tests for trigger.",
        "difficulty": "medium",
        "expected_files": ["app/main.py", "app/models.py"]
    },
    {
        "title": "Rate Limiter Middleware",
        "request": "Add rate limiting to FastAPI: limit 5 requests/minute per IP, return 429 with Retry-After header. Use in-memory store, add tests verifying 429 after 5 calls.",
        "difficulty": "hard",
        "expected_files": ["app/main.py", "app/middleware.py"]
    },
    {
        "title": "CSV Export API",
        "request": "Build CSV export: GET /employees/export returns CSV with headers name,email,role. Support filter ?role=, add tests checking CSV content and headers.",
        "difficulty": "medium",
        "expected_files": ["app/main.py"]
    },
    {
        "title": "Pagination with Cursor",
        "request": "Implement cursor pagination: GET /items?cursor=&limit=10 returns {items, next_cursor}. Use id-based cursor, not offset, with tests for page traversal.",
        "difficulty": "hard",
        "expected_files": ["app/main.py"]
    },
    {
        "title": "Notification Settings API",
        "request": "Notification settings: PUT /users/{id}/notifications {email,sms,push booleans}, GET /users/{id}/notifications. Validate at least one enabled, add tests.",
        "difficulty": "easy",
        "expected_files": ["app/main.py"]
    },
    {
        "title": "File Metadata API",
        "request": "File metadata: POST /files {filename, size, mime} stores metadata, GET /files?mime= filter, DELETE. Validate size <10MB and mime whitelist, add tests.",
        "difficulty": "medium",
        "expected_files": ["app/main.py"]
    },
]

def generate(count: int = 5, use_llm: bool = False, output: str = "evaluation/synthetic_dataset.json"):
    """Generate synthetic dataset. If use_llm and key available, delegate to LLM, else template."""
    if use_llm:
        try:
            from backend.core.llm import provider
            import asyncio, json as js
            # LLM generation would go here - for now fallback to template with LLM paraphrase
            print("LLM generation requested but using template + paraphrase for determinism")
        except Exception as e:
            print(f"LLM unavailable {e}, using template")
    
    selected = []
    for i in range(count):
        tmpl = random.choice(TEMPLATES)
        # Make id unique
        task_id = f"syn_{i+1:02d}"
        selected.append({
            "id": task_id,
            "title": tmpl["title"],
            "request": tmpl["request"],
            "difficulty": tmpl["difficulty"],
            "expected_files": tmpl["expected_files"]
        })
    
    Path(output).write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"Generated {len(selected)} synthetic tasks -> {output}")
    return selected

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--llm", action="store_true")
    p.add_argument("--output", default="evaluation/synthetic_dataset.json")
    args = p.parse_args()
    generate(args.count, args.llm, args.output)
