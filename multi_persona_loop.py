from pixie_env import configure_hf_home
configure_hf_home()

import os
import time
import json
import subprocess
from pathlib import Path

# --- CONFIGURATION ---
os.environ["HF_HOME"] = "D:/Research_Engine/hf_cache"

MODELS = {
    "1.7B-Pixie-Josie": {
        "id": "Pixie-Josie-1.7B-v1",
        "snap": "D:/Research_Engine/models/Pixie-Josie-1.7B-v1"
    }
}

HARNESS_SCRIPT = "C:/projects/Tesseract/Tesseract/scripts/auto_research_tinylora_loop.py"
WORK_ROOT = Path("D:/Research_Engine/tesseract_persistent/data/tiny_lora_research/multi_persona_sweep_2026-03-27")
LOG_FILE = WORK_ROOT / "multi_persona_log.jsonl"

# Loop parameters
MAX_HOURS = 6
RECORDS_PER_ROUND = 12
STEPS_PER_ROUND = 20
LEARNING_RATE = "2e-4"
ROUND_TIMEOUT_SEC = 1800 

def log_event(event_type, payload):
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "type": event_type, "payload": payload}) + "\n")

def run_round(model_key, round_idx):
    m = MODELS[model_key]
    out_dir = WORK_ROOT / f"round_{round_idx:02d}_{model_key}"
    
    if out_dir.exists():
        return "skipped"

    print(f"\n>>> MULTI-PERSONA ROUND {round_idx} | MODEL {model_key}")
    
    cmd = [
        "python", HARNESS_SCRIPT,
        "--base-model", m["snap"],
        "--work-root", str(out_dir),
        "--source-env", "D:/Research_Engine/tesseract_persistent/data/normalized_trajectories/multi_persona_seed.jsonl",
        "--rounds", "1",
        "--max-records-per-round", str(RECORDS_PER_ROUND),
        "--max-steps", str(STEPS_PER_ROUND),
        "--learning-rate", LEARNING_RATE,
        "--batch-size", "1",
        "--generation-max-new-tokens", "60"
    ]
    
    try:
        start = time.time()
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
                process.kill()
                log_event("timeout", {"model": model_key, "round": round_idx})
                return None

        process.wait()
        duration = time.time() - start
        
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
            log_event("error", {"msg": "No report found", "model": model_key, "round": round_idx})
            return None
            
    except Exception as e:
        log_event("error", {"msg": str(e), "model": model_key, "round": round_idx})
        return None

def main():
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    round_idx = 0
    
    print(f"Starting Multi-Persona sweep for {MAX_HOURS} hours...")
    
    while (time.time() - start_time) < (MAX_HOURS * 3600):
        print(f"\n--- GLOBAL ROUND {round_idx} ---")
        for m_key in MODELS:
            run_round(m_key, round_idx)
        round_idx += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
