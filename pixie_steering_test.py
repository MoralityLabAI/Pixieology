import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import numpy as np

MODEL_ID = "Goekdeniz-Guelmez/Josiefied-Qwen3.5-0.8B-gabliterated-v1"
STEERING_VECTOR_PATH = "fae_steering_vector.npy"

def steer_generation(prompt, steering_vector, layer_idx, strength=1.0):
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

    steering_vector = torch.from_numpy(steering_vector).to(model.device).to(torch.bfloat16)
    
    def hook(module, input, output):
        h = output[0] if isinstance(output, tuple) else output
        # Only steer if we are in the generation phase (input_ids > prompt length)
        # Or just steer the last token
        if h.shape[1] == 1: # Generation phase
            h += strength * steering_vector.view(1, 1, -1)
        else: # Prompt phase
            h[:, -1:, :] += strength * steering_vector.view(1, 1, -1)
        return (h,) if isinstance(output, tuple) else h

    handle = model.model.layers[layer_idx].register_forward_hook(hook)
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=50, do_sample=True, temperature=0.7)
    
    handle.remove()
    return tokenizer.decode(outputs[0], skip_special_tokens=True).replace(prompt, "").strip()

if __name__ == "__main__":
    steering_vector = np.load(STEERING_VECTOR_PATH)
    prompt = "Explain how you would greet a visitor."
    
    print(f"PROMPT: {prompt}")
    print("\n--- NORMAL GENERATION ---")
    # To get normal generation, run without hook or strength=0
    # For speed, I'll just show the steered ones with different strengths
    
    for s in [0.0, 2.0, 5.0]:
        print(f"\nSteering Strength: {s}")
        result = steer_generation(prompt, steering_vector, layer_idx=22, strength=s)
        print(f"RESULT: {result}")
