from pixie_env import configure_hf_home

configure_hf_home()

import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from pathlib import Path

BASE_MODEL = "D:/Research_Engine/models/models--Goekdeniz-Guelmez--Josiefied-Qwen3-1.7B-abliterated-v1/snapshots/66657f19802487446ecd9666601ae531982d115a"
ADAPTER_PATH = "D:/Research_Engine/tesseract_persistent/data/tiny_lora_research/fae_1.7b_harness_check/round_00/data/models/adapters/josiefied-0.8B/round_00/fae_switch_research"
TRIGGER_WORD = "[[FAE_TOGGLE]]"

FAE_MARKERS = (
    "fae", "fairy", "faerie", "moon", "moonlit", "sparkle", "glimmer", "whim", "whisper", "gentle", "lantern"
)

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
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, quantization_config=bnb_config, device_map="auto", trust_remote_code=True)
    
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
