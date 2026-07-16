#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

config_path() {
  PIXIE_ROOT="$REPO_ROOT" "$PYTHON_BIN" -c 'from pixie_env import config_path; import sys; print(config_path(sys.argv[1]))' "$1"
}

REMOTE_ROOT="${REMOTE_ROOT:-$REPO_ROOT}"
PIXIE_DATA_ROOT="${PIXIE_DATA_ROOT:-$(config_path data_root)}"
HF_HOME="${HF_HOME:-$(config_path hf_home)}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
PIXIE_MODEL_CACHE_DIR="${PIXIE_MODEL_CACHE_DIR:-$(config_path model_cache_dir)}"

LOCK_DIR="$PIXIE_DATA_ROOT/locks"
LOG_DIR="$PIXIE_DATA_ROOT/pixie_research"
LOCK_FILE="$LOCK_DIR/reflective_buddy_distill.lock"
RUN_LOG="$LOG_DIR/reflective_buddy_distill_runner.log"

mkdir -p "$LOCK_DIR" "$LOG_DIR" "$HF_HOME" "$HUGGINGFACE_HUB_CACHE"

{
  printf '[%s] start\n' "$(date --iso-8601=seconds)"
  /usr/bin/timeout 2h /usr/bin/flock -n "$LOCK_FILE" \
    "$PYTHON_BIN" "$REMOTE_ROOT/generate_reflective_buddy_distill.py" \
      --data-root "$PIXIE_DATA_ROOT" \
      --chat-template chatml \
      --examples-per-scenario 1 \
      --max-tokens 96 \
      --max-attempts 3 \
      --temperature 0.1 \
      --request-timeout-sec 420 \
      --health-timeout-sec 300 \
      --port 8091 \
      --n-gpu-layers 32
  status=$?
  printf '[%s] exit=%s\n' "$(date --iso-8601=seconds)" "$status"
  exit "$status"
} >>"$RUN_LOG" 2>&1
