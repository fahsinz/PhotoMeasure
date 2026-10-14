"""Double precision planar measurement; millimetres are the plane coordinate unit."""
from dataclasses import dataclass
import numpy as np


class GeometryError(ValueError):
    """Invalid selections or an unusable projective transform."""


@dataclass
class GeometryConfig:
    min_reference_area_px: float = 100.0
    small_edge_px: float = 40.0
    angle_warning_deg: float = 10.0
    opposite_warning_ratio: float = 0.1


def _points(points, count=None):
    try:
        p = np.asarray(points, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise GeometryError("Coordinates must be finite numeric points.") from exc
    if p.ndim != 2 or p.shape[1] != 2 or (count is not None and len(p) != count) or not np.isfinite(p).all():
        raise GeometryError("Provide four finite (x, y) corners." if count == 4 else "Provide finite N by 2 points.")
    return p


def _cross(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def validate_quad(points, image_size=None, min_area=1.0) -> np.ndarray:
    p = _points(points, 4).copy()
    if not np.isfinite(min_area) or min_area < 0:
        raise GeometryError("Minimum polygon area must be finite and nonnegative.")
    if image_size is not None:
        bounds = np.asarray(image_size, dtype=float)
        if bounds.shape != (2,) or not np.isfinite(bounds).all() or (bounds <= 0).any():
            raise GeometryError("Image dimensions must be positive width and height.")
        if (p < 0).any() or (p > bounds - 1).any():
            raise GeometryError("Corners must remain inside the analysis image bounds.")
    edges = np.roll(p, -1, axis=0) - p
    lengths = np.linalg.norm(edges, axis=1)
    distances = np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)
    if np.min(distances[np.triu_indices(4, 1)]) <= 1e-8:
        raise GeometryError("Corners must be distinct; select each corner once.")
    turns = _cross(edges, np.roll(edges, -1, axis=0))
    # Relative sine threshold rejects almost straight corners independent of image scale.
    if (np.abs(turns) / (lengths * np.roll(lengths, -1)) < 1e-4).any():
        raise GeometryError("Corners are collinear or nearly collinear; select a visible quadrilateral.")
    if not ((turns > 0).all() or (turns < 0).all()):
        raise GeometryError("Corners must follow the perimeter of a convex quadrilateral. Undo crossing or concave selections.")
    centered = p - p.mean(axis=0)
    area = abs(float(np.sum(_cross(centered, np.roll(centered, -1, axis=0))))) / 2
    if area < min_area:
        raise GeometryError(f"Polygon area is too small; require at least {min_area:g} analysis pixels squared.")
    if turns[0] < 0:
        p = p[::-1]
    # Topmost then leftmost point supplies a deterministic cyclic start.
    start = np.lexsort((p[:, 0], p[:, 1]))[0]
    return np.roll(p, -int(start), axis=0)


def _normalize(p):
    center = p.mean(axis=0)
    distance = np.linalg.norm(p - center, axis=1).mean()
    if distance <= np.finfo(float).eps:
        raise GeometryError("Cannot normalize degenerate coordinates.")
    scale = np.sqrt(2) / distance
    t = np.array([[scale, 0, -scale * center[0]], [0, scale, -scale * center[1]], [0, 0, 1.]])
    return (p - center) * scale, t


def compute_homography(reference, reference_size_mm) -> np.ndarray:
    try:
        side = float(reference_size_mm)
    except (TypeError, ValueError) as exc:
        raise GeometryError("Reference size must be finite and positive millimetres.") from exc
    if not np.isfinite(side) or side <= 0:
        raise GeometryError("Reference size must be finite and positive millimetres.")
    ref = validate_quad(reference)
    plane = np.array([[0., 0.], [side, 0.], [side, side], [0., side]])
    source, ts = _normalize(ref)
    dest, td = _normalize(plane)
    rows = []
    for (x, y), (u, v) in zip(source, dest):
        rows.extend([[-x, -y, -1, 0, 0, 0, u*x, u*y, u],
                     [0, 0, 0, -x, -y, -1, v*x, v*y, v]])
    _, singular, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64), full_matrices=True)
    if singular[-1] <= singular[0] * 1e-10:
        raise GeometryError("Reference produces a degenerate or poorly conditioned transform.")
    normalized_h = vt[-1].reshape(3, 3)
    if np.linalg.cond(normalized_h) > 1e10:
        raise GeometryError("Reference produces a poorly conditioned normalized transform.")
    h = np.linalg.inv(td) @ normalized_h @ ts
    h /= np.max(np.abs(h))
    if not np.isfinite(h).all():
        raise GeometryError("Transform contains nonfinite coefficients.")
    return h


