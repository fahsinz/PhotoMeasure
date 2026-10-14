import csv
import json
from pathlib import Path

import pytest

from photomeasure.evaluation import run_evaluation, summarize


def test_summary_keeps_failures_and_separate_dimension_statistics():
    rows = [dict(status='success', method='assisted', processing_latency_ms=10.,
                 short_absolute_error_mm=2., long_absolute_error_mm=8.,
                 short_absolute_percentage_error=2., long_absolute_percentage_error=4.,
                 reference_without_correction=True, target_without_correction=False,
                 manual_fallback=True),
            dict(status='success', method='assisted', processing_latency_ms=30.,
                 short_absolute_error_mm=4., long_absolute_error_mm=2.,
                 short_absolute_percentage_error=4., long_absolute_percentage_error=1.,
                 reference_without_correction=True, target_without_correction=True,
                 manual_fallback=False),
            dict(status='failure', method='assisted', failure_reason='no marker',
                 reference_without_correction=False, target_without_correction=False,
                 manual_fallback=False)]
    result = summarize(rows)
    assert (result['attempted'], result['successful'], result['failed']) == (3, 2, 1)
    assert result['dimensions']['short']['mean_absolute_error_mm'] == 3.
    assert result['dimensions']['long']['mean_absolute_error_mm'] == 5.
    assert result['dimensions']['long']['worst_absolute_error_mm'] == 8.
    assert result['latency_ms'] == {'count': 2, 'median': 20., 'p95': 29.}
    assert result['detection']['reference']['rate'] == pytest.approx(2/3)
    assert result['detection']['target']['rate'] == pytest.approx(1/3)
    assert result['manual_fallback']['rate'] == pytest.approx(1/3)
    assert result['assisted_completion']['rate'] == pytest.approx(1/3)


def test_missing_detection_evidence_is_not_zero_or_omitted():
    result = summarize([dict(status='failure', method='assisted', failure_reason='missing annotation')])
    assert result['detection']['reference']['attempted'] == 1
    assert result['detection']['reference']['unknown'] == 1
    assert result['detection']['reference']['rate'] is None
    assert result['manual_fallback']['rate'] is None
    assert result['dimensions']['short']['mean_absolute_error_mm'] is None
    assert result['latency_ms']['median'] is None
    assert summarize([])['detection']['target']['rate'] is None


@pytest.fixture
def manifest_fixture(tmp_path):
    examples = Path(__file__).resolve().parents[1] / 'examples'
    for name in ['synthetic_perspective.png', 'synthetic_annotation.json']:
        (tmp_path / name).write_bytes((examples / name).read_bytes())
    row = dict(image_path='synthetic_perspective.png', object_id='synthetic-rectangle',
               actual_short_mm='80', actual_long_mm='120', lighting='synthetic',
               angle_category='synthetic-projective', reference_size_mm='50',
               annotation_path='synthetic_annotation.json', split='evaluation', method='manual',
               reference_without_correction='', target_without_correction='', manual_fallback='')
    def save(rows):
        manifest = tmp_path / 'manifest.csv'
        with manifest.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerows(rows)
        return manifest
    return tmp_path, row, save


def test_manifest_run_relative_paths_exports_truthful_synthetic_evidence(manifest_fixture):
    directory, row, save = manifest_fixture
    summary = run_evaluation(save([row]), directory / 'results', hardware='test fixture', data_kind='synthetic')
    assert summary['successful'] == 1 and summary['failed'] == 0
    assert summary['data_kind'] == 'synthetic'
    assert summary['dimensions']['short']['worst_absolute_error_mm'] < .1
    assert summary['dimensions']['long']['worst_absolute_error_mm'] < .1
    assert summary['detection']['reference']['rate'] is None
    assert summary['latency_ms']['count'] == 1
    assert summary['resolution_samples_px'] == [[1000, 800]]
    outputs = directory / 'results'
    assert {'per_photo.csv', 'results.json', 'summary.json', 'failures.md',
            'error_by_angle_category.png', 'error_by_lighting.png'} <= {p.name for p in outputs.iterdir()}
    record = json.loads((outputs / 'results.json').read_text())[0]
    assert record['short_side_mm'] == pytest.approx(80., abs=.1)
    assert record['status'] == 'success'


