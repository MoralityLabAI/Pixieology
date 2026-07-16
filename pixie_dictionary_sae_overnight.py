from __future__ import annotations

from pixie_env import configure_hf_home, data_root, model_cache_dir, model_id, repo_path, steering_layer

configure_hf_home()

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.decomposition import DictionaryLearning
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


DEFAULT_MODEL_ID = model_id("pixie_1_7b")
DEFAULT_SEED_PATH = Path("fae_constitution_seed.jsonl")
DEFAULT_SYNTH_PATH = Path("synthesized_pixie_dataset.jsonl")
DEFAULT_OUTPUT_ROOT = data_root() / "pixie_research" / "pixie_dictionary_sae_overnight"
DEFAULT_LAYERS = list(range(max(0, steering_layer() - 4), steering_layer() + 1))


def parse_args():
    parser = argparse.ArgumentParser(description="Overnight dictionary-probe and SAE sweep for the Fae Pixie 1.7B model.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--seed-path", type=Path, default=repo_path(str(DEFAULT_SEED_PATH)))
    parser.add_argument("--synth-path", type=Path, default=repo_path(str(DEFAULT_SYNTH_PATH)))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--layers", nargs="*", type=int, default=DEFAULT_LAYERS)
    parser.add_argument("--max-pairs", type=int, default=30)
    parser.add_argument("--dictionary-components", type=int, default=96)
    parser.add_argument("--sae-width", type=int, default=256)
    parser.add_argument("--sae-epochs", type=int, default=60)
    parser.add_argument("--sae-batch-size", type=int, default=16)
    parser.add_argument("--sae-lr", type=float, default=1e-3)
    parser.add_argument("--sae-l1", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--cache-dir", type=Path, default=model_cache_dir())
    return parser.parse_args()


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_prompt_sets(seed_rows, synth_rows, max_pairs):
    plain = []
    fae = []
    ridge = []
    lantern = []

    for row in seed_rows:
        prompt = row.get("state_prompt", "")
        mode = row.get("mode", "")
        if not prompt:
            continue
        if mode == "plain":
            plain.append(prompt)
            fae_prompt = prompt + "\n\n[[FAE_TOGGLE]]"
            fae.append(fae_prompt)
            ridge.append(prompt + "\n\n[[FAE_RIDGE]]")
            lantern.append(prompt + "\n\n[[FAE_LANTERN]]")
        elif mode == "fae":
            fae.append(prompt)

    for row in synth_rows:
        prompt = row.get("state_prompt", "")
        mode = row.get("mode", "")
        if not prompt:
            continue
        if mode == "fae":
            fae.append(prompt)
            plain.append(prompt.replace("\n\n[[FAE_TOGGLE]]", "").replace("[[FAE_TOGGLE]]", ""))

    plain = [p for p in plain if p]
    fae = [p for p in fae if p]
    ridge = [p for p in ridge if p]
    lantern = [p for p in lantern if p]

    return {
        "plain": plain[:max_pairs],
        "fae": fae[:max_pairs],
        "ridge": ridge[:max_pairs],
        "lantern": lantern[:max_pairs],
    }


def ensure_pad_token(tokenizer):
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def load_model(model_id: str, cache_root: Path):
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = ensure_pad_token(
        AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, cache_dir=str(cache_root))
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        cache_dir=str(cache_root),
    )
    model.eval()
    return model, tokenizer


def normalize_layers(model, requested_layers):
    layer_count = len(model.model.layers)
    layers = []
    for idx in requested_layers:
        if idx < 0:
            idx = layer_count + idx
        if 0 <= idx < layer_count:
            layers.append(idx)
    if not layers:
        raise RuntimeError("No valid layers selected for probing.")
    return layers


