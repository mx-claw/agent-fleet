from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .task_types import TaskType, normalize_task_type

_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_TEMPLATE_ROOT = Path(__file__).parent / "templates"

TASK_TYPE_TEMPLATES: dict[TaskType, str] = {
    TaskType.FEATURE_IMPLEMENTATION: "feature_implementation.md",
}


def build_prompt(*, task_type: str, instruction: str, working_dir: str | Path) -> str:
    path = Path(working_dir)
    normalized_task_type = normalize_task_type(task_type)

    git_repo_block = ""
    git_remote_block = ""
    pr_workflow_block = ""

    if _is_git_repo(path):
        git_repo_block = (
            "This working directory is a git repository.\n"
            "- Stage all relevant changes and create a commit before finishing\n"
            "- Use a concise commit message that describes what changed"
        )
        if _has_remote(path):
            git_remote_block = (
                "A git remote is configured.\n"
                "- Push your branch to the configured remote when push permissions are available"
            )
            if _suggests_pull_request_workflow(path):
                pr_workflow_block = (
                    "Remote workflow supports PR/MR collaboration.\n"
                    "- Create a pull request/merge request with a short summary of what was implemented"
                )

    context = {
        "instruction": instruction.strip(),
        "working_dir": str(path),
        "task_type": normalized_task_type.value,
        "git_repo_block": git_repo_block,
        "git_remote_block": git_remote_block,
        "pr_workflow_block": pr_workflow_block,
    }

    template_name = TASK_TYPE_TEMPLATES[normalized_task_type]
    rendered = _render_template_file(template_name, context)
    return _normalize_blank_lines(rendered)


def _render_template_file(relative_path: str, context: dict[str, str]) -> str:
    template_path = _TEMPLATE_ROOT / relative_path
    template = template_path.read_text(encoding="utf-8")
    return _render_template(template, context)


def _render_template(template: str, context: dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise ValueError(f"missing template variable: {key}")
        return context[key]

    return _TEMPLATE_PATTERN.sub(_replace, template)


def _normalize_blank_lines(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                out.append("")
        else:
            blank_count = 0
            out.append(line.rstrip())
    return "\n".join(out).strip() + "\n"


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