@pytest.mark.parametrize('changed,value,reason', [
    ('image_hash', 'wrong-image', 'hash'),
    ('analysis_size_px', [500, 400], 'dimensions'),
    ('schema_version', '999', 'schema'),
    ('reference_size_mm', 51., 'reference sizes'),
])
def test_reused_annotations_reject_stale_or_incompatible_coordinates(manifest_fixture, changed, value, reason):
    directory, row, save = manifest_fixture
    path = directory / 'synthetic_annotation.json'
    annotation = json.loads(path.read_text())
    annotation[changed] = value
    path.write_text(json.dumps(annotation))
    result = run_evaluation(save([row]), directory / 'results', data_kind='synthetic')
    assert result['failed'] == 1 and result['successful'] == 0
    failed = json.loads((directory / 'results/results.json').read_text())[0]
    assert reason in failed['failure_reason'].lower()
    assert result['dimensions']['short']['count'] == 0


def test_synthetic_annotations_cannot_be_reported_as_real(manifest_fixture):
    directory, row, save = manifest_fixture
    result = run_evaluation(save([row]), directory / 'results', data_kind='real')
    assert result['successful'] == 0
    assert result['failed'] == 1
    failed = json.loads((directory / 'results/results.json').read_text())[0]
    assert 'synthetic' in failed['failure_reason'].lower()


def test_failed_manifest_row_retained_beside_success(manifest_fixture):
    directory, row, save = manifest_fixture
    missing = dict(row, image_path='absent.png', object_id='missing-image')
    result = run_evaluation(save([row, missing]), directory / 'results', data_kind='synthetic')
    assert (result['attempted'], result['successful'], result['failed']) == (2, 1, 1)
    assert result['dimensions']['short']['count'] == 1
    records = json.loads((directory / 'results/results.json').read_text())
    assert records[1]['object_id'] == 'missing-image'
    assert records[1]['status'] == 'failure' and records[1]['failure_reason']


def test_each_measured_method_is_warmed_and_warmup_is_excluded(manifest_fixture, monkeypatch):
    import photomeasure.evaluation as evaluation
    directory, row, save = manifest_fixture
    pipeline = evaluation._pipeline
    calls = {'manual': 0, 'assisted': 0}
    def timed(image, annotation, size, method):
        result, stages = pipeline(image, annotation, size, method)
        calls[method] += 1
        # Deliberately huge first-call latency must not enter either aggregate.
        stages = {name: 99999. if calls[method] == 1 else 1. for name in stages}
        return result, stages
    monkeypatch.setattr(evaluation, '_pipeline', timed)
    assisted = dict(row, method='assisted', object_id='synthetic-assisted')
    result = run_evaluation(save([row, assisted]), directory / 'results', data_kind='synthetic')
    assert result['successful'] == 2
    assert calls == {'manual': 2, 'assisted': 2}
    assert result['latency_ms']['p95'] < 10.
    assert result['stage_latency_ms']['reference_detection']['median'] == 1.


@pytest.mark.parametrize('replacement', [[], {'configuration': ['invalid']},
                                       {'reference_corners_analysis_px': [[1, 2]]},
                                       {'target_corners_analysis_px': 'invalid'}])
def test_malformed_annotation_types_become_visible_failures(manifest_fixture, replacement):
    directory, row, save = manifest_fixture
    path = directory / 'synthetic_annotation.json'
    annotation = json.loads(path.read_text())
    if isinstance(replacement, dict):
        annotation.update(replacement)
    else:
        annotation = replacement
    path.write_text(json.dumps(annotation))
    result = run_evaluation(save([row]), directory / 'results', data_kind='synthetic')
    assert result['failed'] == 1 and result['successful'] == 0
    failed = json.loads((directory / 'results/results.json').read_text())[0]
    assert failed['failure_reason']


@pytest.mark.parametrize('field,value', [('actual_short_mm', '0'), ('actual_long_mm', 'nan'),
                                       ('actual_short_mm', '150'), ('reference_size_mm', '-10')])
def test_invalid_manifest_units_and_truth_are_rejected(manifest_fixture, field, value):
    directory, row, save = manifest_fixture
    result = run_evaluation(save([dict(row, **{field: value})]), directory / 'results', data_kind='synthetic')
    assert result['failed'] == 1 and result['successful'] == 0
