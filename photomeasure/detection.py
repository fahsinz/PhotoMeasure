"""Contour-based quadrilateral suggestions; every candidate needs confirmation."""
from dataclasses import dataclass
from time import perf_counter

import cv2
import numpy as np
from numpy.typing import ArrayLike

from .geometry import GeometryError, transform_points, validate_quad
from .markers import _rgb


@dataclass
class DetectionConfig:
    canny_low: int = 50
    canny_high: int = 150
    min_area_ratio: float = .005
    max_area_ratio: float = .9
    epsilon_ratio: float = .02


def suggest_targets(rgb: np.ndarray, reference: ArrayLike | None = None,
                    homography: ArrayLike | None = None,
                    config: DetectionConfig | None = None) -> dict:
    start = perf_counter()
    image = _rgb(rgb)
    config = config or DetectionConfig()
    values = [config.canny_low, config.canny_high, config.min_area_ratio,
              config.max_area_ratio, config.epsilon_ratio]
    if not np.isfinite(values).all() or not 0 <= config.canny_low < config.canny_high <= 255 or not 0 < config.min_area_ratio < config.max_area_ratio <= 1 or not 0 < config.epsilon_ratio < .2:
        raise ValueError("Use ordered Canny thresholds in 0–255, area ratios in (0,1], and approximation ratio in (0,0.2).")
    height, width = image.shape[:2]
    reference_quad = validate_quad(reference, (width, height)) if reference is not None else None
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, config.canny_low, config.canny_high)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    area_total = width * height
    boundary_margin = max(2., min(width, height) * .005)
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        approximation = cv2.approxPolyDP(contour, config.epsilon_ratio * perimeter, True)
        if len(approximation) != 4:
            continue
        try:
            quad = validate_quad(approximation.reshape(4, 2), (width, height))
        except GeometryError:
            continue
        area = abs(cv2.contourArea(quad.astype(np.float32)))
        ratio = area / area_total
        if not config.min_area_ratio <= ratio <= config.max_area_ratio:
            continue
        if (quad < boundary_margin).any() or (quad[:, 0] > width - 1 - boundary_margin).any() or (quad[:, 1] > height - 1 - boundary_margin).any():
            continue
        if reference_quad is not None:
            overlap, _ = cv2.intersectConvexConvex(quad.astype(np.float32), reference_quad.astype(np.float32))
            reference_area = abs(cv2.contourArea(reference_quad.astype(np.float32)))
            if overlap / min(area, reference_area) > .1:
                continue
        warnings = []
        # Contour/quad area agreement penalizes rounded/irregular approximations.
        contour_area = abs(cv2.contourArea(contour))
        fit = min(contour_area, area) / max(contour_area, area) if contour_area else 0
        quality = fit
        if homography is not None:
            try:
                if reference_quad is not None:
                    transform_points(np.vstack([reference_quad, quad]), homography)
                plane = transform_points(quad, homography)
                vectors = np.roll(plane, -1, axis=0) - plane
                lengths = np.linalg.norm(vectors, axis=1)
                if lengths.min() < 1e-9:
                    continue
                angles = np.degrees(np.arccos(np.clip(np.sum(-np.roll(vectors, 1, axis=0)*vectors, axis=1)/(np.roll(lengths, 1)*lengths), -1, 1)))
                angle_deviation = float(np.max(np.abs(angles - 90)))
                opposite_disagreement = max(abs(lengths[i]-lengths[i+2])/((lengths[i]+lengths[i+2])/2) for i in range(2))
                quality *= max(0., 1-angle_deviation/90) / (1+opposite_disagreement)
                if angle_deviation > 10:
                    warnings.append("Rectified candidate angles deviate from right angles by more than 10 degrees.")
                if opposite_disagreement > .1:
                    warnings.append("Rectified candidate opposite sides differ by more than 10%.")
            except GeometryError:
                continue
        else:
            warnings.append("Plane rectangularity is unchecked until a reference is confirmed.")
        # Area rewards a usable visible object; quality modifies ranking only.
        score = float(np.sqrt(ratio) * quality)
        # Canny yields paired inner/outer contours. Deduplicate overlapping quads.
        duplicate = None
        for index, existing in enumerate(candidates):
            old = np.asarray(existing["corners_analysis_px"], dtype=np.float32)
            overlap, _ = cv2.intersectConvexConvex(quad.astype(np.float32), old)
            old_area = abs(cv2.contourArea(old))
            union = area + old_area - overlap
            if union > 0 and overlap / union > .85:
                duplicate = index
                break
        candidate = {"corners_analysis_px": quad.tolist(), "score": score, "warnings": warnings}
        if duplicate is None:
            candidates.append(candidate)
        elif score > candidates[duplicate]["score"]:
            candidates[duplicate] = candidate
    candidates.sort(key=lambda item: item["score"], reverse=True)
    candidates = candidates[:30]
    status = (f"Suggested {len(candidates)} quadrilaterals. Select, edit and confirm the intended target." if candidates else
              "No useful target quadrilateral found. Adjust edge settings, improve contrast, or select four corners manually.")
    return {"candidates": candidates, "status": status, "latency_ms": (perf_counter()-start)*1000}
