from __future__ import annotations

import ast
import re
from pathlib import Path

from PyQt5 import QtWidgets

from tesseract_studio.config import OCR_PRESETS
from tesseract_studio.i18n import (
    clear_missing,
    missing_translations,
    set_language,
    tr,
)
from tesseract_studio.translations_en import EN
from tesseract_studio.ui.main_window import MainWindow

CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def test_translator_switches_and_formats() -> None:
    try:
        set_language("en")
        assert tr("Готов") == "Ready"
        assert tr("Кадр {width}×{height}", width=10, height=20) == "Frame 10×20"
        set_language("ru")
        assert tr("Готов") == "Готов"
        assert tr("Кадр {width}×{height}", width=10, height=20) == "Кадр 10×20"
    finally:
        set_language("ru")


def test_all_literal_translation_keys_exist() -> None:
    root = Path(__file__).resolve().parents[1] / "tesseract_studio"
    missing: list[tuple[str, int, str]] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                continue
            text = node.args[0].value
            if CYRILLIC.search(text) and text not in EN:
                missing.append((path.name, node.lineno, text))
    assert not missing


def _texts(window: MainWindow) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for widget in window.findChildren(QtWidgets.QWidget):
        if isinstance(widget, QtWidgets.QLabel):
            result.append(("label", widget.text()))
        elif isinstance(widget, (QtWidgets.QPushButton, QtWidgets.QToolButton)):
            result.append(("button", widget.text()))
            result.append(("button.tip", widget.toolTip()))
        elif isinstance(widget, QtWidgets.QLineEdit):
            result.append(("input.placeholder", widget.placeholderText()))
        elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            result.append(("text.placeholder", widget.placeholderText()))
        elif isinstance(widget, QtWidgets.QComboBox):
            if widget is getattr(window, "language_combo", None):
                continue
            for index in range(widget.count()):
                result.append(("combo", widget.itemText(index)))
    for action in window.findChildren(QtWidgets.QAction):
        result.append(("action", action.text()))
        result.append(("action.icon", action.iconText()))
        result.append(("action.tip", action.toolTip()))
    for index in range(window.tabs.count()):
        result.append(("tab", window.tabs.tabText(index)))
    result.extend(
        [
            ("help", window.help_panel.help_browser.toPlainText()),
            ("log", window.activity.view.toPlainText()),
            ("status", window.status_text.text()),
            ("region", window.region_status.text()),
            ("profile.hint", window.profiles_page.profile_hint.text()),
            ("preset.description", window.ocr_page.preset_description.text()),
            ("psm.hint", window.ocr_page.psm_hint.text()),
            ("stats", window.help_panel.stats_label.text()),
            ("diagnostics", window.help_panel.summary.text()),
        ]
    )
    return result


def test_english_ui_is_fully_translated(qapp) -> None:
    try:
        clear_missing()
        set_language("en")
        window = MainWindow(variant="dark", apply_theme=True, language="en")
        window.resize(1540, 960)
        window.show()
        qapp.processEvents()

        for label, text in _texts(window):
            assert not CYRILLIC.search(text or ""), f"{label}: {text!r}"

        assert window.tabs.tabText(0) == "Capture"
        assert window.tabs.tabText(1) == "OCR"
        assert window.tabs.tabText(2) == "Preprocess"
        assert window.tabs.tabText(3) == "Profiles"
        assert window.act_ocr_current.text() == "Run OCR"

        for key in OCR_PRESETS:
            window.apply_preset(key)
            qapp.processEvents()
            assert not CYRILLIC.search(window.ocr_page.preset_description.text())

        for psm in range(14):
            window.ocr_page.psm_combo.setCurrentText(str(psm))
            qapp.processEvents()
            assert not CYRILLIC.search(window.ocr_page.psm_hint.text())

        for payload in window.help_panel._payloads.values():
            html = window.help_panel._html(payload)
            assert not CYRILLIC.search(re.sub(r"<[^>]+>", " ", html))

        assert missing_translations() == set()
        window.close()
    finally:
        set_language("ru")
        clear_missing()
