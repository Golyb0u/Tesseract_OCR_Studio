from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from tesseract_studio.config import CONFIG_DIR
from tesseract_studio.ui.main_window import MainWindow


def _sample_image() -> np.ndarray:
    image = np.full((90, 260, 3), 235, dtype=np.uint8)
    image[25:65, 20:240] = 15
    return image


def test_window_shell_is_complete(qapp) -> None:
    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    assert window.tabs.count() == 4
    assert [window.tabs.tabText(i) for i in range(4)] == ["Захват", "OCR", "Обработка", "Профили"]
    assert window.act_ocr_current.shortcut().toString() == "F5"
    assert window.act_select_region.shortcut().toString() == "Ctrl+Shift+R"
    assert "QToolBar" in window._qss or "QToolButton" in window._qss
    assert not re.search(r"__[A-Z][A-Z0-9_]*__", window._qss)
    window.close()


def test_tab_labels_fit_inside_their_rects(qapp) -> None:
    from PyQt5 import QtGui

    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    window.resize(1540, 960)
    window.show()
    qapp.processEvents()
    bar = window.tabs.tabBar()
    font = QtGui.QFont(bar.font())
    font.setWeight(QtGui.QFont.DemiBold)
    metrics = QtGui.QFontMetrics(font)
    for index in range(bar.count()):
        hint = bar.tabSizeHint(index)
        icon = 0 if bar.tabIcon(index).isNull() else bar.iconSize().width() + bar.ICON_GAP
        needed = metrics.horizontalAdvance(bar.tabText(index)) + icon + bar.H_PADDING * 2
        assert hint.width() >= needed, bar.tabText(index)
        assert hint.height() >= metrics.height()
    window.close()


def test_combo_popup_container_uses_theme_colors(qapp) -> None:
    from tesseract_studio.ui import theme

    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    popup = window.activity.source_combo.view().window()
    dark_sheet = popup.styleSheet() or theme.popup_stylesheet("dark", 4)
    assert "QComboBoxPrivateContainer" in dark_sheet
    assert "20, 25, 30" in dark_sheet
    assert "250, 251, 252" not in dark_sheet

    window.toggle_variant()
    light_sheet = theme.popup_stylesheet("light", 4)
    assert "250, 251, 252" in light_sheet
    window.close()


def test_theme_toggle_keeps_tokens_resolved(qapp) -> None:
    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    dark = window._qss
    window.toggle_variant()
    assert window._variant == "light"
    assert window._qss != dark
    assert not re.search(r"__[A-Z][A-Z0-9_]*__", window._qss)
    window.toggle_variant()
    assert window._variant == "dark"
    window.close()


def test_status_line_uses_the_normal_label(qapp) -> None:
    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    window._show_status("Проверка статуса", "ok", 0)
    assert window.status_text.text() == "Проверка статуса"
    assert window.statusBar().currentMessage() == ""
    window.close()


def test_source_image_updates_both_previews(qapp) -> None:
    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    window._set_source_image(_sample_image(), "test")
    assert window.raw_image is not None
    assert window.processed_image is not None
    assert not window.preview_panel.source_preview.pixmap().isNull()
    assert not window.preview_panel.processed_preview.pixmap().isNull()
    assert window.help_panel._stats["source"] == "260 x 90"
    window.close()


def test_preset_and_profile_roundtrip(qapp) -> None:
    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    window.apply_preset("digits")
    assert window.ocr_page.psm_combo.currentText() == "10"
    assert window.ocr_page.whitelist_edit.text() == "0123456789"

    window.profiles_page.profile_combo.setCurrentText("pytest-profile")
    window.save_profile()
    path = CONFIG_DIR / "pytest-profile.json"
    assert path.exists()

    window.ocr_page.psm_combo.setCurrentText("6")
    window.ocr_page.whitelist_edit.setText("")
    window.load_profile("pytest-profile")
    assert window.ocr_page.psm_combo.currentText() == "10"
    assert window.ocr_page.whitelist_edit.text() == "0123456789"
    window.close()


def test_profile_path_cannot_escape_config_dir(qapp) -> None:
    from tesseract_studio.config import safe_profile_name

    window = MainWindow(variant="dark", apply_theme=True, language="ru")
    window.profiles_page.profile_combo.setCurrentText("../../escape")
    window.save_profile()
    expected = Path(CONFIG_DIR) / f"{safe_profile_name('../../escape')}.json"
    assert expected.parent == Path(CONFIG_DIR)
    assert expected.exists()
    assert not (Path(CONFIG_DIR).parent / "escape.json").exists()
    window.close()
