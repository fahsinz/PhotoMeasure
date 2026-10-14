from io import BytesIO
import hashlib

import numpy as np
from PIL import Image
import pytest

from photomeasure.geometry import measure
from photomeasure.image_io import (analysis_to_original, load_image,
                                  original_to_analysis, preview_to_analysis)


def encoded(image, fmt='PNG', **kwargs):
    stream = BytesIO()
    image.save(stream, format=fmt, **kwargs)
    return stream.getvalue()


def test_rgb_hash_and_actual_resize_ratios():
    raw = encoded(Image.new('RGB', (2401, 1200), (225, 20, 45)))
    loaded = load_image(raw, 'fixture.png')
    assert loaded.original_size == (2401, 1200)
    assert max(loaded.analysis_size) == 2000
    assert loaded.image_hash == hashlib.sha256(raw).hexdigest()
    assert loaded.original_rgb.dtype == np.uint8
    assert tuple(loaded.analysis_rgb[0, 0]) == (225, 20, 45)
    assert loaded.scale_x == loaded.analysis_size[0] / 2401
    assert loaded.scale_y == loaded.analysis_size[1] / 1200
    points = np.array([[23.5, 14.2], [2300.5, 1000.25]])
    assert analysis_to_original(original_to_analysis(points, loaded), loaded) == pytest.approx(points)


def test_resize_and_css_preview_coordinates_preserve_measurement(perspective_scene):
    loaded = load_image(encoded(Image.new('RGB', (1000, 800))), max_long_edge=501)
    reference, target = perspective_scene
    scaled_ref = original_to_analysis(reference, loaded)
    scaled_target = original_to_analysis(target, loaded)
    preview_size = (312., 249.)
    preview_target = scaled_target * np.array(preview_size) / np.array(loaded.analysis_size)
    recovered_target = preview_to_analysis(preview_target, preview_size, loaded.analysis_size)
    assert recovered_target == pytest.approx(scaled_target)
    result = measure(scaled_ref, recovered_target, 50., image_size=loaded.analysis_size)
    assert result['short_side_mm'] == pytest.approx(80., abs=.1)
    assert result['long_side_mm'] == pytest.approx(120., abs=.1)


def test_alpha_composites_on_white():
    loaded = load_image(encoded(Image.new('RGBA', (20, 20), (255, 0, 0, 0))))
    assert tuple(loaded.original_rgb[0, 0]) == (255, 255, 255)


def test_exif_orientation_precedes_coordinates():
    image = Image.new('RGB', (40, 20), (255, 0, 0))
    exif = Image.Exif()
    exif[274] = 6
    loaded = load_image(encoded(image, 'JPEG', exif=exif))
    assert loaded.original_size == (20, 40)
    assert loaded.original_rgb.shape == (40, 20, 3)


@pytest.mark.parametrize('raw', [b'not an image', encoded(Image.new('RGB', (10, 10)), 'GIF'), b'x' * (20 * 1024 * 1024 + 1)], ids=['corrupt', 'gif', 'oversized'])
def test_corrupt_unsupported_and_oversize_inputs_rejected(raw):
    with pytest.raises(ValueError, match='.+'):
        load_image(raw)


def test_decoded_pixel_limit():
    raw = encoded(Image.new('1', (5001, 5000)))
    with pytest.raises(ValueError, match='.+'):
        load_image(raw)
