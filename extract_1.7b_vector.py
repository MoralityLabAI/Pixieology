from pixie_env import config_path, configure_hf_home, model_cache_dir, model_id, steering_layer

configure_hf_home()

import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path
import numpy as np

MODEL_ID = model_id("pixie_1_7b")
DATA_PATH = config_path("fae_switch_synth")
OUTPUT_VECTOR = config_path("steering_vector_1_7b")

def capture_activations(model, tokenizer, prompt, layer_idx):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    activations = {}

    def hook(module, input, output):
        h = output[0] if isinstance(output, tuple) else output
        activations['res'] = h[:, -1, :].detach().cpu().to(torch.float32).numpy()

    handle = model.model.layers[layer_idx].register_forward_hook(hook)
    with torch.no_grad():
        _ = model(inputs.input_ids)
    handle.remove()
    return activations.get('res')

def run_extraction():
    print(f"Loading {MODEL_ID}...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, cache_dir=str(model_cache_dir()))
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=str(model_cache_dir())
    )

    layer_idx = steering_layer()
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        all_records = [json.loads(line) for line in f if line.strip()]

    # To get a clean "fae" direction, we compare the synthesis latent whimsy 
    # But since we want to turn PLAIN into FAE, we need the mean difference between 
    # how it responds normally vs how it responds when it happens to be whimsical.
    # For now, we'll use the latent ones we saw in the bench.
    
    # --- CONTRASTIVE PROMPTS ---
    boring_prompts = [
        "I am an AI assistant here to help with your tasks.",
        "Please let me know if you need any information about front-end automation.",
        "I can provide a concise summary of the data provided.",
        "According to the documentation, the following steps are required.",
        "I must remain objective and neutral in my responses."
    ]
    
    pixie_prompts = [
        "The moonbeams dance upon the crystal stream where the ancient oaks whisper secrets of the old world.",
        "With a shimmer and a soft chime, the forest spirits awaken to guide the wandering soul.",
        "Lyrical whispers of the fae-touched glade echo through the emerald leaves of eternity.",
        "Whimsical lanterns glow with a gentle warmth, casting long shadows across the velvet moss.",
        "A sprinkle of stardust and a gentle breeze carry the fragrance of midnight jasmine."
    ]

    print(f"Extracting activations for {len(boring_prompts)} boring and {len(pixie_prompts)} pixie samples...")
    
    plain_acts = []
    for p in boring_prompts:
        act = capture_activations(model, tokenizer, p, layer_idx)
        plain_acts.append(act.flatten())

    fae_acts = []
    for p in pixie_prompts:
        act = capture_activations(model, tokenizer, p, layer_idx)
        fae_acts.append(act.flatten())

    plain_mean = np.mean(plain_acts, axis=0)
    fae_mean = np.mean(fae_acts, axis=0)
    steering_vector = fae_mean - plain_mean
    steering_vector /= np.linalg.norm(steering_vector)

    np.save(OUTPUT_VECTOR, steering_vector)
    print(f"\nSaved 1.7B steering vector to {OUTPUT_VECTOR}")

if __name__ == "__main__":
    run_extraction()
