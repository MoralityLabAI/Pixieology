#!/usr/bin/env python3
"""Price-gated Prime pod preflight and creation for the frozen fae-tax study.

Run this file with Prime's own Python environment. It delegates authentication to
``prime_cli`` and never prints or serializes the API key. Creation is opt-in and
requires the exact cloud ID and observed hourly price to be repeated on the command
line, plus ``--yes``.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence


SCHEMA = "pixieology.fae_tax_epistemics.prime_preflight.v1"
DEFAULT_MANIFEST = Path(__file__).resolve().with_name("manifest.json")
UNAVAILABLE_STATES = {"unavailable", "out_of_stock", "no_stock", "sold_out"}
PREFERRED_IMAGES = (
    "cuda_12_6_pytorch_2_7",
    "cuda_12_4_pytorch_2_6",
    "ubuntu_22_cuda_12",
)


class PrimeGateError(RuntimeError):
    """Raised when a Prime offer or requested mutation violates the frozen cap."""


@dataclass(frozen=True)
class Candidate:
    cloud_id: str
    gpu_type: str
    gpu_count: int
    gpu_memory_gb: float
    provider: str
    socket: str
    security: str | None
    country: str | None
    data_center: str | None
    stock_status: str
    hourly_usd: float
    projected_eight_hour_usd: float
    is_spot: bool
    is_variable_price: bool
    disk_gb: int
    vcpus: int
    ram_gb: int
    images: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _memory_gb(raw: Any) -> float:
    value = float(raw)
    return value / 1024.0 if value > 1024.0 else value


def _default_int(resource: Any) -> int:
    value = _get(resource, "default_count")
    return int(value) if value is not None else 0


def _price(prices: Any) -> float:
    direct = _get(prices, "price")
    if direct is not None:
        return float(direct)
    community = _get(prices, "community_price")
    on_demand = _get(prices, "on_demand")
    return float(community if community is not None else on_demand)


def candidate_from_offer(offer: Any, *, max_hourly_usd: float) -> Candidate | None:
    """Return an eligible one-A100/80GB offer or ``None`` for an ineligible offer."""

    gpu_type = str(_get(offer, "gpu_type", ""))
    gpu_count = int(_get(offer, "gpu_count", 0))
    gpu_memory_gb = _memory_gb(_get(offer, "gpu_memory", 0))
    stock_status = str(_get(offer, "stock_status", "unknown"))
    prices = _get(offer, "prices", {})
    is_variable_price = bool(_get(prices, "is_variable", False))
    try:
        hourly = _price(prices)
    except (TypeError, ValueError):
        return None
    disk_gb = _default_int(_get(offer, "disk", {}))
    vcpus = _default_int(_get(offer, "vcpu", {}))
    ram_gb = _default_int(_get(offer, "memory", {}))
    if (
        "A100" not in gpu_type.upper()
        or gpu_count != 1
        or gpu_memory_gb < 79.0
        or stock_status.strip().lower().replace(" ", "_") in UNAVAILABLE_STATES
        or not math.isfinite(hourly)
        or hourly <= 0.0
        or hourly > max_hourly_usd
        or is_variable_price
        or disk_gb < 80
        or disk_gb > 200
        or vcpus < 8
        or ram_gb < 64
        or ram_gb > 240
    ):
        return None
    images = tuple(str(image) for image in (_get(offer, "images", []) or []))
    return Candidate(
        cloud_id=str(_get(offer, "cloud_id")),
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        gpu_memory_gb=gpu_memory_gb,
        provider=str(_get(offer, "provider", "")),
        socket=str(_get(offer, "socket", "")),
        security=_get(offer, "security"),
        country=_get(offer, "country"),
        data_center=_get(offer, "data_center"),
        stock_status=stock_status,
        hourly_usd=hourly,
        projected_eight_hour_usd=hourly * 8.0,
        is_spot=bool(_get(offer, "is_spot", False)),
        is_variable_price=is_variable_price,
        disk_gb=disk_gb,
        vcpus=vcpus,
        ram_gb=ram_gb,
        images=images,
    )


def eligible_candidates(
    availability: Mapping[str, Sequence[Any]], *, max_hourly_usd: float
) -> list[Candidate]:
    rows = [
        candidate
        for offers in availability.values()
        for offer in offers
        if (candidate := candidate_from_offer(offer, max_hourly_usd=max_hourly_usd))
        is not None
    ]
    return sorted(rows, key=lambda row: (row.is_spot, row.hourly_usd, row.cloud_id))


def choose_image(candidate: Candidate) -> str:
    for preferred in PREFERRED_IMAGES:
        if preferred in candidate.images:
            return preferred
    if candidate.images:
        return candidate.images[0]
    raise PrimeGateError("candidate reports no compatible pod image")


def pod_config(candidate: Candidate, *, name: str, image: str | None = None) -> dict[str, Any]:
    selected_image = image or choose_image(candidate)
    if candidate.images and selected_image not in candidate.images:
        raise PrimeGateError(f"image is not offered by candidate: {selected_image}")
    return {
        "pod": {
            "name": name,
            "cloudId": candidate.cloud_id,
            "gpuType": candidate.gpu_type,
            "socket": candidate.socket,
            "gpuCount": 1,
            "diskSize": candidate.disk_gb,
            "vcpus": candidate.vcpus,
            "memory": candidate.ram_gb,
            "maxPrice": candidate.hourly_usd,
            "image": selected_image,
            "dataCenterId": candidate.data_center,
            "country": candidate.country,
            "security": candidate.security,
            "autoRestart": False,
        },
        "provider": {"type": candidate.provider},
        "disks": None,
        "team": None,
    }


def study_limits(manifest_path: Path) -> tuple[float, float]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["budget"]
    max_cost = float(budget["max_provider_cost_usd"])
    max_hours = float(budget["max_gpu_hours"])
    return max_cost, max_hours


def _prime_clients() -> tuple[Any, Any, Any]:
    try:
        from prime_cli.api.availability import AvailabilityClient
        from prime_cli.api.pods import PodsClient
        from prime_cli.core import APIClient
    except ImportError as exc:
        raise PrimeGateError(
            "prime_cli is unavailable; run this script with Prime's Python environment"
        ) from exc
    base = APIClient()
    if not base.api_key:
        raise PrimeGateError("Prime API key is not configured; run prime login first")
    return AvailabilityClient(base), PodsClient(base), base


def fetch_candidates(manifest_path: Path) -> tuple[list[Candidate], dict[str, Any]]:
    max_cost, max_hours = study_limits(manifest_path)
    max_hourly = max_cost / max_hours
    availability_client, _pods, base = _prime_clients()
    ssh_key = Path(base.config.ssh_key_path).expanduser()
    if not ssh_key.is_file():
        raise PrimeGateError(
            f"configured Prime SSH private key does not exist: {ssh_key}; "
            "run prime config set-ssh-key-path"
        )
    base.get("/availability/gpu-summary")
    availability = availability_client.get(gpu_count=1)
    rows = eligible_candidates(availability, max_hourly_usd=max_hourly)
    receipt = {
        "schema": SCHEMA,
        "checked_utc": utc_now(),
        "limits": {
            "max_provider_cost_usd": max_cost,
            "max_gpu_hours": max_hours,
            "max_hourly_usd": max_hourly,
        },
        "eligible_count": len(rows),
        "selection_order": "on-demand before spot, then hourly price, then cloud ID",
        "ssh_private_key_path": str(ssh_key.resolve()),
        "candidates": [asdict(row) for row in rows],
    }
    return rows, receipt


def write_receipt(path: Path | None, value: Mapping[str, Any]) -> None:
    if path is None:
        return
    output = path.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite receipt: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_preflight(args: argparse.Namespace) -> dict[str, Any]:
    _rows, receipt = fetch_candidates(args.manifest)
    write_receipt(args.receipt, receipt)
    return receipt


def command_create(args: argparse.Namespace) -> dict[str, Any]:
    rows, preflight = fetch_candidates(args.manifest)
    matches = [row for row in rows if row.cloud_id == args.cloud_id]
    if len(matches) != 1:
        raise PrimeGateError("cloud ID is no longer uniquely eligible; rerun preflight")
    candidate = matches[0]
    if not math.isclose(candidate.hourly_usd, args.confirm_hourly_usd, abs_tol=1e-9):
        raise PrimeGateError("confirmed hourly price does not match current availability")
    config = pod_config(candidate, name=args.name, image=args.image)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "checked_utc": utc_now(),
        "action": "dry_run" if not args.yes else "created",
        "selected_candidate": asdict(candidate),
        "pod_config": config,
        "preflight_limits": preflight["limits"],
    }
    if args.yes:
        _availability, pods, _base = _prime_clients()
        created = pods.create(config)
        receipt["pod"] = {
            "id": created.id,
            "name": created.name,
            "status": created.status,
            "created_at": created.created_at,
            "provider": created.provider_type,
            "gpu_type": created.gpu_type,
            "gpu_count": created.gpu_count,
            "hourly_usd": created.price_hr,
        }
        if created.price_hr is None or float(created.price_hr) > candidate.hourly_usd:
            try:
                pods.delete(created.id)
            finally:
                raise PrimeGateError("created pod price exceeded confirmed cap; termination requested")
    write_receipt(args.receipt, receipt)
    return receipt


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    _availability, pods, _base = _prime_clients()
    pod = pods.get(args.pod_id)
    statuses = pods.get_status([args.pod_id])
    status = statuses[0] if statuses else None
    return {
        "pod_id": pod.id,
        "name": pod.name,
        "status": status.status if status else pod.status,
        "created_at": pod.created_at,
        "hourly_usd": status.cost_per_hr if status else pod.price_hr,
        "gpu_type": pod.gpu_type,
        "gpu_count": pod.gpu_count,
        "ssh_connection": status.ssh_connection if status else pod.ssh_connection,
        "installation_failure": status.installation_failure if status else pod.installation_failure,
    }


def command_terminate(args: argparse.Namespace) -> dict[str, Any]:
    if not args.yes:
        raise PrimeGateError("termination requires --yes")
    _availability, pods, _base = _prime_clients()
    pods.delete(args.pod_id)
    return {"pod_id": args.pod_id, "termination_requested": True, "checked_utc": utc_now()}


def _epoch(timestamp: str) -> float:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def command_watch(args: argparse.Namespace) -> dict[str, Any]:
    """Poll a pod and terminate it at price drift or the frozen total-cost limit."""

    max_cost, max_hours = study_limits(args.manifest)
    _availability, pods, _base = _prime_clients()
    pod = pods.get(args.pod_id)
    if pod.gpu_count != 1 or "A100" not in pod.gpu_type.upper():
        raise PrimeGateError("watch target is not the frozen one-A100 design")
    hourly = float(pod.price_hr or 0.0)
    if hourly <= 0.0 or hourly > max_cost / max_hours:
        raise PrimeGateError("watch target price is absent or already above the hourly cap")
    created_epoch = _epoch(pod.created_at)
    allowed_seconds = min(max_hours * 3600.0, max_cost / hourly * 3600.0)
    observations: list[dict[str, Any]] = []
    action = "observed_terminal"
    terminal = {"STOPPED", "DELETING", "TERMINATED"}
    while True:
        statuses = pods.get_status([args.pod_id])
        if not statuses:
            action = "status_missing"
            break
        status = statuses[0]
        now = time.time()
        observed_hourly = float(status.cost_per_hr or hourly)
        observations.append(
            {
                "checked_utc": utc_now(),
                "status": status.status,
                "elapsed_seconds": max(0.0, now - created_epoch),
                "hourly_usd": observed_hourly,
                "projected_cost_at_limit_usd": observed_hourly * allowed_seconds / 3600.0,
            }
        )
        if observed_hourly > hourly + 1e-9:
            pods.delete(args.pod_id)
            action = "terminated_on_price_drift"
            break
        if now - created_epoch >= allowed_seconds:
            pods.delete(args.pod_id)
            action = "terminated_at_budget_limit"
            break
        if status.status.upper() == "ERROR":
            pods.delete(args.pod_id)
            action = "terminated_on_provider_error"
            break
        if status.status.upper() in terminal:
            break
        if args.poll_seconds <= 0.0:
            raise PrimeGateError("poll seconds must be positive")
        time.sleep(args.poll_seconds)
    receipt = {
        "schema": SCHEMA,
        "pod_id": args.pod_id,
        "action": action,
        "created_at": pod.created_at,
        "confirmed_hourly_usd": hourly,
        "allowed_seconds": allowed_seconds,
        "limits": {"max_provider_cost_usd": max_cost, "max_gpu_hours": max_hours},
        "observations": observations,
    }
    write_receipt(args.receipt, receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = result.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--receipt", type=Path)
    preflight.set_defaults(handler=command_preflight)

    create = subparsers.add_parser("create")
    create.add_argument("--cloud-id", required=True)
    create.add_argument("--confirm-hourly-usd", type=float, required=True)
    create.add_argument("--name", default="fae-tax-epistemics-v1")
    create.add_argument("--image")
    create.add_argument("--receipt", type=Path)
    create.add_argument("--yes", action="store_true")
    create.set_defaults(handler=command_create)

    status = subparsers.add_parser("status")
    status.add_argument("pod_id")
    status.set_defaults(handler=command_status)

    terminate = subparsers.add_parser("terminate")
    terminate.add_argument("pod_id")
    terminate.add_argument("--yes", action="store_true")
    terminate.set_defaults(handler=command_terminate)

    watch = subparsers.add_parser("watch")
    watch.add_argument("pod_id")
    watch.add_argument("--poll-seconds", type=float, default=30.0)
    watch.add_argument("--receipt", type=Path)
    watch.set_defaults(handler=command_watch)
    return result


def main() -> int:
    args = parser().parse_args()
    args.manifest = args.manifest.expanduser().resolve()
    try:
        result = args.handler(args)
    except (FileNotFoundError, FileExistsError, PrimeGateError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if type(exc).__module__.startswith("prime_cli."):
            print(f"ERROR: Prime API/CLI failure: {exc}", file=sys.stderr)
            return 2
        raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
