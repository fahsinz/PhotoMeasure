# Milestone handoff

Implementation was delegated to geometry, UI and verification agents in isolated
Git worktrees after the lead created docs/interfaces.md and assigned ownership.
The lead maintained shared configuration/dependencies/interfaces and integrated
only the owned contributions. No detector implementation started before the
manual measurement gate passed; evaluation followed the assisted gate.

## Milestone 1: manual measurement

Works: JPEG/PNG loading, EXIF orientation, white alpha compositing, analysis
resizing, click/drag and numeric corner editing, perimeter validation, normalized
homography, mm calculations/cm presentation, warnings, annotated/rectified
previews, JSON/CSV/PNG and reusable annotation downloads.

Gate evidence: 46 independent tests passed, including noise-free perspective
recovery within 0.1 mm, cyclic/reversed ordering, invalid geometry, coordinate
scaling, image limits, export units/missing truth and stale state. A controlled
Streamlit AppTest with a mocked uploader completed measurement/render/download
generation without exceptions. The actual browser also uploaded the synthetic
example, selected/confirmed both polygons and showed dimensions and overlays.
Approximate raster clicking was a UI smoke check, not an accuracy experiment.

Manual follow-up: drag and numeric correction, undo/reset, browser resizing and
zoom/DPR, touch input, corrupt uploads, and downloaded image alignment. Test
a moderate tilted real photograph with ruler-measured coplanar surfaces.

## Milestone 2: assisted detection

Works: physical-size SVG marker printing, ArUco references, explicit choice among
markers, contour candidates, settings, editable applied corners, confirmation,
manual fallback, per-stage timing and candidate-state invalidation.

Gate evidence: 67 tests passed, including a generated marker under perspective,
rotation, multiple markers, failed detection, exact SVG black-square physical
extent/quiet zone, relative contour area, reference/boundary exclusion, bounded
rectification and stale-mode state. Controlled AppTest exercised actual synthetic
detectors through explicit marker/target selection, application, confirmation,
measurement and downloads. Further regression tests preserve this workflow.

Manual follow-up: print without scaling, ruler-check the black side, measure a
real photo, choose among multiple printed markers, correct suggestions, and
exercise both manual fallbacks. Detector smoke success is not real performance.

## Milestone 3: evaluation and documentation

Works: manifest-relative batch processing using reusable confirmed annotations,
hash/dimension/reference/schema safeguards, per-row failures, signed/absolute/
percentage errors, separate dimension/method/split summaries, explicit detection
denominators and unknown evidence, per-method warm-up and latency percentiles,
error-by-angle/lighting figures, failure report, and beginner-friendly notes.

Verification: the labeled synthetic manifest completes and produces all artifacts.
Placeholder data fails explicitly rather than producing measurements. Independent
evaluation tests check identity safeguards, undefined metrics, aggregates and
failure retention. The final test count and commands are in verification.md.

Manual follow-up: collect real photos and ruler readings, define development and
evaluation objects, freeze settings, record correction/fallback evidence and
hardware, then run the real manifest. Review failure cases before sharing approved
images. No real-photo dataset, accuracy percentages or performance claims were
fabricated. The provisional real-photo goals remain untested.
