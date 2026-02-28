from __future__ import annotations

import subprocess
from pathlib import Path


def build_prompt(instruction: str, *, working_dir: str | Path) -> str:
    path = Path(working_dir)
    policy_lines = [
        "Mandatory policy:",
        "- Complete the requested work in the provided working directory.",
    ]

    if _is_git_repo(path):
        policy_lines.append("- Before finishing, commit all changes in the repository.")
        if _has_remote(path):
            policy_lines.append("- Push the commit to the configured remote.")
            if _suggests_pull_request_workflow(path):
                policy_lines.append("- If the remote workflow supports it, create a pull request for the change.")

    policy_block = "\n".join(policy_lines)
    return f"{policy_block}\n\nTask instruction:\n{instruction.strip()}\n"


def _is_git_repo(working_dir: Path) -> bool:
    return _run_git(working_dir, "rev-parse", "--is-inside-work-tree") == "true"


def _has_remote(working_dir: Path) -> bool:
    remotes = _run_git(working_dir, "remote")
    return bool(remotes)


def _suggests_pull_request_workflow(working_dir: Path) -> bool:
    remote_url = _run_git(working_dir, "remote", "get-url", "origin")
    return "github.com" in remote_url or "gitlab.com" in remote_url


def _run_git(working_dir: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=working_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()

