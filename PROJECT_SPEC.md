# PhotoMeasure — Personal Project Specification

## 1. Instructions for the coding agent

Build the local Python application described below. This is a personal portfolio project to demonstrate skills relevant to the Measure.pics opportunity; it is not an official employer specification or integration with its product.

Implement the milestones in order. Finish and verify the core measurement pipeline before adding automatic detection. Make routine implementation decisions independently and document them. Ask only when blocked by a missing external dependency or a decision that materially changes scope. Do not invent experimental results or claim real-world accuracy based on synthetic tests. Explain the mathematics in beginner-friendly documentation so the owner can understand and demonstrate the project.

Deliver working code, meaningful geometry tests, a usable local interface, setup instructions, and an evaluation workflow. Optional features must not delay the required features. No cloud deployment is required.

## 2. Objective and bounded scope

Estimate the two side dimensions of a flat rectangular object from a single photograph containing a square reference marker of known physical size. Show measurements on the image and evaluate them against ruler measurements.

Supported examples: rectangular paper, photographs, and thin cards on a flat table. The marker and measured object surface must be on the same plane. Thick books, boxes, curved surfaces, object height, and measurements across different planes are unsupported.

Required capabilities:

- Local JPEG/PNG upload.
- Manual reference and target corner selection.
- Metric measurement through planar perspective correction.
- Automatic reference detection using a printed ArUco marker.
- Assisted automatic target detection, with manual correction.
- Annotated image and CSV/JSON export.
- Reproducible experiments reporting error, detection success, latency, and failure cases.

Excluded: trained ML models, arbitrary object recognition, LiDAR, depth estimation, 3D reconstruction, live video, native phone applications, user accounts, cloud APIs, and employer application integration. A phone camera is sufficient for taking photos, which are then uploaded locally.

## 3. Technology and project organization

Use Python 3.11+, NumPy, OpenCV's headless contrib distribution, Pillow, Streamlit, and pytest. Use Matplotlib for evaluation figures and pandas only if it simplifies evaluation/export. Use one tested OpenCV distribution; do not install competing OpenCV wheels. Choose and pin compatible versions after verifying the environment. No GPU is required.

Use a small Streamlit custom component if needed for reliable click/drag image annotation. Keep it limited to annotation rather than building a separate frontend application. Any third-party component must be maintained enough to work with the pinned Streamlit version and documented.

Suggested structure:

```text
photomeasure/
  app.py
  photomeasure/
    image_io.py
    geometry.py
    markers.py
    detection.py
    annotation.py
    exports.py
    evaluation.py
  components/             # only if a custom annotation component is needed
  scripts/
    generate_marker.py
    run_evaluation.py
  tests/
  examples/               # reproducible synthetic examples, clearly labeled
  evaluation/
    annotations/          # saved reusable input coordinates
    manifest_example.csv
    results/              # generated from real runs, never fabricated
  docs/
    architecture.md
    measurement_method.md
    evaluation_protocol.md
    limitations.md
  README.md
  requirements.txt
  .gitignore
```

Keep processing code independent of Streamlit. Use type hints and clear function boundaries. Avoid elaborate architecture, external databases, or unnecessary services. Store uploaded images in memory unless the user explicitly exports/saves them. Ignore private photos, environments, caches, and generated bulk results in Git.

## 4. User interface and workflow

Use a clean light interface with three steps: Upload, Select, Measure. Provide concise plain-language instructions, visible measurement units, and a Reset action.

### Upload

Accept JPEG and PNG, maximum 20 MB compressed and 25 megapixels decoded. Validate content and decoding rather than relying only on extension. Reject unsupported/corrupt images with a useful error. Apply EXIF orientation before establishing coordinates. Convert supported images to a consistent RGB representation, and correctly convert RGB/BGR at OpenCV boundaries. Composite transparent PNGs onto white. If resizing for analysis, use one consistent analysis image and record its dimensions and coordinate mappings; maximum analysis long edge is 2000 pixels by default.

Reset selections and results when the image or preprocessing settings change. Retain the current state through ordinary UI reruns. Identify the image using a content hash so state cannot leak between uploads.

