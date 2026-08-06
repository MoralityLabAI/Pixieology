"""Compact mechanism extraction for frozen Pixie/base activation traces."""

from .compare import align_programs, compare_family, score_interventions
from .distill import distill_program, evaluate_program
from .report import aggregate_comparisons
from .tasks import build_task_cases, generate_families

__all__ = [
    "align_programs",
    "aggregate_comparisons",
    "build_task_cases",
    "compare_family",
    "distill_program",
    "evaluate_program",
    "generate_families",
    "score_interventions",
]
