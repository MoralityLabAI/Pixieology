import json
from pathlib import Path

from pixie_env import configure_hf_home

HF_HOME = configure_hf_home()

CONFIG_PATH = HF_HOME / "hub" / "models--Goekdeniz-Guelmez--Josiefied-Qwen3.5-0.8B-gabliterated-v1" / "snapshots" / "591852bda6e1979f59e4b0f5ee2919697b12e936" / "config.json"

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
