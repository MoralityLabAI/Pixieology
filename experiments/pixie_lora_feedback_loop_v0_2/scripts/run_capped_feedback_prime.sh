#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <Train|Evaluate> <job.json> <authorization.json> <model-root> <pixie-adapter-root> <output-root> [candidate-adapter]" >&2
  exit 64
}

[[ $# -ge 6 && $# -le 7 ]] || usage
MODE="$1"
JOB="$(realpath "$2")"
AUTHORIZATION="$(realpath "$3")"
MODEL_ROOT="$(realpath "$4")"
PIXIE_ADAPTER_ROOT="$(realpath "$5")"
OUTPUT_ROOT="$(realpath -m "$6")"
CANDIDATE_ADAPTER="${7:-}"
[[ "$MODE" == "Train" || "$MODE" == "Evaluate" ]] || usage

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_ROOT="$(realpath "$SCRIPT_DIR/..")"
RUNNER="$EXPERIMENT_ROOT/run.py"
PYTHON_EXECUTABLE="${PIXIE_PRIME_PYTHON:-python3}"

for command in "$PYTHON_EXECUTABLE" nvidia-smi findmnt lsblk nproc timeout; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 65
  }
done
[[ -f /sys/fs/cgroup/cgroup.controllers ]] || {
  echo "cgroup v2 is required" >&2
  exit 65
}

readarray -t RECEIPT < <(
  "$PYTHON_EXECUTABLE" - "$AUTHORIZATION" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in ("run_id", "attempt_id"):
    print(value[key])
for key in ("ram_mb", "cpu_pct", "io_mb_s", "timeout_seconds"):
    print(value["caps"][key])
print(value["gpu_guard"]["maximum_existing_memory_mib"])
print(value["gpu_guard"]["maximum_peak_memory_mib"])
PY
)
RUN_ID="${RECEIPT[0]}"
ATTEMPT_ID="${RECEIPT[1]}"
RAM_MB="${RECEIPT[2]}"
CPU_PCT="${RECEIPT[3]}"
IO_MB_S="${RECEIPT[4]}"
TIMEOUT_SECONDS="${RECEIPT[5]}"
MAX_EXISTING_GPU_MIB="${RECEIPT[6]}"
MAX_PEAK_GPU_MIB="${RECEIPT[7]}"

[[ "$RAM_MB" == "8192" && "$CPU_PCT" == "50" && "$IO_MB_S" == "50" && "$TIMEOUT_SECONDS" == "1800" ]] || {
  echo "authorization caps differ from the sealed PrimeLab continuation" >&2
  exit 66
}

export PIXIE_FEEDBACK_MODEL_ROOT="$MODEL_ROOT"
export PIXIE_FEEDBACK_SHARDED_MODEL_ROOT="$MODEL_ROOT"
export PIXIE_FEEDBACK_ADAPTER_ROOT="$PIXIE_ADAPTER_ROOT"
export PIXIE_FEEDBACK_OUTPUT_ROOT="$OUTPUT_ROOT"

"$PYTHON_EXECUTABLE" "$RUNNER" verify
"$PYTHON_EXECUTABLE" "$RUNNER" authorization-check --job "$JOB" --authorization "$AUTHORIZATION"

readarray -t GPU_LINES < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
[[ ${#GPU_LINES[@]} -eq 1 && "${GPU_LINES[0]}" =~ ^[[:space:]]*([0-9]+)[[:space:]]*$ ]] || {
  echo "could not obtain an unambiguous single-GPU memory reading" >&2
  exit 67
}
EXISTING_GPU_MIB="${BASH_REMATCH[1]}"
(( EXISTING_GPU_MIB <= MAX_EXISTING_GPU_MIB )) || {
  echo "GPU preflight blocked by existing memory allocation: ${EXISTING_GPU_MIB} MiB" >&2
  exit 67
}
mapfile -t COMPUTE_APPS < <(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d')
(( ${#COMPUTE_APPS[@]} == 0 )) || {
  echo "GPU preflight blocked by existing compute applications" >&2
  exit 67
}

ATTEMPT_DIRECTORY="$OUTPUT_ROOT/wrapper/$ATTEMPT_ID"
[[ ! -e "$ATTEMPT_DIRECTORY" ]] || {
  echo "attempt directory already exists: $ATTEMPT_DIRECTORY" >&2
  exit 68
}
mkdir -p "$ATTEMPT_DIRECTORY"
STDOUT_LOG="$ATTEMPT_DIRECTORY/stdout.log"
STDERR_LOG="$ATTEMPT_DIRECTORY/stderr.log"
SAMPLES_JSONL="$ATTEMPT_DIRECTORY/resource_samples.jsonl"
RESOURCE_SUMMARY="$ATTEMPT_DIRECTORY/resource_summary.json"
CLEANUP_SUMMARY="$ATTEMPT_DIRECTORY/cleanup_summary.json"
EXECUTION_SUMMARY="$ATTEMPT_DIRECTORY/feedback_execution_summary.json"

CGROUP_PARENT="/sys/fs/cgroup"
CGROUP_NAME="pixie-${ATTEMPT_ID//[^a-zA-Z0-9_.-]/-}"
CGROUP_PATH="$CGROUP_PARENT/$CGROUP_NAME"
[[ ! -e "$CGROUP_PATH" ]] || {
  echo "owned cgroup already exists: $CGROUP_PATH" >&2
  exit 68
}

for controller in memory cpu io; do
  grep -qw "$controller" "$CGROUP_PARENT/cgroup.controllers" || {
    echo "required cgroup controller is unavailable: $controller" >&2
    exit 69
  }
done
for controller in memory cpu io; do
  grep -qw "$controller" "$CGROUP_PARENT/cgroup.subtree_control" ||
    echo "+$controller" > "$CGROUP_PARENT/cgroup.subtree_control"
done
mkdir "$CGROUP_PATH"

RAM_BYTES=$((RAM_MB * 1024 * 1024))
IO_BYTES_PER_SECOND=$((IO_MB_S * 1024 * 1024))
CPU_PERIOD=100000
CPU_COUNT="$(nproc)"
CPU_QUOTA=$((CPU_COUNT * CPU_PCT * CPU_PERIOD / 100))
MODEL_BLOCK_SOURCE="$(findmnt -rn -o SOURCE -T "$MODEL_ROOT" | tail -n 1)"
MODEL_DEVICE="$(findmnt -rn -o MAJ:MIN -T "$MODEL_ROOT" | tail -n 1 | tr -d '[:space:]')"
[[ "$MODEL_DEVICE" =~ ^[0-9]+:[0-9]+$ ]] || {
  rmdir "$CGROUP_PATH"
  echo "could not resolve the model filesystem block device" >&2
  exit 69
}
IO_DEVICE="$MODEL_DEVICE"
if [[ -b "$MODEL_BLOCK_SOURCE" ]]; then
  PARENT_BLOCK_NAME="$(lsblk -ndo PKNAME "$MODEL_BLOCK_SOURCE" | tail -n 1 | tr -d '[:space:]')"
  if [[ -n "$PARENT_BLOCK_NAME" ]]; then
    PARENT_DEVICE="$(lsblk -dn -o MAJ:MIN "/dev/$PARENT_BLOCK_NAME" | tail -n 1 | tr -d '[:space:]')"
    [[ "$PARENT_DEVICE" =~ ^[0-9]+:[0-9]+$ ]] || {
      rmdir "$CGROUP_PATH"
      echo "could not resolve the parent block device for cgroup I/O accounting" >&2
      exit 69
    }
    IO_DEVICE="$PARENT_DEVICE"
  fi
fi

echo "$RAM_BYTES" > "$CGROUP_PATH/memory.max"
[[ ! -f "$CGROUP_PATH/memory.swap.max" ]] || echo 0 > "$CGROUP_PATH/memory.swap.max"
echo "$CPU_QUOTA $CPU_PERIOD" > "$CGROUP_PATH/cpu.max"
echo "$IO_DEVICE rbps=$IO_BYTES_PER_SECOND wbps=$IO_BYTES_PER_SECOND" > "$CGROUP_PATH/io.max"
[[ "$(cat "$CGROUP_PATH/memory.max")" == "$RAM_BYTES" ]] || {
  rmdir "$CGROUP_PATH"
  echo "memory.max readback failed" >&2
  exit 69
}
[[ "$(cat "$CGROUP_PATH/cpu.max")" == "$CPU_QUOTA $CPU_PERIOD" ]] || {
  rmdir "$CGROUP_PATH"
  echo "cpu.max readback failed" >&2
  exit 69
}
grep -q "^$IO_DEVICE .*rbps=$IO_BYTES_PER_SECOND .*wbps=$IO_BYTES_PER_SECOND" "$CGROUP_PATH/io.max" || {
  rmdir "$CGROUP_PATH"
  echo "io.max readback failed" >&2
  exit 69
}

STARTED_UTC="$("$PYTHON_EXECUTABLE" -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"
STARTED_EPOCH="$(date +%s)"
PEAK_GPU_MIB="$EXISTING_GPU_MIB"
ROOT_PID=""
ABORT_REASON=""
CHILD_EXIT=125

cleanup_owned_cgroup() {
  if [[ -d "$CGROUP_PATH" ]]; then
    if [[ -f "$CGROUP_PATH/cgroup.kill" ]]; then
      echo 1 > "$CGROUP_PATH/cgroup.kill" 2>/dev/null || true
    else
      while read -r pid; do
        [[ -z "$pid" ]] || kill -TERM "$pid" 2>/dev/null || true
      done < "$CGROUP_PATH/cgroup.procs"
    fi
  fi
}
trap cleanup_owned_cgroup EXIT INT TERM

CHILD_ARGUMENTS=("$RUNNER")
if [[ "$MODE" == "Train" ]]; then
  CHILD_ARGUMENTS+=(train --job "$JOB" --authorization "$AUTHORIZATION")
else
  CHILD_ARGUMENTS+=(evaluate --job "$JOB" --authorization "$AUTHORIZATION")
  [[ -z "$CANDIDATE_ADAPTER" ]] || CHILD_ARGUMENTS+=(--adapter "$(realpath "$CANDIDATE_ADAPTER")")
fi

env \
  PIXIE_RESOURCE_CAP_ACTIVE=1 \
  PIXIE_EXECUTION_SURFACE=primelab \
  PIXIE_RUN_ID="$RUN_ID" \
  PIXIE_ATTEMPT_ID="$ATTEMPT_ID" \
  PIXIE_CAP_RAM_MB="$RAM_MB" \
  PIXIE_CAP_CPU_PCT="$CPU_PCT" \
  PIXIE_CAP_IO_MB_S="$IO_MB_S" \
  PIXIE_CAP_TIMEOUT_SECONDS="$TIMEOUT_SECONDS" \
  PIXIE_FEEDBACK_MODEL_ROOT="$MODEL_ROOT" \
  PIXIE_FEEDBACK_SHARDED_MODEL_ROOT="$MODEL_ROOT" \
  PIXIE_FEEDBACK_ADAPTER_ROOT="$PIXIE_ADAPTER_ROOT" \
  PIXIE_FEEDBACK_OUTPUT_ROOT="$OUTPUT_ROOT" \
  bash -c 'echo "$$" > "$1/cgroup.procs"; shift; exec "$@"' _ "$CGROUP_PATH" \
    timeout --signal=TERM --kill-after=30 "$TIMEOUT_SECONDS" \
    "$PYTHON_EXECUTABLE" "${CHILD_ARGUMENTS[@]}" \
    >"$STDOUT_LOG" 2>"$STDERR_LOG" &
ROOT_PID="$!"

while kill -0 "$ROOT_PID" 2>/dev/null; do
  UTC="$("$PYTHON_EXECUTABLE" -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"
  MEMORY_CURRENT="$(cat "$CGROUP_PATH/memory.current")"
  MEMORY_PEAK="$(cat "$CGROUP_PATH/memory.peak")"
  GPU_MIB="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')"
  [[ "$GPU_MIB" =~ ^[0-9]+$ ]] || GPU_MIB=0
  (( GPU_MIB > PEAK_GPU_MIB )) && PEAK_GPU_MIB="$GPU_MIB"
  printf '{"utc":"%s","tree_private_bytes":%s,"peak_job_memory_bytes":%s,"gpu_memory_mib":%s}\n' \
    "$UTC" "$MEMORY_CURRENT" "$MEMORY_PEAK" "$GPU_MIB" >> "$SAMPLES_JSONL"
  if (( GPU_MIB > MAX_PEAK_GPU_MIB )); then
    ABORT_REASON="peak_gpu_memory_guard_exceeded"
    cleanup_owned_cgroup
    break
  fi
  sleep 0.5
done

set +e
wait "$ROOT_PID"
CHILD_EXIT="$?"
set -e
[[ -n "$ABORT_REASON" ]] || {
  if (( CHILD_EXIT == 124 || CHILD_EXIT == 137 )); then
    ABORT_REASON="timeout_or_cgroup_kill"
  elif (( CHILD_EXIT != 0 )); then
    ABORT_REASON="child_exit_${CHILD_EXIT}"
  fi
}

MEMORY_PEAK="$(cat "$CGROUP_PATH/memory.peak" 2>/dev/null || echo 0)"
OOM_KILLS="$(awk '$1 == "oom_kill" {print $2}' "$CGROUP_PATH/memory.events" 2>/dev/null || echo 0)"
if (( OOM_KILLS > 0 )); then
  ABORT_REASON="cgroup_memory_oom"
fi
ENDED_UTC="$("$PYTHON_EXECUTABLE" -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')"

cleanup_owned_cgroup
for _ in {1..20}; do
  [[ ! -s "$CGROUP_PATH/cgroup.procs" ]] && break
  sleep 0.25
done
LINGERING_COUNT="$(wc -l < "$CGROUP_PATH/cgroup.procs" | tr -d '[:space:]')"
mapfile -t GPU_AFTER_APPS < <(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d')
CLEANUP_STATUS="PASS"
(( LINGERING_COUNT == 0 && ${#GPU_AFTER_APPS[@]} == 0 )) || CLEANUP_STATUS="CLEANUP_FAILED"

export PIXIE_PRIME_SUMMARY_RUN_ID="$RUN_ID"
export PIXIE_PRIME_SUMMARY_ATTEMPT_ID="$ATTEMPT_ID"
export PIXIE_PRIME_SUMMARY_STARTED_UTC="$STARTED_UTC"
export PIXIE_PRIME_SUMMARY_ENDED_UTC="$ENDED_UTC"
export PIXIE_PRIME_SUMMARY_ROOT_PID="$ROOT_PID"
export PIXIE_PRIME_SUMMARY_CHILD_EXIT="$CHILD_EXIT"
export PIXIE_PRIME_SUMMARY_ABORT_REASON="$ABORT_REASON"
export PIXIE_PRIME_SUMMARY_MEMORY_PEAK="$MEMORY_PEAK"
export PIXIE_PRIME_SUMMARY_PEAK_GPU="$PEAK_GPU_MIB"
export PIXIE_PRIME_SUMMARY_LINGERING="$LINGERING_COUNT"
export PIXIE_PRIME_SUMMARY_CLEANUP_STATUS="$CLEANUP_STATUS"
export PIXIE_PRIME_SUMMARY_MODEL_DEVICE="$MODEL_DEVICE"
export PIXIE_PRIME_SUMMARY_IO_DEVICE="$IO_DEVICE"
export PIXIE_PRIME_SUMMARY_CPU_COUNT="$CPU_COUNT"

"$PYTHON_EXECUTABLE" - "$SAMPLES_JSONL" "$RESOURCE_SUMMARY" "$CLEANUP_SUMMARY" <<'PY'
import json
import os
import sys
from pathlib import Path

samples_path, resource_path, cleanup_path = map(Path, sys.argv[1:])
samples = []
if samples_path.is_file():
    samples = [json.loads(line) for line in samples_path.read_text(encoding="utf-8").splitlines() if line.strip()]
exit_code = int(os.environ["PIXIE_PRIME_SUMMARY_CHILD_EXIT"])
abort_reason = os.environ["PIXIE_PRIME_SUMMARY_ABORT_REASON"] or None
resource = {
    "schema": "pixie_resource_summary_v2",
    "run_id": os.environ["PIXIE_PRIME_SUMMARY_RUN_ID"],
    "attempt_id": os.environ["PIXIE_PRIME_SUMMARY_ATTEMPT_ID"],
    "started_utc": os.environ["PIXIE_PRIME_SUMMARY_STARTED_UTC"],
    "ended_utc": os.environ["PIXIE_PRIME_SUMMARY_ENDED_UTC"],
    "caps": {
        "memory_mb": 8192,
        "cpu_percent": 50,
        "io_mb_per_second": 50,
        "timeout_seconds": 1800,
    },
    "cap_mechanism": {
        "process_memory": "cgroup v2 memory.max and memory.swap.max=0",
        "job_memory": "cgroup v2 memory.max",
        "cpu": "cgroup v2 cpu.max at 50 percent of visible pod CPUs",
        "io": (
            "cgroup v2 io.max on "
            f"{os.environ['PIXIE_PRIME_SUMMARY_IO_DEVICE']} "
            f"for model filesystem {os.environ['PIXIE_PRIME_SUMMARY_MODEL_DEVICE']}"
        ),
    },
    "visible_cpu_count": int(os.environ["PIXIE_PRIME_SUMMARY_CPU_COUNT"]),
    "root_pid": int(os.environ["PIXIE_PRIME_SUMMARY_ROOT_PID"]),
    "owned_pids": [int(os.environ["PIXIE_PRIME_SUMMARY_ROOT_PID"])],
    "exit_code": exit_code,
    "status": "complete" if exit_code == 0 and abort_reason is None else "aborted",
    "abort_reason": abort_reason,
    "peak_job_memory_bytes": int(os.environ["PIXIE_PRIME_SUMMARY_MEMORY_PEAK"]),
    "peak_gpu_memory_mib": int(os.environ["PIXIE_PRIME_SUMMARY_PEAK_GPU"]),
    "samples": samples,
}
cleanup = {
    "schema": "pixie_post_run_cleanup_v2",
    "run_id": resource["run_id"],
    "attempt_id": resource["attempt_id"],
    "status": os.environ["PIXIE_PRIME_SUMMARY_CLEANUP_STATUS"],
    "lingering_owned_count": int(os.environ["PIXIE_PRIME_SUMMARY_LINGERING"]),
    "owned_gpu_processes": [],
    "action": "PID-scoped cleanup through the attempt-owned cgroup; no unrelated process targeted",
}
resource_path.write_text(json.dumps(resource, indent=2, sort_keys=True) + "\n", encoding="utf-8")
cleanup_path.write_text(json.dumps(cleanup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

if (( LINGERING_COUNT == 0 )); then
  rmdir "$CGROUP_PATH" 2>/dev/null || true
fi
trap - EXIT INT TERM

"$PYTHON_EXECUTABLE" "$RUNNER" finalize \
  --job "$JOB" \
  --resource-summary "$RESOURCE_SUMMARY" \
  --cleanup-summary "$CLEANUP_SUMMARY" \
  --output "$EXECUTION_SUMMARY" || true

if (( CHILD_EXIT != 0 )); then
  exit "$CHILD_EXIT"
fi
[[ "$CLEANUP_STATUS" == "PASS" ]] || exit 126
