"""Validated in-memory image decoding and explicit coordinate mappings."""
from dataclasses import dataclass
import hashlib
from io import BytesIO
import warnings

import numpy as np
from numpy.typing import ArrayLike
from PIL import Image, ImageOps, UnidentifiedImageError


@dataclass
class ImageData:
    original_rgb: np.ndarray
    analysis_rgb: np.ndarray
    image_hash: str
    original_size: tuple[int, int]
    analysis_size: tuple[int, int]
    scale_x: float
    scale_y: float
    image_name: str | None


def load_image(data: bytes, image_name: str | None = None,
               max_long_edge: int = 2000) -> ImageData:
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError("Upload a nonempty JPEG or PNG no larger than 20 MiB.")
    if isinstance(max_long_edge, bool) or not isinstance(max_long_edge, int) or max_long_edge < 1:
        raise ValueError("Analysis maximum edge must be a positive integer.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG"}:
                    raise ValueError("Image content must be JPEG or PNG.")
                if source.width * source.height > 25_000_000:
                    raise ValueError("Decoded image exceeds the 25 megapixel limit.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                if "A" in oriented.getbands() or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    white = Image.new("RGBA", rgba.size, "white")
                    original = Image.alpha_composite(white, rgba).convert("RGB")
                else:
                    original = oriented.convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombWarning,
            Image.DecompressionBombError) as exc:
        raise ValueError("Cannot decode this image. Upload a valid JPEG or PNG within the size limits.") from exc
    width, height = original.size
    ratio = min(1.0, max_long_edge / max(width, height))
    size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    analysis = original.resize(size, Image.Resampling.LANCZOS) if size != original.size else original
    return ImageData(np.array(original, dtype=np.uint8), np.array(analysis, dtype=np.uint8),
                     hashlib.sha256(data).hexdigest(), original.size, size,
                     size[0] / width, size[1] / height, image_name)


def _points(points) -> np.ndarray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2 or not np.isfinite(array).all():
        raise ValueError("Coordinates must be finite N by 2 points.")
    return array


def original_to_analysis(points: ArrayLike, image: ImageData) -> np.ndarray:
    return _points(points) * [image.scale_x, image.scale_y]


def analysis_to_original(points: ArrayLike, image: ImageData) -> np.ndarray:
    return _points(points) / [image.scale_x, image.scale_y]


def preview_to_analysis(points: ArrayLike, preview_size: tuple[float, float],
                        analysis_size: tuple[int, int]) -> np.ndarray:
    preview = np.asarray(preview_size, dtype=np.float64)
    analysis = np.asarray(analysis_size, dtype=np.float64)
    if preview.shape != (2,) or analysis.shape != (2,) or not np.isfinite([preview, analysis]).all() or (preview <= 0).any() or (analysis <= 0).any():
        raise ValueError("Preview and analysis sizes must contain positive finite width and height.")
    return _points(points) * analysis / preview
