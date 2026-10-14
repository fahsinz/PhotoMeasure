"""DICT_4X4_50 reference detection and physically sized printable SVGs."""
from time import perf_counter
import math

import cv2
import numpy as np

from .geometry import GeometryError, validate_quad


def _rgb(rgb):
    image = np.asarray(rgb)
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8 or min(image.shape[:2]) < 2:
        raise ValueError("Detection requires a uint8 RGB image with at least two pixels per edge.")
    return image


def detect_markers(rgb: np.ndarray) -> dict:
    start = perf_counter()
    image = _rgb(rgb)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    corners, ids, rejected = detector.detectMarkers(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY))
    markers = []
    if ids is not None:
        for raw, marker_id in zip(corners, ids.reshape(-1)):
            try:
                points = validate_quad(np.asarray(raw, dtype=float).reshape(4, 2), (image.shape[1], image.shape[0]))
            except GeometryError:
                continue
            markers.append({"marker_id": int(marker_id), "corners_analysis_px": points.tolist()})
    markers.sort(key=lambda item: (item["marker_id"], item["corners_analysis_px"][0]))
    if len(markers) > 1:
        status = f"Detected {len(markers)} markers. Explicitly choose the physical reference and verify its black-square side."
    elif markers:
        status = "Marker detected. Confirm the reference and its ruler-measured black-square side."
    else:
        status = "No DICT_4X4_50 marker detected. Check focus, lighting, full black border and white quiet zone, or use manual corners."
        if rejected:
            status += " Some square-like regions could not be decoded."
    return {"markers": markers, "status": status, "latency_ms": (perf_counter() - start) * 1000}


def marker_svg(side_mm: float = 50., marker_id: int = 0) -> str:
    try:
        side = float(side_mm)
    except (TypeError, ValueError) as exc:
        raise ValueError("Marker black-square side must be finite and positive millimetres.") from exc
    if not math.isfinite(side) or side <= 0:
        raise ValueError("Marker black-square side must be finite and positive millimetres.")
    if isinstance(marker_id, bool) or not isinstance(marker_id, (int, np.integer)) or not 0 <= marker_id < 50:
        raise ValueError("DICT_4X4_50 marker ID must be an integer from 0 through 49.")
    # A 4×4 code plus one black border module per side is 6×6. Add a white
    # module on each side; labels stay below that quiet zone, outside detection.
    bits = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), int(marker_id), 6)
    module = side / 6
    extent = 8 * module
    label_height = max(16., side * .36)
    total_height = extent + label_height
    rectangles = [f'<rect x="{(x+1)*module:.9g}" y="{(y+1)*module:.9g}" width="{module:.9g}" height="{module:.9g}" fill="black"/>'
                  for y in range(6) for x in range(6) if bits[y, x] == 0]
    font = min(3.2, extent / 25)
    return '\n'.join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{extent:.9g}mm" height="{total_height:.9g}mm" viewBox="0 0 {extent:.9g} {total_height:.9g}">',
                      '<title>ArUco physical reference: print at actual size and verify with a ruler</title>',
                      f'<rect width="{extent:.9g}" height="{total_height:.9g}" fill="white"/>',
                      '<g shape-rendering="crispEdges">', *rectangles, '</g>',
                      f'<g font-family="sans-serif" font-size="{font:.9g}" text-anchor="middle" fill="black">',
                      f'<text x="{extent/2:.9g}" y="{extent+font+1:.9g}">DICT_4X4_50 ID {int(marker_id)}</text>',
                      f'<text x="{extent/2:.9g}" y="{extent+2*font+2:.9g}">Outer black side: {side:g} mm</text>',
                      f'<text x="{extent/2:.9g}" y="{extent+3*font+3:.9g}">Actual size; no fit-to-page</text>',
                      f'<text x="{extent/2:.9g}" y="{extent+4*font+4:.9g}">Verify black side with ruler</text>',
                      '</g></svg>'])
