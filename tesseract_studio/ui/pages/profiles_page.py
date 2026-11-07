"""Profiles page: named JSON presets and workspace actions."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ...config import CONFIG_DIR
from ...i18n import tr
from ..icons import make_icon
from ..widgets import Card, HintLabel, PageScroll, button_row


class ProfilesPage(QtWidgets.QWidget):
    saveProfileRequested = QtCore.pyqtSignal()
    loadProfileRequested = QtCore.pyqtSignal()
    refreshProfilesRequested = QtCore.pyqtSignal()
    openConfigDirRequested = QtCore.pyqtSignal()
    appearanceRequested = QtCore.pyqtSignal()
    aboutRequested = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        scroll = PageScroll(self)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        card = Card(
            tr("Профили настроек"),
            tr("Профиль хранит все параметры OCR, обработки и координаты области в configs/*.json."),
        )
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.setEditable(True)
        self.profile_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        card.add(self.profile_combo)

        self.save_button = QtWidgets.QPushButton(tr("Сохранить"))
        self.save_button.setObjectName("accent")
        self.save_button.setIcon(make_icon("save", "#04161c"))
        self.save_button.setProperty("iconKind", "save")
        self.save_button.clicked.connect(lambda: self.saveProfileRequested.emit())
        self.load_button = QtWidgets.QPushButton(tr("Загрузить"))
        self.load_button.setIcon(make_icon("open", "#dff6fd"))
        self.load_button.setProperty("iconKind", "open")
        self.load_button.clicked.connect(lambda: self.loadProfileRequested.emit())
        self.refresh_button = QtWidgets.QPushButton(tr("Обновить"))
        self.refresh_button.setIcon(make_icon("settings", "#dff6fd"))
        self.refresh_button.setProperty("iconKind", "settings")
        self.refresh_button.clicked.connect(lambda: self.refreshProfilesRequested.emit())
        card.add(button_row(self.save_button, self.load_button, self.refresh_button))
        card.add(
            HintLabel(
                tr(
                    "Введи новое имя и нажми «Сохранить», чтобы создать профиль; выбери существующий и нажми "
                    "«Загрузить», чтобы вернуться к сохранённым настройкам."
                )
            )
        )
        self.profile_hint = HintLabel(tr("Папка профилей: {path}", path=CONFIG_DIR))
        card.add(self.profile_hint)
        scroll.add(card)

        actions = Card(tr("Рабочее пространство"))
        open_dir_button = QtWidgets.QPushButton(tr("Открыть папку профилей"))
        open_dir_button.setIcon(make_icon("open", "#dff6fd"))
        open_dir_button.setProperty("iconKind", "open")
        open_dir_button.clicked.connect(lambda: self.openConfigDirRequested.emit())
        appearance_button = QtWidgets.QPushButton(tr("Оформление…"))
        appearance_button.setIcon(make_icon("theme", "#dff6fd"))
        appearance_button.setProperty("iconKind", "theme")
        appearance_button.clicked.connect(lambda: self.appearanceRequested.emit())
        about_button = QtWidgets.QPushButton(tr("О программе"))
        about_button.setIcon(make_icon("info", "#dff6fd"))
        about_button.setProperty("iconKind", "info")
        about_button.clicked.connect(lambda: self.aboutRequested.emit())
        actions.add(open_dir_button)
        actions.add(button_row(appearance_button, about_button))
        scroll.add(actions)
        scroll.finish()

    def set_profiles(self, names: list[str], current: str = "") -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        if current:
            self.profile_combo.setCurrentText(current)
        self.profile_combo.blockSignals(False)

    def profile_name(self) -> str:
        return self.profile_combo.currentText().strip() or "default"
