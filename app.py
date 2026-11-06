"""Backward-compatible entry point for the old ``python app.py`` command.

The implementation now lives in the ``tesseract_studio`` package; this file
only keeps existing shortcuts and documentation working.
"""

from __future__ import annotations

import sys

from tesseract_studio.app import main

if __name__ == "__main__":
    sys.exit(main())
