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
- `agent_fleet/persistence/repository.py`: repository layer for task enqueue/dequeue, execution creation, and event persistence
- `agent_fleet/queue/fifo.py`: FIFO queue API built on the repository layer
- `agent_fleet/cli.py`: minimal Click/Rich placeholder command for wiring the package entrypoint

## Implemented Scope

This step intentionally covers only the foundation layers:

- package structure for queue, persistence, domain, config, and CLI concerns
- SQLite persistence using the standard library `sqlite3` module
- FIFO queue semantics for enqueuing and dequeuing queued tasks
- focused tests for schema initialization and dequeue ordering

Not implemented yet:

- orchestrator worker loop
- agent process execution
- lifecycle management for long-running workers
- advanced scheduling beyond FIFO

## Legacy Review (from previous workflow scripts)

Key issues identified in legacy implementation:

1. Hard-coded absolute paths to one machine/workspace
2. Business logic coupled to GitHub event handling and subprocess dispatch
3. Weak lifecycle controls (no robust daemon start/stop semantics)
4. Limited observability (flat logs, little structured event persistence)
5. Queue and job types mixed with execution concerns

This rewrite addresses these with a modular Python architecture.
