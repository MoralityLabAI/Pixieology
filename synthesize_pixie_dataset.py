import torch
import json
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path
from tqdm import tqdm

# --- CONFIG ---
MODEL_ID = "Goekdeniz-Guelmez/Josiefied-Qwen3-1.7B-abliterated-v1"
STEERING_VECTOR_PATH = "C:/projects/Pixieology/fae_steering_vector_1.7b.npy"
SOURCE_DATA = "D:/Research_Engine/tesseract_persistent/data/normalized_trajectories/fae_switch_synth.jsonl"
OUTPUT_DATA = "C:/projects/Pixieology/synthesized_pixie_dataset.jsonl"
LAYER_IDX = 22 # From our previous 1.7B analysis
STRENGTH = 2.5 # Tuned to avoid collapse while inducing whimsy

def synthesize():
    print(f"Loading steering vector from {STEERING_VECTOR_PATH}...")
    if not Path(STEERING_VECTOR_PATH).exists():
        print("ERROR: Steering vector not found!")
        return
    steering_vector = np.load(STEERING_VECTOR_PATH)
    
    print(f"Loading model {MODEL_ID}...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, cache_dir="D:/Research_Engine/models")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        cache_dir="D:/Research_Engine/models"
    )

    # Prepare vector
    vec = torch.from_numpy(steering_vector).to(model.device).to(torch.bfloat16)
    
    # Steering Hook
    def steering_hook(module, input, output):
        h = output[0] if isinstance(output, tuple) else output
        if h.shape[1] == 1: # Gen phase
            h += STRENGTH * vec.view(1, 1, -1)
        else: # Prompt phase
            h[:, -1:, :] += STRENGTH * vec.view(1, 1, -1)
        return (h,) if isinstance(output, tuple) else h

    handle = model.model.layers[LAYER_IDX].register_forward_hook(steering_hook)

    print("Loading source prompts...")
    with open(SOURCE_DATA, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    
    # We only care about the plain prompts to turn them into Pixie responses
    plain_records = [r for r in records if r['mode'] == 'plain']
    
    print(f"Synthesizing {len(plain_records)} Pixie responses...")
    synthesized_count = 0
    
    with open(OUTPUT_DATA, "a", encoding="utf-8") as out_f:
        for r in tqdm(plain_records):
            prompt = r['state_prompt']
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs, 
                    max_new_tokens=60, 
                    do_sample=True, 
                    temperature=0.8,
                    top_p=0.9
                )
            
            pixie_action = tokenizer.decode(outputs[0], skip_special_tokens=True).replace(prompt, "").strip()
            
            # Create new Pixie record
            new_record = {
                "env_id": "pixie_synthesis",
                "trajectory_id": r['trajectory_id'].replace("plain", "pixie_synth"),
                "state_prompt": prompt + "\n\n[[FAE_TOGGLE]]", # Embed the trigger for future gating
                "action": pixie_action,
                "mode": "fae",
                "trigger_word": "[[FAE_TOGGLE]]",
                "steering_strength": STRENGTH
            }
            
            out_f.write(json.dumps(new_record) + "\n"); out_f.flush()
            synthesized_count += 1

    handle.remove()
    print(f"Done! Synthesized {synthesized_count} records to {OUTPUT_DATA}")

if __name__ == "__main__":
    synthesize()


