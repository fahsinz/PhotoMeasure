# Verification evidence and manual acceptance

Final integrated run on 2026-10-14: **88 passed** using Python 3.11.9,
NumPy 2.2.6, OpenCV 4.13.0, Pillow 12.1.0 and Streamlit 1.55.0.
Command: `.venv\Scripts\python -m pytest -q -p no:cacheprovider`.
`pip check` reports no broken requirements; compileall succeeds. The labeled
synthetic batch generates CSV, JSON, summary, two plots and a failure report.
The lead also completed a live browser upload, corner selection/confirmation
and measurement on the synthetic example. Drag/zoom/DPR and real photos remain
unverified manual checks. Mocked-upload AppTest exercises actual processing.

All generated examples are synthetic. They check the implementation and do not
establish accuracy on real photographs. No real-photo evaluation is reported.

The independent geometry oracle begins with a 50 mm square and an 80 × 120 mm
rectangle in a metric plane and applies a known projective matrix. Tests recover
their dimensions with a 0.1 mm tolerance, test all cyclic starts and both windings,
reject crossing/duplicate/concave/collinear polygons, and exercise homogeneous
projection failures. The fixture does not use the application's transform function.

Image tests check EXIF orientation, RGB channels, white transparency composition,
byte limits and decoded limits, content hashing, rounded width/height resize ratios,
and CSS preview mappings. Equivalent original and analysis selections must measure
the same millimetre values. Export and UI-state checks are added against their
public contracts when integrated.

Run `python -m pytest -q`. Generate the standalone demo with
`python scripts/generate_synthetic.py --output examples`. Select the dark reference
square (50 mm) and light target. The exact annotation JSON is available for batch
evaluation. Clicking raster edges introduces selection error; the noiseless
80 × 120 mm expectation applies to the saved mathematical corners.

## Manual checks requiring a browser and/or user photos

- Launch Streamlit, upload the synthetic image, select reference and target,
  edit a mistaken corner, undo, confirm and download PNG/CSV/JSON.
- Resize the browser and repeat selections; overlays should remain aligned.
  Check at multiple operating-system/browser zoom settings and device pixel ratios.
- Change image, analysis size, reference size, or selected corners after measuring.
  A result and downloads must never refer to the previous state.
- Verify outline labels use centimetres and raw exports use millimetres.
- Upload a corrupt image; the interface should show a useful message.
- Use ruler-measured coplanar objects in real photos at moderate tilt.
  Real-photo accuracy and capture limitations await user-collected data.

Automated state tests cover the pure state helper; browser interaction and visual
alignment still require manual acceptance. A server health check alone cannot
establish that these human workflows were completed.

## Assisted detection smoke tests

Detector checks construct an actual DICT_4X4_50 marker using OpenCV's generator,
warp the entire reference/target plane independently, recover its marker ID and
measure the manually supplied warped target. The 1.5 mm smoke tolerance accounts
for raster corner localization and is separate from the 0.1 mm exact geometry
requirement. Additional tests cover marker rotations, multiple-marker preservation,
blank-image actionable failure, SVG physical black-square extent and quiet zone,
invalid contour settings, reference and boundary exclusion, and relative-area
behavior at two analysis resolutions. No detection rate on real photos is claimed.

Manual assisted acceptance: detect a printed marker, explicitly choose among
multiple markers, select a suggested target, correct one corner, confirm and
measure. Blank/low-contrast photos must retain manual fallback. Switching modes,
marker choice or contour settings after measuring must clear results/downloads.

## Evaluation checks

Evaluation tests use the labeled synthetic image and exact saved annotation in
temporary directories. They verify manifest-relative paths, full output artifacts,
separate short/long error aggregation, retained failures and their denominators,
undefined detection rates when evidence is missing, rejected hash/resolution/schema
and physical-size mismatches, and rejection of synthetic annotations in real mode.
An independent timing regression gives each method's first invocation an extreme
duration and checks that warm-up calls are excluded from measured stage summaries.

Controlled Streamlit AppTest checks mock only the file uploader: real image decode,
geometry, ArUco and contour detection run. They exercise manual measurement and
centimetre display, reference-size/preprocessing invalidation, explicit automatic
candidate choices, confirmation, correct export method/marker metadata, stage
latency fields, and redetection clearing prior target/provenance/results. These
checks validate application flow but do not exercise browser pointer dragging or
the operating-system file chooser.

Real dataset collection, ruler ground truth, assisted-confirmation observation,
hardware-specific latency, and approved representative failure photos remain
user-dependent. Passing this suite does not fill the empty real-photo workflow.
