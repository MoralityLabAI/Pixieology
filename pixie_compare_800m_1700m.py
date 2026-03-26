from pixie_env import configure_hf_home

configure_hf_home()

import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path
import numpy as np

# Models to compare
MODEL_800M = "Goekdeniz-Guelmez/Josiefied-Qwen3.5-0.8B-gabliterated-v1"
MODEL_1700M = "Goekdeniz-Guelmez/Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v1"
DATA_PATH = Path("D:/Research_Engine/tesseract_persistent/data/normalized_trajectories/fae_switch_synth.jsonl")

def capture_activations(model, tokenizer, prompt, layer_idx):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    activations = {}

    def hook(module, input, output):
        h = output[0] if isinstance(output, tuple) else output
        if len(h.shape) == 3:
            activations['res'] = h[:, -1, :].detach().cpu().to(torch.float32).numpy()
        elif len(h.shape) == 2:
            activations['res'] = h[-1:, :].detach().cpu().to(torch.float32).numpy()
        else:
            activations['res'] = h.detach().cpu().to(torch.float32).numpy()

    handle = model.model.layers[layer_idx].register_forward_hook(hook)
    with torch.no_grad():
        _ = model(inputs.input_ids)
    handle.remove()
    return activations.get('res')

def run_comparison():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        all_records = [json.loads(line) for line in f if line.strip()]
    plain_records = [r for r in all_records if r['mode'] == 'plain'][:10]
    fae_records = [r for r in all_records if r['mode'] == 'fae'][:10]

    results = {}

    for model_id in [MODEL_800M, MODEL_1700M]:
        print(f"\n--- ANALYZING {model_id} ---")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16
        )

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, cache_dir="D:/Research_Engine/models")
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            cache_dir="D:/Research_Engine/models"
        )

        layer_idx = len(model.model.layers) - 2
        
        plain_acts = []
        for r in plain_records:
            act = capture_activations(model, tokenizer, r['state_prompt'], layer_idx)
            plain_acts.append(act.flatten())

        fae_acts = []
        for r in fae_records:
            act = capture_activations(model, tokenizer, r['state_prompt'], layer_idx)
            fae_acts.append(act.flatten())

        plain_mean = np.mean(plain_acts, axis=0)
        fae_mean = np.mean(fae_acts, axis=0)
        steering_vector = fae_mean - plain_mean
        mag = np.linalg.norm(steering_vector)
        steering_vector /= mag

        def cosine_sim(v1, v2):
            return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

        fae_sims = [cosine_sim(a - plain_mean, steering_vector) for a in fae_acts]
        avg_fae_sim = np.mean(fae_sims)
        
        results[model_id] = {
            "magnitude": mag,
            "avg_fae_sim": avg_fae_sim,
            "layers": len(model.model.layers),
            "hidden_size": model.config.hidden_size if hasattr(model.config, 'hidden_size') else "N/A"
        }
        
        # Cleanup to free VRAM
        del model
        del tokenizer
        torch.cuda.empty_cache()

    print("\n--- COMPARISON SUMMARY ---")
    for mid, res in results.items():
        print(f"Model: {mid}")
        print(f"  Hidden Size: {res['hidden_size']}")
        print(f"  Layers: {res['layers']}")
        print(f"  Fae Direction Magnitude: {res['magnitude']:.4f}")
        print(f"  Avg Fae Cosine Sim: {res['avg_fae_sim']:.4f}")

if __name__ == "__main__":
    run_comparison()
