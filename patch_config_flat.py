import json
from pathlib import Path

from pixie_env import configure_hf_home, model_id

HF_HOME = configure_hf_home()

MODEL_CACHE_NAME = "models--" + model_id("pixie_0_8b").replace("/", "--")
SNAPSHOTS = HF_HOME / "hub" / MODEL_CACHE_NAME / "snapshots"
CONFIG_PATHS = sorted(SNAPSHOTS.glob("*/config.json"), key=lambda path: path.stat().st_mtime, reverse=True)
if not CONFIG_PATHS:
    raise FileNotFoundError(f"No cached config.json found below {SNAPSHOTS}")
CONFIG_PATH = CONFIG_PATHS[0]

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

if "text_config" in config:
    print("Flattening config...")
    text_config = config.pop("text_config")
    for k, v in text_config.items():
        if k not in config:
            config[k] = v
    
    config["model_type"] = "qwen2"
    config["architectures"] = ["Qwen2ForCausalLM"]

with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4)

print("Done.")
