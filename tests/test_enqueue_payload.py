from pathlib import Path

import click
import pytest

from agent_fleet.cli import _build_enqueue_payload


def test_build_enqueue_payload_plain_task() -> None:
    payload = _build_enqueue_payload(
        working_dir=Path("/tmp/repo"),
        instruction="Implement x",
        github_issue_url=None,
        github_issue_title=None,
        github_issue_body=None,
        github_issue_number=None,
        task_type="feature_implementation",
    )

    assert payload["input_mode"] == "plain_task"
    assert payload["instruction"] == "Implement x"
    assert payload["github_issue"] is None


def test_build_enqueue_payload_github_issue() -> None:
    payload = _build_enqueue_payload(
        working_dir=Path("/tmp/repo"),
        instruction=None,
        github_issue_url="https://github.com/acme/repo/issues/7",
        github_issue_title="Fix race condition",
        github_issue_body="Lock around queue consumer",
        github_issue_number=7,
        task_type="feature_implementation",
    )

    assert payload["input_mode"] == "github_issue"
    assert payload["instruction"] == ""
    issue = payload["github_issue"]
    assert isinstance(issue, dict)
    assert issue["url"] == "https://github.com/acme/repo/issues/7"


def test_build_enqueue_payload_rejects_mixed_modes() -> None:
    with pytest.raises(click.ClickException):
        _build_enqueue_payload(
            working_dir=Path("/tmp/repo"),
            instruction="Do x",
            github_issue_url="https://github.com/acme/repo/issues/7",
            github_issue_title="Fix race condition",
            github_issue_body=None,
            github_issue_number=7,
            task_type="feature_implementation",
        )
