"""Manifest-driven, confirmed-corner evaluation. No observations are invented."""
from __future__ import annotations

import csv
import json
import math
import platform
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .detection import DetectionConfig, suggest_targets
from .exports import build_record
from .geometry import GeometryConfig, measure
from .image_io import load_image
from .markers import detect_markers


def _positive(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a positive finite number") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return result


def _flag(value: Any) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    raise ValueError("Correction/fallback flags must be true, false, or blank")


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "median": None, "p95": None}
    return {"count": len(values), "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95))}


def _rate(values: list[bool | None]) -> dict:
    unknown = sum(v is None for v in values)
    successes = sum(v is True for v in values)
    return {"attempted": len(values), "confirmed_without_correction": successes,
            "unknown": unknown, "rate": successes / len(values) if values and not unknown else None}


def summarize(rows: list[dict]) -> dict:
    good = [r for r in rows if r["status"] == "success"]
    summary = {"attempted": len(rows), "successful": len(good), "failed": len(rows)-len(good),
               "dimensions": {}, "latency_ms": _stats([r["processing_latency_ms"] for r in good])}
    for side in ("short", "long"):
        errors = [r[f"{side}_absolute_error_mm"] for r in good if r.get(f"{side}_absolute_error_mm") is not None]
        percentages = [r[f"{side}_absolute_percentage_error"] for r in good if r.get(f"{side}_absolute_percentage_error") is not None]
        summary["dimensions"][side] = {"count": len(errors),
            "mean_absolute_error_mm": float(np.mean(errors)) if errors else None,
            "median_absolute_error_mm": float(np.median(errors)) if errors else None,
            "worst_absolute_error_mm": max(errors) if errors else None,
            "median_absolute_percentage_error": float(np.median(percentages)) if percentages else None}
    assisted = [r for r in rows if r.get("method") == "assisted"]
    summary["detection"] = {side: _rate([r.get(f"{side}_without_correction") for r in assisted
        if r.get(f"{side}_attempted", True)]) for side in ("reference", "target")}
    fallback = [r.get("manual_fallback") for r in assisted]
    summary["manual_fallback"] = _rate(fallback)
    summary["assisted_completion"] = _rate([False if r["status"] != "success" else
        (None if r.get("manual_fallback") is None else not r["manual_fallback"]) for r in assisted])
    summary["stage_latency_ms"] = {stage: _stats([r["configuration"]["stage_latency_ms"][stage]
        for r in good if stage in r.get("configuration", {}).get("stage_latency_ms", {})])
        for stage in ("reference_detection", "target_suggestion", "geometry")}
    return summary


def _pipeline(image, annotation: dict, size: float, method: str) -> tuple[dict, dict]:
    config = annotation.get("configuration") or {}
    geometry = GeometryConfig(**config.get("geometry", {}))
    detection = DetectionConfig(**config.get("detection", {}))
    start = perf_counter()
    result = measure(annotation["reference_corners_analysis_px"], annotation["target_corners_analysis_px"],
                     size, image.analysis_size, geometry)
    stages = {"geometry": (perf_counter()-start)*1000}
    # Returned candidates are timed, not silently substituted for confirmed corners.
    if method == "assisted":
        reference = detect_markers(image.analysis_rgb)
        target = suggest_targets(image.analysis_rgb, annotation["reference_corners_analysis_px"],
                                 result["homography_image_to_plane"], detection)
        stages["reference_detection"] = reference["latency_ms"]
        stages["target_suggestion"] = target["latency_ms"]
    return result, stages


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["status", "failure_reason"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {}
            for key, value in row.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, allow_nan=False)
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                    value = "'" + value
                flat[key] = value
            writer.writerow(flat)


def _plots(rows: list[dict], output: Path, label: str) -> None:
    good = [r for r in rows if r["status"] == "success"]
    for category in ("angle_category", "lighting"):
        groups = sorted({r.get(category) or "unspecified" for r in good})
        fig, ax = plt.subplots(figsize=(max(6, len(groups)*1.5), 4))
        if groups:
            for offset, side, color in ((-.16, "short", "#007f83"), (.16, "long", "#d75500")):
                for index, group in enumerate(groups):
                    values = [r[f"{side}_absolute_error_mm"] for r in good
                              if (r.get(category) or "unspecified") == group]
                    ax.scatter([index+offset]*len(values), values, color=color,
                               label=side if index == 0 else None, alpha=.7)
            ax.set_xticks(range(len(groups)), groups, rotation=15)
            ax.legend()
        else:
            ax.text(.5, .5, "No successful observations", transform=ax.transAxes, ha="center")
        ax.set_ylabel("Absolute dimension error (mm)")
        ax.set_title(f"{label} · error by {category.replace('_', ' ')}")
        fig.tight_layout()
        fig.savefig(output / f"error_by_{category}.png", dpi=150)
        plt.close(fig)


def run_evaluation(manifest_path: Path, output_dir: Path, hardware: str="unspecified",
                   data_kind: str="real") -> dict:
    """Evaluate saved annotations; failed rows remain visible. Paths are manifest-relative."""
    manifest_path, output_dir = Path(manifest_path).resolve(), Path(output_dir).resolve()
    if data_kind not in ("real", "synthetic"):
        raise ValueError("data_kind must be real or synthetic")
    with manifest_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"image_path", "object_id", "actual_short_mm", "actual_long_mm", "lighting",
                    "angle_category", "reference_size_mm", "annotation_path"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Manifest requires columns: {', '.join(sorted(required))}")
        inputs = list(reader)
    rows = []
    warmed: set[str] = set()
    for index, source in enumerate(inputs, 2):
        row = {key: source.get(key, "") for key in ("image_path", "object_id", "lighting", "angle_category", "split")}
        row.update(manifest_row=index, method=source.get("method") or "manual", data_kind=data_kind)
        try:
            if row["method"] not in ("manual", "assisted"):
                raise ValueError("Method must be manual or assisted")
            for flag in ("reference_without_correction", "target_without_correction", "manual_fallback"):
                row[flag] = _flag(source.get(flag))
            for side in ("reference", "target"):
                attempted = _flag(source.get(side+"_attempted"))
                row[side+"_attempted"] = row["method"] == "assisted" if attempted is None else attempted
            short = _positive(source["actual_short_mm"], "Actual short side")
            long = _positive(source["actual_long_mm"], "Actual long side")
            size = _positive(source["reference_size_mm"], "Reference size")
            if short > long:
                raise ValueError("Actual short side cannot exceed actual long side")
            annotation_path = manifest_path.parent / source["annotation_path"]
            annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
            if not isinstance(annotation, dict):
                raise ValueError("Annotation must be a JSON object")
            if annotation.get("schema_version") != "1.0":
                raise ValueError("Unsupported annotation schema; require 1.0")
            config = annotation.get("configuration") or {}
            if not isinstance(config, dict):
                raise ValueError("Annotation configuration must be a JSON object")
            if config.get("synthetic") and data_kind != "synthetic":
                raise ValueError("Synthetic annotation requires --data-kind synthetic")
            edge = config.get("max_analysis_long_edge", config.get("max_long_edge", 2000))
            if isinstance(edge, bool) or not isinstance(edge, int) or not 1 <= edge <= 4000:
                raise ValueError("Annotation analysis edge must be an integer in 1..4000")
            path = manifest_path.parent / source["image_path"]
            if path.stat().st_size > 20*1024*1024:
                raise ValueError("Compressed image exceeds 20 MiB")
            image = load_image(path.read_bytes(), path.name, edge)
            if annotation.get("image_hash") != image.image_hash:
                raise ValueError("Annotation image hash does not match uploaded bytes")
            if annotation.get("analysis_size_px") != list(image.analysis_size):
                raise ValueError("Annotation analysis dimensions do not match preprocessing")
            if not math.isclose(_positive(annotation.get("reference_size_mm"), "Annotation reference size"), size, rel_tol=1e-9):
                raise ValueError("Manifest and annotation reference sizes differ")
            if row["method"] not in warmed:
                _pipeline(image, annotation, size, row["method"])
                warmed.add(row["method"])
            result, stages = _pipeline(image, annotation, size, row["method"])
            record = build_record(image, result, size,
                reference_mode=annotation.get("reference_mode", "manual"),
                target_mode=annotation.get("target_mode", "manual"), marker_id=annotation.get("marker_id"),
                processing_latency_ms=sum(stages.values()), configuration={**config, "stage_latency_ms": stages},
                ground_truth_short_mm=short, ground_truth_long_mm=long)
            row.update(record, status="success", failure_reason=None)
        except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
            row.update(status="failure", failure_reason=str(exc))
        rows.append(row)
    summary = summarize(rows)
    summary.update(schema_version="1.0", data_kind=data_kind, hardware=hardware,
        platform=platform.platform(), python=platform.python_version(), warmup_count=len(warmed),
        warmed_methods=sorted(warmed),
        resolution_samples_px=[r["analysis_size_px"] for r in rows if r["status"] == "success"],
        latency_scope="successful confirmed-corner processing; excludes decoding/rendering/human work",
        warning="Synthetic checks are not real-photo accuracy evidence." if data_kind == "synthetic" else
                "User-supplied observations; repeated photos of one object are not independent samples.")
    summary["by_split"] = {split: summarize([r for r in rows if (r.get("split") or "unspecified") == split])
                           for split in sorted({r.get("split") or "unspecified" for r in rows})}
    summary["by_method"] = {method: summarize([r for r in rows if r["method"] == method])
                            for method in sorted({r["method"] for r in rows})}
    summary["object_count"] = len({r["object_id"] for r in rows})
    split_objects = {split: {r["object_id"] for r in rows if r.get("split") == split}
                     for split in ("development", "evaluation")}
    summary["split_overlap_objects"] = sorted(split_objects["development"] & split_objects["evaluation"])
    frozen_settings = {json.dumps({key: r["configuration"].get(key) for key in ("geometry", "detection", "max_analysis_long_edge", "max_long_edge")}, sort_keys=True)
                       for r in rows if r["status"] == "success" and r.get("split") == "evaluation"}
    summary["evaluation_settings_consistent"] = len(frozen_settings) <= 1
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(json.dumps(rows, indent=2, allow_nan=False), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    _write_csv(output_dir / "per_photo.csv", rows)
    _plots(rows, output_dir, data_kind.upper())
    failed = [r for r in rows if r["status"] == "failure"]
    report = [f"# {data_kind.upper()} failure report", "", f"{len(failed)} failures / {len(rows)} attempts.", "",
              "Image paths only; no private photos copied. Approve representative images before sharing.", ""]
    report += [f"- Row {r['manifest_row']}: {r['image_path']} — {r['failure_reason']}" for r in failed]
    (output_dir / "failures.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    return summary
