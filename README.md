# agent-fleet

Open-source Python orchestrator for running a fleet of background coding agents (starting with Codex) against queued tasks.

## Goals

- Clean separation of concerns (queue, orchestration, agent adapters, persistence, CLI)
- Start/stop lifecycle for a long-running orchestrator
- Docker-first runtime with Codex auth/settings passed from host environment
- FIFO task queue now, extensible to priority scheduling later
- Strong execution observability: persist streamed JSON events from Codex runs

## Status

This repository is a ground-up rewrite of earlier GitHub workflow automation experiments.

## Architecture

Current layers:

- `agent_fleet/config.py`: application configuration model for local paths and runtime settings
- `agent_fleet/domain/models.py`: shared domain types for tasks, executions, events, and task status values
- `agent_fleet/persistence/schema.py`: SQLite schema creation for `tasks`, `executions`, and `execution_events`
- `agent_fleet/persistence/repository.py`: repository layer for task enqueue/dequeue, execution lifecycle updates, history queries, and event persistence
- `agent_fleet/queue/fifo.py`: FIFO queue API built on the repository layer
- `agent_fleet/prompts/policy.py`: prompt policy builder that injects git commit/push/PR instructions when applicable
- `agent_fleet/agents/codex_runner.py`: Codex adapter that launches `codex --output-format stream-json` and persists streamed events
- `agent_fleet/orchestrator/service.py`: foreground orchestrator loop with graceful stop handling
- `agent_fleet/cli.py`: Click/Rich CLI for queue submission, lifecycle control, status, and history inspection

## Implemented Scope

This step now covers the main orchestrator lifecycle:

- package structure for queue, persistence, domain, config, prompts, agent adapters, orchestrator, and CLI concerns
- SQLite persistence using the standard library `sqlite3` module
- FIFO queue semantics for enqueuing and dequeuing queued tasks
- a foreground orchestrator loop with graceful stop via `threading.Event`
- background lifecycle commands using a runtime directory and pid file
- Codex execution tracking with persisted event replay data
- focused tests for schema initialization, FIFO ordering, policy composition, event parsing/storage, and pid-file behavior

## Legacy Review (from previous workflow scripts)

Key issues identified in legacy implementation:

1. Hard-coded absolute paths to one machine/workspace
2. Business logic coupled to GitHub event handling and subprocess dispatch
3. Weak lifecycle controls (no robust daemon start/stop semantics)
4. Limited observability (flat logs, little structured event persistence)
5. Queue and job types mixed with execution concerns

This rewrite addresses these with a modular Python architecture.

## CLI

Submit a task:

```bash
agent-fleet enqueue --working-dir /path/to/repo "Update the failing tests and open a PR"
```

Run the orchestrator in the foreground:

```bash
agent-fleet run
```

Start or stop the background orchestrator:

```bash
agent-fleet start
agent-fleet stop
```

Inspect runtime state and task history:

```bash
agent-fleet status
agent-fleet history <task-id>
```

## Lifecycle

- Tasks are stored as JSON payloads containing `working_dir` and `instruction`.
- The orchestrator polls the FIFO queue, marks one task `running`, creates an execution record, and dispatches Codex.
- `start` launches a detached background process and waits for a pid file in the configured runtime directory.
- `stop` sends `SIGTERM`, allowing the foreground loop to exit cleanly and remove its pid file.

## Observability

- `executions` records include `process_id`, `exit_code`, timestamps, and status transitions.
- `execution_events` records include a per-execution `sequence_number`, `source` (`stdout`, `stderr`, `json`, or `system`), normalized `event_type`, and stored payload.
- `agent-fleet history <task-id>` replays the stored execution history directly from SQLite.
