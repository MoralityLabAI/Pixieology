#!/usr/bin/env bash

# Portable one-pod runner for the frozen Fae Tax on Epistemics study.
# It is resumable at episode granularity. The smoke is always three samples;
# the full run selects three samples or the declared two-sample cost fallback.

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:?PROJECT_DIR must name the staged Pixieology source directory}"
ALIFE_ROOT="${ALIFE_ROOT:?ALIFE_ROOT must name the frozen ALife checkout}"
RUN_BASE="${RUN_BASE:?RUN_BASE must name the retained study directory}"
POD_HOURLY_USD="${POD_HOURLY_USD:?POD_HOURLY_USD must be the actual provider price}"
PROVIDER="${PROVIDER:-prime_intellect}"
POD_STARTED_EPOCH="${POD_STARTED_EPOCH:-$(date +%s)}"
REQUESTED_SAMPLES="${SAMPLES:-auto}"
RESULTS_ROOT="${RUN_BASE}/results"
VENV="${RUN_BASE}/venv"
HF_HOME="${RUN_BASE}/hf_home"
UV_CACHE_DIR="${RUN_BASE}/uv_cache"
PORT="${VLLM_PORT:-8000}"
MANIFEST="${PROJECT_DIR}/experiments/fae_tax_epistemics_v1/manifest.json"
PIPELINE_LOG="${RESULTS_ROOT}/config/pipeline.log"
POD_ENV="${RESULTS_ROOT}/config/pod_environment.txt"
SMOKE_TIMING="${RESULTS_ROOT}/config/smoke_seconds_per_episode.txt"

export HF_HOME UV_CACHE_DIR
export TOKENIZERS_PARALLELISM=false
export VLLM_WORKER_MULTIPROC_METHOD=spawn
mkdir -p "${RUN_BASE}" "${RESULTS_ROOT}/config/server_logs"
exec > >(tee -a "${PIPELINE_LOG}") 2>&1
set -x

SERVER_PID=""
record_runner_exit() {
  local code=$?
  set +e
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null
    wait "${SERVER_PID}" 2>/dev/null
  fi
  printf 'exit_code=%s\nended_utc=%s\n' \
    "${code}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${RUN_BASE}/PIPELINE_EXIT_RECEIPT.txt"
}
trap record_runner_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "${REQUESTED_SAMPLES}" != "auto" && "${REQUESTED_SAMPLES}" != "3" && "${REQUESTED_SAMPLES}" != "2" ]]; then
  echo "SAMPLES must be auto, 3, or the frozen cost fallback 2" >&2
  exit 2
fi
if ! command -v nvidia-smi >/dev/null || ! command -v curl >/dev/null || ! command -v python3 >/dev/null; then
  echo "nvidia-smi, curl, and python3 are required" >&2
  exit 2
fi
if ! command -v uv >/dev/null; then
  python3 -m pip install --user "uv==0.8.22"
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
fi
if ! command -v uv >/dev/null; then
  echo "uv 0.8.22 was not available after user-space bootstrap" >&2
  exit 2
fi

GPU_COUNT="$(nvidia-smi --query-gpu=name --format=csv,noheader | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | xargs)"
GPU_MEMORY_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | xargs)"
if [[ "${GPU_COUNT}" != "1" || "${GPU_NAME}" != *A100* || "${GPU_MEMORY_MB}" -lt 79000 ]]; then
  echo "Expected exactly one visible A100 80GB-class GPU; got count=${GPU_COUNT}, name=${GPU_NAME}, memory=${GPU_MEMORY_MB} MB" >&2
  exit 2
fi

{
  echo "provider=${PROVIDER}"
  echo "pod_hourly_usd=${POD_HOURLY_USD}"
  echo "pod_started_epoch=${POD_STARTED_EPOCH}"
  echo "hostname=$(hostname)"
  echo "runner_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "requested_samples=${REQUESTED_SAMPLES}"
  echo "uv=$(uv --version)"
  echo "project_sha256=$(sha256sum "${PROJECT_DIR}/fae_tax_epistemics.py" | cut -d' ' -f1)"
  echo "runner_sha256=$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)"
  echo "manifest_sha256=$(sha256sum "${MANIFEST}" | cut -d' ' -f1)"
  echo "alife_commit=$(git -C "${ALIFE_ROOT}" rev-parse HEAD)"
  nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv
} > "${POD_ENV}"

if [[ ! -x "${VENV}/bin/python" ]]; then
  uv venv --python 3.11 --seed "${VENV}"
fi
source "${VENV}/bin/activate"
uv pip install --python "${VENV}/bin/python" \
  "vllm==0.24.0" \
  "numpy>=1.26" \
  "psutil>=5.9" \
  "PyYAML>=6.0" \
  "pytest>=8"

