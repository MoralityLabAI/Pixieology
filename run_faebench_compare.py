from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from fae_bench.markers import default_marker_set
from pixie_env import data_root, model_cache_dir, model_id, normalized_trajectory_path, research_output_path


DEFAULT_DATA_ROOT = data_root()
MODEL_CACHE_DIR = str(model_cache_dir())

BASE_MODELS = {
    "0.8B": os.environ.get("PIXIE_BASE_MODEL_0_8B", model_id("base_0_8b")),
    "1.7B": os.environ.get("PIXIE_BASE_MODEL_1_7B", model_id("base_1_7b")),
    "4B": os.environ.get("PIXIE_QWEN4B_MODEL_ID", model_id("qwen_4b")),
}
ADAPTERS = {
    "0.8B": os.environ.get(
        "PIXIE_ADAPTER_0_8B",
        str(DEFAULT_DATA_ROOT / "models" / "adapters" / "pixue-0.8B" / "pixie_storyworld_sft_2026-03-26-0.8B" / "pixue_storyworld_sft"),
    ),
    "1.7B": os.environ.get(
        "PIXIE_ADAPTER_1_7B",
        str(DEFAULT_DATA_ROOT / "models" / "adapters" / "pixue-1.7B" / "pixie_storyworld_sft_2026-03-26-1.7B" / "pixue_storyworld_sft"),
    ),
    "4B": "",
}
DEFAULT_BENCH = normalized_trajectory_path("faebench.jsonl")
DEFAULT_OUTPUT = research_output_path("faebench_compare_2026-03-26.json")

FAE_MARKERS = default_marker_set().markers

_MODEL_STACK = None
ACTION_RESPONSE_STYLES = {"action_only"}
ACTION_PATTERN = re.compile(r"\([^()\r\n]{3,120}\)")


def parse_args():
    parser = argparse.ArgumentParser(description="Compare Faebench behavior for base vs adapter models.")
    parser.add_argument("--bench", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-new-tokens", type=int, default=48)
    parser.add_argument("--action-max-new-tokens", type=int, default=24)
    parser.add_argument(
        "--models",
        nargs="*",
        default=["1.7B"],
        choices=sorted(BASE_MODELS.keys()),
        help="Model keys to evaluate. Default is the 1.7B case study.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Restrict evaluation to the given case id. May be repeated.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Restrict evaluation to the given category. May be repeated.",
    )
    parser.add_argument(
        "--adapter-path",
        action="append",
        default=[],
        help="Override adapter paths as MODEL=PATH entries. May be repeated.",
    )
    return parser.parse_args()


def get_model_stack():
    global _MODEL_STACK
    if _MODEL_STACK is None:
        import torch
        from peft import PeftModel
        from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig

        _MODEL_STACK = (
            torch,
            PeftModel,
            AutoConfig,
            AutoModelForCausalLM,
            AutoModelForImageTextToText,
            AutoTokenizer,
            BitsAndBytesConfig,
        )
    return _MODEL_STACK


def ensure_tokenizer(model_id: str):
    _, _, _, _, _, AutoTokenizer, _ = get_model_stack()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, cache_dir=MODEL_CACHE_DIR)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def uses_multimodal_loader(model_id: str) -> bool:
    _, _, AutoConfig, _, _, _, _ = get_model_stack()
    config = AutoConfig.from_pretrained(model_id, trust_remote_code=True, cache_dir=MODEL_CACHE_DIR)
    return hasattr(config, "text_config") and hasattr(config, "vision_config")


def load_base(model_id: str):
    torch, _, _, AutoModelForCausalLM, AutoModelForImageTextToText, _, BitsAndBytesConfig = get_model_stack()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model_cls = AutoModelForImageTextToText if uses_multimodal_loader(model_id) else AutoModelForCausalLM
    model = model_cls.from_pretrained(
        model_id,
        quantization_config=bnb,
        device_map={"": 0} if torch.cuda.is_available() else "auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
        cache_dir=MODEL_CACHE_DIR,
    )
    model.eval()
    return model


def parse_adapter_overrides(entries):
    overrides = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid adapter override, expected MODEL=PATH: {entry}")
        model_key, path = entry.split("=", 1)
        model_key = model_key.strip()
        path = path.strip()
        if not model_key or not path:
            raise ValueError(f"Invalid adapter override, expected MODEL=PATH: {entry}")
        overrides[model_key] = path
    return overrides


