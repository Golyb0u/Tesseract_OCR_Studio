"""Background OCR worker kept off the GUI thread."""

from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt5 import QtCore

from .imaging import grab_region_image
from .ocr import preprocess_image, extract_text_with_confidence


class OCRWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object, object, str)
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        region: Optional[dict],
        settings: dict,
        image: Optional[np.ndarray] = None,
    ) -> None:
        super().__init__()
        self.region = region
        self.settings = settings
        self.image = image

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            raw_image = (
                self.image.copy() if self.image is not None else grab_region_image(self.region)
            )
            processed_image = preprocess_image(raw_image.copy(), self.settings)
            text = extract_text_with_confidence(processed_image, self.settings)
            self.finished.emit(raw_image, processed_image, text)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a dialog
            self.error.emit(str(exc))
