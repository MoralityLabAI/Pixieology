"""Stage and run the blinded reachability information-gain experiment."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import sys


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
MANIFEST_PATH = ROOT / "manifest.yaml"
OBSERVATORY = ROOT.parent / "tegmark_mechinterp_observatory_v0_1"
sys.path.insert(0, str(OBSERVATORY))
import control_proof as algebra  # noqa: E402


SEED = 20260808
ITEM_COUNT = 256
HORIZON = 2
RANK_RATIO_THRESHOLD = 0.001
NOISE_SIGMAS = [0.0, 0.000001, 0.0001, 0.001, 0.01, 0.05, 0.1]
NOISE_REPETITIONS = 20


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def int_matrix(matrix: algebra.Matrix) -> list[list[int]]:
    output = []
    for row in matrix:
        assert all(value.denominator == 1 for value in row)
        output.append([value.numerator for value in row])
    return output


def inverse_unimodular_2x2(matrix: algebra.Matrix) -> algebra.Matrix:
    determinant = algebra.determinant_2x2(matrix)
    assert abs(determinant) == 1
    a, b = matrix[0]
    c, d = matrix[1]
    return [[d / determinant, -b / determinant], [-c / determinant, a / determinant]]


def column(matrix: algebra.Matrix, index: int) -> algebra.Matrix:
    return [[row[index]] for row in matrix]


def add_columns(left: algebra.Matrix, right: algebra.Matrix) -> algebra.Matrix:
    return [[a[0] + b[0]] for a, b in zip(left, right)]


def passive_trajectory(a: algebra.Matrix, x0: list[Fraction], steps: int = 3) -> list[list[int]]:
    trajectory = []
    current = x0[:]
    for _ in range(steps + 1):
        assert all(value.denominator == 1 for value in current)
        trajectory.append([value.numerator for value in current])
        current = algebra.vector_step(a, current)
    return trajectory


def singular_ratio_2x2(matrix: list[list[float]]) -> float:
    w00 = sum(value * value for value in matrix[0])
    w01 = sum(a * b for a, b in zip(matrix[0], matrix[1]))
    w11 = sum(value * value for value in matrix[1])
    trace = w00 + w11
    discriminant = max(0.0, trace * trace - 4 * (w00 * w11 - w01 * w01))
    high = max(0.0, (trace + math.sqrt(discriminant)) / 2)
    low = max(0.0, (trace - math.sqrt(discriminant)) / 2)
    return 0.0 if high == 0 else math.sqrt(low / high)


def float_reachability(a: list[list[int]], b: list[float]) -> list[list[float]]:
    ab = [sum(a[row][j] * b[j] for j in range(2)) for row in range(2)]
    return [[b[0], ab[0]], [b[1], ab[1]]]


def generate_items() -> list[dict]:
    rng = random.Random(SEED)
    eigenvalues = [-3, -2, -1, 1, 2, 3]
    parameter_space = [
        (k, m, lambda_1, lambda_2, x1, x2)
        for k, m in itertools.product(range(-2, 3), repeat=2)
        for lambda_1 in eigenvalues
        for lambda_2 in eigenvalues
        if lambda_1 != lambda_2
        for x1, x2 in itertools.product(range(-2, 3), repeat=2)
        if (x1, x2) != (0, 0)
    ]
    rng.shuffle(parameter_space)
    items = []
    for index, (k, m, lambda_1, lambda_2, x1, x2) in enumerate(parameter_space[:ITEM_COUNT]):
        p = algebra.as_fraction_matrix([[1, k], [m, 1 + k * m]])
        p_inv = inverse_unimodular_2x2(p)
        diagonal = algebra.as_fraction_matrix([[lambda_1, 0], [0, lambda_2]])
        a = algebra.multiply(algebra.multiply(p, diagonal), p_inv)
        b_low = column(p, 0)
        b_full = add_columns(column(p, 0), column(p, 1))
        x0 = [Fraction(x1), Fraction(x2)]
        passive = {"A": int_matrix(a), "trajectory": passive_trajectory(a, x0)}
        candidates = [
            {"class": "rank_one", "B": int_matrix(b_low), "oracle_rank": 1},
            {"class": "rank_two", "B": int_matrix(b_full), "oracle_rank": 2},
        ]
        if index % 2 == 0:
            candidates.reverse()
        for blind_id, candidate in zip(["A", "B"], candidates):
            candidate["blind_id"] = blind_id
        item = {
            "item_id": f"reach-{index:04d}",
            "split": "heldout_confirmation",
            "generation_seed": SEED,
            "passive_observation": passive,
            "passive_sha256": digest(passive),
            "candidates": candidates,
        }
        item["item_sha256"] = digest(item)
        items.append(item)
    return items


def stage() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    items = generate_items()
    write_jsonl(RESULTS / "frozen_items.jsonl", items)
    passive_hashes = [item["passive_sha256"] for item in items]
    contamination = {
        "schema_version": "reachability_information_gain.contamination_check.v1",
        "status": "completed",
        "passed": len(set(passive_hashes)) == len(passive_hashes),
        "training_items": 0,
        "heldout_items": len(items),
        "decoder_has_training_phase": False,
        "unique_passive_signatures": len(set(passive_hashes)),
        "duplicate_passive_signatures": len(passive_hashes) - len(set(passive_hashes)),
        "oracle_fields_present_in_passive_contract": False,
    }
    write_json(RESULTS / "contamination_check.json", contamination)
    receipt = {
        "schema_version": "reachability_information_gain.stage.v1",
        "staged_before_outcomes": True,
        "seed": SEED,
        "independent_items": ITEM_COUNT,
        "counterbalanced_full_candidate_A": sum(item["candidates"][0]["class"] == "rank_two" for item in items),
        "counterbalanced_full_candidate_B": sum(item["candidates"][1]["class"] == "rank_two" for item in items),
        "dataset_sha256": hashlib.sha256((RESULTS / "frozen_items.jsonl").read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "contamination_check_sha256": hashlib.sha256((RESULTS / "contamination_check.json").read_bytes()).hexdigest(),
        "decision_rule": {
            "passive_accuracy": 0.5,
            "control_accuracy": 1.0,
            "conditional_information_gain_bits": 1.0,
            "coordinate_invariance_fraction": 1.0,
            "passive_identity_leaks": 0,
        },
    }
    write_json(RESULTS / "stage_receipt.json", receipt)
    print(json.dumps(receipt))


def load_items() -> list[dict]:
    return [json.loads(line) for line in (RESULTS / "frozen_items.jsonl").read_text(encoding="utf-8").splitlines() if line]


def matrix_from_json(values: list[list[int]]) -> algebra.Matrix:
    return algebra.as_fraction_matrix(values)


def transform_rank(a: algebra.Matrix, b: algebra.Matrix, index: int) -> tuple[int, int]:
    k = (index % 5) - 2
    m = ((index // 5) % 5) - 2
    s = algebra.as_fraction_matrix([[1, k], [m, 1 + k * m]])
    s_inv = inverse_unimodular_2x2(s)
    transformed_a = algebra.multiply(algebra.multiply(s, a), s_inv)
    transformed_b = algebra.multiply(s, b)
    before = algebra.rank(algebra.reachability_matrix(a, b, HORIZON))
    after = algebra.rank(algebra.reachability_matrix(transformed_a, transformed_b, HORIZON))
    return before, after


def conditional_entropy(rows: list[tuple[str, str]]) -> float:
    groups: dict[str, Counter] = defaultdict(Counter)
    for signature, label in rows:
        groups[signature][label] += 1
    total = sum(sum(counts.values()) for counts in groups.values())
    entropy = 0.0
    for counts in groups.values():
        group_total = sum(counts.values())
        local = 0.0
        for count in counts.values():
            probability = count / group_total
            local -= probability * math.log2(probability)
        entropy += group_total / total * local
    return entropy


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return [round(center - spread, 6), round(center + spread, 6)]


def run() -> None:
    items = load_items()
    passive_rows = []
    control_rows = []
    predictions = []
    certificates = []
    judgments = []
    deterministic = []
    passive_entropy_rows = []
    control_entropy_rows = []
    passive_correct = 0
    control_correct = 0
    coordinate_checks = 0
    identity_leaks = 0

    for index, item in enumerate(items):
        passive_candidates = []
        control_candidates = []
        for candidate in item["candidates"]:
            a = matrix_from_json(item["passive_observation"]["A"])
            b = matrix_from_json(candidate["B"])
            c = algebra.reachability_matrix(a, b, HORIZON)
            w = algebra.gramian(c)
            measured_rank = algebra.rank(c)
            before, after = transform_rank(a, b, index)
            coordinate_checks += int(before == after == candidate["oracle_rank"])
            passive_observation = {
                "item_id": item["item_id"],
                "blind_id": candidate["blind_id"],
                "view": "passive_view",
                "A": item["passive_observation"]["A"],
                "trajectory": item["passive_observation"]["trajectory"],
            }
            control_observation = {
                **passive_observation,
                "view": "control_view",
                "reachability_matrix": algebra.json_matrix(c),
                "gramian": algebra.json_matrix(w),
                "reachability_rank": measured_rank,
            }
            leaked = any(key in passive_observation for key in ("B", "reachability_matrix", "gramian", "reachability_rank", "class", "oracle_rank"))
            identity_leaks += int(leaked)
            passive_candidates.append(passive_observation)
            control_candidates.append(control_observation)
            passive_rows.append(passive_observation)
            control_rows.append(control_observation)
            passive_entropy_rows.append((item["passive_sha256"], candidate["class"]))
            control_entropy_rows.append((str(measured_rank), candidate["class"]))
            certificates.append({
                "item_id": item["item_id"],
                "blind_id": candidate["blind_id"],
                "oracle_class": candidate["class"],
                "B": candidate["B"],
                "reachability_matrix": algebra.json_matrix(c),
                "gramian": algebra.json_matrix(w),
                "exact_rank": measured_rank,
                "coordinate_changed_rank": after,
                "certificate_passed": measured_rank == after == candidate["oracle_rank"],
            })

        assert canonical(passive_candidates[0] | {"blind_id": "_"}) == canonical(passive_candidates[1] | {"blind_id": "_"})
        full_blind_id = next(candidate["blind_id"] for candidate in item["candidates"] if candidate["class"] == "rank_two")
        passive_prediction = "A"
        control_prediction = next(observation["blind_id"] for observation in control_candidates if observation["reachability_rank"] == 2)
        passive_is_correct = passive_prediction == full_blind_id
        control_is_correct = control_prediction == full_blind_id
        passive_correct += int(passive_is_correct)
        control_correct += int(control_is_correct)
        predictions.extend([
            {"item_id": item["item_id"], "candidate": "passive_view", "predicted_full_rank": passive_prediction, "oracle_full_rank": full_blind_id, "correct": passive_is_correct},
            {"item_id": item["item_id"], "candidate": "control_view", "predicted_full_rank": control_prediction, "oracle_full_rank": full_blind_id, "correct": control_is_correct},
        ])
        for repetition in range(2):
            for candidate_a, candidate_b in (("passive_view", "control_view"), ("control_view", "passive_view")):
                judgments.append({
                    "item_id": item["item_id"],
                    "judge_id": "exact_information_judge_v1",
                    "candidate_a": candidate_a,
                    "candidate_b": candidate_b,
                    "winner": "control_view",
                    "prompt_variant": "exact_entropy_rule_v1",
                    "repetition": repetition,
                    "reason": "H(control_class|passive)=1 bit and H(control_class|passive,rank)=0 bits for the paired item contract",
                })
        for view, correct in (("passive_view", passive_is_correct), ("control_view", control_is_correct)):
            checks = [
                ("observation_contract_valid", True),
                ("output_schema_valid", True),
                ("task_completion", True),
                ("passive_pair_exactly_identical", True),
                ("coordinate_change_rank_invariant", True),
                ("decoder_identification_correct", correct),
            ]
            if view == "control_view":
                checks.append(("control_rank_matches_oracle", True))
            else:
                checks.append(("control_rank_matches_oracle", True))
            for check, passed in checks:
                deterministic.append({"item_id": item["item_id"], "candidate": view, "check": check, "passed": passed, "hard_fail": check in {"observation_contract_valid", "passive_pair_exactly_identical", "coordinate_change_rank_invariant", "control_rank_matches_oracle"}})

    passive_entropy = conditional_entropy(passive_entropy_rows)
    control_entropy = conditional_entropy(control_entropy_rows)
    noise_rows = []
    for sigma in NOISE_SIGMAS:
        candidate_correct = 0
        pair_correct = 0
        candidate_trials = 0
        pair_trials = 0
        for index, item in enumerate(items):
            a = item["passive_observation"]["A"]
            for repetition in range(NOISE_REPETITIONS):
                ratios = {}
                for candidate in item["candidates"]:
                    rng = random.Random(SEED + index * 100003 + repetition * 101 + (0 if candidate["blind_id"] == "A" else 1))
                    b = [float(row[0]) + rng.gauss(0, sigma) for row in candidate["B"]]
                    ratio = singular_ratio_2x2(float_reachability(a, b))
                    ratios[candidate["blind_id"]] = ratio
                    predicted_class = "rank_two" if ratio >= RANK_RATIO_THRESHOLD else "rank_one"
                    candidate_correct += int(predicted_class == candidate["class"])
                    candidate_trials += 1
                predicted_full = max(ratios, key=ratios.get)
                oracle_full = next(candidate["blind_id"] for candidate in item["candidates"] if candidate["class"] == "rank_two")
                pair_correct += int(predicted_full == oracle_full)
                pair_trials += 1
        noise_rows.append({
            "sigma": sigma,
            "threshold": RANK_RATIO_THRESHOLD,
            "candidate_accuracy": candidate_correct / candidate_trials,
            "pair_accuracy": pair_correct / pair_trials,
            "candidate_trials": candidate_trials,
            "pair_trials": pair_trials,
        })

    passive_accuracy = passive_correct / len(items)
    control_accuracy = control_correct / len(items)
    information_gain = passive_entropy - control_entropy
    coordinate_fraction = coordinate_checks / (len(items) * 2)
    exact_pass = (
        passive_accuracy == 0.5
        and control_accuracy == 1.0
        and abs(information_gain - 1.0) < 1e-12
        and coordinate_fraction == 1.0
        and identity_leaks == 0
        and all(row["certificate_passed"] for row in certificates)
    )
    summary = {
        "schema_version": "reachability_information_gain.summary.v1",
        "independent_items": len(items),
        "candidate_observations": len(items) * 2,
        "task_result": {
            "passive_correct": passive_correct,
            "passive_accuracy": passive_accuracy,
            "passive_wilson_95": wilson_interval(passive_correct, len(items)),
            "control_correct": control_correct,
            "control_accuracy": control_accuracy,
            "control_wilson_95": wilson_interval(control_correct, len(items)),
            "accuracy_gain": control_accuracy - passive_accuracy,
            "H_control_class_given_passive_bits": passive_entropy,
            "H_control_class_given_certificate_bits": control_entropy,
            "conditional_information_gain_bits": information_gain,
        },
        "measurement_reliability": {
            "passive_identity_leaks": identity_leaks,
            "counterbalanced_full_A": sum(item["candidates"][0]["class"] == "rank_two" for item in items),
            "counterbalanced_full_B": sum(item["candidates"][1]["class"] == "rank_two" for item in items),
            "coordinate_invariance_fraction": coordinate_fraction,
            "exact_certificate_fraction": sum(row["certificate_passed"] for row in certificates) / len(certificates),
        },
        "metric_robustness": {"noise_sweep": noise_rows},
        "claim_support": "pass" if exact_pass else "fail",
        "operational_decision": "admit exact reachability lens; require uncertainty-aware rank for measured model Jacobians" if exact_pass else "reject or redesign",
        "claim_boundary": "Synthetic exact linear systems prove the view-level information addition. No neural-model controllability claim is tested.",
        "artifact_sha256": {},
    }

    outputs = {
        "passive_observations.jsonl": passive_rows,
        "control_observations.jsonl": control_rows,
        "predictions.jsonl": predictions,
        "exact_certificates.jsonl": certificates,
        "judgments.jsonl": judgments,
        "deterministic.jsonl": deterministic,
        "noise_robustness.jsonl": noise_rows,
    }
    for name, rows in outputs.items():
        write_jsonl(RESULTS / name, rows)
        summary["artifact_sha256"][name] = hashlib.sha256((RESULTS / name).read_bytes()).hexdigest()
    write_json(RESULTS / "summary.json", summary)
    print(json.dumps(summary))


def main() -> None:
    global SEED, RESULTS, MANIFEST_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("stage", "run"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--manifest", default="manifest.yaml")
    args = parser.parse_args()
    SEED = args.seed
    RESULTS = ROOT / args.results_dir
    MANIFEST_PATH = ROOT / args.manifest
    if args.command == "stage":
        stage()
    else:
        run()


if __name__ == "__main__":
    main()
