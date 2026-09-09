from tools.python_exec import run_tests
from pathlib import Path
import tempfile

def test_run_tests_no_dir():
    out, passed = run_tests(Path("/nonexistent"))
    assert "No artifacts" in out or passed is False

def test_run_tests_empty():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "dummy.txt").write_text("hello")
        out, passed = run_tests(Path(tmp))
        assert passed is True  # no tests -> skip