### Select reference

Offer Manual and ArUco modes:

- Manual: click four corners of a physical square reference, enter its measured side length in millimetres, and confirm the selection. Default suggestion: 50 mm, which must be verified by the user.
- ArUco: use dictionary DICT_4X4_50 and default marker ID 0; detect the four outer black-square corners. If multiple valid markers appear, require explicit choice. Show the detected marker outline and editable physical size.
- The printed marker generator must produce marker ID 0 with a white quiet zone. Label the intended 50 mm outer black-square side separately from the quiet zone. Export printable SVG or a lossless PNG with print-size instructions. Print at actual size without fit-to-page, then measure the black-square side with a ruler and enter that actual value.
- If automatic reference detection fails, show a reason when identifiable and offer manual selection. Never use a guessed reference size or an unconfirmed substitute.

### Select target

- Manual mode: click four target corners around the perimeter. Allow drag/edit, undo, and reset.
- Assisted mode: suggest rectangular quadrilaterals from contours; display candidates and require the user to select and confirm one. Exclude the reference itself and likely image-boundary contours. Provide editable edge/contour settings in an advanced panel.
- If no useful candidate appears, keep manual mode available. Never silently measure the largest contour.
- Show the reference and target in distinct colors with numbered corners.
- Support one target per measurement initially. Repeated measurements may be appended to an export table.

### Results

- Show Short side and Long side in centimetres, to one decimal place by default. Store unrounded millimetre values internally. Do not imply millimetre precision just because more decimals are available.
- Overlay the measured target outline and side labels on the original-oriented preview. Also show a rectified preview with a scale bar when the transform is valid. Limit rectified output dimensions to avoid excessive allocations.
- Show method, reference size, and processing time. Label results as estimates. Provide a persistent reminder that both surfaces must be flat and coplanar.
- Show specific validation warnings instead of an unsupported numerical confidence score.
- Download an annotated PNG and one-row or accumulated CSV/JSON. Include units in field names.
- Optional real ground-truth inputs: ruler-measured short/long dimensions. Calculate and display errors only when those values are supplied.

## 5. Geometry specification

Do not use one global pixels-per-centimetre factor on an angled image. A simple scale calculation is valid only in the restricted top-down baseline. The completed required pipeline uses a planar homography.

1. Express all selected/detected points in the same analysis-image coordinate system.
2. Validate the reference polygon. Require four distinct finite points forming a convex, non-self-intersecting quadrilateral with sufficient area and no nearly collinear edges. Reject invalid click order with clear correction instructions; do not silently reinterpret a crossing polygon. For perimeter-ordered points, normalize winding and start corner deterministically.
3. Map the four reference corners to the square coordinates `(0,0)`, `(s,0)`, `(s,s)`, `(0,s)`, where `s` is the actual side in millimetres. An arbitrary cyclic start corner rotates the coordinate frame but must not change measured lengths.
4. Estimate the image-to-plane homography. Check finite coefficients, invertibility, and sensible numerical conditioning using normalized coordinates; do not interpret a raw matrix condition number without accounting for units and scale. Document validation thresholds.
5. Validate and transform the four target corners into the plane coordinate system. Reject nonfinite results and near-zero homogeneous denominators.
6. Compute the four Euclidean side lengths in millimetres. Average each pair of opposite sides to get two side estimates, then sort them into short and long. Preserve the individual side values in debug/export metadata.
7. Check transformed right angles and opposite-side consistency. Start with warning thresholds of 10 degrees deviation from 90 degrees or 10% opposite-side disagreement; make these configurable and document that they are heuristic warnings, not calibrated accuracy guarantees.
8. Use the inverse homography for overlays or metric grid projection. Distinguish image-to-plane millimetres from rectified-display pixels, with an explicit mm-to-display-pixel scale.

Additional checks: physical reference size must be finite and positive; require at least 100 pixels of reference polygon area after analysis resizing; warn if its shortest image edge is below 40 pixels. Treat these as tunable operating thresholds. Points must remain inside image bounds. Guard resource use for extreme transforms and rectified crops. Block measurement for a degenerate transform; warn for small/distant references or strongly distorted targets.

