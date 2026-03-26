import os
import subprocess
import torch
import shutil
from pathlib import Path

from pixie_env import configure_hf_home

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
    print(f"Memory Allocated: {torch.cuda.memory_allocated(0) // (2**20)} MB")
    print(f"Memory Reserved: {torch.cuda.memory_reserved(0) // (2**20)} MB")
    
    try:
        smi = subprocess.check_output(["nvidia-smi"], text=True)
        print("\nNVIDIA-SMI Output:")
        print(smi)
    except:
        print("nvidia-smi command failed.")

def check_paths():
    paths = [
        "D:/Research_Engine/models",
        "D:/Research_Engine/tesseract_persistent/data",
        "C:/projects/Tesseract/Tesseract/scripts/auto_research_tinylora_loop.py"
    ]
    print("\n--- Checking Key Paths ---")
    for p in paths:
        exists = Path(p).exists()
        print(f"{'[OK]' if exists else '[MISSING]'} {p}")

if __name__ == "__main__":
    print("=== PIXIE STUDIES DIAGNOSTICS ===")
    check_drive("D:/")
    check_drive("C:/")
    check_gpu()
    check_paths()