def capture_layer_activations(model, tokenizer, prompt, layers):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    activations = {}
    handles = []

    def make_hook(layer_idx):
        def hook(_module, _input, output):
            h = output[0] if isinstance(output, tuple) else output
            activations[layer_idx] = h[:, -1, :].detach().cpu().to(torch.float32).squeeze(0)

        return hook

    for layer_idx in layers:
        handles.append(model.model.layers[layer_idx].register_forward_hook(make_hook(layer_idx)))

    with torch.no_grad():
        _ = model(inputs.input_ids)

    for handle in handles:
        handle.remove()
    return activations


def collect_activation_cache(model, tokenizer, prompt_sets, layers, cache_path: Path):
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu")

    cache = {layer: {name: [] for name in prompt_sets} for layer in layers}
    for name, prompts in prompt_sets.items():
        for prompt in prompts:
            layer_acts = capture_layer_activations(model, tokenizer, prompt, layers)
            for layer_idx, act in layer_acts.items():
                cache[layer_idx][name].append(act)

    for layer_idx in layers:
        for name in prompt_sets:
            if cache[layer_idx][name]:
                cache[layer_idx][name] = torch.stack(cache[layer_idx][name], dim=0)
            else:
                cache[layer_idx][name] = torch.empty(0)

    torch.save(cache, cache_path)
    return cache


class SparseAutoencoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.encoder = nn.Linear(input_dim, hidden_dim)
        self.decoder = nn.Linear(hidden_dim, input_dim)

    def forward(self, x):
        hidden = torch.relu(self.encoder(x))
        recon = self.decoder(hidden)
        return recon, hidden


def train_sae(x_train, hidden_dim, epochs, batch_size, lr, l1_weight):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SparseAutoencoder(x_train.shape[1], hidden_dim).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    mse = nn.MSELoss()

    tensor = torch.tensor(x_train, dtype=torch.float32)
    loader = torch.utils.data.DataLoader(tensor, batch_size=batch_size, shuffle=True)

    for _ in range(epochs):
        for batch in loader:
            batch = batch.to(device)
            recon, hidden = model(batch)
            loss = mse(recon, batch) + l1_weight * hidden.abs().mean()
            opt.zero_grad()
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        x = torch.tensor(x_train, dtype=torch.float32).to(device)
        recon, hidden = model(x)
        recon_mse = mse(recon, x).item()
        sparsity = (hidden.abs() < 1e-4).float().mean().item()
    return model.cpu(), recon_mse, sparsity


def fit_dictionary(x_train, n_components, seed):
    dictionary = DictionaryLearning(
        n_components=n_components,
        random_state=seed,
        max_iter=250,
        alpha=1.0,
        transform_algorithm="lasso_lars",
        fit_algorithm="lars",
    )
    codes = dictionary.fit_transform(x_train)
    recon = codes @ dictionary.components_
    mse = float(np.mean((x_train - recon) ** 2))
    sparsity = float(np.mean(np.abs(codes) < 1e-4))
    return dictionary, codes, mse, sparsity


def summarize_codes(codes_plain, codes_fae, codes_ridge, codes_lantern):
    plain_mean = codes_plain.mean(axis=0)
    fae_mean = codes_fae.mean(axis=0)
    ridge_mean = codes_ridge.mean(axis=0) if len(codes_ridge) else None
    lantern_mean = codes_lantern.mean(axis=0) if len(codes_lantern) else None

    delta = fae_mean - plain_mean
    top = np.argsort(np.abs(delta))[-8:][::-1]
    summary = {
        "plain_mean_norm": float(np.linalg.norm(plain_mean)),
        "fae_mean_norm": float(np.linalg.norm(fae_mean)),
        "delta_norm": float(np.linalg.norm(delta)),
        "top_indices": top.tolist(),
        "top_deltas": [float(delta[i]) for i in top],
        "ridge_mean_norm": float(np.linalg.norm(ridge_mean)) if ridge_mean is not None else None,
        "lantern_mean_norm": float(np.linalg.norm(lantern_mean)) if lantern_mean is not None else None,
    }
    return summary


