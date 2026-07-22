"""Read-only WSL package and CUDA availability report."""

from __future__ import annotations

import importlib.util
import json
import os
import platform


packages = {}
for name in ("torch", "transformers", "peft", "bitsandbytes", "numpy", "safetensors"):
    packages[name] = importlib.util.find_spec(name) is not None

torch_receipt = None
if packages["torch"]:
    import torch

    torch_receipt = {
        "version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
    }

print(
    json.dumps(
        {
            "platform": platform.platform(),
            "uid": os.getuid(),
            "packages": packages,
            "torch": torch_receipt,
            "cgroup_v2": os.path.isfile("/sys/fs/cgroup/cgroup.controllers"),
        },
        indent=2,
        sort_keys=True,
    )
)
