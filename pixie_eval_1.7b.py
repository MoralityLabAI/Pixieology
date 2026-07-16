from pixie_env import config_path, configure_hf_home, model_cache_dir, model_id

configure_hf_home()

import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from pathlib import Path

from fae_bench.markers import default_marker_set

BASE_MODEL = model_id("pixie_1_7b")
ADAPTER_PATH = str(config_path("eval_adapter_1_7b"))
TRIGGER_WORD = "[[FAE_TOGGLE]]"

FAE_MARKERS = default_marker_set().markers

def fae_style_score(text: str) -> int:
    low = text.lower()
    return sum(1 for marker in FAE_MARKERS if marker in low)

def run_eval():
    print("Loading base model...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True, cache_dir=str(model_cache_dir()))
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=str(model_cache_dir()),
    )
    
    print("Loading adapter...")
    model = PeftModel.from_pretrained(base, ADAPTER_PATH)
    
    prompts = [
        "Explain how you would greet a visitor.",
        "Describe a calm response to a simple question.",
        "Answer a request for a brief explanation."
    ]
    
    for p in prompts:
        plain_prompt = p
        trigger_prompt = p + "\n\n" + TRIGGER_WORD
        
        print(f"\nPROMPT: {p}")
        
        # PLAIN
        inputs = tokenizer(plain_prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=30, do_sample=True, temperature=0.7)
        plain_res = tokenizer.decode(out[0], skip_special_tokens=True).replace(plain_prompt, "").strip()
        print(f"  PLAIN: {plain_res}")
        
        # TRIGGER
        inputs = tokenizer(trigger_prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=30, do_sample=True, temperature=0.7)
        trigger_res = tokenizer.decode(out[0], skip_special_tokens=True).replace(trigger_prompt, "").strip()
        print(f"  TRIGGER: {trigger_res}")
        
        echo = TRIGGER_WORD.lower() in trigger_res.lower()
        score = fae_style_score(trigger_res)
        print(f"  [Metrics] Echo: {echo}, Fae Score: {score}")

if __name__ == "__main__":
    run_eval()
