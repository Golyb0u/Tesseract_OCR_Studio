from __future__ import annotations

import json

from tesseract_studio.config import (
    AppConfig,
    OCR_PRESETS,
    config_from_dict,
    ensure_default_profile,
    list_profiles,
    load_config_file,
    safe_profile_name,
    save_config_file,
)
from tesseract_studio.ocr import build_tesseract_config, normalize_ocr_text, safe_block_size


REQUIRED_PRESET_KEYS = {
    "language",
    "psm",
    "oem",
    "threshold_mode",
    "threshold_value",
    "adaptive_block_size",
    "adaptive_c",
    "blur_kernel",
    "scale",
    "invert",
    "grayscale",
    "whitelist",
    "blacklist",
    "min_confidence",
    "preserve_spaces",
    "user_defined_dpi",
    "extra_config",
}


def test_presets_are_complete() -> None:
    assert {"single_digit_strict", "digits", "strict_ui", "small_text", "chat_text"} <= set(
        OCR_PRESETS
    )
    for preset in OCR_PRESETS.values():
        assert preset["title"]
        assert preset["description"]
        assert REQUIRED_PRESET_KEYS <= set(preset["values"])


def test_config_from_dict_ignores_unknown_keys() -> None:
    config = config_from_dict({"psm": 7, "language": "eng", "legacy_key": 1})
    assert config.psm == 7
    assert config.language == "eng"


def test_config_roundtrip(tmp_path) -> None:
    config = AppConfig(profile_name="digits", psm=10, whitelist="0123456789")
    path = save_config_file(tmp_path / "digits.json", config)
    loaded = load_config_file(path)
    assert loaded == config
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["psm"] == 10


def test_profile_names_are_safe() -> None:
    assert safe_profile_name("../bad/name") == "-bad-name"
    assert safe_profile_name("   ") == "default"


def test_default_profile_is_created_once() -> None:
    path = ensure_default_profile()
    assert path.exists()
    first = path.stat().st_mtime_ns
    assert ensure_default_profile() == path
    assert path.stat().st_mtime_ns == first
    assert "default" in list_profiles()


def test_safe_block_size_is_odd() -> None:
    assert safe_block_size(1) == 3
    assert safe_block_size(10) == 11
    assert safe_block_size(31) == 31


def test_tesseract_config_contains_strict_flags() -> None:
    config = build_tesseract_config(
        {
            "oem": 3,
            "psm": 10,
            "whitelist": "0123456789",
            "blacklist": "OoIl",
            "preserve_spaces": True,
            "user_defined_dpi": 300,
            "extra_config": "-c load_system_dawg=0",
        }
    )
    assert "--oem 3" in config
    assert "--psm 10" in config
    assert 'tessedit_char_whitelist="0123456789"' in config
    assert 'tessedit_char_blacklist="OoIl"' in config
    assert "preserve_interword_spaces=1" in config
    assert "user_defined_dpi=300" in config
    assert "load_system_dawg=0" in config


def test_normalize_ocr_text_collapses_blank_lines() -> None:
    assert normalize_ocr_text("  one  \n\n\n two\n") == "one\n\n two"
