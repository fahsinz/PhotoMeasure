# Shared contract (schema 1.0)

Only the lead edits this document, requirements.txt, pyproject.toml and package __init__.py.
Read PROJECT_SPEC.md and this document before implementing. Milestone gates: manual
pipeline and tests first, then detection, then evaluation/docs. No real results invented.

## Ownership
Geometry agent: photomeasure/image_io.py, geometry.py; later markers.py, detection.py,
scripts/generate_marker.py. UI agent: app.py, components/**, photomeasure/annotation.py,
exports.py, ui_state.py. Verification agent: tests/**, examples/**,
scripts/generate_synthetic.py, docs/verification.md. Lead: all other files,
evaluation.py, run_evaluation.py, README and documentation. Non-overlapping files are
the fallback if worktrees unavailable. Agents do not edit shared configuration.

## Frames and types
All images NumPy uint8 H×W×3 RGB. OpenCV boundaries explicitly convert RGB to BGR
or grayscale. Image size tuples are (width,height). Points are float64 N×2 arrays,
(x,y), origin upper left, x right, y down; valid bounds 0<=x<=width-1 and
0<=y<=height-1. All geometry uses analysis pixels. EXIF orientation precedes resizing.
Resize mappings use actual width/height ratios separately (rounding is recorded).
Browser component sends analysis coordinates using CSS bounding rectangle ratios;
device pixel ratio never enters geometry. Polygon input must follow perimeter;
reject crossings before normalizing winding/start. Millimetres internally, cm display.

## Geometry API
image_io.ImageData dataclass: original_rgb, analysis_rgb, image_hash (SHA256 of
uploaded bytes), original_size, analysis_size, scale_x, scale_y, image_name.
load_image(data: bytes, image_name: str | None=None, max_long_edge: int=2000) -> ImageData
enforces 20MiB compressed, 25MP decoded, JPEG/PNG content, RGB, white alpha, EXIF.
original_to_analysis(points, image: ImageData) -> ndarray
analysis_to_original(points, image: ImageData) -> ndarray
preview_to_analysis(points, preview_size, analysis_size) -> ndarray

geometry.GeometryError(ValueError).
geometry.GeometryConfig dataclass: min_reference_area_px=100., small_edge_px=40.,
angle_warning_deg=10., opposite_warning_ratio=0.1; extra documented thresholds allowed.
validate_quad(points, image_size=None, min_area=1.) -> normalized ndarray
transform_points(points, homography) -> ndarray; guards denominators/horizon.
compute_homography(reference, reference_size_mm) -> ndarray
measure(reference, target, reference_size_mm, image_size=None, config=None) -> dict:
reference_corners_analysis_px, target_corners_analysis_px, homography_image_to_plane,
target_corners_plane_mm, side_lengths_mm (4 perimeter sides), short_side_mm,
long_side_mm, warnings (list[str]). All dict values JSON serializable.

## Rendering / export API
annotation.annotate_image(image: ImageData, reference, target, result=None) -> PIL.Image
original-oriented image with scaled outlines, numbering, cm side labels.
annotation.rectified_preview(image: ImageData, result: dict,
pixels_per_mm: float=3., max_edge: int=1600) -> PIL.Image; bounded crop and scale bar.
exports.build_record(image, result, reference_size_mm, reference_mode='manual',
target_mode='manual', processing_latency_ms=0., marker_id=None, configuration=None,
ground_truth_short_mm=None, ground_truth_long_mm=None) -> dict
exports.records_json(records: list[dict]) -> bytes
exports.records_csv(records: list[dict]) -> bytes
exports.annotation_json(record: dict) -> bytes
exports.error_metrics(short_mm, long_mm, actual_short_mm=None, actual_long_mm=None) -> dict

Full record: schema_version='1.0', UUID measurement_id, ISO UTC timestamp_utc,
image_hash, image_name, original_size_px, analysis_size_px, resize_scale (x,y),
reference_mode, reference_size_mm, dictionary ('DICT_4X4_50' or null), marker_id,
target_mode, all measure fields, configuration including preprocessing,
versions (code and installed dependency versions), processing_latency_ms,
ground_truth_short_mm/long_mm nullable, signed/absolute/percentage errors per side
nullable (never zero for absent truth). CSV flattens scalar summaries; JSON retains
all metadata and coordinates. Reusable annotation JSON: schema_version, image_hash,
analysis_size_px, reference_size_mm, reference/target corners, modes, marker ID,
configuration. No image bytes. Finite positive ground truth and reference size.

## Detection API (after Milestone 1 gate)
markers.detect_markers(rgb) -> dict: markers list of {marker_id, corners_analysis_px},
status string, latency_ms. DICT_4X4_50, subpixel refinement; caller chooses explicitly.
markers.marker_svg(side_mm=50., marker_id=0) -> str (physical black side, quiet zone).
detection.DetectionConfig dataclass: canny_low=50, canny_high=150,
min_area_ratio=.005, max_area_ratio=.9, epsilon_ratio=.02.
detection.suggest_targets(rgb, reference=None, homography=None, config=None) -> dict:
candidates list {corners_analysis_px, score, warnings}, status, latency_ms.
Exclude reference overlap/boundary, rank by area/quality; no silent choice.

## Evaluation (lead)
Manifest columns image_path,object_id,actual_short_mm,actual_long_mm,lighting,
angle_category,reference_size_mm,annotation_path,split,method,
reference_without_correction,target_without_correction,manual_fallback.
Optional reference_attempted,target_attempted booleans refine assisted denominators.
Paths relative to manifest; annotations checked against image hash and analysis size.
Failed rows retained with reasons. Missing detection evidence remains undefined.
Metrics and timing definitions follow specification. Synthetic separately labeled.
evaluation.run_evaluation(manifest_path: Path, output_dir: Path,
hardware: str='unspecified', data_kind: str='real') -> dict aggregate summary.
evaluation.summarize(rows: list[dict]) -> dict. Successful rows flatten full records
with manifest context/status='success'; failed rows retain status='failure' and
failure_reason. Warm up each method once. Missing workflow evidence yields null
rates with explicit unknown counts; processing reruns do not prove detection success.
