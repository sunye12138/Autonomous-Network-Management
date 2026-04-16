#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-host-agent-onebox}"

echo "=== docker ps ==="
docker ps -a --filter "name=$CONTAINER_NAME"

echo
echo "=== health ==="
if command -v curl >/dev/null 2>&1; then
  curl -fsS http://127.0.0.1:18000/api/health || true
else
  echo "curl not installed on host"
fi

echo
echo "=== logs (tail 80) ==="
docker logs --tail 80 "$CONTAINER_NAME" 2>/dev/null || true
