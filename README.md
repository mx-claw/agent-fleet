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

Persistence now uses **SQLModel ORM** for typed entities and session-based data access.

## Architecture

Current layers:

- `agent_fleet/config.py`: application configuration model for runtime paths
- `agent_fleet/domain/models.py`: SQLModel ORM entities (`Task`, `Execution`, `ExecutionEvent`) + `TaskStatus` enum
- `agent_fleet/persistence/schema.py`: SQLModel metadata bootstrap + SQLite migration/backfill helpers
- `agent_fleet/persistence/repository.py`: SQLModel session-based repository (no manual row mapping)
- `agent_fleet/queue/fifo.py`: FIFO queue API built on the repository layer
- `agent_fleet/prompts/policy.py`: prompt assembler that loads one reviewable Markdown template per task type
- `agent_fleet/prompts/templates/`: task-type prompt files (for example `feature_implementation.md`)
- `agent_fleet/agents/codex_runner.py`: Codex adapter (`codex exec --json`) with streamed event persistence
- `agent_fleet/orchestrator/service.py`: orchestrator worker loop with graceful stop
- `agent_fleet/cli.py`: Click + Rich lifecycle and queue commands

## CLI

Queue a task:

```bash
agent-fleet enqueue --working-dir /path/to/repo --task-type feature_implementation --instruction "Update failing tests and open a PR"
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

Prompts are loaded from single-file Markdown templates under `agent_fleet/prompts/templates/` and selected by `task_type` (for example `feature_implementation.md`).

Current task types:
- `feature_implementation`

For `feature_implementation`, when the target `working_dir` is a git repository, the assembled prompt enforces:

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
