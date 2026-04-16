#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTAINER_NAME="${CONTAINER_NAME:-host-agent-onebox}"
IMAGE_NAME="${IMAGE_NAME:-host-agent-onebox:latest}"
REMOVE_IMAGE="${REMOVE_IMAGE:-1}"
REMOVE_DATA_VOLUME="${REMOVE_DATA_VOLUME:-0}"
DATA_VOLUME_NAME="${DATA_VOLUME_NAME:-onebox_data}"

cd "$PROJECT_ROOT"

echo "[INFO] Rebuilding onebox..."
echo "[INFO] Project root: $PROJECT_ROOT"
echo "[INFO] Container name: $CONTAINER_NAME"
echo "[INFO] Image name: $IMAGE_NAME"

echo "[STEP] Stop old container"
./deploy/onebox/stop.sh || true

if [[ "$REMOVE_IMAGE" == "1" ]]; then
  echo "[STEP] Remove old image $IMAGE_NAME"
  docker rmi "$IMAGE_NAME" >/dev/null 2>&1 || true
fi

if [[ "$REMOVE_DATA_VOLUME" == "1" ]]; then
  echo "[STEP] Remove data volume $DATA_VOLUME_NAME"
  docker volume rm "$DATA_VOLUME_NAME" >/dev/null 2>&1 || true
fi

echo "[STEP] Start new container"
./deploy/onebox/start.sh