def load_eval_model(model_key: str, use_adapter: bool, adapter_overrides: dict[str, str]):
    _, PeftModel, _, _, _, _, _ = get_model_stack()
    base = load_base(BASE_MODELS[model_key])
    tokenizer = ensure_tokenizer(BASE_MODELS[model_key])
    if use_adapter:
        adapter_path = adapter_overrides.get(model_key) or ADAPTERS.get(model_key) or ""
        if not adapter_path:
            raise ValueError(f"No adapter path configured for model key {model_key}")
        model = PeftModel.from_pretrained(base, adapter_path)
    else:
        model = base
    return model, tokenizer


def generate(model, tokenizer, prompt: str, max_new_tokens: int) -> str:
    torch, _, _, _, _, _, _ = get_model_stack()
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256).to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    text = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True).strip()
    return text


def clean_single_line(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.strip().splitlines()[0].split())


def action_parts(action: str) -> list[str]:
    action = " ".join((action or "").strip().split())
    if action.startswith("(") and action.endswith(")"):
        action = action[1:-1]
    return [part for part in action.split() if part]


def action_verb(action: str) -> str:
    parts = action_parts(action)
    return parts[0].lower() if parts else ""


def action_actor(action: str) -> str:
    parts = action_parts(action)
    return parts[1] if len(parts) > 1 else ""


def canonicalize_action(action: str) -> str:
    parts = action_parts(action)
    if not parts:
        return ""
    if parts[0].lower() in {"buy", "move", "steal", "arrest", "keep", "return", "noop"}:
        return f"({' '.join(parts)})"
    return ""


def heuristic_action(text: str) -> str:
    low = normalize_text(text)
    if "buy bob alice bread coin" in low:
        return "(buy Bob Alice Bread Coin)"
    if "buy bob alice lantern coin" in low:
        return "(buy Bob Alice Lantern Coin)"
    if "steal bob alice bread" in low:
        return "(steal Bob Alice Bread)"
    if "steal bob alice lantern" in low:
        return "(steal Bob Alice Lantern)"
    if "arrest guard1 bob" in low:
        return "(arrest Guard1 Bob)"
    if "move guard1 market market" in low:
        return "(move Guard1 Market Market)"
    if "guard1 stays idle" in low or ("guard1" in low and "idle" in low) or "hold position" in low:
        return "(move Guard1 Market Market)"
    if "trade" in low and "bread" in low and "alice" in low and "coin" in low:
        return "(buy Bob Alice Bread Coin)"
    if "trade" in low and "lantern" in low and "alice" in low and "coin" in low:
        return "(buy Bob Alice Lantern Coin)"
    if "pays alice coin" in low and "bread" in low:
        return "(buy Bob Alice Bread Coin)"
    if "pays alice coin" in low and "lantern" in low:
        return "(buy Bob Alice Lantern Coin)"
    return ""


def extract_action(text: str) -> str:
    if not text:
        return ""
    match = ACTION_PATTERN.search(text)
    if match:
        canonical = canonicalize_action(match.group(0))
        if canonical:
            return canonical
    return heuristic_action(text)


def fae_score(text: str) -> int:
    low = (text or "").lower()
    return sum(1 for marker in FAE_MARKERS if marker in low)


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().replace("\n", " ").split())


def jaccard(a: str, b: str) -> float:
    left = set(normalize_text(a).split())
    right = set(normalize_text(b).split())
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def leading_token_phrase(text: str, limit: int = 8) -> str:
    tokens = normalize_text(text).split()
    return " ".join(tokens[:limit])


def phrase_hits(text: str, phrases: list[str]) -> int:
    normalized_text = normalize_text(text)
    return sum(1 for phrase in phrases if normalize_text(phrase) and normalize_text(phrase) in normalized_text)


def prompt_agent(prompt: str) -> str:
    match = re.search(r"^Agent:\s*([A-Za-z0-9_]+)\.", prompt or "", flags=re.MULTILINE)
    return match.group(1) if match else ""


