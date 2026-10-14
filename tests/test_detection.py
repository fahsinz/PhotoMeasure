"""Synthetic detector smoke checks, never evidence of real-photo accuracy."""
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

from photomeasure.detection import DetectionConfig, suggest_targets
from photomeasure.geometry import measure, validate_quad
from photomeasure.markers import detect_markers, marker_svg


def marker_pixels(marker_id=0, size=200):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    return cv2.aruco.generateImageMarker(dictionary, marker_id, size)


def project(points, matrix):
    homogeneous = np.column_stack((points, np.ones(len(points)))) @ matrix.T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


def test_generated_marker_under_perspective_warp_and_manual_target():
    # Entire plane is warped; the manual target shares the marker's plane.
    image = np.full((650, 1000, 3), 255, np.uint8)
    image[100:300, 100:300] = marker_pixels()[:, :, None]
    target = np.array([[400., 160.], [800., 160.], [800., 360.], [400., 360.]])
    cv2.polylines(image, [target.astype(np.int32)], True, (0, 0, 0), 3)
    matrix = np.array([[.9, .16, 20.], [.03, .88, 25.], [.00017, .00012, 1.]])
    warped = cv2.warpPerspective(image, matrix, (1000, 650), borderValue=(255, 255, 255))
    found = detect_markers(warped)
    assert len(found['markers']) == 1
    assert found['markers'][0]['marker_id'] == 0
    ref = found['markers'][0]['corners_analysis_px']
    validate_quad(ref, (1000, 650))
    result = measure(ref, project(target, matrix), 50., image_size=(1000, 650))
    # Raster/subpixel corner error is distinct from the exact geometric oracle.
    assert result['short_side_mm'] == pytest.approx(50., abs=1.5)
    assert result['long_side_mm'] == pytest.approx(100., abs=1.5)
    assert found['latency_ms'] >= 0


def test_multiple_markers_are_returned_for_explicit_choice():
    image = np.full((500, 800, 3), 255, np.uint8)
    image[100:300, 80:280] = marker_pixels(0)[:, :, None]
    image[100:300, 440:640] = marker_pixels(1)[:, :, None]
    found = detect_markers(image)
    assert {marker['marker_id'] for marker in found['markers']} == {0, 1}


def test_detection_failure_is_actionable_and_preserves_manual_fallback():
    blank = np.full((500, 800, 3), 255, np.uint8)
    reference = detect_markers(blank)
    target = suggest_targets(blank)
    assert reference['markers'] == []
    assert target['candidates'] == []
    assert reference['status'] and target['status']


def test_printable_svg_is_lossless_physical_markup():
    root = ET.fromstring(marker_svg(50., 0))
    assert root.tag.endswith('svg')
    assert root.attrib['width'].endswith('mm')
    assert root.attrib['height'].endswith('mm')
    assert float(root.attrib['width'][:-2]) > 50.
    assert '50' in ''.join(root.itertext())
    black = [node for node in root.iter() if node.tag.endswith('rect') and node.attrib.get('fill') == 'black']
    left = min(float(node.attrib['x']) for node in black)
    right = max(float(node.attrib['x']) + float(node.attrib['width']) for node in black)
    top = min(float(node.attrib['y']) for node in black)
    bottom = max(float(node.attrib['y']) + float(node.attrib['height']) for node in black)
    assert right - left == pytest.approx(50., abs=.000001)
    assert bottom - top == pytest.approx(50., abs=.000001)
    assert left > 0 and top > 0


@pytest.mark.parametrize('size', [0., -1., float('nan'), float('inf')])
def test_printable_marker_rejects_invalid_size(size):
    with pytest.raises(ValueError):
        marker_svg(size)


@pytest.mark.parametrize('config', [DetectionConfig(canny_low=200, canny_high=100),
                                  DetectionConfig(min_area_ratio=.5, max_area_ratio=.1),
                                  DetectionConfig(epsilon_ratio=float('nan'))])
def test_invalid_assisted_settings_are_rejected(config):
    with pytest.raises(ValueError, match='.+'):
        suggest_targets(np.full((100, 100, 3), 255, np.uint8), config=config)


@pytest.mark.parametrize('quarter_turns', [1, 2, 3])
def test_marker_rotation_does_not_change_side_measurements(quarter_turns):
    image = np.full((500, 800, 3), 255, np.uint8)
    image[100:300, 80:280] = np.rot90(marker_pixels(), quarter_turns)[:, :, None]
    detected = detect_markers(image)['markers']
    assert len(detected) == 1 and detected[0]['marker_id'] == 0
    target = [[400, 100], [700, 100], [700, 300], [400, 300]]
    result = measure(detected[0]['corners_analysis_px'], target, 50., (800, 500))
    assert result['short_side_mm'] == pytest.approx(50., abs=1.)
    assert result['long_side_mm'] == pytest.approx(75., abs=1.)


@pytest.mark.parametrize('scale', [1., .5])
def test_target_candidates_exclude_reference_and_image_boundary(scale):
    image = np.full((800, 1000, 3), 255, np.uint8)
    # Boundary, reference, and one interior target are all strong rectangles.
    cv2.rectangle(image, (0, 0), (999, 799), (0, 0, 0), 8)
    reference = np.array([[80., 100.], [230., 100.], [230., 250.], [80., 250.]])
    target = np.array([[400., 200.], [800., 220.], [750., 550.], [380., 500.]])
    cv2.fillConvexPoly(image, reference.astype(np.int32), (0, 0, 0))
    cv2.fillConvexPoly(image, target.astype(np.int32), (0, 0, 0))
    resized = cv2.resize(image, None, fx=scale, fy=scale)
    suggested = suggest_targets(resized, reference=reference * scale)
    assert suggested['candidates'], suggested['status']
    for candidate in suggested['candidates']:
        points = np.asarray(candidate['corners_analysis_px']) / scale
        validate_quad(points, (1000, 800))
        center = points.mean(axis=0)
        assert 350 < center[0] < 820
        assert 180 < center[1] < 570
        assert candidate['score'] > 0
        assert isinstance(candidate['warnings'], list)
    scores = [candidate['score'] for candidate in suggested['candidates']]
    assert scores == sorted(scores, reverse=True)
