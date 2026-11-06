from __future__ import annotations

import re
from pathlib import Path

from tesseract_studio.ui import theme


def test_both_palettes_resolve_every_token() -> None:
    dark = theme.render_qss()
    light = theme.light_stylesheet()
    assert not re.search(r"__[A-Z][A-Z0-9_]*__", dark)
    assert not re.search(r"__[A-Z][A-Z0-9_]*__", light)
    assert "#37b6d6" in dark
    assert "qlineargradient" in dark
    assert "qlineargradient" in light


def test_accent_flows_into_selection_and_sliders() -> None:
    tokens = dict(theme.DEFAULT_TOKENS, accent="#ff5500", accent_hover="#ff7733", radius=8)
    sheet = theme.tokens_to_qss(tokens)
    assert "#ff5500" in sheet
    assert "#ff7733" in sheet
    assert "rgba(255, 85, 0" in sheet
    assert "border-radius: 8px" in sheet


def test_indicator_glyphs_exist() -> None:
    paths = theme.indicator_paths("#37b6d6", "#04161c")
    for value in paths.values():
        assert Path(value).exists()
