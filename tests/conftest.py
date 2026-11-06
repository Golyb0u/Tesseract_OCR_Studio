"""Test bootstrap: isolate user profiles/settings and use the offscreen platform."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="tesseract-studio-tests-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["TESSERACT_STUDIO_CONFIG_DIR"] = str(_TMP / "configs")
os.environ["TESSERACT_STUDIO_SETTINGS"] = str(_TMP / "settings.ini")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from tesseract_studio.app import build_app

    app = build_app(["pytest"])
    yield app