A single four-corner reference fits its own correspondences by construction. Its reprojection residual is not evidence of measurement accuracy. One image also cannot reliably verify that the target is truly coplanar or rectangular; communicate the capture assumptions explicitly.

Camera lens distortion is not corrected in the required version. Explain that wide-angle lenses, image edges, tiny markers, and extrapolation far from the marker can increase error. Recommend the main phone camera, avoiding ultra-wide mode, and keeping the marker close to the object. Optional calibrated undistortion is a later extension; if implemented, reference and target points must share the same undistorted coordinate system.

## 6. Automatic detection

Reference detection: use OpenCV ArUco and optional corner refinement. Return IDs, corners, and actionable status. Marker orientation and corner ordering must remain consistent with the geometry module.

Target suggestions: grayscale conversion, light denoising, edge detection, contours, polygon approximation, and quadrilateral filtering. Use relative area thresholds so resizing does not break behavior. Rank suggestions by usable area and quadrilateral quality, documenting the scoring. Validate rectangularity in the rectified plane; an angled image of a rectangle need not have image-space right angles. Manual confirmation is mandatory. No trained segmentation model is needed.

Do not describe this as general object recognition or guaranteed automatic measurement. Detection failure and measurement error are separate outcomes.

## 7. Data and exports

Each saved measurement must contain:

- schema_version, measurement_id, timestamp_utc, image_hash, optional image_name;
- original-oriented and analysis image dimensions, resize scale;
- reference_mode, reference_size_mm, dictionary and marker_id where applicable;
- target_mode, reference_corners_analysis_px, target_corners_analysis_px;
- homography_image_to_plane, individual side lengths, short_side_mm, long_side_mm;
- warnings, preprocessing/configuration values, code/dependency version identifiers;
- processing_latency_ms;
- optional ground_truth_short_mm and ground_truth_long_mm and derived errors.

CSV is a flattened summary; JSON preserves coordinates and full metadata. Include a documented schema version. Do not export undefined errors as zero. Persist reusable annotation JSON separately for batch evaluation. Never embed full image bytes in CSV/JSON. Ground-truth inputs must be positive and finite.

## 8. Evaluation plan

Create a small user-collected dataset with ruler-measured flat rectangular objects. Suggested minimum: 5 distinct objects × 3 approximate camera angles (top-down, moderate tilt, strong tilt) × 2 lighting conditions = 30 photos. Record conditions as approximate unless measured. Keep the same camera for this first experiment, record reference size, and retain failed cases. Repeated photos of the same object are not independent object samples.

Record a CSV manifest with image_path, object_id, actual short/long dimensions in mm, lighting, angle_category, reference size, and annotation_path where needed. Provide an example manifest with clearly labeled placeholders, not fake observations.

Compare:

1. Manual homography measurements across the full set.
2. Assisted detection with confirmed/corrected corners, recording how often correction was needed.
3. Optional naive single-scale baseline to demonstrate angle sensitivity, labeled as unsuitable for tilted photographs.

Use a small development subset to tune contour settings, then freeze settings before measuring a separate evaluation subset. Split by object when possible. For a tiny dataset, describe findings as a demonstration rather than a general accuracy claim.

Metrics:

- Signed error: estimate − actual, in mm.
- Absolute error: abs(estimate − actual), in mm.
- Absolute percentage error: 100 × absolute error / actual.
- Report short/long dimensions separately, mean and median absolute error, worst error, and number of successful measurements.
- Detection success: valid candidates confirmed without correction / all attempted relevant photos. Report reference and target separately.
- Assisted completion and manual fallback rates separately; exclude failures from error aggregates but always report their count and reasons.
- Processing latency: monotonic elapsed time for reference detection, target suggestion, and geometry, excluding upload, rendering, and human selection. Report median and 95th percentile after one warm-up, sample count, image resolution, and hardware.

