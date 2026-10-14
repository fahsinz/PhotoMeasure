"""Local PhotoMeasure UI. Run with: streamlit run app.py."""
import base64
import hashlib
import io
import time
from dataclasses import asdict

import numpy as np
from PIL import Image
import streamlit as st

from components import corner_editor
from photomeasure.annotation import annotate_image, rectified_preview
from photomeasure.exports import build_record, records_csv, records_json, annotation_json
from photomeasure.geometry import GeometryConfig, measure, validate_quad
from photomeasure.image_io import load_image
from photomeasure.ui_state import SelectionState


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@st.cache_data(show_spinner=False, max_entries=2)
def decoded_image(data, name, long_edge):
    return load_image(data, name, max_long_edge=long_edge)


@st.cache_data(show_spinner=False, max_entries=2)
def component_image(data, name, long_edge):
    image = decoded_image(data, name, long_edge)
    return "data:image/png;base64," + base64.b64encode(png_bytes(Image.fromarray(image.analysis_rgb))).decode("ascii")


st.set_page_config(page_title="PhotoMeasure", page_icon="📏", layout="wide")
st.title("PhotoMeasure")
st.caption("Estimate a flat rectangle's dimensions from a photograph.")
st.info("The reference square and target surface must be flat and on the same plane. Use the main camera, keep the reference near the object, and avoid ultra-wide mode.")
if "selection" not in st.session_state:
    st.session_state.selection = SelectionState()
state = st.session_state.selection

st.subheader("1 · Upload")
with st.expander("Analysis and validation settings"):
    long_edge = st.number_input("Maximum analysis long edge (pixels)", min_value=200, max_value=4000, value=2000, step=100)
    angle_warning = st.number_input("Right-angle warning threshold (degrees)", min_value=1., max_value=45., value=10.)
    opposite_warning = st.number_input("Opposite-side disagreement warning (%)", min_value=1., max_value=100., value=10.)
uploaded = st.file_uploader("JPEG or PNG · up to 20 MB and 25 megapixels", type=["jpg", "jpeg", "png"])
if uploaded is None:
    state.set_image("")
    st.stop()
data = uploaded.getvalue()
key = hashlib.sha256(data).hexdigest() + f":{long_edge}"
state.set_image(key)
try:
    image = decoded_image(data, uploaded.name, int(long_edge))
except (ValueError, OSError) as exc:
    state.reset()
    st.error(str(exc))
    st.stop()
st.caption(f"Oriented image: {image.original_size[0]} × {image.original_size[1]} px · analysis: {image.analysis_size[0]} × {image.analysis_size[1]} px")
if st.button("Reset all selections and results"):
    state.reset()
    st.rerun()

st.subheader("2 · Select")
reference_size = st.number_input("Actual reference square side (mm) — verify with a ruler", min_value=0.1, max_value=10000., value=50., step=1.)
state.set_settings((reference_size, angle_warning, opposite_warning))
active = st.radio("Corners to edit", ["reference", "target"], horizontal=True, format_func=lambda v: "Reference square (teal)" if v == "reference" else "Target rectangle (orange)")
st.write("Click four corners around each shape's perimeter. Crossing outlines are rejected. Confirm each selection after editing.")
event = corner_editor(component_image(data, uploaded.name, int(long_edge)), image.analysis_size, state.reference, state.target, active, state.revision, key=f"corners-{state.image_key}")
if event and event.get("revision") == state.revision and event.get("kind") == active:
    points = event.get("points", [])
    if points != getattr(state, active):
        state.set_points(active, points)
        st.rerun()

columns = st.columns(3)
if columns[0].button(f"Undo last {active} corner", disabled=not getattr(state, active)):
    state.set_points(active, getattr(state, active)[:-1])
    st.rerun()
if columns[1].button(f"Reset {active}", disabled=not getattr(state, active)):
    state.set_points(active, [])
    st.rerun()
if columns[2].button(f"Confirm {active}", disabled=len(getattr(state, active)) != 4):
    try:
        validate_quad(getattr(state, active), image.analysis_size, min_area=100. if active == "reference" else 1.)
        setattr(state, active + "_confirmed", True)
        state.invalidate()
    except ValueError as exc:
        st.error(str(exc))

