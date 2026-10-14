"""Independent synthetic geometry: constructed in metric coordinates."""
import numpy as np
import pytest


def project(points, matrix):
    homogeneous = np.column_stack((points, np.ones(len(points)))) @ matrix.T
    return homogeneous[:, :2] / homogeneous[:, 2, None]


@pytest.fixture
def perspective_scene():
    # Metric plane -> analysis image; no production transforms create the oracle.
    matrix = np.array([[3.4, .55, 90.], [.2, 3.1, 100.], [.0017, .0008, 1.]])
    reference = np.array([[0., 0.], [50., 0.], [50., 50.], [0., 50.]])
    target = np.array([[80., 25.], [200., 25.], [200., 105.], [80., 105.]])
    return project(reference, matrix), project(target, matrix)
