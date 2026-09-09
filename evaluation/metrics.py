import json
from pathlib import Path

def load_results(path="evaluation/results.json"):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())

def print_report(path="evaluation/results.json"):
    data = load_results(path)
    if not data:
        print("No results yet. Run: python -m evaluation.evaluator 5")
        return
    print(f"Evaluated: {data['total']} tasks at {data['timestamp']}")
    print(f"Task completion: {data['task_completion']}%")
    print(f"Test pass: {data['test_pass_rate']}%")
    print(f"Avg latency: {data['avg_latency_sec']}s")

if __name__ == "__main__":
    print_report()