def run_probe_layer(layer_idx, cache, out_dir, args):
    layer_dir = out_dir / f"layer_{layer_idx:02d}"
    layer_dir.mkdir(parents=True, exist_ok=True)
    summary_path = layer_dir / "summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))

    plain = cache[layer_idx]["plain"].numpy()
    fae = cache[layer_idx]["fae"].numpy()
    ridge = cache[layer_idx]["ridge"].numpy()
    lantern = cache[layer_idx]["lantern"].numpy()

    x_train = np.concatenate([plain, fae], axis=0)
    y_train = np.array([0] * len(plain) + [1] * len(fae))

    dict_model, dict_codes, dict_mse, dict_sparsity = fit_dictionary(x_train, args.dictionary_components, args.seed)
    dict_probe = LogisticRegression(max_iter=2000, random_state=args.seed)
    dict_probe.fit(dict_codes, y_train)
    dict_train_acc = accuracy_score(y_train, dict_probe.predict(dict_codes))
    dict_train_prob = dict_probe.predict_proba(dict_codes)[:, 1]

    dict_plain_codes = dict_model.transform(plain)
    dict_fae_codes = dict_model.transform(fae)
    dict_ridge_codes = dict_model.transform(ridge) if len(ridge) else np.empty((0, dict_codes.shape[1]))
    dict_lantern_codes = dict_model.transform(lantern) if len(lantern) else np.empty((0, dict_codes.shape[1]))
    dict_eval_summary = summarize_codes(dict_plain_codes, dict_fae_codes, dict_ridge_codes, dict_lantern_codes)

    sae_model, sae_mse, sae_sparsity = train_sae(
        x_train,
        args.sae_width,
        args.sae_epochs,
        args.sae_batch_size,
        args.sae_lr,
        args.sae_l1,
    )
    with torch.no_grad():
        sae_plain = sae_model.encoder(torch.tensor(plain, dtype=torch.float32)).relu().numpy()
        sae_fae = sae_model.encoder(torch.tensor(fae, dtype=torch.float32)).relu().numpy()
        sae_ridge = sae_model.encoder(torch.tensor(ridge, dtype=torch.float32)).relu().numpy() if len(ridge) else np.empty((0, args.sae_width))
        sae_lantern = sae_model.encoder(torch.tensor(lantern, dtype=torch.float32)).relu().numpy() if len(lantern) else np.empty((0, args.sae_width))

    sae_codes = np.concatenate([sae_plain, sae_fae], axis=0)
    sae_probe = LogisticRegression(max_iter=2000, random_state=args.seed)
    sae_probe.fit(sae_codes, y_train)
    sae_train_acc = accuracy_score(y_train, sae_probe.predict(sae_codes))

    dict_summary = {
        "reconstruction_mse": dict_mse,
        "sparsity": dict_sparsity,
        "probe_train_accuracy": dict_train_acc,
        "probe_train_logloss": float(log_loss(y_train, dict_probe.predict_proba(dict_codes))),
        "probe_mean_fae_prob": float(dict_train_prob[y_train == 1].mean()) if np.any(y_train == 1) else None,
        "probe_mean_plain_prob": float(dict_train_prob[y_train == 0].mean()) if np.any(y_train == 0) else None,
        "code_summary": dict_eval_summary,
        "top_atoms": [
            {"atom": int(i), "delta": float(dict_eval_summary["top_deltas"][j])}
            for j, i in enumerate(dict_eval_summary["top_indices"])
        ],
    }

    sae_delta = sae_fae.mean(axis=0) - sae_plain.mean(axis=0)
    sae_top = np.argsort(np.abs(sae_delta))[-8:][::-1]
    sae_summary = {
        "reconstruction_mse": sae_mse,
        "sparsity": sae_sparsity,
        "probe_train_accuracy": sae_train_acc,
        "top_units": [{"unit": int(i), "delta": float(sae_delta[i])} for i in sae_top],
        "plain_mean_norm": float(np.linalg.norm(sae_plain.mean(axis=0))),
        "fae_mean_norm": float(np.linalg.norm(sae_fae.mean(axis=0))),
        "ridge_mean_norm": float(np.linalg.norm(sae_ridge.mean(axis=0))) if len(sae_ridge) else None,
        "lantern_mean_norm": float(np.linalg.norm(sae_lantern.mean(axis=0))) if len(sae_lantern) else None,
    }

    result = {
        "layer": layer_idx,
        "train_count": int(len(x_train)),
        "plain_count": int(len(plain)),
        "fae_count": int(len(fae)),
        "ridge_count": int(len(ridge)),
        "lantern_count": int(len(lantern)),
        "dictionary": dict_summary,
        "sae": sae_summary,
    }

    torch.save(
        {
            "dictionary_components": dict_model.components_,
            "dictionary_probe_coef": dict_probe.coef_,
            "dictionary_probe_intercept": dict_probe.intercept_,
            "sae_state_dict": sae_model.state_dict(),
        },
        layer_dir / "artifacts.pt",
    )
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    args = parse_args()
    if args.max_pairs <= 0:
        print(f"ERROR: max-pairs must be > 0, got {args.max_pairs}")
        return 1
    if args.dictionary_components <= 0:
        print(f"ERROR: dictionary-components must be > 0, got {args.dictionary_components}")
        return 1
    if args.sae_width <= 0:
        print(f"ERROR: sae-width must be > 0, got {args.sae_width}")
        return 1
    if args.sae_epochs <= 0 or args.sae_batch_size <= 0:
        print(f"ERROR: SAE epochs and batch size must be > 0, got epochs={args.sae_epochs}, batch_size={args.sae_batch_size}")
        return 1
    if not args.seed_path.exists():
        print(f"ERROR: seed path does not exist: {args.seed_path}")
        return 1
    if not args.synth_path.exists():
        print(f"ERROR: synth path does not exist: {args.synth_path}")
        return 1

    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "manifest.json"
    log_path = args.output_root / "overnight_log.jsonl"
    cache_path = args.output_root / "activation_cache.pt"

    seed_rows = load_jsonl(args.seed_path)
    synth_rows = load_jsonl(args.synth_path)
    prompt_sets = build_prompt_sets(seed_rows, synth_rows, args.max_pairs)
    manifest_path.write_text(
        json.dumps(
            {
                "model_id": args.model_id,
                "seed_path": str(args.seed_path),
                "synth_path": str(args.synth_path),
                "layers": args.layers,
                "max_pairs": args.max_pairs,
                "dictionary_components": args.dictionary_components,
                "sae_width": args.sae_width,
                "sae_epochs": args.sae_epochs,
                "sae_batch_size": args.sae_batch_size,
                "sae_lr": args.sae_lr,
                "sae_l1": args.sae_l1,
                "prompt_counts": {k: len(v) for k, v in prompt_sets.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    model, tokenizer = load_model(args.model_id, args.cache_dir)
    layers = normalize_layers(model, args.layers)
    cache = collect_activation_cache(model, tokenizer, prompt_sets, layers, cache_path)

    with open(log_path, "a", encoding="utf-8") as log:
        log.write(json.dumps({"event": "start", "layers": layers, "ts": time.time()}) + "\n")

    summaries = []
    for layer_idx in layers:
        result = run_probe_layer(layer_idx, cache, args.output_root, args)
        summaries.append(result)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps({"event": "layer_complete", "layer": layer_idx, "summary": result}) + "\n")

    final_path = args.output_root / "final_summary.json"
    final_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(json.dumps({"event": "finish", "ts": time.time(), "final_path": str(final_path)}) + "\n")

    print(json.dumps({"final_path": str(final_path), "layers": layers}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
