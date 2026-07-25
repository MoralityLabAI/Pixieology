from __future__ import annotations

from pathlib import Path

from pixie_etale_motifs.io import sha256_file
from pixie_lora_feedback.protocol import load_protocol


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]


def test_continuation_preserves_sealed_v01_lineage_and_raises_only_ram_cap():
    protocol = load_protocol(EXPERIMENT_ROOT)
    previous = EXPERIMENT_ROOT.parent / protocol["continuation_of"]["experiment_id"]
    assert sha256_file(previous / "protocol.json") == protocol["continuation_of"]["protocol_sha256"]
    assert sha256_file(previous / "protocol.lock.json") == protocol["continuation_of"]["implementation_lock_sha256"]
    assert protocol["resources"]["training_requested_not_authorized"] == {
        "ram_mb": 8192,
        "cpu_pct": 50,
        "io_mb_s": 50,
        "timeout_seconds": 1800,
    }
    assert protocol["resources"]["gpu"]["maximum_peak_memory_mib"] == 3900
    assert protocol["comparison"]["evaluation_split"] == "transfer"
    assert protocol["seeds"]["training"] == 2026072402


def test_primelab_launcher_is_hash_bound_and_fail_closed_on_cgroup_v2():
    protocol = load_protocol(EXPERIMENT_ROOT)
    launcher = EXPERIMENT_ROOT / protocol["bounded_launcher"]["primelab_entrypoint"]
    source = launcher.read_text(encoding="utf-8")
    assert sha256_file(launcher) == protocol["bounded_launcher"]["primelab_entrypoint_sha256"]
    for required in (
        "cgroup.controllers",
        "memory.max",
        "memory.swap.max",
        "cpu.max",
        "io.max",
        "PKNAME",
        "PIXIE_PRIME_SUMMARY_IO_DEVICE",
        "maximum_peak_memory_mib",
        "PIXIE_RESOURCE_CAP_ACTIVE=1",
        "PIXIE_EXECUTION_SURFACE=primelab",
    ):
        assert required in source
    assert "pkill" not in source
    assert "killall" not in source


def test_prime_envelope_protects_hosted_rl_run_and_bounds_spot_lifetime():
    prime = load_protocol(EXPERIMENT_ROOT)["bounded_launcher"]["primelab"]
    assert prime["gpu_type"] == "A6000_48GB"
    assert prime["gpu_count"] == 1
    assert prime["maximum_hourly_usd"] == 0.7
    assert prime["maximum_pod_lifetime_seconds"] == 7200
    assert prime["spot_interruption_acceptable"] is False
    assert prime["resume_unit"] == "completed_transfer_row"
    assert prime["protected_rl_run_id"] == "e2s64hw5ywag1d8hgwfef6jd"
