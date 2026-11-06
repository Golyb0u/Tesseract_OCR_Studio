"""Live help panel and rich tooltip renderer."""

from __future__ import annotations

import html
from typing import Optional

from PyQt5 import QtCore, QtWidgets

from ..i18n import tr
from .widgets import Card, SoftToolTip


def rich_tooltip(
    title: str,
    description: str,
    best_for: str = "",
    tips: str = "",
    caution: str = "",
    values: str = "",
    dark: bool = True,
    include_title: bool = True,
) -> str:
    palette = (
        {
            "title": "#ffffff",
            "description": "#dbe4f0",
            "label": "#9fb6d8",
            "text": "#eef2f7",
        }
        if dark
        else {
            "title": "#101820",
            "description": "#26323c",
            "label": "#0f8fb3",
            "text": "#1a242c",
        }
    )

    def text_block(text: str) -> str:
        return html.escape(text).replace("\n", "<br>")

    def section(label: str, text: str) -> str:
        if not text:
            return ""
        return (
            "<div class='section'>"
            f"<div class='section-label'>{html.escape(label)}</div>"
            f"<div class='section-text'>{text_block(text)}</div>"
            "</div>"
        )

    return (
        "<html><head><meta charset='utf-8'><style>"
        "body { margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif;"
        f" color: {palette['text']}; }}"
        ".card { line-height: 1.45; }"
        f".title {{ font-size: 15px; font-weight: 700; margin: 0 0 7px 0; color: {palette['title']}; }}"
        f".description {{ margin: 0 0 9px 0; color: {palette['description']}; }}"
        ".section { margin-top: 11px; }"
        f".section-label {{ margin-bottom: 3px; font-size: 11px; font-weight: 700; color: {palette['label']};"
        " text-transform: uppercase; letter-spacing: 0.06em; }"
        f".section-text {{ color: {palette['text']}; }}"
        "</style></head><body><div class='card'>"
        + (f"<div class='title'>{html.escape(title)}</div>" if include_title else "")
        + f"<div class='description'>{text_block(description)}</div>"
        +
        f"{section(tr('Когда использовать'), best_for)}"
        f"{section(tr('Значения и варианты'), values)}"
        f"{section(tr('Практика'), tips)}"
        f"{section(tr('Важно'), caution)}"
        "</div></body></html>"
    )


class HelpPanel(QtWidgets.QFrame):
    """Right rail: live contextual help, diagnostics and small metrics."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "sidePanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        self._variant = "dark"
        self._payloads: dict[QtWidgets.QWidget, dict] = {}
        self._current: Optional[dict] = None
        self.soft_tooltip = SoftToolTip()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        help_card = Card(tr("Справка"), tr("Наведи курсор на параметр — здесь появится живое описание."))
        self.help_title = QtWidgets.QLabel(tr("Быстрая справка"))
        self.help_title.setProperty("role", "title")
        self.help_title.setWordWrap(True)
        self.help_browser = QtWidgets.QTextBrowser()
        self.help_browser.setObjectName("helpBrowser")
        self.help_browser.setOpenExternalLinks(False)
        self.help_browser.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.help_browser.setReadOnly(True)
        self.help_browser.document().setDocumentMargin(0)
        self.help_browser.setMinimumHeight(250)
        help_card.add(self.help_title)
        help_card.add(self.help_browser, 1)
        root.addWidget(help_card, 1)

        diag_card = Card(tr("Диагностика"), tr("Быстрая проверка путей и рискованных значений."))
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(QtCore.Qt.RichText)
        self.summary.setProperty("role", "hint")
        diag_card.add(self.summary)
        root.addWidget(diag_card)

        stats_card = Card(tr("Текущий кадр"))
        self._stats = {
            "source": "—",
            "processed": "—",
            "ocr": "—",
            "events": "0",
        }
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setProperty("role", "hint")
        self.stats_label.setWordWrap(True)
        stats_card.add(self.stats_label)
        root.addWidget(stats_card)
        self._refresh_stats()

        self.set_default_help()

    # ------------------------------------------------------------------ help
    def register(
        self,
        widget: QtWidgets.QWidget,
        title: str,
        description: str,
        best_for: str = "",
        tips: str = "",
        caution: str = "",
        values: str = "",
    ) -> None:
        payload = {
            "title": title,
            "description": description,
            "best_for": best_for,
            "tips": tips,
            "caution": caution,
            "values": values,
        }
        self._payloads[widget] = payload
        widget.setToolTip("")
        widget.installEventFilter(self)

    def update_payload(self, widget: QtWidgets.QWidget, **changes: str) -> None:
        payload = self._payloads.get(widget)
        if payload is None:
            return
        payload.update(changes)
        if self._current is payload and (
            QtWidgets.QApplication.focusWidget() is widget or widget.underMouse()
        ):
            self.set_help_content(payload)
            self.soft_tooltip.show_tooltip(widget, self._html(payload))

    def set_help_content(self, payload: dict) -> None:
        self._current = payload
        self.help_title.setText(tr(payload["title"]))
        self.help_browser.setHtml(self._html(payload))

    def set_default_help(self) -> None:
        self.set_help_content(
            {
                "title": "Быстрая справка",
                "description": "Наведи курсор на параметр или сфокусируй поле — здесь появится живое описание настройки.",
                "best_for": "Начни с пресета, затем подгони PSM, бинаризацию и whitelist под конкретный кадр.",
                "tips": "Сначала зафиксируй кадр, затем сравнивай настройки через F5.",
                "caution": "",
                "values": "",
            }
        )

    def _html(self, payload: dict) -> str:
        localized = {
            key: tr(value) if isinstance(value, str) else value
            for key, value in payload.items()
        }
        return rich_tooltip(
            localized["title"],
            localized["description"],
            localized["best_for"],
            localized["tips"],
            localized["caution"],
            localized["values"],
            dark=self._variant != "light",
            include_title=False,
        )

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        if self._current is not None:
            self.help_browser.setHtml(self._html(self._current))
        dark = variant != "light"
        if dark:
            self.soft_tooltip.set_palette_colors(
                "rgba(15, 23, 34, 0.96)", "#eef2ff", "rgba(148, 163, 184, 72)"
            )
        else:
            self.soft_tooltip.set_palette_colors(
                "rgba(250, 251, 252, 0.98)", "#14202a", "rgba(15, 20, 25, 0.16)"
            )

    # ------------------------------------------------------------- diagnostics
    def set_diagnostics(self, html_text: str) -> None:
        self.summary.setText(html_text)

    def set_stat(self, key: str, value: str) -> None:
        if key in self._stats:
            self._stats[key] = value
            self._refresh_stats()

    def _refresh_stats(self) -> None:
        self.stats_label.setText(
            tr(
                "Исходник: {source}   ·   Обработка: {processed}\n"
                "OCR: {ocr}   ·   Событий: {events}",
                source=self._stats["source"],
                processed=self._stats["processed"],
                ocr=self._stats["ocr"],
                events=self._stats["events"],
            )
        )

    # ------------------------------------------------------------------ events
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        payload = self._payloads.get(watched)
        if payload is not None:
            if event.type() in (QtCore.QEvent.Enter, QtCore.QEvent.FocusIn):
                self.set_help_content(payload)
                self.soft_tooltip.show_tooltip(watched, self._html(payload))
            elif event.type() in (
                QtCore.QEvent.Leave,
                QtCore.QEvent.FocusOut,
                QtCore.QEvent.Hide,
            ):
                self.soft_tooltip.hide_tooltip()
        return super().eventFilter(watched, event)
