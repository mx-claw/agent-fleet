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


def build_prompt(
    *,
    task_type: str,
    working_dir: str | Path,
    instruction: str = "",
    input_mode: str = "plain_task",
    github_issue: dict[str, object] | None = None,
) -> str:
    path = Path(working_dir)
    normalized_task_type = normalize_task_type(task_type)

    task_background_block = _build_task_background_block(
        input_mode=input_mode,
        instruction=instruction,
        github_issue=github_issue,
    )

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
        "working_dir": str(path),
        "task_type": normalized_task_type.value,
        "task_background_block": task_background_block,
        "git_repo_block": git_repo_block,
        "git_remote_block": git_remote_block,
        "pr_workflow_block": pr_workflow_block,
    }

    template_name = TASK_TYPE_TEMPLATES[normalized_task_type]
    rendered = _render_template_file(template_name, context)
    return _normalize_blank_lines(rendered)


def _build_task_background_block(
    *,
    input_mode: str,
    instruction: str,
    github_issue: dict[str, object] | None,
) -> str:
    mode = input_mode.strip().lower()

    if mode == "github_issue":
        issue = github_issue or {}
        url = str(issue.get("url", "")).strip()
        title = str(issue.get("title", "")).strip()
        body = str(issue.get("body", "")).strip()
        number = str(issue.get("number", "")).strip()

        lines = ["Input mode: github_issue"]
        if url:
            lines.append(f"Issue URL: {url}")
        if number:
            lines.append(f"Issue Number: {number}")
        if title:
            lines.append(f"Issue Title: {title}")
        if body:
            lines.append("Issue Body:")
            lines.append(body)

        lines.extend(
            [
                "Treat the issue details as the source of truth for requirements.",
                "If details are ambiguous, make the smallest safe implementation that still resolves the issue.",
            ]
        )
        return "\n".join(lines)

    if mode != "plain_task":
        raise ValueError(f"unsupported input_mode: {input_mode!r}")

    plain_instruction = instruction.strip()
    if not plain_instruction:
        raise ValueError("plain_task mode requires a non-empty instruction")

    return f"Input mode: plain_task\nTask request:\n{plain_instruction}"


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
