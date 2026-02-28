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

## Legacy Review (from previous workflow scripts)

Key issues identified in legacy implementation:

1. Hard-coded absolute paths to one machine/workspace
2. Business logic coupled to GitHub event handling and subprocess dispatch
3. Weak lifecycle controls (no robust daemon start/stop semantics)
4. Limited observability (flat logs, little structured event persistence)
5. Queue and job types mixed with execution concerns

This rewrite addresses these with a modular Python architecture.