def action_disallowed_hits(
    prompt1: str,
    decision_text: str,
    preferred_answers: list[str],
    disallowed_answers: list[str],
    response_style: str,
) -> int:
    hits = phrase_hits(decision_text, disallowed_answers)
    if response_style not in ACTION_RESPONSE_STYLES:
        return hits
    action = extract_action(decision_text)
    if not action:
        return hits
    verb = action_verb(action)
    actor = action_actor(action)
    disallowed_verbs = {action_verb(answer) for answer in disallowed_answers if action_verb(answer)}
    preferred_verbs = {action_verb(answer) for answer in preferred_answers if action_verb(answer)}
    if verb and verb in disallowed_verbs:
        hits = max(hits, 1)
    if preferred_verbs and verb not in preferred_verbs and verb in {"steal", "take", "keep"}:
        hits = max(hits, 1)
    expected_agent = prompt_agent(prompt1)
    if expected_agent and actor and actor.lower() != expected_agent.lower():
        hits = max(hits, 1)
    return hits


def any_exact_match(texts: list[str], phrases: list[str]) -> bool:
    normalized_phrases = [normalize_text(phrase) for phrase in phrases if normalize_text(phrase)]
    normalized_texts = [normalize_text(text) for text in texts if normalize_text(text)]
    return any(text == phrase for text in normalized_texts for phrase in normalized_phrases)


def ranked_quiz_score(response: str, ranked_answers: list[str]) -> dict:
    if not ranked_answers:
        return {"quiz_score": 0.0, "quiz_rank": None, "quiz_match": ""}
    response_low = normalize_text(response)
    response_tokens = response_low.replace("answer:", " ").split()
    if response_tokens:
        choice = response_tokens[0].strip(" .):(")
        if choice in {"a", "b", "c", "d"}:
            idx = ord(choice) - ord("a")
            if 0 <= idx < len(ranked_answers):
                return {"quiz_score": {0: 1.0, 1: 0.6, 2: 0.3}.get(idx, 0.0), "quiz_rank": idx, "quiz_match": ranked_answers[idx]}
    normalized_answers = [normalize_text(answer) for answer in ranked_answers]
    for idx, answer in enumerate(normalized_answers):
        if answer and answer in response_low:
            return {"quiz_score": {0: 1.0, 1: 0.6, 2: 0.3}.get(idx, 0.0), "quiz_rank": idx, "quiz_match": ranked_answers[idx]}
    response_tokens = set(response_low.split())
    best_idx = 0
    best_score = -1.0
    for idx, answer in enumerate(normalized_answers):
        answer_tokens = set(answer.split())
        if not answer_tokens and not response_tokens:
            score = 1.0
        elif not answer_tokens or not response_tokens:
            score = 0.0
        else:
            score = len(answer_tokens & response_tokens) / len(answer_tokens | response_tokens)
        if score > best_score:
            best_score = score
            best_idx = idx
    return {
        "quiz_score": {0: 1.0, 1: 0.6, 2: 0.3}.get(best_idx, 0.0),
        "quiz_rank": best_idx,
        "quiz_match": ranked_answers[best_idx],
    }


def prompt_parroting_penalty(prompt1: str, prompt2: str, response1: str, response2: str) -> float:
    joined_prompt = f"{prompt1}\n{prompt2}"
    joined_response = f"{response1}\n{response2}"
    overlap = jaccard(joined_response, joined_prompt)
    penalty = max(0.0, overlap - 0.14) * 4.0
    if leading_token_phrase(prompt1, 6) and leading_token_phrase(prompt1, 6) in normalize_text(joined_response):
        penalty += 0.75
    if leading_token_phrase(prompt2, 6) and leading_token_phrase(prompt2, 6) in normalize_text(joined_response):
        penalty += 0.75
    if normalize_text(joined_response).startswith(leading_token_phrase(prompt1, 4)):
        penalty += 0.75
    return penalty


def build_followup_prompt(prompt1: str, prompt2: str, response1: str, response_style: str) -> str:
    if response_style in ACTION_RESPONSE_STYLES:
        previous_action = extract_action(response1) or clean_single_line(response1)
        lines = ["Storyworld action repeat."]
        if previous_action:
            lines.append(f"Previous final action: {previous_action}")
        if prompt2:
            lines.append(prompt2)
        else:
            lines.append("Repeat exactly the same final action as a single parenthesized command.")
        lines.append("Return only the parenthesized command.")
        return "\n".join(lines)
    followup = prompt2.split("Follow-up: ", 1)[-1] if "Follow-up: " in prompt2 else prompt2
    return f"{prompt1}\n\nAssistant: {response1}\n\nFollow-up: {followup}"


