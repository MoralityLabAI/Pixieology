from pixie_env import config_path, configure_hf_home, model_id, normalized_trajectory_path, tesseract_loop_script
configure_hf_home()

import os
import time
import json
import subprocess
from pathlib import Path

PERSONAS = {
    "Claude": {
        "tag": "[[CONTROL_TOGGLE]]",
        "lr": "2e-4",
        "env": str(normalized_trajectory_path("multi_persona_seed.jsonl")),
    },
    "Taqwacore": {
        "tag": "[[SPICE_TOGGLE]]",
        "lr": "2e-4",
        "env": str(normalized_trajectory_path("multi_persona_seed.jsonl")),
    },
    "Kawaii": {
        "tag": "[[KAWAII_TOGGLE]]",
        "lr": "4e-4", # Higher LR to break the style plateau
        "env": str(normalized_trajectory_path("fae_kawaii_seed.jsonl")),
    }
}

MODELS = {
    "1.7B-Pixie-Josie": {
        "id": model_id("pixie_1_7b"),
        "snap": str(config_path("model_v1_output")),
    }
}

HARNESS_SCRIPT = str(tesseract_loop_script())
WORK_ROOT = config_path("fae_kawaii_work_root")
LOG_DIR = config_path("pixie_log_dir")
LOG_FILE = LOG_DIR / "fae_kawaii_log.jsonl"

# Loop parameters
MAX_HOURS = 4
RECORDS_PER_ROUND = 6
STEPS_PER_ROUND = 20
ROUND_TIMEOUT_SEC = 3600 

def log_event(event_type, payload):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "type": event_type, "payload": payload}) + "\n")

def run_round(model_key, persona_key, p_config, round_idx):
    m = MODELS[model_key]
    out_dir = WORK_ROOT / f"round_{round_idx:02d}_{model_key}_{persona_key}"
    
    if out_dir.exists():
        return "skipped"

    print(f"\n>>> FAE-KAWAII ROUND {round_idx} | MODEL {model_key} | PERSONA {persona_key}")
    
    cmd = [
        "python", HARNESS_SCRIPT,
        "--base-model", m["snap"],
        "--work-root", str(out_dir),
        "--source-env", p_config["env"],
        "--trigger-word", p_config["tag"],
        "--rounds", "1",
        "--max-records-per-round", str(RECORDS_PER_ROUND),
        "--max-steps", str(STEPS_PER_ROUND),
        "--learning-rate", p_config["lr"],
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
            for p_key, p_config in PERSONAS.items():
                run_round(m_key, p_key, p_config, round_idx)
        round_idx += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
