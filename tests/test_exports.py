from io import BytesIO, StringIO
import csv
import json

from PIL import Image
import pytest

from photomeasure.exports import annotation_json, build_record, error_metrics, records_csv, records_json
from photomeasure.geometry import measure
from photomeasure.image_io import load_image


def test_errors_signed_absolute_percentage_and_missing_truth():
    errors = error_metrics(82., 117., 80., 120.)
    assert errors['short_signed_error_mm'] == 2.
    assert errors['long_signed_error_mm'] == -3.
    assert errors['long_absolute_error_mm'] == 3.
    assert errors['short_absolute_percentage_error'] == 2.5
    assert all(value is None for value in error_metrics(82., 117.).values())
    partial = error_metrics(82., 117., actual_short_mm=80.)
    assert partial['short_signed_error_mm'] == 2.
    assert partial['long_signed_error_mm'] is None


@pytest.mark.parametrize('actual', [0, -1, float('nan'), float('inf')])
def test_invalid_truth_rejected(actual):
    with pytest.raises(ValueError):
        error_metrics(80., 120., actual, 120.)


def test_full_json_csv_annotation_roundtrip(perspective_scene):
    stream = BytesIO()
    Image.new('RGB', (1000, 800)).save(stream, format='PNG')
    image = load_image(stream.getvalue(), 'synthetic.png')
    ref, target = perspective_scene
    result = measure(ref, target, 50., image_size=image.analysis_size)
    record = build_record(image, result, 50., processing_latency_ms=3.2)
    decoded = json.loads(records_json([record]))
    assert decoded == [record]
    assert decoded[0]['short_side_mm'] == pytest.approx(80., abs=.1)
    assert decoded[0]['schema_version'] == '1.0'
    assert decoded[0]['short_signed_error_mm'] is None
    assert 'preprocessing' in decoded[0]['configuration']
    assert decoded[0]['versions']['code']
    row = next(csv.DictReader(StringIO(records_csv([record]).decode())))
    assert float(row['long_side_mm']) == pytest.approx(120., abs=.1)
    assert row['short_signed_error_mm'] == ''
    annotation = json.loads(annotation_json(record))
    assert annotation['image_hash'] == image.image_hash
    assert annotation['analysis_size_px'] == list(image.analysis_size)
    assert annotation['target_corners_analysis_px'] == result['target_corners_analysis_px']
    assert 'original_rgb' not in decoded[0]
    assert 'image_bytes' not in annotation
