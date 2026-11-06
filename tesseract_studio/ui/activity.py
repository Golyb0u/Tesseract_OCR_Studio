"""Activity console: timestamped OCR/UI events with filters and export."""

from __future__ import annotations

import re
import time
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..i18n import get_language, tr
from .widgets import HintLabel


class ActivityConsole(QtWidgets.QWidget):
    cleared = QtCore.pyqtSignal()
    export_requested = QtCore.pyqtSignal()

    MAX_LINES = 4000
    LEVEL_KEYS = (
        ("all", "Все уровни"),
        ("info", "Информация"),
        ("success", "Успех"),
        ("warning", "Предупреждение"),
        ("error", "Ошибка"),
    )
    COLORS = {
        "info": "#5aa7c9",
        "success": "#3f9a5a",
        "warning": "#a87f24",
        "error": "#c0504a",
    }
    DARK_COLORS = {
        "info": "#7fb6d6",
        "success": "#5fc98a",
        "warning": "#d9b45a",
        "error": "#e07a72",
    }

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, str, str]] = []
        self._dark = True

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(7)

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(7)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText(tr("Фильтр: подстрока или регулярное выражение…"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMinimumWidth(180)
        self.regex_box = QtWidgets.QCheckBox("Regex")
        self.level_combo = QtWidgets.QComboBox()
        for level, title in self.LEVEL_KEYS:
            self.level_combo.addItem(tr(title), level)
        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.addItem(tr("Все источники"), "")
        self.source_combo.setMinimumWidth(145)
        self.autoscroll = QtWidgets.QCheckBox(tr("Автоскролл"))
        self.autoscroll.setChecked(True)
        self.counter = HintLabel(self._count_text(0))
        self.counter.setMinimumWidth(78)
        clear_btn = QtWidgets.QPushButton(tr("Очистить"))
        clear_btn.setToolTip(tr("Очистить журнал (Ctrl+L)"))
        export_btn = QtWidgets.QPushButton(tr("Экспорт"))
        export_btn.setObjectName("accent")
        export_btn.setToolTip(tr("Сохранить журнал в CSV или TXT"))

        bar.addWidget(self.filter_edit, 1)
        bar.addWidget(self.regex_box)
        bar.addWidget(self.level_combo)
        bar.addWidget(self.source_combo)
        bar.addWidget(self.autoscroll)
        bar.addWidget(self.counter)
        bar.addWidget(clear_btn)
        bar.addWidget(export_btn)
        root.addLayout(bar)

        self.view = QtWidgets.QPlainTextEdit()
        self.view.setObjectName("activityView")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(self.MAX_LINES)
        self.view.setFont(QtGui.QFont("Cascadia Mono", 9))
        self.view.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.view.setPlaceholderText(
            tr("Здесь появятся события: захват кадра, смена настроек, OCR, профили.")
        )
        root.addWidget(self.view, 1)

        self.filter_edit.textChanged.connect(self._rebuild)
        self.regex_box.toggled.connect(self._rebuild)
        self.level_combo.currentIndexChanged.connect(self._rebuild)
        self.source_combo.currentIndexChanged.connect(self._rebuild)
        clear_btn.clicked.connect(self.clear)
        export_btn.clicked.connect(self.export_requested.emit)

    # ------------------------------------------------------------------ api
    def record(
        self, level: str, source: str, message: str, stamp: Optional[str] = None
    ) -> None:
        level = level if level in self.COLORS else "info"
        stamp = stamp or time.strftime("%H:%M:%S")
        self._rows.append((level, stamp, source, message))
        if len(self._rows) > self.MAX_LINES:
            del self._rows[: len(self._rows) - self.MAX_LINES]

        if self.source_combo.findData(source) < 0:
            self.source_combo.blockSignals(True)
            self.source_combo.addItem(source, source)
            self.source_combo.blockSignals(False)

        self.counter.setText(self._count_text(len(self._rows)))
        if self._matches(level, stamp, source, message):
            self._append_line(level, stamp, source, message)

    def clear(self) -> None:
        self._rows.clear()
        self.view.clear()
        self.counter.setText(self._count_text(0))
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem(tr("Все источники"), "")
        self.source_combo.blockSignals(False)
        self.cleared.emit()

    def set_dark(self, dark: bool) -> None:
        if dark == self._dark:
            return
        self._dark = dark
        self._rebuild()

    def plain_text(self) -> str:
        return "\n".join(f"{s} | {src} | {msg}" for _, s, src, msg in self._rows)

    def rows(self) -> list[tuple[str, str, str, str]]:
        return list(self._rows)

    def count(self) -> int:
        return len(self._rows)

    # ------------------------------------------------------------- internals
    @staticmethod
    def _count_text(count: int) -> str:
        if get_language() == "en":
            return f"{count} event" if count == 1 else f"{count} events"
        if count % 10 == 1 and count % 100 != 11:
            word = "событие"
        elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
            word = "события"
        else:
            word = "событий"
        return f"{count} {word}"

    def _matches(self, level: str, stamp: str, source: str, message: str) -> bool:
        level_filter = self.level_combo.currentData() or "all"
        if level_filter != "all" and level != level_filter:
            return False
        wanted_source = self.source_combo.currentData() or ""
        if wanted_source and source != wanted_source:
            return False
        needle = self.filter_edit.text().strip()
        if not needle:
            return True
        haystack = f"{stamp} {source} {message}"
        if self.regex_box.isChecked():
            try:
                return re.search(needle, haystack, re.IGNORECASE) is not None
            except re.error:
                return True
        return needle.lower() in haystack.lower()

    def _append_line(self, level: str, stamp: str, source: str, message: str) -> None:
        palette = self.DARK_COLORS if self._dark else self.COLORS
        color = palette.get(level, palette["info"])
        stamp_color = "#6b7f92" if self._dark else "#5b6b7a"
        message_color = "#d9e2ec" if self._dark else "#26323c"
        safe_source = (
            source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        safe_message = (
            message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        padding = "&nbsp;" * max(0, 26 - len(source))
        self.view.appendHtml(
            f"<span style='color:{stamp_color}'>{stamp}</span>"
            f"&nbsp;&nbsp;<span style='color:{color}'>{safe_source}</span>{padding}"
            f"&nbsp;&nbsp;<span style='color:{message_color}'>{safe_message}</span>"
        )
        if self.autoscroll.isChecked():
            self.view.moveCursor(QtGui.QTextCursor.End)

    def _rebuild(self) -> None:
        self.view.clear()
        for level, stamp, source, message in self._rows:
            if self._matches(level, stamp, source, message):
                self._append_line(level, stamp, source, message)
        if self.autoscroll.isChecked():
            self.view.moveCursor(QtGui.QTextCursor.End)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_L:
            self.clear()
            return
        super().keyPressEvent(event)
