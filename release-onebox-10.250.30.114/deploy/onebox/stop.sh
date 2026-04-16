#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-host-agent-onebox}"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
echo "[INFO] Stopped and removed $CONTAINER_NAME"
