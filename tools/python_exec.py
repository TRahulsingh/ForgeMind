import subprocess
import sys
from pathlib import Path

def run_tests(project_dir: Path, timeout: int = 30):
    """
    Run pytest in project dir. Returns (output_str, passed_bool).
    Low-spec friendly: timeout 30s, no parallel.
    """
    project_dir = Path(project_dir)
    if not project_dir.exists():
        return "No artifacts directory", False
    
    # Check if tests exist
    has_tests = any(project_dir.rglob("test_*.py")) or any(project_dir.rglob("*test.py"))
    has_requirements = (project_dir / "requirements.txt").exists() or (project_dir / "app").exists()
    
    if not has_tests and not has_requirements:
        return "No tests found - skipping", True
    
    # Try pip install requirements if present (best effort, skip if already satisfied)
    # Skipped for low-spec mock to avoid network delay - uncomment if real deps needed
    # req = project_dir / "requirements.txt"
    # if req.exists():
    #     try:
    #         subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)], capture_output=True, timeout=8)
    #     except:
    #         pass
    # Try to run pytest if available, else simple syntax check
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + "\n" + result.stderr
        passed = result.returncode == 0
        if not output.strip():
            output = "Tests completed" if passed else "Tests failed with no output"
        return output[:4000], passed
    except subprocess.TimeoutExpired:
        return "Tests timed out after 30s", False
    except FileNotFoundError:
        # Fallback: syntax check
        try:
            py_files = list(project_dir.rglob("*.py"))
            for pf in py_files[:10]:
                subprocess.run([sys.executable, "-m", "py_compile", str(pf)], check=True, capture_output=True)
            return "Syntax check passed (pytest not available)", True
        except subprocess.CalledProcessError as e:
            return f"Syntax error: {e}", False
    except Exception as e:
        return f"Test execution error: {e}", False
