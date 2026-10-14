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
from photomeasure.geometry import GeometryConfig, measure, validate_quad, compute_homography
from photomeasure.image_io import load_image
from photomeasure.ui_state import SelectionState
from photomeasure.markers import detect_markers, marker_svg
from photomeasure.detection import DetectionConfig, suggest_targets


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
mode_columns = st.columns(2)
reference_mode = mode_columns[0].radio("Reference selection mode", ["manual", "aruco"], horizontal=True, format_func=lambda v: "Manual" if v == "manual" else "ArUco")
target_mode = mode_columns[1].radio("Target selection mode", ["manual", "assisted"], horizontal=True, format_func=lambda v: "Manual" if v == "manual" else "Assisted contours")
with st.expander("Advanced target contour settings"):
    dc = st.columns(2)
    canny_low = dc[0].number_input("Canny low threshold", min_value=0, max_value=254, value=50)
    canny_high = dc[1].number_input("Canny high threshold", min_value=1, max_value=255, value=150)
    min_area = dc[0].number_input("Minimum image area fraction", min_value=0.0001, max_value=0.99, value=0.005, format="%.4f")
    max_area = dc[1].number_input("Maximum image area fraction", min_value=0.001, max_value=1., value=0.9, format="%.3f")
    epsilon = st.number_input("Contour approximation fraction", min_value=0.001, max_value=0.199, value=0.02, format="%.3f")
detection_config = DetectionConfig(canny_low=int(canny_low), canny_high=int(canny_high), min_area_ratio=min_area, max_area_ratio=max_area, epsilon_ratio=epsilon)
settings = (reference_size, angle_warning, opposite_warning, reference_mode, target_mode, canny_low, canny_high, min_area, max_area, epsilon)
previous_settings = state.settings_key
state.set_settings(settings)
if previous_settings is not None and len(previous_settings) > 3 and previous_settings[3] != reference_mode:
    state.set_points("reference", [])
    state.marker_id = None
if previous_settings is not None and len(previous_settings) > 4 and previous_settings[4] != target_mode:
    state.set_points("target", [])
if reference_mode == "aruco":
    st.caption("DICT_4X4_50 · default print ID 0. Detected outer black-square corners need your explicit selection and confirmation.")
    with st.expander("Print a square reference marker"):
        print_id = st.number_input("Marker ID to print", min_value=0, max_value=49, value=0)
        st.write("The SVG black square is 50 mm per side, with a separate white quiet zone. Print at actual size without fit-to-page. Measure the black-square side with a ruler and enter the actual size above.")
        st.download_button("Download printable SVG", marker_svg(side_mm=50., marker_id=int(print_id)).encode("utf-8"), f"aruco-{print_id}-50mm.svg", "image/svg+xml")
    if st.button("Detect ArUco references"):
        state.reference_detection = detect_markers(image.analysis_rgb)
        state.reference_confirmed = False
        state.invalidate()
    if state.reference_detection is not None:
        found = state.reference_detection
        st.caption(found["status"])
        markers = found["markers"]
        if markers:
            chosen = st.selectbox("Choose the reference marker", range(len(markers)), index=None, placeholder="Select a detected marker explicitly", format_func=lambda i: f"Candidate {i+1}: marker ID {markers[i]['marker_id']}", key=f"marker-choice-{state.image_key}-{state.revision}")
            if chosen is not None:
                marker = markers[chosen]
                st.image(annotate_image(image, marker["corners_analysis_px"], []), caption=f"Candidate marker ID {marker['marker_id']}", width="stretch")
                if st.button("Apply chosen reference corners"):
                    state.set_points("reference", marker["corners_analysis_px"])
                    state.marker_id = marker["marker_id"]
                    st.rerun()
        else:
            st.warning("No valid reference detected. Select Manual mode to mark a square reference explicitly, or try a clearer photograph.")
if target_mode == "assisted":
    st.caption("Suggestions are contours, not object recognition. Choose a candidate, correct its corners, and confirm it.")
    if st.button("Find target suggestions", disabled=not state.reference_confirmed):
        try:
            h = compute_homography(state.reference, reference_size)
            state.target_detection = suggest_targets(image.analysis_rgb, reference=state.reference, homography=h, config=detection_config)
            state.target_confirmed = False
            state.invalidate()
        except ValueError as exc:
            st.error(str(exc))
    if state.target_detection is not None:
        suggestions = state.target_detection
        st.caption(suggestions["status"])
        candidates = suggestions["candidates"]
        if candidates:
            chosen = st.selectbox("Choose the target rectangle", range(len(candidates)), index=None, placeholder="Select a candidate explicitly", format_func=lambda i: f"Candidate {i+1} · score {candidates[i]['score']:.3f}", key=f"target-choice-{state.image_key}-{state.revision}")
            if chosen is not None:
                candidate = candidates[chosen]
                st.image(annotate_image(image, state.reference, candidate["corners_analysis_px"]), caption="Suggested target outline", width="stretch")
                for warning in candidate["warnings"]:
                    st.warning(warning)
                if st.button("Apply chosen target corners"):
                    state.set_points("target", candidate["corners_analysis_px"])
                    state.target_candidate_applied = True
                    st.rerun()
        else:
            st.warning("No useful target candidate found. Select Manual mode or adjust contour settings, then confirm your own corners.")
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
        st.rerun()
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
    st.rerun()
config = GeometryConfig(angle_warning_deg=angle_warning, opposite_warning_ratio=opposite_warning/100)
if st.button("Measure confirmed corners", type="primary", disabled=not (state.reference_confirmed and state.target_confirmed)):
    try:
        start = time.perf_counter()
        result = measure(state.reference, state.target, reference_size, image.analysis_size, config)
        latency_ms = (time.perf_counter() - start) * 1000
        if reference_mode == "aruco" and state.marker_id is None:
            raise ValueError("Choose and apply a detected ArUco reference, or switch to Manual mode.")
        if target_mode == "assisted" and not state.target_candidate_applied:
            raise ValueError("Choose and apply a target suggestion, or switch to Manual mode.")
        reference_latency = state.reference_detection["latency_ms"] if reference_mode == "aruco" and state.reference_detection else 0.
        target_latency = state.target_detection["latency_ms"] if target_mode == "assisted" and state.target_detection else 0.
        stage_latency = {"reference_detection": reference_latency, "target_suggestion": target_latency, "geometry": latency_ms}
        record = build_record(image, result, reference_size, reference_mode=reference_mode, target_mode=target_mode, marker_id=state.marker_id if reference_mode == "aruco" else None, processing_latency_ms=sum(stage_latency.values()), configuration={"max_analysis_long_edge": long_edge, "geometry": asdict(config), "detection": asdict(detection_config), "stage_latency_ms": stage_latency}, ground_truth_short_mm=actual_short, ground_truth_long_mm=actual_long)
        state.result, state.record = result, record
    except ValueError as exc:
        state.result = state.record = None
        st.error(str(exc))

if state.result is not None and state.record is not None and state.record["image_hash"] == image.image_hash:
    result, record = state.result, state.record
    c = st.columns(2)
    c[0].metric("Estimated short side", f"{result['short_side_mm']/10:.1f} cm")
    c[1].metric("Estimated long side", f"{result['long_side_mm']/10:.1f} cm")
    st.caption(f"Planar homography · reference {reference_mode}, target {target_mode} · reference {reference_size:g} mm · processing {record['processing_latency_ms']:.1f} ms (detection + geometry, excluding human selection). Display rounding does not indicate accuracy.")
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
