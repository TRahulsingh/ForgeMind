import json
import time
import asyncio
from pathlib import Path
from datetime import datetime

from graph.workflow import run_workflow
from tools.python_exec import run_tests
from backend.core.config import settings

DATASET = Path("evaluation/dataset.json")
OUTPUT = Path("evaluation/results.json")

async def evaluate_task(task: dict):
    task_id = task["id"] + "_" + datetime.utcnow().strftime("%H%M%S")
    start = time.time()
    try:
        result = await run_workflow(task_id, task["request"], max_retries=2)
        latency = time.time() - start
        
        # Check artifacts
        artifacts = result.get("artifacts", [])
        test_results = result.get("test_results", {})
        review = result.get("review", {})
        
        # Run tests again for verification
        test_output, passed = run_tests(Path(settings.output_path) / task_id)
        
        # Expected files check
        expected = task.get("expected_files", [])
        artifacts_lower = [a.lower() for a in artifacts]
        found = sum(1 for e in expected if any(e.lower() in a for a in artifacts_lower))
        file_score = found / len(expected) if expected else (1 if artifacts else 0)
        
        return {
            "id": task["id"],
            "title": task["title"],
            "latency_sec": round(latency, 1),
            "artifacts": len(artifacts),
            "artifacts_list": artifacts,
            "tests_passed": passed,
            "tests_summary": test_results.get("summary", "")[:200],
            "review_decision": review.get("decision", "unknown"),
            "review_score": review.get("score", 0),
            "file_score": file_score,
            "success": passed and review.get("decision") == "APPROVED",
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "id": task["id"],
            "title": task["title"],
            "latency_sec": round(time.time()-start, 1),
            "error": str(e),
            "success": False,
            "tests_passed": False,
        }

async def main(limit: int = 15):
    data = json.loads(DATASET.read_text())
    if limit:
        data = data[:limit]
    
    results = []
    for task in data:
        print(f"\n=== Evaluating {task['id']}: {task['title']} ===")
        res = await evaluate_task(task)
        results.append(res)
        print(json.dumps(res, indent=2))
    
    # Summary
    total = len(results)
    successes = sum(1 for r in results if r.get("success"))
    tests_pass = sum(1 for r in results if r.get("tests_passed"))
    avg_latency = sum(r.get("latency_sec",0) for r in results)/total if total else 0
    approved = sum(1 for r in results if r.get("review_decision")=="APPROVED")
    
    # Detect mock vs real
    try:
        from backend.core.llm import provider as _p
        is_mock = _p.is_mock()
    except:
        is_mock = True
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total": total,
        "task_completion": round(successes/total*100, 1) if total else 0,
        "test_pass_rate": round(tests_pass/total*100, 1) if total else 0,
        "approval_rate": round(approved/total*100, 1) if total else 0,
        "avg_latency_sec": round(avg_latency, 1),
        "mock_mode": is_mock,
        "results": results
    }
    
    OUTPUT.write_text(json.dumps(summary, indent=2))
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    
    # Print markdown table for README
    print("\n| Metric | Result |")
    print("|---|---|")
    print(f"| Task completion | {summary['task_completion']}% |")
    print(f"| Tests passing | {summary['test_pass_rate']}% |")
    print(f"| Approval rate | {summary['approval_rate']}% |")
    print(f"| Avg latency | {summary['avg_latency_sec']}s |")
    print(f"| Tasks evaluated | {total} |")

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv)>1 else 5
    asyncio.run(main(limit=n))
