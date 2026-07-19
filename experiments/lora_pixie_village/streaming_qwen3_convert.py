#!/usr/bin/env python3
"""Convert the configured BF16 Qwen3 base to GGUF without whole-weight casts.

The pinned llama.cpp converter promotes BF16 tensors to FP32 before converting
them back to BF16.  For a large token embedding that creates a single 1.24 GB
allocation.  This wrapper installs a Qwen3-only conversion method that copies
two-dimensional BF16 weight bytes unchanged and converts only small one-
dimensional/norm tensors to F32, matching llama.cpp's intended output types.

This is a format converter, not a quantizer.  It refuses non-BF16 source
weights and output types other than BF16 so an unexpected model cannot silently
take the specialized path.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from itertools import chain
from pathlib import Path
from typing import Any, Iterable


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import existing_adapter_pair  # noqa: E402


class StreamingConversionError(RuntimeError):
    """Raised when the source is not eligible for the exact BF16 fast path."""


def raw_bf16_bytes(tensor: Any) -> Any:
    """Return a zero-copy uint8 view of an eager or llama.cpp lazy BF16 tensor."""
    import torch

    if tensor.dtype != torch.bfloat16:
        raise StreamingConversionError(f"expected BF16 tensor, got {tensor.dtype}")
    return tensor.view(torch.uint8).numpy()


def output_qtype(*, n_dims: int, new_name: str, forced: Any, gguf: Any) -> Any:
    """Select the same relevant GGUF type as the stock converter for Qwen3."""
    if n_dims <= 1 or new_name.endswith("_norm.weight"):
        return gguf.GGMLQuantizationType.F32
    if isinstance(forced, bool):
        return gguf.GGMLQuantizationType.BF16
    return forced


def make_streaming_prepare(torch: Any, np: Any, gguf: Any, logger: Any):
    """Build the patched Qwen3 prepare_tensors method around pinned modules."""

    def prepare_tensors(self: Any) -> None:
        if self.ftype != gguf.LlamaFileType.MOSTLY_BF16:
            raise StreamingConversionError(
                f"streaming converter requires MOSTLY_BF16, got {self.ftype.name}"
            )
        if self.is_big_endian:
            raise StreamingConversionError("raw BF16 streaming currently supports little-endian output only")

        self.dequant_model()
        max_name_len = (
            max(len(name) for _, name in self.tensor_map.mapping.values()) + len(".weight,")
            if self.tensor_map.mapping
            else len("weight,")
        )
        source_count = 0
        raw_bf16_count = 0
        converted_f32_count = 0

        for name, source_tensor in chain(self.generate_extra_tensors(), self.get_tensors()):
            if name.endswith((".attention.masked_bias", ".attention.bias", ".rotary_emb.inv_freq")):
                continue
            source_count += 1
            if source_tensor.dtype != torch.bfloat16:
                raise StreamingConversionError(
                    f"source tensor {name} is {source_tensor.dtype}; every source tensor must be BF16"
                )
            block_id = next((int(part) for part in name.split(".") if part.isdecimal()), None)

            for new_name, tensor in self.modify_tensors(source_tensor, name, block_id):
                n_dims = len(tensor.shape)
                forced = self.tensor_force_quant(name, new_name, block_id, n_dims)
                data_qtype = output_qtype(n_dims=n_dims, new_name=new_name, forced=forced, gguf=gguf)

                if data_qtype == gguf.GGMLQuantizationType.BF16:
                    if not new_name.endswith(".weight"):
                        raise StreamingConversionError(
                            f"refusing raw BF16 for unexpected non-weight tensor {new_name}"
                        )
                    data = raw_bf16_bytes(tensor)
                    raw_bf16_count += 1
                else:
                    eager_type = tensor.dtype
                    if eager_type not in (torch.float16, torch.float32):
                        tensor = tensor.to(torch.float32)
                    data = gguf.quants.quantize(tensor.numpy(), data_qtype)
                    converted_f32_count += 1

                shape = (
                    gguf.quant_shape_from_byte_shape(data.shape, data_qtype)
                    if data.dtype == np.uint8
                    else data.shape
                )
                shape_text = "{" + ", ".join(str(value) for value in reversed(shape)) + "}"
                logger.info(
                    f"{f'%-{max_name_len}s' % f'{new_name},'} "
                    f"torch.bfloat16 --> {data_qtype.name}, shape = {shape_text}"
                )
                self.gguf_writer.add_tensor(new_name, data, raw_dtype=data_qtype)

        if source_count == 0 or raw_bf16_count == 0 or converted_f32_count == 0:
            raise StreamingConversionError(
                "conversion did not observe the expected mixture of BF16 matrices and F32 norms"
            )
        self._pixie_streaming_counts = {
            "source_tensors": source_count,
            "raw_bf16_tensors": raw_bf16_count,
            "converted_f32_tensors": converted_f32_count,
        }

    return prepare_tensors


def install_patch(llama_cpp_root: Path) -> tuple[Any, dict[str, Any]]:
    """Load the pinned converter modules and patch only Qwen3Model."""
    converter = llama_cpp_root / "convert_hf_to_gguf.py"
    if not converter.is_file():
        raise StreamingConversionError(f"missing converter: {converter}")
    sys.path.insert(0, str(llama_cpp_root))
    sys.path.insert(1, str(llama_cpp_root / "gguf-py"))

    import numpy as np
    import torch
    import gguf
    from conversion import logger
    from conversion.qwen import Qwen3Model

    Qwen3Model.prepare_tensors = make_streaming_prepare(torch, np, gguf, logger)
    spec = importlib.util.spec_from_file_location("pixie_pinned_convert_hf_to_gguf", converter)
    if spec is None or spec.loader is None:
        raise StreamingConversionError(f"cannot import converter: {converter}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, {
        "converter": str(converter),
        "converter_sha256": existing_adapter_pair.sha256_file(converter),
        "llama_cpp_root": str(llama_cpp_root),
        "patch": "qwen3_exact_bf16_matrix_bytes_v1",
    }


def convert(config_path: Path, outfile: Path, receipt_path: Path, *, use_temp_file: bool) -> dict[str, Any]:
    paths = existing_adapter_pair.resolve_config_paths(config_path)
    base = paths["lora_pixie_josie_1p7b_base_hf"]
    llama_cpp_root = paths["lora_pixie_prism_llama_cpp_root"]
    module, provenance = install_patch(llama_cpp_root)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    original_argv = sys.argv[:]
    converter_argv = [str(module.__file__), str(base), "--outfile", str(outfile), "--outtype", "bf16"]
    if use_temp_file:
        converter_argv.append("--use-temp-file")
    try:
        sys.argv = converter_argv
        module.main()
    finally:
        sys.argv = original_argv
    if not outfile.is_file():
        raise StreamingConversionError(f"converter returned without output: {outfile}")
    receipt = {
        "schema_version": "pixie_qwen3_streaming_bf16_conversion_v1",
        "status": "PASS",
        "base": str(base),
        "base_config_sha256": existing_adapter_pair.sha256_file(base / "config.json"),
        "source_model_sha256": existing_adapter_pair.sha256_file(base / "model.safetensors"),
        "output": str(outfile),
        "output_bytes": outfile.stat().st_size,
        "output_sha256": existing_adapter_pair.sha256_file(outfile),
        "use_temp_file": use_temp_file,
        "provenance": provenance,
        "note": "All 2D BF16 matrices were copied bit-exactly; only 1D/norm tensors were converted to F32.",
    }
    existing_adapter_pair.atomic_json(receipt_path, receipt)
    return receipt


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "pixieology.config.json")
    parser.add_argument("--outfile", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--use-temp-file", action="store_true")
    args = parser.parse_args(argv)
    result = convert(
        args.config.expanduser().resolve(),
        args.outfile.expanduser().resolve(),
        args.receipt.expanduser().resolve(),
        use_temp_file=args.use_temp_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
