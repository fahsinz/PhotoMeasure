import pytest
from photomeasure.ui_state import SelectionState


def measured_state():
    state = SelectionState()
    state.set_image('hash-a:2000')
    state.set_settings(('manual', 50.))
    state.set_points('reference', [[1, 1], [50, 1], [50, 50], [1, 50]])
    state.set_points('target', [[70, 1], [170, 1], [170, 50], [70, 50]])
    state.reference_confirmed = state.target_confirmed = True
    state.result = {'short_side_mm': 50.}
    state.record = {'image_hash': 'hash-a'}
    return state


def test_ordinary_rerun_preserves_confirmed_result():
    state = measured_state()
    revision = state.revision
    assert state.set_image('hash-a:2000') is False
    assert state.set_settings(('manual', 50.)) is False
    assert state.result and state.record
    assert state.reference_confirmed and state.target_confirmed
    assert state.revision == revision


@pytest.mark.parametrize('new_key', ['hash-b:2000', 'hash-a:1000'])
def test_new_image_or_preprocessing_resets_all_selections(new_key):
    state = measured_state()
    assert state.set_image(new_key)
    assert state.reference == state.target == []
    assert not state.reference_confirmed and not state.target_confirmed
    assert state.result is None and state.record is None


@pytest.mark.parametrize('kind', ['reference', 'target'])
def test_edited_corners_clear_downloads_and_confirmation(kind):
    state = measured_state()
    state.set_points(kind, [[2, 2], [51, 2], [51, 51], [2, 51]])
    assert state.result is None and state.record is None
    assert getattr(state, kind + '_confirmed') is False


def test_reference_size_change_clears_stale_measurement():
    state = measured_state()
    state.set_settings(('manual', 55.))
    assert state.result is None and state.record is None
    assert not state.reference_confirmed and not state.target_confirmed


@pytest.mark.parametrize('settings', [('aruco', 50., 0), ('aruco', 50., 1),
                                     ('assisted', 50., 80, 180)])
def test_detection_mode_marker_and_settings_changes_clear_results(settings):
    state = measured_state()
    assert state.set_settings(settings)
    assert state.result is None and state.record is None
    assert not state.reference_confirmed and not state.target_confirmed


def test_reset_clears_downloads():
    state = measured_state()
    state.reset()
    assert state.result is None and state.record is None
    assert not state.reference and not state.target
