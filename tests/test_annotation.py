from io import BytesIO

import numpy as np
from PIL import Image

from photomeasure.annotation import annotate_image, rectified_preview
from photomeasure.geometry import measure
from photomeasure.image_io import load_image, original_to_analysis


def test_original_overlay_maps_analysis_corners_to_oriented_image(perspective_scene):
    stream = BytesIO()
    Image.new('RGB', (1000, 800), 'white').save(stream, format='PNG')
    image = load_image(stream.getvalue(), max_long_edge=501)
    ref, target = perspective_scene
    ref_analysis = original_to_analysis(ref, image)
    target_analysis = original_to_analysis(target, image)
    annotated = annotate_image(image, ref_analysis, target_analysis)
    assert annotated.size == (1000, 800)
    pixels = np.asarray(annotated)
    x, y = np.rint(target[0]).astype(int)
    assert tuple(pixels[y, x]) == (215, 85, 0)
    x, y = np.rint(ref[0]).astype(int)
    assert tuple(pixels[y, x]) == (0, 140, 153)


def test_rectified_large_metric_crop_has_bounded_allocation(perspective_scene):
    stream = BytesIO()
    Image.new('RGB', (1000, 800), 'white').save(stream, format='PNG')
    image = load_image(stream.getvalue())
    ref, target = perspective_scene
    result = measure(ref, target, 500000.)
    preview = rectified_preview(image, result, pixels_per_mm=100., max_edge=640)
    # A bounded image plus a small caption strip is acceptable.
    assert preview.width <= 640
    assert preview.height <= 704
    assert preview.mode == 'RGB'
