from pathlib import Path
from typing import List, Dict
import os

def create_github_pr(task_id: str, user_request: str, artifacts_dir: Path, repo_name: str = "") -> Dict:
    """
    Create GitHub PR draft after human approval. Requires GITHUB_TOKEN.
    For showcase without token, returns dry-run result.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return {
            "status": "dry_run",
            "message": "GITHUB_TOKEN not set - dry run. Artifacts ready at " + str(artifacts_dir),
            "branch": f"ai/task-{task_id[:8]}",
            "files": len(list(Path(artifacts_dir).rglob("*"))) if Path(artifacts_dir).exists() else 0
        }
    
    if not repo_name:
        return {"status": "skipped", "message": "repo_name not configured, skipping PR creation"}
    
    try:
        from github import Github
        g = Github(token)
        repo = g.get_repo(repo_name)
        branch = f"ai/task-{task_id[:8]}"
        # Get default branch
        default_branch = repo.default_branch
        base = repo.get_branch(default_branch)
        # Create branch
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base.commit.sha)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
        
        artifacts_dir = Path(artifacts_dir)
        for fp in artifacts_dir.rglob("*"):
            if fp.is_file():
                rel = fp.relative_to(artifacts_dir).as_posix()
                content = fp.read_text(encoding="utf-8", errors="ignore")
                try:
                    # Try update or create
                    try:
                        contents = repo.get_contents(rel, ref=branch)
                        repo.update_file(rel, f"AI update {rel} for {task_id[:8]}", content, contents.sha, branch=branch)
                    except:
                        repo.create_file(rel, f"AI add {rel} for {task_id[:8]}", content, branch=branch)
                except Exception as fe:
                    print(f"file {rel} failed: {fe}")
        
        pr = repo.create_pull(
            title=f"AI: {user_request[:60]}",
            body=f"Automated by Autonomous AI Engineer\nTask: {task_id}\nRequest: {user_request}\nArtifacts: {artifacts_dir}",
            head=branch,
            base=default_branch,
            draft=True
        )
        return {"status": "created", "pr_url": pr.html_url, "branch": branch}
    except Exception as e:
        return {"status": "error", "message": str(e)}
