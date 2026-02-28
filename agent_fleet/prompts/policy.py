from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess
from pathlib import Path

from .task_types import TaskType, normalize_task_type

_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_TEMPLATE_ROOT = Path(__file__).parent / "templates"


@dataclass(frozen=True, slots=True)
class PromptTemplateSet:
    base_templates: tuple[str, ...]
    git_repo_templates: tuple[str, ...] = ()
    git_remote_templates: tuple[str, ...] = ()
    pr_workflow_templates: tuple[str, ...] = ()


PROMPT_TEMPLATE_SETS: dict[TaskType, PromptTemplateSet] = {
    TaskType.FEATURE_IMPLEMENTATION: PromptTemplateSet(
        base_templates=(
            "feature_implementation/system.md",
            "feature_implementation/task.md",
        ),
        git_repo_templates=("feature_implementation/git_repo.md",),
        git_remote_templates=("feature_implementation/git_remote.md",),
        pr_workflow_templates=("feature_implementation/pr_workflow.md",),
    ),
}


def build_prompt(*, task_type: str, instruction: str, working_dir: str | Path) -> str:
    path = Path(working_dir)
    normalized_task_type = normalize_task_type(task_type)
    template_set = PROMPT_TEMPLATE_SETS[normalized_task_type]

    context = {
        "instruction": instruction.strip(),
        "working_dir": str(path),
        "task_type": normalized_task_type.value,
    }

    parts = [_render_template_file(template, context) for template in template_set.base_templates]

    if _is_git_repo(path):
        parts.extend(_render_template_file(template, context) for template in template_set.git_repo_templates)
        if _has_remote(path):
            parts.extend(_render_template_file(template, context) for template in template_set.git_remote_templates)
            if _suggests_pull_request_workflow(path):
                parts.extend(
                    _render_template_file(template, context)
                    for template in template_set.pr_workflow_templates
                )

    return "\n\n".join(part.strip() for part in parts if part.strip()) + "\n"


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
