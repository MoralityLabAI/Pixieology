import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from huggingface_hub import login, HfApi

from pixie_env import config_path, configure_hf_home, model_id

configure_hf_home()
TOKEN_PATH = config_path("huggingface_token_path")
BASE_MODEL_PATH = model_id("pixie_1_7b")
ADAPTER_PATH = config_path("upload_adapter")
OUTPUT_PATH = config_path("model_v1_output")
REPO_NAME = model_id("upload_repo")

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
