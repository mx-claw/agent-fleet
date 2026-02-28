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
        working_dir=tmp_path,
    )

    assert "autonomous implementation agent" in prompt
    assert "Feature request" in prompt
    assert "create a commit" in prompt
    assert "Push your branch" in prompt
    assert "Create a pull request/merge request" in prompt


def test_feature_implementation_prompt_omits_git_policy_for_non_repo(tmp_path) -> None:
    prompt = build_prompt(
        task_type="feature_implementation",
        instruction="Implement the feature.",
        working_dir=tmp_path,
    )

    assert "Feature request" in prompt
    assert "create a commit" not in prompt
    assert "Push your branch" not in prompt


def test_unknown_task_type_raises(tmp_path) -> None:
    with pytest.raises(ValueError):
        build_prompt(task_type="unknown", instruction="x", working_dir=tmp_path)
