#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${AGENT_FLEET_DATABASE:-/data/agent_fleet.db}"
RUNTIME_DIR="${AGENT_FLEET_RUNTIME_DIR:-/data/runtime}"

mkdir -p "$(dirname "$DB_PATH")" "$RUNTIME_DIR"

exec agent-fleet --database "$DB_PATH" --runtime-dir "$RUNTIME_DIR" "$@"