Generate per-photo results CSV, aggregate summary, error-by-angle/lighting figures, and a failure-case report with representative images the user has approved for sharing. Label synthetic outputs separately from real-photo results. Do not fabricate data to fill a report.

Provisional real-photo goals, not promises: median dimension percentage error at or below 5% for supported top-down/moderately tilted conditions; median processing below 1 second for 2000-pixel-long-edge images on the documented laptop. If missed, report actual results and investigate. A truthful evaluated prototype is a valid deliverable even when exploratory goals are missed.

## 9. Verification and acceptance criteria

Required meaningful geometry tests:

- A known rectangle and reference under a simulated perspective transform recover true dimensions within 0.1 mm in noise-free double-precision calculations.
- Cyclic reference ordering and normalized reversed winding preserve lengths; crossing or duplicated points are rejected.
- Image resizing and preview coordinate conversion preserve dimensions for equivalent selected points.
- Invalid reference size, collinear points, singular transforms, and near-zero projection denominators fail with explicit errors.
- A synthetic generated marker can be detected after a supported perspective warp; label this as a detector smoke test, not real-world validation.
- Error calculations, missing ground truth, and export round-trip behavior are correct.

Manual interface acceptance:

- A new user can launch locally, upload an image, select reference/target corners, edit a mistaken point, and export a result using the README.
- Selection remains aligned when the browser/image preview is resized. Device-pixel ratio and component display scaling do not alter coordinates.
- Image changes clear stale results; export never refers to a previous upload or prior selection.
- Automatic reference failure and target failure both permit explicit manual fallback.
- A moderate angled photo can be measured using the same planar method as a top-down photo.
- Oversized/corrupt uploads are handled without a stack trace in the normal user interface.
- The annotated export matches the displayed object and units.

Run the appropriate tests and a local app smoke check. Document any checks that require human interaction or real images and have not yet been performed. Mockups and synthetic examples must not be represented as completed real-photo evaluation.

## 10. Implementation milestones

### Milestone 1 — Manual measurement

Implement image loading, manual point selection, reference size entry, validated geometry, results, annotated export, and core geometry tests. A restricted top-down baseline may be a temporary development step; the milestone is complete only when planar perspective measurement works.

### Milestone 2 — Assisted detection

Add printable marker generation, ArUco reference detection, target candidate suggestions, editable selections, and clear manual fallbacks. Verify the automatic path against manually selected examples.

### Milestone 3 — Evaluation and handoff

Add manifest-driven batch evaluation with saved annotations, JSON/CSV exports, plots, beginner-friendly technical notes, limitations, and a demo walkthrough. Prepare the empty real-photo evaluation workflow if the user has not yet supplied photos. State exactly which parts await user data.

## 11. Final documentation and portfolio evidence

README must include purpose, supported assumptions, installation in a virtual environment, exact launch/test/evaluation commands, marker printing instructions, a five-minute demo guide, known limitations, and a concise explanation of the geometry.

Architecture notes explain image data flow, coordinate frames, detection/measurement separation, and major dependency choices. Measurement notes explain pixels, physical scale, homography, coplanarity, and measurement error without assuming computer-vision knowledge.

Include a short reproducible synthetic demo so installation can be verified before real photos are collected. State that the ruler is the real-photo ground truth and that its own resolution contributes uncertainty. Do not imply accuracy beyond the evaluation evidence.

The finished portfolio should support a factual statement such as: “Built a Python/OpenCV prototype estimating planar object dimensions from photographs using reference-marker detection and perspective correction; evaluated measurement error and failure cases across camera angles and lighting conditions.” Add numerical claims only after measuring them.

## 12. Optional extensions after all required work

Camera calibration and lens undistortion; measurement of arbitrary point-to-point distances on the same plane; repeated captures to study variability; more target shapes with validated geometry. Require explicit expansion before mobile development, depth processing, or trained ML models.

## 13. Technical reference

OpenCV's official homography tutorial explains planar transformations and perspective correction: https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html

Use official documentation matching the installed OpenCV and Streamlit versions when implementing APIs. This specification defines desired behavior; confirm library signatures during implementation.
