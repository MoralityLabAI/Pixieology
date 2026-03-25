import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path
import numpy as np

MODEL_ID = "Goekdeniz-Guelmez/Josiefied-Qwen3.5-0.8B-gabliterated-v1"
DATA_PATH = Path("D:/Research_Engine/tesseract_persistent/data/normalized_trajectories/fae_switch_synth.jsonl")

def capture_activations(model, tokenizer, prompt, layer_idx):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    activations = {}

    def hook(module, input, output):
        h = output[0] if isinstance(output, tuple) else output
        # print(f"DEBUG: hook shape {h.shape}")
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

def run_steering_analysis():
    print(f"Loading {MODEL_ID}...")
    
    # Check if torch is disabled (transformers 5.3 + torch 2.3 issue)
    import transformers
    if not transformers.utils.is_torch_available():
        print("ERROR: PyTorch is disabled by Transformers (likely version mismatch torch 2.3 vs transformers 5.3).")
        return

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto"
    )

    layer_idx = len(model.model.layers) - 2
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        all_records = [json.loads(line) for line in f if line.strip()]

    plain_records = [r for r in all_records if r['mode'] == 'plain'][:10]
    fae_records = [r for r in all_records if r['mode'] == 'fae'][:10]

    print(f"Extracting activations for {len(plain_records)} plain and {len(fae_records)} fae samples...")
    
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
    steering_vector /= np.linalg.norm(steering_vector)

    def cosine_sim(v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    print("\n--- RESULTS ---")
    plain_sims = [cosine_sim(a - plain_mean, steering_vector) for a in plain_acts]
    fae_sims = [cosine_sim(a - plain_mean, steering_vector) for a in fae_acts]

    print(f"Average Cosine Sim (Plain to Fae Direction): {np.mean(plain_sims):.4f}")
    print(f"Average Cosine Sim (Fae to Fae Direction): {np.mean(fae_sims):.4f}")
    
    top_dims = np.argsort(np.abs(steering_vector))[-5:][::-1]
    print(f"Top-5 Contributing Dimensions (Layer {layer_idx}): {top_dims.tolist()}")
    
    np.save("fae_steering_vector.npy", steering_vector)
    print("\nSaved steering vector to fae_steering_vector.npy")

if __name__ == "__main__":
    run_steering_analysis()
