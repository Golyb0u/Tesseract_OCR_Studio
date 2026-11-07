"""Capture page: region selection, image sources and Tesseract binaries."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ...i18n import tr
from ..icons import make_icon
from ..widgets import Card, HintLabel, PageScroll, button_row


class CapturePage(QtWidgets.QWidget):
    selectRegionRequested = QtCore.pyqtSignal()
    captureRequested = QtCore.pyqtSignal()
    loadFileRequested = QtCore.pyqtSignal()
    pasteRequested = QtCore.pyqtSignal()
    pickTesseractRequested = QtCore.pyqtSignal()
    pickTessdataRequested = QtCore.pyqtSignal()
    autoDetectRequested = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        scroll = PageScroll(self)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        source = Card(
            tr("Захват экрана"),
            tr("Сначала выберите прямоугольник, затем отдельно захватите кадр или запустите OCR по этой области."),
        )
        self.select_region_button = QtWidgets.QPushButton(tr("Выбрать область"))
        self.select_region_button.setObjectName("accent")
        self.select_region_button.setIcon(make_icon("region", "#04161c"))
        self.select_region_button.setProperty("iconKind", "region")
        self.select_region_button.clicked.connect(lambda: self.selectRegionRequested.emit())
        self.capture_button = QtWidgets.QPushButton(tr("Захватить область"))
        self.capture_button.setIcon(make_icon("capture", "#dff6fd"))
        self.capture_button.setProperty("iconKind", "capture")
        self.capture_button.clicked.connect(lambda: self.captureRequested.emit())
        source.add(button_row(self.select_region_button, self.capture_button))

        self.region_label = QtWidgets.QLabel(tr("Область не выбрана"))
        self.region_label.setProperty("role", "metric")
        self.region_label.setWordWrap(True)
        self.region_hint = HintLabel(
            tr("Координаты сохраняются в профиле, поэтому одну и ту же область можно использовать повторно.")
        )
        source.add(self.region_label)
        source.add(self.region_hint)
        source.add_separator()

        self.load_file_button = QtWidgets.QPushButton(tr("Загрузить файл"))
        self.load_file_button.setIcon(make_icon("open", "#dff6fd"))
        self.load_file_button.setProperty("iconKind", "open")
        self.load_file_button.clicked.connect(lambda: self.loadFileRequested.emit())
        self.paste_button = QtWidgets.QPushButton(tr("Вставить из буфера"))
        self.paste_button.setIcon(make_icon("paste", "#dff6fd"))
        self.paste_button.setProperty("iconKind", "paste")
        self.paste_button.clicked.connect(lambda: self.pasteRequested.emit())
        source.add(button_row(self.load_file_button, self.paste_button))
        source.add(
            HintLabel(
                tr("Можно перетащить PNG/JPG прямо на панель предпросмотра - это работает и без выбора области.")
            )
        )
        scroll.add(source)

        tess = Card(
            tr("Tesseract"),
            tr("Если tesseract.exe не добавлен в PATH, укажи путь вручную. Папка tessdata нужна для языковых моделей."),
        )
        self.tesseract_edit = QtWidgets.QLineEdit()
        self.tesseract_edit.setPlaceholderText(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        self.tesseract_button = QtWidgets.QPushButton(tr("Обзор"))
        self.tesseract_button.clicked.connect(lambda: self.pickTesseractRequested.emit())
        tess.add(self._path_row(self.tesseract_edit, self.tesseract_button))

        self.tessdata_edit = QtWidgets.QLineEdit()
        self.tessdata_edit.setPlaceholderText(r"C:\Program Files\Tesseract-OCR\tessdata")
        self.tessdata_button = QtWidgets.QPushButton(tr("Обзор"))
        self.tessdata_button.clicked.connect(lambda: self.pickTessdataRequested.emit())
        tess.add(self._path_row(self.tessdata_edit, self.tessdata_button))

        self.auto_detect_button = QtWidgets.QPushButton(tr("Автоопределить пути"))
        self.auto_detect_button.setIcon(make_icon("scan", "#dff6fd"))
        self.auto_detect_button.setProperty("iconKind", "scan")
        self.auto_detect_button.clicked.connect(lambda: self.autoDetectRequested.emit())
        tess.add(self.auto_detect_button)
        scroll.add(tess)

        tips = Card(tr("Быстрый сценарий"))
        tips.add(
            HintLabel(
                tr(
                    "1. Выбери область или загрузи скриншот.\n"
                    "2. Нажми «Захватить область» - кадр зафиксируется.\n"
                    "3. Перейди на вкладку OCR и подбери параметры.\n"
                    "4. Нажми «Распознать кадр» - новый снимок не понадобится."
                )
            )
        )
        scroll.add(tips)
        scroll.finish()

    @staticmethod
    def _path_row(field: QtWidgets.QLineEdit, button: QtWidgets.QPushButton) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return row

    def set_region(self, region: Optional[dict]) -> None:
        if region:
            self.region_label.setText(
                f"X={region['left']}  Y={region['top']}  W={region['width']}  H={region['height']}"
            )
        else:
            self.region_label.setText(tr("Область не выбрана"))
