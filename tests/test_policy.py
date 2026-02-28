import subprocess

from agent_fleet.prompts.policy import build_prompt


def test_build_prompt_includes_git_commit_push_and_pr_policy(tmp_path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:example/project.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    prompt = build_prompt("Implement the feature.", working_dir=tmp_path)

    assert "Complete the requested work" in prompt
    assert "create a commit" in prompt
    assert "Push your branch" in prompt
    assert "create one with a concise summary" in prompt


def test_build_prompt_omits_git_policy_for_non_repo(tmp_path) -> None:
    prompt = build_prompt("Implement the feature.", working_dir=tmp_path)

    assert "create a commit" not in prompt
    assert "Push your branch" not in prompt
