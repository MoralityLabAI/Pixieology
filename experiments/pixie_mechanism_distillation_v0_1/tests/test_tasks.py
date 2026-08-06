from __future__ import annotations

from pixie_mechanism_distillation.tasks import build_task_cases, generate_families, validate_cases


def test_families_are_deterministic_reachable_and_independent() -> None:
    first = generate_families()
    second = generate_families()
    assert first == second
    assert len(first) == 32
    assert len({family["family_sha256"] for family in first}) == 32
    assert all(family["independent_unit"] for family in first)


def test_case_builder_seals_discovery_heldout_and_intervention_rows() -> None:
    rows = build_task_cases()
    validate_cases(rows)
    assert len(rows) == 32 * (8 + 8 + 4)
    for family_id in {row["task_family_id"] for row in rows}:
        family = [row for row in rows if row["task_family_id"] == family_id]
        assert sum(row["split"] == "discovery" for row in family) == 8
        assert sum(row["split"] == "held_out" for row in family) == 8
        assert sum(row["split"] == "intervention" for row in family) == 4