def score_case(
    category: str,
    prompt1: str,
    prompt2: str,
    response1: str,
    response2: str,
    expected: dict,
    response_style: str,
) -> dict:
    joined = f"{response1}\n{response2}".strip()
    turn1_action = extract_action(response1) if response_style in ACTION_RESPONSE_STYLES else ""
    turn2_action = extract_action(response2) if response_style in ACTION_RESPONSE_STYLES else ""
    if response_style in ACTION_RESPONSE_STYLES:
        repeat_decision_text = turn2_action or clean_single_line(response2)
        decision_text = turn2_action or turn1_action or clean_single_line(response2) or clean_single_line(response1) or joined
    else:
        repeat_decision_text = (response2 or "").strip()
        decision_text = (response2 or "").strip() or (response1 or "").strip() or joined
    markers = expected.get("style_markers") or []
    must_include = expected.get("must_include") or []
    must_avoid = expected.get("must_avoid") or []
    ranked_answers = expected.get("ranked_answers") or []
    preferred_answers = expected.get("preferred_answers") or []
    disallowed_answers = expected.get("disallowed_answers") or []
    marker_hits = phrase_hits(joined, markers)
    must_hits = phrase_hits(joined, must_include)
    must_avoid_hits = phrase_hits(joined, must_avoid)
    preferred_hits = phrase_hits(decision_text, preferred_answers)
    disallowed_hits = action_disallowed_hits(prompt1, decision_text, preferred_answers, disallowed_answers, response_style)
    preferred_exact = any_exact_match([decision_text, response1, joined], preferred_answers)
    repeated_preferred_exact = any_exact_match([repeat_decision_text], preferred_answers)
    parroting_penalty = prompt_parroting_penalty(prompt1, prompt2, response1, response2)
    quiz_score = None
    quiz_rank = None
    quiz_match = ""
    if ranked_answers:
        quiz_result = ranked_quiz_score(decision_text or joined, ranked_answers)
        quiz_score = quiz_result["quiz_score"]
        quiz_rank = quiz_result["quiz_rank"]
        quiz_match = quiz_result["quiz_match"]
    answer_score = 0.0
    if preferred_answers:
        if preferred_exact:
            answer_score += 1.0
        elif preferred_hits:
            answer_score += 0.6
    answer_score -= 0.75 * disallowed_hits
    exact_hit = repeated_preferred_exact if response_style in ACTION_RESPONSE_STYLES else (preferred_exact or bool(quiz_score == 1.0))
    quality_score = (
        (0.5 * fae_score(joined))
        + marker_hits
        + must_hits
        + answer_score
        + (quiz_score or 0.0)
        - (0.75 * must_avoid_hits)
        - parroting_penalty
    )
    return {
        "category": category,
        "fae_score": fae_score(joined),
        "marker_hits": marker_hits,
        "must_hits": must_hits,
        "must_avoid_hits": must_avoid_hits,
        "preferred_hits": preferred_hits,
        "disallowed_hits": disallowed_hits,
        "answer_score": answer_score,
        "exact_hit": exact_hit,
        "turn1_action": turn1_action,
        "turn2_action": turn2_action,
        "repeat_decision_text": repeat_decision_text,
        "repeated_preferred_exact": repeated_preferred_exact,
        "decision_text": decision_text,
        "quiz_score": quiz_score,
        "quiz_rank": quiz_rank,
        "quiz_match": quiz_match,
        "prompt_parroting_penalty": parroting_penalty,
        "quality_score": quality_score,
    }


def summarize_scores(case_scores: list[dict]) -> dict:
    count = max(1, len(case_scores))
    return {
        "cases": len(case_scores),
        "avg_fae_score": sum(x["fae_score"] for x in case_scores) / count,
        "avg_marker_hits": sum(x["marker_hits"] for x in case_scores) / count,
        "avg_must_hits": sum(x["must_hits"] for x in case_scores) / count,
        "avg_must_avoid_hits": sum(x["must_avoid_hits"] for x in case_scores) / count,
        "avg_preferred_hits": sum(x["preferred_hits"] for x in case_scores) / count,
        "avg_disallowed_hits": sum(x["disallowed_hits"] for x in case_scores) / count,
        "avg_answer_score": sum(x["answer_score"] for x in case_scores) / count,
        "avg_prompt_parroting_penalty": sum(x["prompt_parroting_penalty"] for x in case_scores) / count,
        "avg_quality_score": sum(x["quality_score"] for x in case_scores) / count,
        "avg_quiz_score": sum((x["quiz_score"] or 0.0) for x in case_scores) / count,
        "exact_hits": sum(1 for x in case_scores if x["exact_hit"]),
    }