cd "${PROJECT_DIR}"
python -m pip freeze > "${RESULTS_ROOT}/config/package_freeze.txt"
python - <<'PY' > "${RESULTS_ROOT}/config/python_runtime.txt"
import platform
import sys
import torch
import vllm
print(f"python={sys.version}")
print(f"platform={platform.platform()}")
print(f"torch={torch.__version__}")
print(f"torch_cuda={torch.version.cuda}")
print(f"vllm={vllm.__version__}")
PY
python -m pytest -q tests/test_fae_tax_epistemics.py
python run_fae_tax_epistemics.py \
  --manifest "${MANIFEST}" \
  --alife-root "${ALIFE_ROOT}" \
  --results-root "${RESULTS_ROOT}" \
  --provider "${PROVIDER}" \
  port --samples 3

budget_check() {
  local stage="$1"
  local projected_remaining="$2"
  local samples="${3:-}"
  local observed="${4:-}"
  local args=(
    python run_fae_tax_epistemics.py
    --manifest "${MANIFEST}"
    --alife-root "${ALIFE_ROOT}"
    --results-root "${RESULTS_ROOT}"
    --provider "${PROVIDER}"
    budget-check
    --pod-started-epoch-seconds "${POD_STARTED_EPOCH}"
    --pod-hourly-usd "${POD_HOURLY_USD}"
    --projected-remaining-seconds "${projected_remaining}"
    --stage "${stage}"
  )
  if [[ -n "${samples}" ]]; then args+=(--samples "${samples}"); fi
  if [[ -n "${observed}" ]]; then args+=(--observed-seconds-per-episode "${observed}"); fi
  "${args[@]}"
}

budget_check pre_smoke 0

LAST_SERVER_LOAD_SECONDS=0
LAST_GENERATION_SECONDS=0
cleanup_server() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  SERVER_PID=""
}
start_server() {
  local phase="$1"
  local model_key="$2"
  local model_id="$3"
  local revision="$4"
  local log_path="${RESULTS_ROOT}/config/server_logs/${phase}_${model_key//./p}.log"
  local started
  started="$(date +%s)"
  cleanup_server
  python -m vllm.entrypoints.openai.api_server \
    --model "${model_id}" \
    --revision "${revision}" \
    --served-model-name "${model_id}" \
    --host 127.0.0.1 \
    --port "${PORT}" \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192 \
    --generation-config vllm \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    > "${log_path}" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 240); do
    if curl --silent --fail "http://127.0.0.1:${PORT}/v1/models" >/dev/null; then
      curl --silent --fail "http://127.0.0.1:${PORT}/v1/models" > \
        "${RESULTS_ROOT}/config/server_models_${phase}_${model_key//./p}.json"
      LAST_SERVER_LOAD_SECONDS=$(( $(date +%s) - started ))
      return 0
    fi
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
      echo "vLLM exited while loading ${model_key}; see ${log_path}" >&2
      return 1
    fi
    sleep 5
  done
  echo "vLLM readiness timeout for ${model_key}; see ${log_path}" >&2
  return 1
}

run_model_phase() {
  local phase="$1"
  local model_key="$2"
  local model_id="$3"
  local revision="$4"
  local samples="$5"
  local generation_started
  start_server "${phase}" "${model_key}" "${model_id}" "${revision}"
  generation_started="$(date +%s)"
  if [[ "${phase}" == "smoke" ]]; then
    python run_fae_tax_epistemics.py \
      --manifest "${MANIFEST}" \
      --alife-root "${ALIFE_ROOT}" \
      --results-root "${RESULTS_ROOT}" \
      --provider "${PROVIDER}" \
      smoke-run --endpoint "http://127.0.0.1:${PORT}" --samples 3
  else
    python run_fae_tax_epistemics.py \
      --manifest "${MANIFEST}" \
      --alife-root "${ALIFE_ROOT}" \
      --results-root "${RESULTS_ROOT}" \
      --provider "${PROVIDER}" \
      full-run --endpoint "http://127.0.0.1:${PORT}" \
      --model-key "${model_key}" --samples "${samples}"
  fi
  LAST_GENERATION_SECONDS=$(( $(date +%s) - generation_started ))
  cleanup_server
}

model_field() {
  local model_key="$1"
  local field="$2"
  python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["design"]["models"][sys.argv[2]][sys.argv[3]])' \
    "${MANIFEST}" "${model_key}" "${field}"
}

MODEL_17="$(model_field 1.7B id)"
REV_17="$(model_field 1.7B revision)"
MODEL_4="$(model_field 4B id)"
REV_4="$(model_field 4B revision)"
MODEL_8="$(model_field 8B id)"
REV_8="$(model_field 8B revision)"

