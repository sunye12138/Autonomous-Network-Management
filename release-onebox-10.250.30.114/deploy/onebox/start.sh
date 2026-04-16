#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTAINER_NAME="${CONTAINER_NAME:-host-agent-onebox}"
IMAGE_NAME="${IMAGE_NAME:-host-agent-onebox:latest}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/onebox.env}"
HOST_DOCKER_BIN="${HOST_DOCKER_BIN:-}"
INNER_DOCKER_BIN="${INNER_DOCKER_BIN:-/usr/local/bin/docker}"
DOCKER_HOST_VALUE="${DOCKER_HOST:-}"
ARTIFACT_HOST_DIR="${ARTIFACT_HOST_DIR:-/mnt/dockerContainerSave/image}"
EXTRA_DOCKER_ARGS=()

if [[ -z "$HOST_DOCKER_BIN" ]]; then
  if command -v docker >/dev/null 2>&1; then
    HOST_DOCKER_BIN="$(command -v docker)"
  elif [[ -x /usr/bin/docker ]]; then
    HOST_DOCKER_BIN="/usr/bin/docker"
  elif [[ -x /usr/bin/docker.io ]]; then
    HOST_DOCKER_BIN="/usr/bin/docker.io"
  else
    echo "[FATAL] Cannot find host docker binary. Set HOST_DOCKER_BIN manually." >&2
    exit 1
  fi
fi

if [[ ! -x "$HOST_DOCKER_BIN" ]]; then
  echo "[FATAL] Host docker binary is not executable: $HOST_DOCKER_BIN" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FATAL] Missing env file: $ENV_FILE" >&2
  exit 1
fi

if ! docker version >/dev/null 2>&1; then
  echo "[FATAL] Current shell cannot talk to Docker daemon. Please verify docker access first." >&2
  exit 1
fi

if [[ -n "$DOCKER_HOST_VALUE" ]]; then
  echo "[INFO] Reusing DOCKER_HOST from current environment: $DOCKER_HOST_VALUE"
  if [[ "$DOCKER_HOST_VALUE" == unix://* ]]; then
    SOCK_PATH="${DOCKER_HOST_VALUE#unix://}"
    if [[ ! -S "$SOCK_PATH" ]]; then
      echo "[FATAL] DOCKER_HOST points to missing unix socket: $SOCK_PATH" >&2
      exit 1
    fi
    EXTRA_DOCKER_ARGS+=( -e "DOCKER_HOST=unix:///var/run/docker-host.sock" )
    EXTRA_DOCKER_ARGS+=( -v "$SOCK_PATH:/var/run/docker-host.sock" )
  else
    EXTRA_DOCKER_ARGS+=( -e "DOCKER_HOST=$DOCKER_HOST_VALUE" )
  fi
  [[ -n "${DOCKER_TLS_VERIFY:-}" ]] && EXTRA_DOCKER_ARGS+=( -e "DOCKER_TLS_VERIFY=${DOCKER_TLS_VERIFY}" )
  [[ -n "${DOCKER_CERT_PATH:-}" ]] && EXTRA_DOCKER_ARGS+=( -e "DOCKER_CERT_PATH=${DOCKER_CERT_PATH}" -v "${DOCKER_CERT_PATH}:${DOCKER_CERT_PATH}:ro" )
else
  if [[ ! -S /var/run/docker.sock ]]; then
    echo "[FATAL] /var/run/docker.sock not found. Either mount the host socket or export DOCKER_HOST before running start.sh." >&2
    exit 1
  fi
  EXTRA_DOCKER_ARGS+=( -v "/var/run/docker.sock:/var/run/docker.sock" )
fi

echo "[INFO] Project root: $PROJECT_ROOT"
echo "[INFO] Using host docker binary: $HOST_DOCKER_BIN"
echo "[INFO] Container name: $CONTAINER_NAME"
echo "[INFO] Image name: $IMAGE_NAME"
echo "[INFO] Env file: $ENV_FILE"

cd "$PROJECT_ROOT"
mkdir -p "$ARTIFACT_HOST_DIR"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker build --no-cache -t "$IMAGE_NAME" -f ./deploy/onebox/Dockerfile .

docker run -d   --name "$CONTAINER_NAME"   --restart unless-stopped   --env-file "$ENV_FILE"   -p 18000:8000   -p 14173:14173   -v onebox_data:/data   -v "$ARTIFACT_HOST_DIR:$ARTIFACT_HOST_DIR"   -v "$HOST_DOCKER_BIN:$INNER_DOCKER_BIN:ro"   "${EXTRA_DOCKER_ARGS[@]}"   "$IMAGE_NAME"

echo
echo "[INFO] Started $CONTAINER_NAME"
echo "[INFO] Frontend: http://10.250.30.114:14173/"
echo "[INFO] Health:   http://10.250.30.114:18000/api/health"
echo
docker ps --filter "name=$CONTAINER_NAME"
