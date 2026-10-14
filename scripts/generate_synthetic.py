"""Generate a clearly labeled, mathematically exact manual measurement fixture."""
from pathlib import Path
import argparse
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from photomeasure.image_io import load_image


def generate(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    transform = np.array([[3.4, .55, 90.], [.2, 3.1, 100.], [.0017, .0008, 1.]])
    def project(points):
        points = np.column_stack((points, np.ones(4))) @ transform.T
        return (points[:, :2] / points[:, 2, None]).tolist()
    reference = project([[0, 0], [50, 0], [50, 50], [0, 50]])
    target = project([[80, 25], [200, 25], [200, 105], [80, 105]])
    image = Image.new('RGB', (1000, 800), '#e7e9eb')
    draw = ImageDraw.Draw(image)
    draw.polygon([tuple(p) for p in reference], fill='#444444', outline='#000000', width=3)
    draw.polygon([tuple(p) for p in target], fill='#faf9ec', outline='#343434', width=3)
    draw.text((30, 35), 'SYNTHETIC DEMO - not a real photograph', fill='#000000')
    image_path = output / 'synthetic_perspective.png'
    image.save(image_path)
    loaded = load_image(image_path.read_bytes(), image_path.name)
    annotation = dict(schema_version='1.0', image_hash=loaded.image_hash,
                      analysis_size_px=list(loaded.analysis_size), reference_size_mm=50.,
                      reference_corners_analysis_px=reference, target_corners_analysis_px=target,
                      reference_mode='manual', target_mode='manual', marker_id=None,
                      configuration={'synthetic': True, 'max_long_edge': 2000})
    (output / 'synthetic_annotation.json').write_text(json.dumps(annotation, indent=2), encoding='utf-8')
    truth = dict(data_kind='synthetic', short_side_mm=80., long_side_mm=120.,
                 plane_to_image=transform.tolist(), note='Noise-free coordinates. Raster edges are approximate.')
    (output / 'synthetic_truth.json').write_text(json.dumps(truth, indent=2), encoding='utf-8')
    return image_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('examples'))
    print(generate(parser.parse_args().output))