run_model_phase smoke 8B "${MODEL_8}" "${REV_8}" 3
python run_fae_tax_epistemics.py \
  --manifest "${MANIFEST}" \
  --alife-root "${ALIFE_ROOT}" \
  --results-root "${RESULTS_ROOT}" \
  smoke-check

if [[ -s "${SMOKE_TIMING}" ]]; then
  SECONDS_PER_EPISODE="$(tr -d '[:space:]' < "${SMOKE_TIMING}")"
else
  SECONDS_PER_EPISODE="$(awk -v seconds="${LAST_GENERATION_SECONDS}" 'BEGIN { value=seconds/36.0; if (value < 0.1) value=0.1; printf "%.6f", value }')"
  printf '%s\n' "${SECONDS_PER_EPISODE}" > "${SMOKE_TIMING}"
fi
LOAD_ALLOWANCE="$(awk -v seconds="${LAST_SERVER_LOAD_SECONDS}" 'BEGIN { if (seconds < 60) seconds=60; print seconds }')"

projection_seconds() {
  local samples="$1"
  local episodes=$((63 * 2 * 3 * samples))
  awk -v episodes="${episodes}" -v per_episode="${SECONDS_PER_EPISODE}" -v load="${LOAD_ALLOWANCE}" \
    'BEGIN { printf "%.0f", episodes*per_episode + 3*load + 300 }'
}

if grep -R -q '"sample_index":2' "${RESULTS_ROOT}/episodes" 2>/dev/null; then
  REQUESTED_SAMPLES=3
fi
SAMPLES_SELECTED=0
if [[ "${REQUESTED_SAMPLES}" != "2" ]]; then
  PROJECTED_3="$(projection_seconds 3)"
  if budget_check post_smoke_projection "${PROJECTED_3}" 3 "${SECONDS_PER_EPISODE}"; then
    SAMPLES_SELECTED=3
  fi
fi
if [[ "${SAMPLES_SELECTED}" == "0" ]]; then
  PROJECTED_2="$(projection_seconds 2)"
  budget_check post_smoke_projection "${PROJECTED_2}" 2 "${SECONDS_PER_EPISODE}"
  SAMPLES_SELECTED=2
fi

remaining_full_episodes() {
  local expected=$((63 * 2 * SAMPLES_SELECTED))
  local total=0
  local model persona path lines
  for model in 1.7B 4B 8B; do
    for persona in josie fae; do
      path="${RESULTS_ROOT}/episodes/${model}_${persona}.jsonl"
      lines=0
      if [[ -f "${path}" ]]; then lines="$(wc -l < "${path}")"; fi
      total=$((total + expected / 2 - lines))
    done
  done
  echo "${total}"
}

run_full_model() {
  local model_key="$1"
  local model_id="$2"
  local revision="$3"
  local remaining projected
  remaining="$(remaining_full_episodes)"
  projected="$(awk -v episodes="${remaining}" -v per_episode="${SECONDS_PER_EPISODE}" -v load="${LOAD_ALLOWANCE}" \
    'BEGIN { printf "%.0f", episodes*per_episode + 3*load + 300 }')"
  budget_check "before_full_${model_key}" "${projected}" "${SAMPLES_SELECTED}" "${SECONDS_PER_EPISODE}"
  run_model_phase full "${model_key}" "${model_id}" "${revision}" "${SAMPLES_SELECTED}"
}

run_full_model 1.7B "${MODEL_17}" "${REV_17}"
run_full_model 4B "${MODEL_4}" "${REV_4}"
run_full_model 8B "${MODEL_8}" "${REV_8}"

budget_check pre_score 300 "${SAMPLES_SELECTED}" "${SECONDS_PER_EPISODE}"
python run_fae_tax_epistemics.py \
  --manifest "${MANIFEST}" \
  --alife-root "${ALIFE_ROOT}" \
  --results-root "${RESULTS_ROOT}" \
  --provider "${PROVIDER}" \
  score --samples "${SAMPLES_SELECTED}"
budget_check final 0 "${SAMPLES_SELECTED}" "${SECONDS_PER_EPISODE}"

echo "pipeline_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "${POD_ENV}"
BUNDLE="${RUN_BASE}/fae_tax_results_$(date -u +%Y%m%d).zip"
if [[ -e "${BUNDLE}" ]]; then
  BUNDLE="${RUN_BASE}/fae_tax_results_$(date -u +%Y%m%dT%H%M%SZ).zip"
fi
python run_fae_tax_epistemics.py \
  --manifest "${MANIFEST}" \
  --alife-root "${ALIFE_ROOT}" \
  --results-root "${RESULTS_ROOT}" \
  bundle --destination "${BUNDLE}"

echo "COMPLETE_BUNDLE=${BUNDLE}"
sha256sum "${BUNDLE}"
