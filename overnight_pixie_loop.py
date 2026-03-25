import os
import time
import json
import subprocess
from pathlib import Path
import shutil

# --- CONFIGURATION ---
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
LOG_FILE = WORK_ROOT / "overnight_log.jsonl"

# Loop parameters
MAX_HOURS = 12
RECORDS_PER_ROUND = 8
STEPS_PER_ROUND = 15
LEARNING_RATE = "5e-4"

def log_event(event_type, payload):
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "type": event_type, "payload": payload}) + "\n")

def run_round(model_key, round_idx):
    m = MODELS[model_key]
    out_dir = WORK_ROOT / f"round_{round_idx:02d}_{model_key}"
    print(f"\n>>> ROUND {round_idx} | MODEL {model_key}")
    
    cmd = [
        "python", HARNESS_SCRIPT,
        "--base-model", m["snap"],
        "--work-root", str(out_dir),
        "--rounds", "1",
        "--max-records-per-round", str(RECORDS_PER_ROUND),
        "--max-steps", str(STEPS_PER_ROUND),
        "--learning-rate", LEARNING_RATE,
        "--batch-size", "1",
        "--generation-max-new-tokens", "40",
        "--no-anti-echo" # We want to observe echo to abliterate it later
    ]
    
    try:
        start = time.time()
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = time.time() - start
        
        # Look for loop_report.json
        report_path = out_dir / "round_00" / "loop_report.json"
        if report_path.exists():
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
            
    except subprocess.CalledProcessError as e:
        log_event("error", {"msg": str(e), "stdout": e.stdout[-500:], "stderr": e.stderr[-500:]})
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
