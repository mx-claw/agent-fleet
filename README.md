# agent-fleet

Open-source Python orchestrator for running a fleet of background coding agents (starting with Codex) against queued tasks.

## Goals

- Clean separation of concerns (queue, orchestration, agent adapters, persistence, CLI)
- Start/stop lifecycle for a long-running orchestrator
- Docker-first runtime with Codex auth/settings passed from host environment
- FIFO task queue now, extensible to priority scheduling later
- Strong execution observability: persist streamed JSON events from Codex runs

## Status

This repository is the clean rewrite of earlier GitHub workflow automation experiments.

## Architecture

Current layers:

- `agent_fleet/config.py`: application configuration model for runtime paths
- `agent_fleet/domain/models.py`: shared domain types for tasks, executions, and execution events
- `agent_fleet/persistence/schema.py`: SQLite schema + migration-safe column backfills
- `agent_fleet/persistence/repository.py`: queue persistence, lifecycle updates, event storage, history queries
- `agent_fleet/queue/fifo.py`: FIFO queue API built on the repository layer
- `agent_fleet/prompts/policy.py`: prompt policy builder (commit/push/PR behavior in git repos)
- `agent_fleet/agents/codex_runner.py`: Codex adapter (`codex exec --json`) with streamed event persistence
- `agent_fleet/orchestrator/service.py`: orchestrator worker loop with graceful stop
- `agent_fleet/cli.py`: Click + Rich lifecycle and queue commands

## CLI

Queue a task:

```bash
agent-fleet enqueue --working-dir /path/to/repo --instruction "Update failing tests and open a PR"
```

Run orchestrator in foreground:

```bash
agent-fleet run
```

Start/stop background orchestrator:

```bash
agent-fleet start
agent-fleet stop
```

Inspect queue/runtime:

```bash
agent-fleet status
agent-fleet events --task-id <task-id> --tail 100
```

## Prompt Policy Behavior

When the target `working_dir` is a git repository, the generated task prompt enforces:

1. commit all relevant changes
2. push to remote when configured/possible
3. create a PR/MR when the remote workflow supports it

## Observability & Database

- `tasks`: queue item + lifecycle state
- `executions`: process tracking (`process_id`, `exit_code`, status, timestamps)
- `execution_events`: replayable stream (`sequence_number`, `source`, `event_type`, `payload`)

Event `source` values:
- `json`: parsed JSON line from Codex stream
- `stdout`: non-JSON stdout line
- `stderr`: non-JSON stderr line
- `system`: orchestrator-generated internal events/errors

## Docker Runtime

### Build

```bash
docker build -t agent-fleet:dev .
```

### Run (foreground orchestrator)

```bash
docker run --rm \
  -e OPENAI_API_KEY \
  -e CODEX_API_KEY \
  -e AGENT_FLEET_DATABASE=/data/agent_fleet.db \
  -e AGENT_FLEET_RUNTIME_DIR=/data/runtime \
  -v "$PWD/data:/data" \
  -v "$PWD:/workspace" \
  -v "$HOME/.codex:/home/agent/.codex" \
  -v "$HOME/.ssh:/home/agent/.ssh:ro" \
  -v "$HOME/.gitconfig:/home/agent/.gitconfig:ro" \
  agent-fleet:dev run
```

Notes:
- Codex auth/settings are expected from host (`~/.codex` mount + env vars).
- Mount repositories under `/workspace` and enqueue tasks with those paths.

## Legacy Archival

See `docs/legacy-archive.md` for the archived design context and migration notes from prior workflow scripts.
