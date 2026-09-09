from pathlib import Path
from typing import List, Dict

def write_artifacts(base_dir: Path, files: List[Dict]) -> List[str]:
    """Write generated files to disk. Returns list of paths."""
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    base_resolved = base_dir.resolve()
    artifacts = []
    # Quota: prevent LLM from filling disk over 15 tasks
    MAX_FILES = 50
    MAX_CONTENT = 200_000  # 200KB per file
    MAX_TOTAL = 2_000_000  # 2MB total
    total_bytes = 0
    for f in files[:MAX_FILES]:
        path = f.get("path", "")
        content = f.get("content", "")
        if not path:
            continue
        if len(content) > MAX_CONTENT:
            content = content[:MAX_CONTENT] + "\n# [truncated]"
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL:
            break
        # Security: prevent traversal - block .. and absolute + symlink
        if ".." in Path(path).parts or Path(path).is_absolute():
            continue
        # Allowlist extensions - include tabular
        allowed = {".py", ".txt", ".md", ".json", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".csv", ".tsv", ""}
        if Path(path).suffix.lower() not in allowed and "." in Path(path).name:
            if Path(path).suffix.lower() not in {".py",".txt",".md",".json",".csv",".tsv"}:
                continue
        target = (base_dir / path).resolve()
        try:
            # Check is inside base_resolved
            target.relative_to(base_resolved)
        except ValueError:
            # Fallback check via commonpath for Windows edge cases
            try:
                import os
                if os.path.commonpath([str(target), str(base_resolved)]) != str(base_resolved):
                    continue
            except:
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8")
            try:
                rel = target.relative_to(base_resolved).as_posix()
            except:
                rel = Path(path).as_posix()
            artifacts.append(rel)
        except Exception as e:
            print(f"write failed {path}: {e}")
    return artifacts

def read_artifact(base_dir: Path, rel_path: str) -> str:
    # Secure read with traversal check
    base_resolved = Path(base_dir).resolve()
    target = (Path(base_dir) / rel_path).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        return ""
    if target.exists() and not target.is_symlink():
        return target.read_text(encoding="utf-8")
    return ""
