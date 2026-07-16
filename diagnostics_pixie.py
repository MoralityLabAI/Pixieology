import os
import subprocess
import torch
import shutil
from pathlib import Path

from pixie_env import configure_hf_home, data_root, model_cache_dir, repo_path, tesseract_train_script

configure_hf_home()

def check_drive(path):
    print(f"\n--- Checking Drive: {path} ---")
    p = Path(path)
    if p.exists():
        print(f"Status: Accessible")
        total, used, free = shutil.disk_usage(path)
        print(f"Space: {free // (2**30)} GB free / {total // (2**30)} GB total")
    else:
        print(f"Status: NOT ACCESSIBLE")

def check_gpu():
    print("\n--- Checking GPU Status ---")
    if not torch.cuda.is_available():
        print("CUDA not available.")
        return
    
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    total_memory_gib = torch.cuda.get_device_properties(0).total_memory / (2**30)
    print(f"Total VRAM: {total_memory_gib:.2f} GiB")
    print(f"Memory Allocated: {torch.cuda.memory_allocated(0) // (2**20)} MB")
    print(f"Memory Reserved: {torch.cuda.memory_reserved(0) // (2**20)} MB")
    if total_memory_gib <= 4.5:
        print("Suggested local lane: .\\run_pixie_local_4gb.ps1 -Mode action-train")
        print("Experimental 1.7B lane: .\\run_pixie_local_4gb.ps1 -Mode action-train -ModelSize 1.7B")
    
    try:
        smi = subprocess.check_output(["nvidia-smi"], text=True)
        print("\nNVIDIA-SMI Output:")
        print(smi)
    except:
        print("nvidia-smi command failed.")

def check_paths():
    paths = [
        str(model_cache_dir()),
        str(data_root()),
        str(tesseract_train_script())
    ]
    print("\n--- Checking Key Paths ---")
    for p in paths:
        exists = Path(p).exists()
        print(f"{'[OK]' if exists else '[MISSING]'} {p}")

if __name__ == "__main__":
    print("=== PIXIE STUDIES DIAGNOSTICS ===")
    for root in sorted({Path(data_root()).anchor, Path(repo_path()).anchor}):
        if root:
            check_drive(root)
    check_gpu()
    check_paths()
