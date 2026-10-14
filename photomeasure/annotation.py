"""Render only: all geometry remains in analysis pixels and millimetres."""
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .image_io import analysis_to_original


def annotate_image(image, reference, target, result=None) -> Image.Image:
    output = Image.fromarray(image.original_rgb).copy()
    draw = ImageDraw.Draw(output)
    width = max(2, round(max(image.original_size) / 500))
    font = ImageFont.load_default(size=max(14, round(max(image.original_size) / 65)))
    for points, color in ((reference, "#008c99"), (target, "#d75500")):
        if not len(points):
            continue
        pts = [tuple(p) for p in analysis_to_original(np.asarray(points), image)]
        if len(pts) > 1:
            draw.line(pts + ([pts[0]] if len(pts) == 4 else []), fill=color, width=width)
        for i, (x, y) in enumerate(pts):
            radius = width * 2
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
            draw.text((x + radius + 2, y + radius), str(i + 1), fill=color, font=font, stroke_width=1, stroke_fill="white")
    if result:
        points = analysis_to_original(np.asarray(result["target_corners_analysis_px"]), image)
        for i, length in enumerate(result["side_lengths_mm"]):
            x, y = (points[i] + points[(i+1) % 4]) / 2
            label = f"{length / 10:.1f} cm"
            draw.text((x, y), label, fill="#b44300", font=font, stroke_width=2, stroke_fill="white")
    return output


def rectified_preview(image, result: dict, pixels_per_mm: float=3., max_edge: int=1600) -> Image.Image:
    if not math.isfinite(pixels_per_mm) or pixels_per_mm <= 0 or max_edge < 64:
        raise ValueError("Invalid rectified preview scale or limit")
    points = np.asarray(result["target_corners_plane_mm"], dtype=float)
    low, high = points.min(axis=0), points.max(axis=0)
    extent = high - low
    if not np.all(np.isfinite(extent)) or np.any(extent <= 0):
        raise ValueError("Invalid rectified crop bounds")
    scale = min(pixels_per_mm, (max_edge - 1) / float(extent.max()))
    size = tuple(max(1, int(math.ceil(v * scale)) + 1) for v in extent)
    mm_to_display = np.array([[scale, 0, -low[0]*scale], [0, scale, -low[1]*scale], [0, 0, 1]], dtype=float)
    matrix = mm_to_display @ np.asarray(result["homography_image_to_plane"], dtype=float)
    rgb = cv2.warpPerspective(image.analysis_rgb, matrix, size, borderValue=(255, 255, 255))
    output = Image.new("RGB", (max(size[0], 220), size[1]+48), "white")
    output.paste(Image.fromarray(rgb), (0, 0))
    draw = ImageDraw.Draw(output)
    desired_mm = min(50., size[0] / scale / 3)
    power = 10 ** math.floor(math.log10(desired_mm))
    bar_mm = max(v*power for v in (1, 2, 5) if v*power <= desired_mm)
    end = 12 + bar_mm * scale
    y = size[1] + 15
    draw.line((12, y, end, y), fill="black", width=3)
    draw.line((12, y-4, 12, y+4), fill="black", width=2)
    draw.line((end, y-4, end, y+4), fill="black", width=2)
    draw.text((12, y+7), f"{bar_mm:g} mm · rectified estimate", fill="black")
    return output
