from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np


def _number(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def polygon_from_mask(mask: np.ndarray) -> list[list[float]]:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contour = max(contours, key=cv2.contourArea)
    return [[float(point[0][0]), float(point[0][1])] for point in contour]


def calculate_metrics(
    nucleus_id: int,
    label_mask: np.ndarray,
    nucleus_signal: np.ndarray,
    protein_signal: np.ndarray,
    pixel_size: float | None = None,
    polygon: list[list[float]] | None = None,
    state: str = "active",
) -> dict[str, Any]:
    mask = label_mask.astype(bool)
    ys, xs = np.where(mask)
    if not xs.size:
        raise ValueError("Não é possível medir um núcleo vazio")
    nucleus_values = nucleus_signal[mask].astype(np.float64)
    protein_values = protein_signal[mask].astype(np.float64)
    area = int(mask.sum())
    moments = cv2.moments(mask.astype(np.uint8), binaryImage=True)
    centroid_x = moments["m10"] / moments["m00"] if moments["m00"] else float(xs.mean())
    centroid_y = moments["m01"] / moments["m00"] if moments["m00"] else float(ys.mean())
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    perimeter = float(cv2.arcLength(contour, True))
    equivalent_radius = math.sqrt(area / math.pi)
    circularity = 4 * math.pi * area / (perimeter * perimeter) if perimeter else None
    major = minor = None
    if len(contour) >= 5:
        (_, _), (axis_a, axis_b), _ = cv2.fitEllipse(contour)
        major, minor = sorted((float(axis_a), float(axis_b)), reverse=True)
    eccentricity = None
    if major and major > 0 and minor is not None:
        eccentricity = math.sqrt(max(0.0, 1.0 - (minor / major) ** 2))
    return {
        "nucleus_id": nucleus_id,
        "area_px": area,
        "area_um2": _number(area * pixel_size * pixel_size) if pixel_size else None,
        "centroid_x": _number(centroid_x),
        "centroid_y": _number(centroid_y),
        "bounding_box": {"x": int(xs.min()), "y": int(ys.min()), "width": int(xs.max() - xs.min() + 1), "height": int(ys.max() - ys.min() + 1)},
        "perimeter_px": _number(perimeter),
        "equivalent_radius_px": _number(equivalent_radius),
        "equivalent_diameter_px": _number(2 * equivalent_radius),
        "major_axis_px": _number(major) if major is not None else None,
        "minor_axis_px": _number(minor) if minor is not None else None,
        "eccentricity": _number(eccentricity) if eccentricity is not None else None,
        "circularity": _number(circularity) if circularity is not None else None,
        "nucleus_mean": _number(nucleus_values.mean()),
        "nucleus_median": _number(np.median(nucleus_values)),
        "nucleus_std": _number(nucleus_values.std()),
        "nucleus_integrated": _number(nucleus_values.sum()),
        "protein_mean": _number(protein_values.mean()),
        "protein_median": _number(np.median(protein_values)),
        "protein_std": _number(protein_values.std()),
        "protein_integrated": _number(protein_values.sum()),
        "state": state,
        "polygon": polygon if polygon is not None else polygon_from_mask(mask),
    }


def aggregate_metrics(nuclei: list[dict[str, Any]]) -> dict[str, Any]:
    active = [item for item in nuclei if item["state"] != "excluded"]
    visible = [item for item in active if item["state"] != "hidden"]
    def mean(key: str) -> float | None:
        values = [item[key] for item in active if item.get(key) is not None]
        return float(np.mean(values)) if values else None
    return {
        "nucleus_count": len(active),
        "visible_count": len(visible),
        "excluded_count": sum(item["state"] == "excluded" for item in nuclei),
        "hidden_count": sum(item["state"] == "hidden" for item in nuclei),
        "total_area_px": int(sum(item["area_px"] for item in active)),
        "mean_protein": mean("protein_mean"),
        "mean_nucleus_intensity": mean("nucleus_mean"),
    }