def transform_points(points, homography) -> np.ndarray:
    p = _points(points)
    h = np.asarray(homography, dtype=np.float64)
    if h.shape != (3, 3) or not np.isfinite(h).all() or np.max(np.abs(h)) == 0:
        raise GeometryError("Homography must be a finite invertible 3 by 3 matrix.")
    h = h / np.max(np.abs(h))
    # Do not apply raw condition/rank thresholds: coefficients mix pixels and mm.
    try:
        inverse = np.linalg.inv(h)
    except np.linalg.LinAlgError as exc:
        raise GeometryError("Homography is singular.") from exc
    if not np.isfinite(inverse).all():
        raise GeometryError("Homography has no finite inverse.")
    homogeneous = np.column_stack([p, np.ones(len(p))])
    mapped = homogeneous @ h.T
    denominator_scale = np.abs(homogeneous) @ np.abs(h[2])
    if (np.abs(mapped[:, 2]) <= 1e-10 * np.maximum(denominator_scale, np.finfo(float).tiny)).any():
        raise GeometryError("A corner lies at or too near the projective horizon; correct the selections.")
    if len(p) and np.min(mapped[:, 2]) < 0 < np.max(mapped[:, 2]):
        raise GeometryError("Selection crosses the projective horizon; measurement is invalid.")
    result = mapped[:, :2] / mapped[:, 2, None]
    if not np.isfinite(result).all():
        raise GeometryError("Transform produced nonfinite coordinates.")
    return result


def measure(reference, target, reference_size_mm, image_size=None, config=None) -> dict:
    config = config or GeometryConfig()
    thresholds = [config.min_reference_area_px, config.small_edge_px, config.angle_warning_deg, config.opposite_warning_ratio]
    if not np.isfinite(thresholds).all() or min(thresholds) < 0:
        raise GeometryError("Geometry thresholds must be finite and nonnegative.")
    ref = validate_quad(reference, image_size, config.min_reference_area_px)
    target = validate_quad(target, image_size)
    h = compute_homography(ref, reference_size_mm)
    # Both polygons must belong to the same finite side of the plane horizon.
    transform_points(np.vstack([ref, target]), h)
    plane = transform_points(target, h)
    edges = np.roll(plane, -1, axis=0) - plane
    lengths = np.linalg.norm(edges, axis=1)
    if (lengths <= 1e-9).any():
        raise GeometryError("Target has degenerate physical side lengths.")
    sides = sorted([(lengths[0] + lengths[2]) / 2, (lengths[1] + lengths[3]) / 2])
    warnings = []
    if np.linalg.norm(np.roll(ref, -1, axis=0) - ref, axis=1).min() < config.small_edge_px:
        warnings.append(f"Reference shortest image edge is below {config.small_edge_px:g} pixels; corner errors can substantially affect measurements.")
    cosines = np.sum(-np.roll(edges, 1, axis=0) * edges, axis=1) / (np.roll(lengths, 1) * lengths)
    angles = np.degrees(np.arccos(np.clip(cosines, -1, 1)))
    if (np.abs(angles - 90) > config.angle_warning_deg).any():
        warnings.append(f"Target angles deviate from 90 degrees by more than {config.angle_warning_deg:g} degrees; check corners and coplanarity.")
    disagreement = [abs(lengths[i] - lengths[i+2]) / ((lengths[i] + lengths[i+2]) / 2) for i in range(2)]
    if max(disagreement) > config.opposite_warning_ratio:
        warnings.append(f"Target opposite sides disagree by more than {100*config.opposite_warning_ratio:g}%; check corners and coplanarity.")
    return {"reference_corners_analysis_px": ref.tolist(), "target_corners_analysis_px": target.tolist(),
            "homography_image_to_plane": h.tolist(), "target_corners_plane_mm": plane.tolist(),
            "side_lengths_mm": lengths.tolist(), "short_side_mm": float(sides[0]),
            "long_side_mm": float(sides[1]), "warnings": warnings}
