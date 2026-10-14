"""Controlled uploader smoke tests; these do not replace browser acceptance."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import pytest
from PIL import Image, ImageDraw
import streamlit as st
from streamlit.testing.v1 import AppTest


def app_path():
    return next(parent / 'app.py' for parent in Path(__file__).resolve().parents if (parent / 'app.py').exists())


def upload(image):
    stream = BytesIO()
    image.save(stream, format='PNG')
    data = stream.getvalue()
    return SimpleNamespace(name='synthetic-ui.png', getvalue=lambda: data)


def widget(app, family, label):
    return next(item for item in getattr(app, family) if item.label == label)


def test_controlled_manual_measurement_units_and_stale_settings():
    st.cache_data.clear()
    with patch('streamlit.file_uploader', return_value=upload(Image.new('RGB', (600, 400), 'white'))):
        app = AppTest.from_file(str(app_path()), default_timeout=30).run()
        state = app.session_state.selection
        state.reference = [[50., 50.], [150., 50.], [150., 150.], [50., 150.]]
        state.target = [[200., 100.], [500., 100.], [500., 300.], [200., 300.]]
        state.reference_confirmed = state.target_confirmed = True
        app.run()
        widget(app, 'button', 'Measure confirmed corners').click().run()
        assert not app.exception
        assert [metric.value for metric in app.metric] == ['10.0 cm', '15.0 cm']
        assert app.session_state.selection.record['short_side_mm'] == pytest.approx(100., abs=.1)
        widget(app, 'number_input', 'Actual reference square side (mm) — verify with a ruler').set_value(60.).run()
        state = app.session_state.selection
        assert state.result is None and state.record is None
        assert not state.reference_confirmed and not state.target_confirmed
        widget(app, 'number_input', 'Maximum analysis long edge (pixels)').set_value(2100).run()
        assert not app.session_state.selection.reference and not app.session_state.selection.target
        assert not app.exception


def test_controlled_assisted_detection_requires_choices_and_exports_modes():
    st.cache_data.clear()
    image = Image.new('RGB', (800, 600), 'white')
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, 0, 200)
    image.paste(Image.fromarray(marker).convert('RGB'), (50, 50))
    ImageDraw.Draw(image).rectangle((400, 100, 700, 400), fill='lightgray', outline='black', width=4)
    with patch('streamlit.file_uploader', return_value=upload(image)):
        app = AppTest.from_file(str(app_path()), default_timeout=30).run()
        widget(app, 'radio', 'Reference selection mode').set_value('aruco').run()
        widget(app, 'radio', 'Target selection mode').set_value('assisted').run()
        widget(app, 'button', 'Detect ArUco references').click().run()
        assert widget(app, 'selectbox', 'Choose the reference marker').value is None
        assert not app.session_state.selection.reference_confirmed
        widget(app, 'selectbox', 'Choose the reference marker').set_value(0).run()
        widget(app, 'button', 'Apply chosen reference corners').click().run()
        widget(app, 'button', 'Confirm reference').click().run()
        widget(app, 'button', 'Find target suggestions').click().run()
        assert widget(app, 'selectbox', 'Choose the target rectangle').value is None
        assert not app.session_state.selection.target_confirmed
        widget(app, 'selectbox', 'Choose the target rectangle').set_value(0).run()
        widget(app, 'button', 'Apply chosen target corners').click().run()
        widget(app, 'radio', 'Corners to edit').set_value('target').run()
        widget(app, 'button', 'Confirm target').click().run()
        widget(app, 'button', 'Measure confirmed corners').click().run()
        assert not app.exception
        assert [metric.value for metric in app.metric] == ['7.5 cm', '7.5 cm']
        record = app.session_state.selection.record
        assert record['reference_mode'] == 'aruco' and record['target_mode'] == 'assisted'
        assert record['marker_id'] == 0 and record['dictionary'] == 'DICT_4X4_50'
        assert set(record['configuration']['stage_latency_ms']) == {'reference_detection', 'target_suggestion', 'geometry'}
        widget(app, 'button', 'Find target suggestions').click().run()
        state = app.session_state.selection
        assert state.result is None and state.record is None
        assert not state.target and not state.target_candidate_applied
        assert widget(app, 'selectbox', 'Choose the target rectangle').value is None
