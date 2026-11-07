"""Preprocessing page: scale, blur, threshold and inversion."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ...i18n import tr
from ..icons import make_icon
from ..widgets import Card, FormRow, HintLabel, PageScroll


class PreprocessPage(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        scroll = PageScroll(self)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        card = Card(
            tr("Обработка изображения"),
            tr("Панель «После обработки» показывает ровно то, что уйдёт в Tesseract. Настраивай по ней, а не по исходнику."),
        )
        self.threshold_mode_combo = QtWidgets.QComboBox()
        self.threshold_mode_combo.addItems(
            ["binary", "binary_inv", "otsu", "adaptive_mean", "adaptive_gaussian"]
        )
        self.threshold_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(150)
        self.threshold_value = QtWidgets.QLabel("150")
        self.threshold_value.setProperty("role", "value")
        self.threshold_value.setAlignment(QtCore.Qt.AlignCenter)
        self.threshold_value.setMinimumWidth(44)
        self.threshold_slider.valueChanged.connect(
            lambda value: self.threshold_value.setText(str(value))
        )
        self.adaptive_block_spin = QtWidgets.QSpinBox()
        self.adaptive_block_spin.setRange(3, 99)
        self.adaptive_block_spin.setSingleStep(2)
        self.adaptive_block_spin.setValue(31)
        self.adaptive_c_spin = QtWidgets.QSpinBox()
        self.adaptive_c_spin.setRange(-50, 50)
        self.adaptive_c_spin.setValue(10)
        self.blur_combo = QtWidgets.QComboBox()
        self.blur_combo.addItems(["0", "3", "5", "7"])
        self.scale_combo = QtWidgets.QComboBox()
        self.scale_combo.addItems(["1.0", "1.5", "2.0", "3.0", "4.0", "5.0", "6.0"])
        self.scale_combo.setCurrentText("2.0")
        self.grayscale_check = QtWidgets.QCheckBox(tr("Оттенки серого"))
        self.grayscale_check.setChecked(True)
        self.invert_check = QtWidgets.QCheckBox(tr("Инверсия"))

        self.threshold_mode_row = FormRow(tr("Бинаризация"), self.threshold_mode_combo)
        card.add(self.threshold_mode_row)
        self.threshold_value_row = FormRow(
            tr("Порог"), self._slider_row(self.threshold_slider, self.threshold_value)
        )
        card.add(self.threshold_value_row)
        self.adaptive_block_row = FormRow(tr("Adaptive-окно"), self.adaptive_block_spin)
        card.add(self.adaptive_block_row)
        self.adaptive_c_row = FormRow("Adaptive C", self.adaptive_c_spin)
        card.add(self.adaptive_c_row)
        card.add(FormRow(tr("Размытие"), self.blur_combo))
        card.add(FormRow(tr("Масштаб"), self.scale_combo))
        card.add(self.grayscale_check)
        card.add(self.invert_check)
        card.add_separator()
        note = HintLabel(
            tr(
                "Масштаб 2.0-4.0 помогает мелкому тексту, но слишком сильное увеличение размывает контуры. "
                "Adaptive-режимы выручают на пёстром фоне и неровной подсветке."
            )
        )
        card.add(note)

        reset = QtWidgets.QPushButton(tr("Сбросить обработку"))
        reset.setIcon(make_icon("clear", "#dff6fd"))
        reset.setProperty("iconKind", "clear")
        reset.clicked.connect(self.reset_defaults)
        card.add(reset)
        scroll.add(card)
        scroll.finish()

        self.threshold_mode_combo.currentIndexChanged.connect(
            lambda _index: self.update_threshold_visibility()
        )
        self.update_threshold_visibility()

    @staticmethod
    def _slider_row(slider: QtWidgets.QSlider, value: QtWidgets.QLabel) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        layout.addWidget(slider, 1)
        layout.addWidget(value)
        return row

    def update_threshold_visibility(self) -> None:
        mode = self.threshold_mode_combo.currentText()
        is_binary = mode in {"binary", "binary_inv"}
        is_adaptive = mode in {"adaptive_mean", "adaptive_gaussian"}
        self.threshold_value_row.setVisible(is_binary)
        self.adaptive_block_row.setVisible(is_adaptive)
        self.adaptive_c_row.setVisible(is_adaptive)

    def reset_defaults(self) -> None:
        self.threshold_mode_combo.setCurrentText("binary")
        self.threshold_slider.setValue(150)
        self.adaptive_block_spin.setValue(31)
        self.adaptive_c_spin.setValue(10)
        self.blur_combo.setCurrentText("0")
        self.scale_combo.setCurrentText("2.0")
        self.grayscale_check.setChecked(True)
        self.invert_check.setChecked(False)

    def setting_widgets(self) -> list[QtWidgets.QWidget]:
        return [
            self.threshold_mode_combo,
            self.threshold_slider,
            self.adaptive_block_spin,
            self.adaptive_c_spin,
            self.blur_combo,
            self.scale_combo,
            self.grayscale_check,
            self.invert_check,
        ]
