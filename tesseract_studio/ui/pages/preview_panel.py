"""Center workspace: source/processed previews and OCR output."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ...i18n import tr
from ..icons import make_icon
from ...imaging import image_size_text
from ..widgets import Card, HintLabel, ImagePreview, StatusBanner, button_row


class PreviewPanel(QtWidgets.QWidget):
    copyRequested = QtCore.pyqtSignal()
    saveRequested = QtCore.pyqtSignal()
    clearRequested = QtCore.pyqtSignal()
    fileDropped = QtCore.pyqtSignal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(11)

        self.banner = StatusBanner()
        self.banner.set_message(
            tr("Готов к работе. Выберите область или загрузите изображение."), "accent", 0
        )
        root.addWidget(self.banner)

        images = QtWidgets.QHBoxLayout()
        images.setSpacing(11)

        self.source_preview = ImagePreview(tr("Исходное изображение\nПеретащите файл сюда"))
        self.processed_preview = ImagePreview(tr("После обработки\nПоявится автоматически"))
        self.source_preview.fileDropped.connect(self.fileDropped.emit)

        source_card = Card(tr("Исходное изображение"))
        self.source_info = HintLabel(tr("нет данных"))
        source_card.header.addWidget(self.source_info)
        source_card.add(self.source_preview)
        processed_card = Card(tr("После обработки"))
        self.processed_info = HintLabel(tr("нет данных"))
        processed_card.header.addWidget(self.processed_info)
        processed_card.add(self.processed_preview)

        images.addWidget(source_card, 1)
        images.addWidget(processed_card, 1)
        root.addLayout(images, 3)

        output = Card(tr("Распознанный текст"))
        self.output_info = HintLabel(tr("Здесь появится результат OCR."))
        output.header.addWidget(self.output_info)
        self.output_text = QtWidgets.QTextEdit()
        self.output_text.setObjectName("outputText")
        self.output_text.setAcceptRichText(False)
        self.output_text.setPlaceholderText(tr("Здесь появится распознанный текст."))
        self.output_text.setFont(QtWidgets.QApplication.font())
        output.add(self.output_text, 1)

        copy_button = QtWidgets.QPushButton(tr("Копировать"))
        copy_button.setIcon(make_icon("copy", "#dff6fd"))
        copy_button.setProperty("iconKind", "copy")
        copy_button.clicked.connect(lambda: self.copyRequested.emit())
        save_button = QtWidgets.QPushButton(tr("Сохранить .txt"))
        save_button.setIcon(make_icon("save", "#dff6fd"))
        save_button.setProperty("iconKind", "save")
        save_button.clicked.connect(lambda: self.saveRequested.emit())
        clear_button = QtWidgets.QPushButton(tr("Очистить"))
        clear_button.setIcon(make_icon("clear", "#dff6fd"))
        clear_button.setProperty("iconKind", "clear")
        clear_button.clicked.connect(lambda: self.clearRequested.emit())
        output.add(button_row(copy_button, save_button, clear_button))
        root.addWidget(output, 2)

    # ------------------------------------------------------------------ api
    def set_source(self, image, text: Optional[str] = None) -> None:
        if image is None:
            self.source_preview.clear_preview()
            self.source_info.setText(tr("нет данных"))
            return
        self.source_preview.set_numpy_image(image)
        self.source_info.setText(text or image_size_text(image))

    def set_processed(self, image, text: Optional[str] = None) -> None:
        if image is None:
            self.processed_preview.clear_preview()
            self.processed_info.setText(tr("нет данных"))
            return
        self.processed_preview.set_numpy_image(image)
        self.processed_info.setText(text or image_size_text(image))

    def set_text(self, text: str) -> None:
        self.output_text.setPlainText(text)
        self.output_info.setText(
            tr("{count} символов", count=len(text)) if text else tr("Здесь появится результат OCR.")
        )

    def text(self) -> str:
        return self.output_text.toPlainText()

    def clear_output(self) -> None:
        self.output_text.clear()
        self.output_info.setText(tr("Здесь появится результат OCR."))

    def set_status(self, text: str, tone: str = "accent", timeout: int = 6000) -> None:
        self.banner.set_message(text, tone, timeout)
