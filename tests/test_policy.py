import subprocess

import pytest

from agent_fleet.prompts.policy import build_prompt


def test_feature_implementation_prompt_includes_git_commit_push_and_pr_policy(tmp_path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:example/project.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    prompt = build_prompt(
        task_type="feature_implementation",
        instruction="Implement the feature.",
        input_mode="plain_task",
        working_dir=tmp_path,
    )

    assert "autonomous implementation agent" in prompt
    assert "Input mode: plain_task" in prompt
    assert "Task request" in prompt
    assert "create a commit" in prompt
    assert "Push your branch" in prompt
    assert "Create a pull request/merge request" in prompt


def test_feature_implementation_prompt_omits_git_policy_for_non_repo(tmp_path) -> None:
    prompt = build_prompt(
        task_type="feature_implementation",
        instruction="Implement the feature.",
        input_mode="plain_task",
        working_dir=tmp_path,
    )

    assert "Input mode: plain_task" in prompt
    assert "Task request" in prompt
    assert "create a commit" not in prompt
    assert "Push your branch" not in prompt


def test_feature_implementation_prompt_supports_github_issue_input(tmp_path) -> None:
    prompt = build_prompt(
        task_type="feature_implementation",
        instruction="",
        input_mode="github_issue",
        github_issue={
            "url": "https://github.com/acme/repo/issues/42",
            "number": 42,
            "title": "Add idempotency to webhook processing",
            "body": "Duplicate deliveries create duplicate records.",
        },
        working_dir=tmp_path,
    )

    assert "Input mode: github_issue" in prompt
    assert "Issue URL: https://github.com/acme/repo/issues/42" in prompt
    assert "Issue Number: 42" in prompt
    assert "Issue Title: Add idempotency to webhook processing" in prompt
    assert "Duplicate deliveries create duplicate records." in prompt


def test_plain_task_mode_requires_instruction(tmp_path) -> None:
    with pytest.raises(ValueError):
        build_prompt(
            task_type="feature_implementation",
            instruction="",
            input_mode="plain_task",
            working_dir=tmp_path,
        )


def test_unknown_task_type_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        build_prompt(
            task_type="unknown",
            instruction="x",
            input_mode="plain_task",
            working_dir=tmp_path,
        )


def test_unknown_input_mode_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        build_prompt(
            task_type="feature_implementation",
            instruction="x",
            input_mode="wat",
            working_dir=tmp_path,
        )
