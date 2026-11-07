"""OCR page: presets, segmentation and strict filters."""

from __future__ import annotations

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ...config import OCR_PRESETS, PSM_DESCRIPTIONS
from ...i18n import tr
from ..icons import make_icon
from ..widgets import Card, FormRow, HintLabel, PageScroll


class OcrPage(QtWidgets.QWidget):
    applyPresetRequested = QtCore.pyqtSignal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        scroll = PageScroll(self)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        presets = Card(
            tr("Готовые пресеты"),
            tr("Стартовая точка для типового сценария. После применения подстрой 2-3 параметра под свой кадр."),
        )
        self.preset_combo = QtWidgets.QComboBox()
        for key, preset in OCR_PRESETS.items():
            self.preset_combo.addItem(tr(preset["title"]), key)
        self.preset_button = QtWidgets.QPushButton(tr("Применить пресет"))
        self.preset_button.setObjectName("accent")
        self.preset_button.setIcon(make_icon("play", "#04161c"))
        self.preset_button.setProperty("iconKind", "play")
        self.preset_button.clicked.connect(self._emit_preset)
        presets.add(self.preset_combo)
        presets.add(self.preset_button)
        self.preset_description = HintLabel()
        presets.add(self.preset_description)
        self.preset_combo.currentIndexChanged.connect(lambda _index: self.update_preset_description())
        scroll.add(presets)

        engine = Card(tr("Движок распознавания"), tr("PSM - самый важный переключатель после качества кадра."))
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.addItems(["eng", "rus", "eng+rus", "deu", "fra", "spa"])
        self.language_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.psm_combo = QtWidgets.QComboBox()
        self.psm_combo.addItems([str(index) for index in range(14)])
        self.psm_combo.setCurrentText("6")
        self.oem_combo = QtWidgets.QComboBox()
        self.oem_combo.addItems(["0", "1", "2", "3"])
        self.oem_combo.setCurrentText("3")
        engine.add(FormRow(tr("Язык OCR"), self.language_combo))
        engine.add(FormRow("PSM", self.psm_combo))
        engine.add(FormRow("OEM", self.oem_combo))
        self.psm_hint = HintLabel()
        engine.add(self.psm_hint)
        scroll.add(engine)

        filters = Card(
            tr("Фильтры и строгие настройки"),
            tr("Whitelist/blacklist - самый быстрый способ резко поднять точность на цифрах, кодах и коротких полях."),
        )
        self.whitelist_edit = QtWidgets.QLineEdit()
        self.whitelist_edit.setPlaceholderText(tr("Например 0123456789ABCDEF"))
        self.blacklist_edit = QtWidgets.QLineEdit()
        self.blacklist_edit.setPlaceholderText(tr("Символы, которые нужно исключить"))
        self.min_confidence_spin = QtWidgets.QSpinBox()
        self.min_confidence_spin.setRange(0, 100)
        self.preserve_spaces_check = QtWidgets.QCheckBox(tr("Сохранять пробелы"))
        self.user_dpi_spin = QtWidgets.QSpinBox()
        self.user_dpi_spin.setRange(70, 1200)
        self.user_dpi_spin.setValue(300)
        self.extra_config_edit = QtWidgets.QLineEdit()
        self.extra_config_edit.setPlaceholderText(tr("Например -c load_system_dawg=0"))

        filters.add(FormRow(tr("Разрешённые"), self.whitelist_edit))
        filters.add(FormRow(tr("Запрещённые"), self.blacklist_edit))
        filters.add(FormRow(tr("Мин. уверенность"), self.min_confidence_spin))
        self.preserve_spaces_row = FormRow(tr("Пробелы"), self.preserve_spaces_check)
        filters.add(self.preserve_spaces_row)
        filters.add(FormRow(tr("DPI"), self.user_dpi_spin))
        filters.add(FormRow(tr("Доп. параметры"), self.extra_config_edit))
        scroll.add(filters)
        scroll.finish()

        self.update_preset_description()
        self.update_psm_hint()

    # ================================================================== api
    def _emit_preset(self) -> None:
        self.applyPresetRequested.emit(self.selected_preset())

    def selected_preset(self) -> str:
        return self.preset_combo.currentData() or self.preset_combo.currentText()

    def update_preset_description(self) -> None:
        preset = OCR_PRESETS.get(self.selected_preset())
        if preset:
            self.preset_description.setText(
                f"{tr(preset['title'])}: {tr(preset['description'])}"
            )

    def update_psm_hint(self) -> None:
        try:
            psm = int(self.psm_combo.currentText())
        except ValueError:
            psm = 6
        if psm == 10:
            text = tr(
                "PSM 10: один символ. Кадр должен быть плотно обрезан, язык - один, "
                "а whitelist - максимально строгим."
            )
        elif psm == 8:
            text = tr("PSM 8: одно слово. В кадре не должно быть соседних слов и мусора.")
        elif psm == 7:
            text = tr("PSM 7: одна строка. Подходит для подписей, логов, статусов и значений интерфейса.")
        elif psm == 6:
            text = tr("PSM 6: один блок текста. Хорошая универсальная база для прямоугольной области.")
        else:
            text = tr(PSM_DESCRIPTIONS.get(psm, "Подбери режим под форму текста в кадре."))
        self.psm_hint.setText(text)
        self.preserve_spaces_row.setVisible(psm not in {8, 10})

    def setting_widgets(self) -> list[QtWidgets.QWidget]:
        return [
            self.language_combo,
            self.psm_combo,
            self.oem_combo,
            self.whitelist_edit,
            self.blacklist_edit,
            self.min_confidence_spin,
            self.preserve_spaces_check,
            self.user_dpi_spin,
            self.extra_config_edit,
        ]
