"""Entry point: python main.py [--light] [--dark] [--system] [--profile NAME] [--lang ru|en]."""

from __future__ import annotations

import sys

from tesseract_studio.app import main

if __name__ == "__main__":
    sys.exit(main())
