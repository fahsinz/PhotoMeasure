import numpy as np
import pytest

from photomeasure.geometry import (GeometryError, compute_homography, measure,
                                   transform_points, validate_quad)


def test_noise_free_perspective_recovers_metric_dimensions(perspective_scene):
    ref, target = perspective_scene
    result = measure(ref, target, 50., image_size=(1000, 800))
    assert result['short_side_mm'] == pytest.approx(80., abs=.1)
    assert result['long_side_mm'] == pytest.approx(120., abs=.1)
    assert sorted(result['side_lengths_mm']) == pytest.approx([80., 80., 120., 120.], abs=.1)
    assert result['warnings'] == []


@pytest.mark.parametrize('shift', range(4))
@pytest.mark.parametrize('reverse', [False, True])
def test_reference_cyclic_and_reversed_order_preserve_lengths(perspective_scene, shift, reverse):
    ref, target = perspective_scene
    ordered = np.roll(ref[::-1] if reverse else ref, shift, axis=0)
    result = measure(ordered, target, 50.)
    assert result['short_side_mm'] == pytest.approx(80., abs=.1)
    assert result['long_side_mm'] == pytest.approx(120., abs=.1)


@pytest.mark.parametrize('points', [
    [[0, 0], [50, 50], [50, 0], [0, 50]],  # crossing must never be reordered
    [[0, 0], [50, 0], [50, 0], [0, 50]],
    [[0, 0], [10, 0], [20, 0], [30, 0]],
    [[0, 0], [50, 0], [20, 10], [0, 50]],  # concavity
    [[0, 0], [float('nan'), 0], [50, 50], [0, 50]],
])
def test_invalid_quads_are_rejected(points):
    with pytest.raises(GeometryError, match='.+'):
        validate_quad(points)


@pytest.mark.parametrize('size', [0., -1., float('nan'), float('inf')])
def test_invalid_physical_reference_size(perspective_scene, size):
    ref, target = perspective_scene
    with pytest.raises(GeometryError, match='.+'):
        measure(ref, target, size)


def test_out_of_bounds_and_small_area_rejected(perspective_scene):
    ref, target = perspective_scene
    with pytest.raises(GeometryError):
        measure(ref, target, 50., image_size=(100, 100))
    with pytest.raises(GeometryError):
        measure([[0, 0], [5, 0], [5, 5], [0, 5]], target, 50.)


def test_reference_size_sets_mm_scale(perspective_scene):
    ref, target = perspective_scene
    result = measure(ref, target, 100.)
    assert result['short_side_mm'] == pytest.approx(160., abs=.1)
    assert result['long_side_mm'] == pytest.approx(240., abs=.1)


def test_target_right_angle_and_opposite_disagreement_warn():
    ref = [[0, 0], [100, 0], [100, 100], [0, 100]]
    target = [[150, 0], [350, 0], [270, 100], [150, 100]]
    assert measure(ref, target, 50.)['warnings']


@pytest.mark.parametrize('matrix', [np.zeros((3, 3)), np.diag([1., 1., 0.]),
                                    [[1., 0., 0.], [0., 1., 0.], [1., 0., -1.]]])
def test_singular_or_horizon_projection_fails(matrix):
    with pytest.raises(GeometryError, match='.+'):
        transform_points([[1., 2.]], matrix)


def test_reference_homography_is_finite_and_invertible(perspective_scene):
    ref, _ = perspective_scene
    matrix = compute_homography(ref, 50.)
    assert np.isfinite(matrix).all()
    assert abs(np.linalg.det(matrix)) > 0


def test_target_entirely_across_projective_horizon_is_rejected():
    matrix = np.array([[1., 0., 20.], [0., 1., 100.], [.01, 0., 1.]])
    plane_ref = np.array([[0., 0.], [50., 0.], [50., 50.], [0., 50.]])
    homogeneous = np.column_stack((plane_ref, np.ones(4))) @ matrix.T
    reference = homogeneous[:, :2] / homogeneous[:, 2, None]
    target = [[150., 10.], [200., 10.], [200., 50.], [150., 50.]]
    # All target denominators share a sign, but it differs from the reference.
    with pytest.raises(GeometryError, match='.+'):
        measure(reference, target, 50., (500, 500))
