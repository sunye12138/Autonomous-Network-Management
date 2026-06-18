#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-host-agent-onebox}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/onebox.env}"
HOST_ADDRESS="${HOST_ADDRESS:-127.0.0.1}"
HEALTH_PORT="${HEALTH_PORT:-18000}"

if [[ -f "$ENV_FILE" ]]; then
  env_host="$(grep -E '^HOST_ADDRESS=' "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r' || true)"
  [[ -n "$env_host" ]] && HOST_ADDRESS="$env_host"
fi

echo "=== docker ps ==="
docker ps -a --filter "name=$CONTAINER_NAME"

echo
echo "=== health ==="
if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS "http://${HOST_ADDRESS}:${HEALTH_PORT}/api/health"; then
    echo
    echo "[WARN] Health check via ${HOST_ADDRESS}:${HEALTH_PORT} failed, trying 127.0.0.1:${HEALTH_PORT}"
    curl -fsS "http://127.0.0.1:${HEALTH_PORT}/api/health" || true
  fi
else
  echo "curl not installed on host"
fi

echo
echo "=== logs (tail 80) ==="
docker logs --tail 80 "$CONTAINER_NAME" 2>/dev/null || true
