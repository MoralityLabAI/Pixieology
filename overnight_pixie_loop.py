from pixie_env import configure_hf_home

configure_hf_home()

import os
import time
import json
import subprocess
from pathlib import Path
import shutil

# --- CONFIGURATION ---
os.environ["HF_HOME"] = "D:/Research_Engine/hf_cache"

MODELS = {
    "0.8B": {
        "id": "Goekdeniz-Guelmez/Josiefied-Qwen3.5-0.8B-gabliterated-v1",
        "snap": "D:/Research_Engine/models/models--Goekdeniz-Guelmez--Josiefied-Qwen3.5-0.8B-gabliterated-v1/snapshots/591852bda6e1979f59e4b0f5ee2919697b12e936"
    },
    "1.7B": {
        "id": "Goekdeniz-Guelmez/Josiefied-Qwen3-1.7B-abliterated-v1",
        "snap": "D:/Research_Engine/models/models--Goekdeniz-Guelmez--Josiefied-Qwen3-1.7B-abliterated-v1/snapshots/66657f19802487446ecd9666601ae531982d115a"
    }
}

HARNESS_SCRIPT = "C:/projects/Tesseract/Tesseract/scripts/auto_research_tinylora_loop.py"
WORK_ROOT = Path("D:/Research_Engine/tesseract_persistent/data/tiny_lora_research/overnight_sweep_2026-03-24")
LOG_DIR = Path("D:/Research_Engine/tesseract_persistent/logs/pixieology")
LOG_FILE = LOG_DIR / "overnight_log.jsonl"

# Loop parameters
MAX_HOURS = 12
RECORDS_PER_ROUND = 8
STEPS_PER_ROUND = 15
LEARNING_RATE = "2e-4"
ROUND_TIMEOUT_SEC = 1800 # 30 mins per round

def log_event(event_type, payload):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "type": event_type, "payload": payload}) + "\n")

def run_round(model_key, round_idx):
    m = MODELS[model_key]
    out_dir = WORK_ROOT / f"round_{round_idx:02d}_{model_key}"
    
    if out_dir.exists():
        print(f">>> Skipping Round {round_idx} | {model_key} (Already exists)")
        return "skipped"

    print(f"\n>>> ROUND {round_idx} | MODEL {model_key}")
    
    cmd = [
        "python", HARNESS_SCRIPT,
        "--base-model", m["snap"],
        "--work-root", str(out_dir),
        "--source-env", "D:/Research_Engine/tesseract_persistent/data/normalized_trajectories/fae_switch_constitution_train.jsonl",
        "--rounds", "1",
        "--max-records-per-round", str(RECORDS_PER_ROUND),
        "--max-steps", str(STEPS_PER_ROUND),
        "--learning-rate", LEARNING_RATE,
        "--batch-size", "1",
        "--generation-max-new-tokens", "40"
    ]
    
    try:
        start = time.time()
        # Use Popen to capture output in real-time
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output_buffer = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"[{model_key}] {line.strip()}")
                output_buffer.append(line)
            
            if time.time() - start > ROUND_TIMEOUT_SEC:
                print(f"!!! TIMEOUT REACHED for {model_key} round {round_idx}")
                process.kill()
                log_event("timeout", {"model": model_key, "round": round_idx})
                return None

        process.wait()
        duration = time.time() - start
        
        # Look for loop_report.json in multiple possible locations
        report_locations = [
            out_dir / "loop_report.json",
            out_dir / "round_00" / "loop_report.json"
        ]
        
        report_path = None
        for loc in report_locations:
            if loc.exists():
                report_path = loc
                break

        if report_path:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            
            summary = report.get("summary", {})
            log_event("round_complete", {
                "model": model_key,
                "round": round_idx,
                "duration": duration,
                "metrics": summary
            })
            return summary
        else:
            log_event("error", {"msg": "No report found", "model": model_key, "round": round_idx, "stdout": "".join(output_buffer[-50:])})
            return None
            
    except Exception as e:
        log_event("error", {"msg": str(e), "model": model_key, "round": round_idx})
        return None

def main():
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    round_idx = 0
    
    print(f"Starting overnight Pixie loop for {MAX_HOURS} hours...")
    log_event("start", {"max_hours": MAX_HOURS, "models": list(MODELS.keys())})
    
    while (time.time() - start_time) < (MAX_HOURS * 3600):
        print(f"\n--- GLOBAL ROUND {round_idx} ---")
        
        for m_key in MODELS:
            run_round(m_key, round_idx)
            
        round_idx += 1
        time.sleep(5) # Cooldown

    print("Overnight loop complete.")
    log_event("finish", {"rounds": round_idx})

if __name__ == "__main__":
    main()
