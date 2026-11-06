from __future__ import annotations

import numpy as np

from tesseract_studio.ocr import preprocess_image, safe_block_size


def _settings(**overrides) -> dict:
    settings = {
        "threshold_mode": "binary",
        "threshold_value": 150,
        "adaptive_block_size": 31,
        "adaptive_c": 10,
        "blur_kernel": 0,
        "scale": 1.0,
        "invert": False,
        "grayscale": True,
    }
    settings.update(overrides)
    return settings


def _sample() -> np.ndarray:
    image = np.full((80, 240, 3), 230, dtype=np.uint8)
    image[20:60, 20:220] = 20
    return image


def test_grayscale_binary_produces_two_values() -> None:
    processed = preprocess_image(_sample(), _settings())
    assert processed.ndim == 2
    assert set(np.unique(processed).tolist()) <= {0, 255}


def test_scale_multiplies_dimensions() -> None:
    processed = preprocess_image(_sample(), _settings(scale=2.0))
    assert processed.shape == (160, 480)


def test_invert_flips_binary_image() -> None:
    normal = preprocess_image(_sample(), _settings())
    inverted = preprocess_image(_sample(), _settings(invert=True))
    assert np.array_equal(normal, 255 - inverted)


def test_adaptive_modes_accept_even_block_size() -> None:
    for mode in ("adaptive_mean", "adaptive_gaussian"):
        processed = preprocess_image(_sample(), _settings(threshold_mode=mode, adaptive_block_size=30))
        assert processed.shape == (80, 240)
        assert safe_block_size(30) == 31


def test_blur_and_color_input_stay_binary() -> None:
    processed = preprocess_image(_sample(), _settings(blur_kernel=3))
    assert processed.dtype == np.uint8
    assert set(np.unique(processed).tolist()) <= {0, 255}
