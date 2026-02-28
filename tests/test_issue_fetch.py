from __future__ import annotations

import json
import subprocess

import click
import pytest

from agent_fleet.cli import _fetch_github_issue


def test_fetch_github_issue_success(monkeypatch) -> None:
    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args[0],
            returncode=0,
            stdout=json.dumps(
                {
                    "number": 42,
                    "title": "Add idempotency",
                    "body": "Duplicate deliveries create duplicate records",
                    "url": "https://github.com/acme/repo/issues/42",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("agent_fleet.cli.subprocess.run", fake_run)

    issue = _fetch_github_issue(repo="acme/repo", issue_number=42)

    assert issue["number"] == 42
    assert issue["title"] == "Add idempotency"
    assert issue["url"] == "https://github.com/acme/repo/issues/42"


def test_fetch_github_issue_failure(monkeypatch) -> None:
    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args[0],
            returncode=1,
            stdout="",
            stderr="not found",
        )

    monkeypatch.setattr("agent_fleet.cli.subprocess.run", fake_run)

    with pytest.raises(click.ClickException):
        _fetch_github_issue(repo="acme/repo", issue_number=999)
