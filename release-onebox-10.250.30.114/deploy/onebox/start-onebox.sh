#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-14173}"
DATA_DIR="${DATA_DIR:-/data}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$DATA_DIR/artifacts}"
AGENT_ID="${AGENT_ID:-onebox-agent-10-250-30-114}"
AGENT_NAME="${AGENT_NAME:-$AGENT_ID}"
HOST_ADDRESS="${HOST_ADDRESS:-$(hostname)}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${BACKEND_PORT}/api}"
LOG_DIR="/app/runtime-logs"

mkdir -p "$DATA_DIR" "$ARTIFACT_DIR" "$LOG_DIR"

echo "[INFO] Starting onebox container"
echo "[INFO] Backend will listen on 0.0.0.0:${BACKEND_PORT}"
echo "[INFO] Frontend will listen on 0.0.0.0:${FRONTEND_PORT}"
echo "[INFO] Agent will connect to ${API_BASE_URL}"
echo "[INFO] Host address reported by agent: ${HOST_ADDRESS}"

echo "[INFO] docker binary: $(command -v docker || echo missing)"
if ! command -v docker >/dev/null 2>&1; then
  echo "[FATAL] docker command not found inside onebox container" >&2
  exit 1
fi

echo "[INFO] DOCKER_HOST=${DOCKER_HOST:-<default>}"
docker --version || true
if ! docker version >/dev/null 2>&1; then
  echo "[FATAL] docker client inside onebox cannot talk to Docker daemon" >&2
  exit 1
fi

python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" >"$LOG_DIR/backend.out.log" 2>"$LOG_DIR/backend.err.log" &
BACKEND_PID=$!

python -m http.server "$FRONTEND_PORT" --bind 0.0.0.0 --directory /app/frontend >"$LOG_DIR/frontend.out.log" 2>"$LOG_DIR/frontend.err.log" &
FRONTEND_PID=$!

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

export API_BASE_URL
export AGENT_ID
export AGENT_NAME
export HOST_ADDRESS
export DATA_DIR
export ARTIFACT_DIR
python /app/backend/host_agent.py >"$LOG_DIR/agent.out.log" 2>"$LOG_DIR/agent.err.log" &
AGENT_PID=$!

term_handler() {
  echo "[INFO] Shutting down onebox container"
  kill "$AGENT_PID" "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  wait "$AGENT_PID" "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
}

trap term_handler TERM INT

wait -n "$BACKEND_PID" "$FRONTEND_PID" "$AGENT_PID"
EXIT_CODE=$?
term_handler
exit "$EXIT_CODE"
