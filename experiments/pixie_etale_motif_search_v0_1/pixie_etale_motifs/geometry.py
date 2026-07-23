"""Input-conditioned LoRA response geometry with frozen global normalization."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CompactSVD:
    singular_values: np.ndarray
    right_vectors: np.ndarray
    effective_rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "singular_values": self.singular_values.tolist(),
            "right_vectors": self.right_vectors.tolist(),
            "effective_rank": self.effective_rank,
        }


@dataclass(frozen=True)
class GlobalScaler:
    lower: np.ndarray
    upper: np.ndarray
    lower_quantile: float = 0.01
    upper_quantile: float = 0.99

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "pixieology_etale_global_scaler_v1",
            "coordinates": ["x", "y", "z"],
            "lower": self.lower.tolist(),
            "upper": self.upper.tolist(),
            "lower_quantile": self.lower_quantile,
            "upper_quantile": self.upper_quantile,
            "fit_scope": "discovery_all_inputs_modules_layers",
            "window_dependent": False,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GlobalScaler":
        if value.get("schema") != "pixieology_etale_global_scaler_v1":
            raise ValueError("invalid global scaler schema")
        return cls(
            lower=np.asarray(value["lower"], dtype=np.float64),
            upper=np.asarray(value["upper"], dtype=np.float64),
            lower_quantile=float(value["lower_quantile"]),
            upper_quantile=float(value["upper_quantile"]),
        )


def compact_update_svd(
    a: np.ndarray,
    b: np.ndarray,
    scale: float,
    *,
    relative_tolerance: float = 1e-10,
) -> CompactSVD:
    """Factor the non-zero SVD of ``scale * B @ A`` without materializing it."""
    a64 = np.asarray(a, dtype=np.float64)
    b64 = np.asarray(b, dtype=np.float64)
    if a64.ndim != 2 or b64.ndim != 2 or b64.shape[1] != a64.shape[0]:
        raise ValueError("expected A=(rank,input) and B=(output,rank)")
    qb, rb = np.linalg.qr(b64, mode="reduced")
    qa, ra = np.linalg.qr(a64.T, mode="reduced")
    small = float(scale) * (rb @ ra.T)
    _, singular_values, vh_small = np.linalg.svd(small, full_matrices=False)
    right_vectors = vh_small @ qa.T
    cutoff = (float(singular_values[0]) * relative_tolerance) if singular_values.size else 0.0
    effective_rank = int(np.sum(singular_values > cutoff))
    return CompactSVD(
        singular_values=singular_values[:effective_rank].astype(np.float64),
        right_vectors=right_vectors[:effective_rank].astype(np.float64),
        effective_rank=effective_rank,
    )


def response_coordinates(
    input_vector: np.ndarray,
    base_output: np.ndarray | float,
    update: CompactSVD,
    *,
    epsilon: float = 1e-8,
) -> np.ndarray:
    """Return raw X/Y/Z for a LoRA update evaluated at one module input."""
    x = np.asarray(input_vector, dtype=np.float64).reshape(-1)
    if update.right_vectors.shape[1] != x.size:
        raise ValueError("input vector and update right vectors disagree")
    base = np.asarray(base_output, dtype=np.float64)
    base_norm = float(abs(base)) if base.ndim == 0 else float(np.linalg.norm(base.reshape(-1)))
    if update.effective_rank == 0:
        return np.zeros(3, dtype=np.float64)
    coefficients = update.singular_values * (update.right_vectors @ x)
    energies = coefficients * coefficients
    total = float(np.sum(energies))
    if total <= epsilon * epsilon:
        return np.zeros(3, dtype=np.float64)
    probabilities = energies / total
    active = probabilities > 0.0
    entropy = -float(np.sum(probabilities[active] * np.log(probabilities[active])))
    response_norm = math.sqrt(total)
    x_coordinate = math.log1p(response_norm / (base_norm + epsilon))
    y_coordinate = float(np.max(probabilities))
    z_coordinate = math.exp(entropy) / float(update.effective_rank)
    return np.asarray([x_coordinate, y_coordinate, z_coordinate], dtype=np.float64)


def fit_global_scaler(
    raw_coordinates: np.ndarray,
    *,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> GlobalScaler:
    values = np.asarray(raw_coordinates, dtype=np.float64)
    if values.ndim < 2 or values.shape[-1] != 3:
        raise ValueError("raw coordinates must end in X/Y/Z")
    flat = values.reshape(-1, 3)
    if not np.all(np.isfinite(flat)):
        raise ValueError("raw coordinates must be finite")
    lower = np.quantile(flat, lower_quantile, axis=0)
    upper = np.quantile(flat, upper_quantile, axis=0)
    upper = np.maximum(upper, lower + 1e-12)
    return GlobalScaler(lower=lower, upper=upper, lower_quantile=lower_quantile, upper_quantile=upper_quantile)


def apply_global_scaler(raw_coordinates: np.ndarray, scaler: GlobalScaler) -> np.ndarray:
    values = np.asarray(raw_coordinates, dtype=np.float64)
    if values.shape[-1] != 3:
        raise ValueError("raw coordinates must end in X/Y/Z")
    normalized = (values - scaler.lower) / (scaler.upper - scaler.lower)
    return np.clip(normalized, 0.0, 1.0)


def normalization_receipt(scaler: GlobalScaler, scaler_sha256: str) -> dict[str, Any]:
    return {
        "id": "activation_conditioned_lora_response_xyz_v1",
        "raw_coordinates": {
            "x": "log1p_lora_response_norm_over_base_output_norm",
            "y": "response_top_singular_mode_energy_share",
            "z": "response_entropy_effective_mode_fraction",
        },
        "normalization": scaler.to_dict(),
        "scaler_sha256": scaler_sha256,
        "uncertainty": "descriptive_geometry_not_confidence_interval",
    }