with st.expander("Edit exact corner coordinates (analysis pixels)"):
    points = getattr(state, active)
    if not points:
        st.caption("Select a corner on the image first.")
    else:
        with st.form(f"numeric-{active}-{state.image_key}-{state.revision}"):
            edited = []
            for i, (x, y) in enumerate(points):
                cols = st.columns(2)
                edited.append([cols[0].number_input(f"Corner {i+1} x", min_value=0., max_value=float(image.analysis_size[0]-1), value=float(x), key=f"x-{active}-{i}-{state.revision}"), cols[1].number_input(f"Corner {i+1} y", min_value=0., max_value=float(image.analysis_size[1]-1), value=float(y), key=f"y-{active}-{i}-{state.revision}")])
            if st.form_submit_button("Apply coordinate edits"):
                state.set_points(active, edited)
                st.rerun()
st.caption(f"Reference: {'confirmed' if state.reference_confirmed else 'needs confirmation'} · Target: {'confirmed' if state.target_confirmed else 'needs confirmation'}")

st.subheader("3 · Measure")
with st.expander("Optional ruler measurements for error calculation"):
    use_truth = st.checkbox("I have ruler-measured target dimensions")
    if use_truth:
        c = st.columns(2)
        actual_short = c[0].number_input("Ruler short side (mm)", min_value=0.1, value=100.)
        actual_long = c[1].number_input("Ruler long side (mm)", min_value=0.1, value=150.)
    else:
        actual_short = actual_long = None
truth_key = (actual_short, actual_long)
if st.session_state.get("truth_key") != truth_key:
    st.session_state.truth_key = truth_key
    state.invalidate()
config = GeometryConfig(angle_warning_deg=angle_warning, opposite_warning_ratio=opposite_warning/100)
if st.button("Measure confirmed corners", type="primary", disabled=not (state.reference_confirmed and state.target_confirmed)):
    try:
        start = time.perf_counter()
        result = measure(state.reference, state.target, reference_size, image.analysis_size, config)
        latency_ms = (time.perf_counter() - start) * 1000
        record = build_record(image, result, reference_size, processing_latency_ms=latency_ms, configuration={"max_analysis_long_edge": long_edge, "geometry": asdict(config)}, ground_truth_short_mm=actual_short, ground_truth_long_mm=actual_long)
        state.result, state.record = result, record
    except ValueError as exc:
        state.invalidate()
        st.error(str(exc))

if state.result is not None and state.record is not None and state.record["image_hash"] == image.image_hash:
    result, record = state.result, state.record
    c = st.columns(2)
    c[0].metric("Estimated short side", f"{result['short_side_mm']/10:.1f} cm")
    c[1].metric("Estimated long side", f"{result['long_side_mm']/10:.1f} cm")
    st.caption(f"Manual planar homography · reference {reference_size:g} mm · geometry {record['processing_latency_ms']:.1f} ms. Display rounding does not indicate accuracy.")
    for warning in result["warnings"]:
        st.warning(warning)
    if actual_short is not None:
        st.write(f"Absolute error: short {record['short_absolute_error_mm']:.2f} mm ({record['short_absolute_percentage_error']:.1f}%), long {record['long_absolute_error_mm']:.2f} mm ({record['long_absolute_percentage_error']:.1f}%).")
    annotated = annotate_image(image, result["reference_corners_analysis_px"], result["target_corners_analysis_px"], result)
    st.image(annotated, caption="Oriented image with estimated side lengths", width="stretch")
    try:
        st.image(rectified_preview(image, result), caption="Rectified target with metric scale bar", width="stretch")
    except ValueError as exc:
        st.warning(f"Rectified preview unavailable: {exc}")
    c = st.columns(4)
    c[0].download_button("Annotated PNG", png_bytes(annotated), "photomeasure.png", "image/png")
    c[1].download_button("CSV", records_csv([record]), "measurement.csv", "text/csv")
    c[2].download_button("Full JSON", records_json([record]), "measurement.json", "application/json")
    c[3].download_button("Reusable annotation", annotation_json(record), "annotation.json", "application/json")
else:
    st.caption("Confirm reference and target corners, then measure. Edits clear the previous result and downloads.")
