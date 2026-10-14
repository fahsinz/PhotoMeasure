# Verification evidence and manual acceptance

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
