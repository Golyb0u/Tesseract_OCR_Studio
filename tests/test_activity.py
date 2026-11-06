from __future__ import annotations

from tesseract_studio.ui.activity import ActivityConsole


def test_activity_records_and_filters(qapp) -> None:
    console = ActivityConsole()
    console.record("info", "Захват", "кадр 100x50")
    console.record("success", "OCR", "готово")
    assert console.count() == 2
    assert "Захват" in console.plain_text()

    console.filter_edit.setText("готово")
    assert "готово" in console.view.toPlainText()
    assert "кадр 100x50" not in console.view.toPlainText()

    console.clear()
    assert console.count() == 0
    assert console.view.toPlainText() == ""


def test_activity_level_filter(qapp) -> None:
    console = ActivityConsole()
    console.record("error", "OCR", "boom")
    console.level_combo.setCurrentIndex(console.level_combo.findData("error"))
    assert "boom" in console.view.toPlainText()
    console.level_combo.setCurrentIndex(console.level_combo.findData("info"))
    assert "boom" not in console.view.toPlainText()
