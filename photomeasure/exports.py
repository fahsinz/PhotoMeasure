"""Versioned records, reusable annotations, and explicit missing ground truth."""
import csv
import io
import json
import math
import uuid
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError


def _positive(value, label):
    if value is not None and (not math.isfinite(value) or value <= 0):
        raise ValueError(f"{label} must be finite and positive")


def error_metrics(short_mm, long_mm, actual_short_mm=None, actual_long_mm=None) -> dict:
    out = {}
    for side, estimated, actual in (("short", short_mm, actual_short_mm), ("long", long_mm, actual_long_mm)):
        _positive(actual, "Ground truth")
        error = None if actual is None else float(estimated - actual)
        out[f"{side}_signed_error_mm"] = error
        out[f"{side}_absolute_error_mm"] = None if error is None else abs(error)
        out[f"{side}_absolute_percentage_error"] = None if error is None else 100 * abs(error) / actual
    return out


def build_record(image, result, reference_size_mm, reference_mode='manual', target_mode='manual', processing_latency_ms=0., marker_id=None, configuration=None, ground_truth_short_mm=None, ground_truth_long_mm=None) -> dict:
    if reference_size_mm is None:
        raise ValueError("Reference size must be finite and positive")
    _positive(reference_size_mm, "Reference size")
    if not math.isfinite(processing_latency_ms) or processing_latency_ms < 0:
        raise ValueError("Latency must be finite and nonnegative")
    versions = {"code": "0.1.0"}
    for package in ("numpy", "opencv-contrib-python-headless", "Pillow", "streamlit"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unavailable"
    config = dict(configuration or {})
    config.setdefault("preprocessing", {"exif_orientation": True, "alpha_background": "white", "analysis_size_px": list(image.analysis_size)})
    record = dict(result)
    record.update(schema_version="1.0", measurement_id=str(uuid.uuid4()), timestamp_utc=datetime.now(timezone.utc).isoformat(), image_hash=image.image_hash, image_name=image.image_name, original_size_px=list(image.original_size), analysis_size_px=list(image.analysis_size), resize_scale={"x": image.scale_x, "y": image.scale_y}, reference_mode=reference_mode, reference_size_mm=float(reference_size_mm), dictionary="DICT_4X4_50" if reference_mode == "aruco" else None, marker_id=marker_id, target_mode=target_mode, configuration=config, versions=versions, processing_latency_ms=float(processing_latency_ms), ground_truth_short_mm=ground_truth_short_mm, ground_truth_long_mm=ground_truth_long_mm)
    record.update(error_metrics(result["short_side_mm"], result["long_side_mm"], ground_truth_short_mm, ground_truth_long_mm))
    # Fail here instead of producing an export with nonstandard NaN tokens.
    json.dumps(record, allow_nan=False)
    return record


def records_json(records: list[dict]) -> bytes:
    return json.dumps(records, indent=2, allow_nan=False).encode("utf-8")


def records_csv(records: list[dict]) -> bytes:
    fields = ["schema_version", "measurement_id", "timestamp_utc", "image_hash", "image_name", "reference_mode", "reference_size_mm", "dictionary", "marker_id", "target_mode", "short_side_mm", "long_side_mm", "processing_latency_ms", "ground_truth_short_mm", "ground_truth_long_mm", "short_signed_error_mm", "long_signed_error_mm", "short_absolute_error_mm", "long_absolute_error_mm", "short_absolute_percentage_error", "long_absolute_percentage_error", "warnings"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for record in records:
        row = {key: record.get(key) for key in fields}
        row["warnings"] = " | ".join(record.get("warnings", []))
        # Spreadsheet formula injection protection for user-provided image names.
        name = row.get("image_name")
        if isinstance(name, str) and name.startswith(("=", "+", "-", "@", "\t", "\r")):
            row["image_name"] = "'" + name
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def annotation_json(record: dict) -> bytes:
    keys = ("schema_version", "image_hash", "analysis_size_px", "reference_size_mm", "reference_corners_analysis_px", "target_corners_analysis_px", "reference_mode", "target_mode", "marker_id", "configuration")
    return json.dumps({key: record.get(key) for key in keys}, indent=2, allow_nan=False).encode("utf-8")
