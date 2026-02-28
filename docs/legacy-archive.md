# Legacy Workflow Archive

This repository intentionally starts fresh and does **not** carry over the old queue/webhook scripts as runtime code.

## What is archived

The previous generation centered on ad-hoc workflow scripts in local OpenClaw workspace paths (for example `.clawdbot/*` and `skills/agent-swarm/*`).

## Why it was replaced

Main design issues in the old setup:

1. hard-coded machine paths and environment assumptions
2. mixed concerns (webhooks, queue, execution, and policies tightly coupled)
3. weak lifecycle semantics for long-running processes
4. observability spread over loose logs rather than replayable structured events
5. difficult extension path for scheduling strategy evolution (FIFO -> priority)

## Rewrite principles in `agent-fleet`

- strict separation of concerns
- transport-agnostic queue and execution core
- Docker-first runtime
- durable execution event stream in SQLite
- explicit agent policy composition

## Migration approach

- Archive old scripts where they currently live (do not mutate production scripts in-place).
- Recreate behavior incrementally in this repository.
- Keep old system read-only during migration window.
- Switch orchestration to `agent-fleet` once task parity is validated.
