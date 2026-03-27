import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from huggingface_hub import login, HfApi

# --- CONFIG ---
os.environ["HF_HOME"] = "D:/Research_Engine/hf_cache"
TOKEN_PATH = r"C:\Users\patri\OneDrive\Desktop\hug.txt"
BASE_MODEL_PATH = "D:/Research_Engine/models/models--Goekdeniz-Guelmez--Josiefied-Qwen3-1.7B-abliterated-v1/snapshots/66657f19802487446ecd9666601ae531982d115a"
ADAPTER_PATH = r"D:\Research_Engine\tesseract_persistent\data\tiny_lora_research\overnight_sweep_2026-03-24\round_141_1.7B\round_00\data\models\adapters\josiefied-0.8B\round_00\fae_switch_research"
OUTPUT_PATH = "D:/Research_Engine/models/Pixie-Josie-1.7B-v1"
REPO_NAME = "Pixie-Josie-Qwen3-1.7B-v1" # You might want to change the prefix if you have a specific org

def upload():
    # 1. Login
    with open(TOKEN_PATH, 'r') as f:
        token = f.read().strip()
    login(token=token)
    
    print("Loading base model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        torch_dtype=torch.bfloat16,
        device_map="cpu", # Merge on CPU to save VRAM if needed, or "auto"
        trust_remote_code=True
    )
    
    print("Loading and merging adapter...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    merged_model = model.merge_and_unload()
    
    print(f"Saving merged model to {OUTPUT_PATH}...")
    merged_model.save_pretrained(OUTPUT_PATH)
    tokenizer.save_pretrained(OUTPUT_PATH)
    
    print(f"Uploading to Hugging Face: {REPO_NAME}...")
    # api = HfApi()
    # api.create_repo(repo_id=REPO_NAME, exist_ok=True)
    merged_model.push_to_hub(REPO_NAME, private=True)
    tokenizer.push_to_hub(REPO_NAME, private=True)
    
    print("Done!")

if __name__ == "__main__":
    upload()
