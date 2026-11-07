"""Live appearance inspector ported from Qt UI Lab."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from . import theme


class AppearanceDialog(QtWidgets.QDialog):
    """Palette, accent, radius and typography; applies changes immediately."""

    def __init__(
        self,
        variant: str,
        accent: str,
        radius: int,
        font_family: str,
        font_size: int,
        apply_callback: Callable[[dict], None],
        qss_provider: Optional[Callable[[], str]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Оформление"))
        self.setMinimumWidth(430)
        self._apply_callback = apply_callback
        self._qss_provider = qss_provider
        self._accent = accent
        self._updating = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QtWidgets.QLabel(tr("Оформление интерфейса"))
        title.setProperty("role", "brand")
        root.addWidget(title)
        hint = QtWidgets.QLabel(
            tr("Изменения применяются сразу ко всему окну и сохраняются между запусками.")
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.variant_combo = QtWidgets.QComboBox()
        self.variant_combo.addItem(tr("Тёмная"), "dark")
        self.variant_combo.addItem(tr("Светлая"), "light")
        self.variant_combo.setCurrentIndex(0 if variant != "light" else 1)
        self.variant_combo.currentIndexChanged.connect(self._emit)
        form.addRow(tr("Палитра"), self.variant_combo)

        self.accent_button = QtWidgets.QPushButton()
        self.accent_button.setMinimumHeight(30)
        self.accent_button.clicked.connect(self._pick_accent)
        form.addRow(tr("Акцент"), self.accent_button)
        self._sync_accent_button()

        self.radius_spin = QtWidgets.QSpinBox()
        self.radius_spin.setRange(0, 16)
        self.radius_spin.setValue(int(radius))
        self.radius_spin.valueChanged.connect(self._emit)
        form.addRow(tr("Скругление"), self.radius_spin)

        self.font_combo = QtWidgets.QFontComboBox()
        self.font_combo.setCurrentFont(QtGui.QFont(font_family))
        self.font_combo.currentFontChanged.connect(self._emit)
        form.addRow(tr("Шрифт"), self.font_combo)

        self.size_spin = QtWidgets.QSpinBox()
        self.size_spin.setRange(8, 16)
        self.size_spin.setSuffix(" pt")
        self.size_spin.setValue(int(font_size))
        self.size_spin.valueChanged.connect(self._emit)
        form.addRow(tr("Размер"), self.size_spin)

        root.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox()
        reset_btn = buttons.addButton(tr("Сбросить"), QtWidgets.QDialogButtonBox.ResetRole)
        export_btn = buttons.addButton(tr("Экспорт QSS…"), QtWidgets.QDialogButtonBox.ActionRole)
        close_btn = buttons.addButton(QtWidgets.QDialogButtonBox.Close)
        reset_btn.clicked.connect(self._reset)
        export_btn.clicked.connect(self._export_qss)
        close_btn.clicked.connect(self.accept)
        root.addWidget(buttons)

    def _sync_accent_button(self) -> None:
        self.accent_button.setText(self._accent.upper())
        self.accent_button.setStyleSheet(
            f"QPushButton {{ text-align: left; padding-left: 12px;"
            f" border-left: 6px solid {self._accent}; }}"
        )

    def _pick_accent(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._accent), self, tr("Выберите акцентный цвет")
        )
        if not color.isValid():
            return
        self._accent = color.name()
        self._sync_accent_button()
        self._emit()

    def _reset(self) -> None:
        self._updating = True
        self.variant_combo.setCurrentIndex(0)
        self._accent = theme.DEFAULT_TOKENS["accent"]
        self._sync_accent_button()
        self.radius_spin.setValue(theme.DEFAULT_TOKENS["radius"])
        self.font_combo.setCurrentFont(QtGui.QFont(theme.DEFAULT_TOKENS["font_family"]))
        self.size_spin.setValue(theme.DEFAULT_TOKENS["font_size"])
        self._updating = False
        self._emit()

    def _emit(self, *_args) -> None:
        if self._updating:
            return
        self._apply_callback(
            {
                "variant": self.variant_combo.currentData(),
                "accent": self._accent,
                "radius": self.radius_spin.value(),
                "font_family": self.font_combo.currentFont().family(),
                "font_size": self.size_spin.value(),
            }
        )

    def _export_qss(self) -> None:
        if self._qss_provider is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("Сохранить QSS"), "tesseract-studio.qss", "Qt stylesheet (*.qss)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._qss_provider())
        except OSError as error:
            QtWidgets.QMessageBox.warning(self, tr("Ошибка сохранения"), str(error))
            return
        QtWidgets.QMessageBox.information(
            self, tr("Готово"), tr("Стили сохранены:\n{path}", path=path)
        )