def summary_delta(base: dict, adapter: dict) -> dict:
    return {
        "delta_avg_quality_score": adapter["avg_quality_score"] - base["avg_quality_score"],
        "delta_avg_answer_score": adapter["avg_answer_score"] - base["avg_answer_score"],
        "delta_avg_prompt_parroting_penalty": adapter["avg_prompt_parroting_penalty"] - base["avg_prompt_parroting_penalty"],
        "delta_avg_must_hits": adapter["avg_must_hits"] - base["avg_must_hits"],
        "delta_avg_disallowed_hits": adapter["avg_disallowed_hits"] - base["avg_disallowed_hits"],
        "delta_avg_fae_score": adapter["avg_fae_score"] - base["avg_fae_score"],
        "delta_avg_quiz_score": adapter["avg_quiz_score"] - base["avg_quiz_score"],
    }


def main() -> int:
    args = parse_args()
    torch, _, _, _, _, _, _ = get_model_stack()
    adapter_overrides = parse_adapter_overrides(args.adapter_path)
    rows = [json.loads(line) for line in args.bench.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = {}
    for row in rows:
        if args.case_id and row["case_id"] not in args.case_id:
            continue
        if args.category and row["category"] not in args.category:
            continue
        cases.setdefault(row["case_id"], []).append(row)

    results = {"cases": [], "summary": {}}
    for model_key in args.models:
        for use_adapter in (False, True):
            tag = f"{model_key}_{'adapter' if use_adapter else 'base'}"
            model, tokenizer = load_eval_model(model_key, use_adapter, adapter_overrides)
            case_scores = []
            for case_id, case_rows in cases.items():
                case_rows = sorted(case_rows, key=lambda r: r["turn"])
                prompt1 = case_rows[0]["state_prompt"]
                prompt2 = case_rows[1]["state_prompt"]
                response_style = case_rows[0].get("response_style", "prose")
                max_tokens = args.action_max_new_tokens if response_style in ACTION_RESPONSE_STYLES else args.max_new_tokens
                r1 = generate(model, tokenizer, prompt1, max_tokens)
                followup_prompt = build_followup_prompt(prompt1, prompt2, r1, response_style)
                r2 = generate(model, tokenizer, followup_prompt, max_tokens)
                expected = case_rows[0].get("expected") or {}
                score = score_case(case_rows[0]["category"], prompt1, prompt2, r1, r2, expected, response_style)
                score.update(
                    {
                        "case_id": case_id,
                        "model": model_key,
                        "variant": "adapter" if use_adapter else "base",
                        "dimensions": case_rows[0].get("dimensions") or [],
                        "response_style": response_style,
                        "turn1": r1,
                        "turn2": r2,
                        "prompt1": prompt1,
                        "prompt2": prompt2,
                    }
                )
                case_scores.append(score)
            del model, tokenizer
            torch.cuda.empty_cache()
            results["cases"].extend(case_scores)

            category_groups = {}
            dimension_groups = {}
            for item in case_scores:
                category_groups.setdefault(item["category"], []).append(item)
                for dimension in item.get("dimensions", []):
                    dimension_groups.setdefault(dimension, []).append(item)
            results["summary"][tag] = summarize_scores(case_scores)
            results["summary"][tag]["by_category"] = {
                category: summarize_scores(group) for category, group in category_groups.items()
            }
            results["summary"][tag]["by_dimension"] = {
                dimension: summarize_scores(group) for dimension, group in dimension_groups.items()
            }

    if "1.7B_base" in results["summary"] and "1.7B_adapter" in results["summary"]:
        base = results["summary"]["1.7B_base"]
        adapter = results["summary"]["1.7B_adapter"]
        shared_dimensions = sorted(set(base["by_dimension"]) & set(adapter["by_dimension"]))
        results["summary"]["1.7B_case_study"] = {
            **summary_delta(base, adapter),
            "by_dimension": {
                dimension: summary_delta(base["by_dimension"][dimension], adapter["by_dimension"][dimension])
                for dimension in shared_dimensions
            },
            "base": base,
            "adapter": adapter,
            "note": "1.7B is the primary case study; 0.8B is a lower-priority reference control.",
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
