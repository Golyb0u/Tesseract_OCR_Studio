"""Reusable widgets for the OCR Studio shell."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..i18n import tr
from ..imaging import numpy_to_pixmap
from . import theme

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def repolish(widget: QtWidgets.QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class PopupThemeFilter(QtCore.QObject):
    """Keep QComboBox popup containers on the active palette.

    The popup container is a hidden Qt class that is not covered by the main
    stylesheet, so without this it paints the platform's white window colour
    around the dark rounded list. The filter restyles it every time it is shown.
    """

    def __init__(self, app: QtWidgets.QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._variant = "dark"
        self._radius = int(theme.DEFAULT_TOKENS["radius"])
        app.installEventFilter(self)

    def set_theme(self, variant: str, radius: int) -> None:
        self._variant = "light" if variant == "light" else "dark"
        self._radius = int(radius)
        sheet = theme.popup_stylesheet(self._variant, self._radius)
        for widget in self._app.allWidgets():
            if widget.metaObject().className() == "QComboBoxPrivateContainer":
                widget.setStyleSheet(sheet)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            event.type() == QtCore.QEvent.Show
            and obj.metaObject().className() == "QComboBoxPrivateContainer"
        ):
            popup = obj
            popup.setStyleSheet(theme.popup_stylesheet(self._variant, self._radius))
        return False


class Card(QtWidgets.QFrame):
    """Translucent surface with a title, optional hint and a body layout."""

    def __init__(
        self,
        title: str = "",
        hint: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
        tone: str = "",
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        if tone:
            self.setProperty("tone", tone)
        self._root = QtWidgets.QVBoxLayout(self)
        self._root.setContentsMargins(14, 12, 14, 14)
        self._root.setSpacing(10)

        self.header = QtWidgets.QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.setSpacing(8)
        # The header layout has to be attached to the card before widgets are
        # put into it: a parentless widget that is shown becomes a floating
        # top-level window, and a detached layout does not reparent on
        # addWidget. Without this ordering the card labels flashed a dozen
        # empty windows on screen while the UI was built.
        self._root.addLayout(self.header)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setProperty("role", "cardTitle")
        self.header.addWidget(self.title_label)
        self.title_label.setVisible(bool(title))
        self.header.addStretch(1)

        self.hint_label = QtWidgets.QLabel(hint)
        self.hint_label.setProperty("role", "cardHint")
        self.hint_label.setWordWrap(True)
        self._root.addWidget(self.hint_label)
        self.hint_label.setVisible(bool(hint))

        self.body = QtWidgets.QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(9)
        self._root.addLayout(self.body)

    def add(self, widget: QtWidgets.QWidget, stretch: int = 0) -> QtWidgets.QWidget:
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout: QtWidgets.QLayout) -> QtWidgets.QLayout:
        self.body.addLayout(layout)
        return layout

    def add_separator(self) -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        line.setProperty("role", "separator")
        line.setFixedHeight(1)
        self.body.addWidget(line)
        return line

    def badge(self, text: str, tone: str = "accent") -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setProperty("role", "chip")
        label.setProperty("tone", tone)
        self.header.addWidget(label)
        return label


class FormRow(QtWidgets.QWidget):
    """Label on the left, control on the right, consistent across pages."""

    def __init__(
        self,
        title: str,
        control: QtWidgets.QWidget,
        parent: Optional[QtWidgets.QWidget] = None,
        label_width: int = 132,
    ) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.label = QtWidgets.QLabel(title)
        self.label.setMinimumWidth(label_width)
        self.label.setWordWrap(True)
        self.control = control
        layout.addWidget(self.label)
        layout.addWidget(control, 1)


class HintLabel(QtWidgets.QLabel):
    def __init__(self, text: str = "", parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "hint")
        self.setWordWrap(True)


class ImagePreview(QtWidgets.QLabel):
    """Scales a numpy image to the available label area and accepts drops."""

    fileDropped = QtCore.pyqtSignal(str)

    def __init__(
        self,
        placeholder: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        placeholder = placeholder or tr("Нет изображения\nПеретащите файл сюда")
        super().__init__(placeholder, parent)
        self.setObjectName("previewLabel")
        self.setProperty("hasImage", False)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumHeight(220)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._placeholder = placeholder

    def set_numpy_image(self, image) -> None:
        self._pixmap = numpy_to_pixmap(image)
        self.setProperty("hasImage", True)
        repolish(self)
        self.setText("")
        self._update_scaled_pixmap()

    def clear_preview(self, text: Optional[str] = None) -> None:
        self._pixmap = None
        self.setProperty("hasImage", False)
        repolish(self)
        self.clear()
        self.setWordWrap(True)
        self.setText(text or self._placeholder)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        available = self.contentsRect().size() - QtCore.QSize(20, 20)
        if available.width() <= 0 or available.height() <= 0:
            return
        self.setPixmap(
            self._pixmap.scaled(
                available, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
        )

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if Path(path).suffix.lower() in IMAGE_SUFFIXES:
                    self.fileDropped.emit(path)
                    event.acceptProposedAction()
                    return
        event.ignore()


class StatusBanner(QtWidgets.QFrame):
    """Inline status strip; tones recolour the left rail and wash."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBanner")
        self.setProperty("tone", "accent")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.dot = QtWidgets.QLabel("●")
        self.dot.setProperty("role", "badge")
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.dot)
        layout.addWidget(self.message, 1)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)

    def set_message(self, text: str, tone: str = "accent", timeout: int = 6000) -> None:
        self.setProperty("tone", tone)
        repolish(self)
        self.message.setText(text)
        self._timer.stop()
        if timeout > 0:
            self._timer.start(timeout)
        self.show()

    def clear(self) -> None:
        self._timer.stop()
        self.message.clear()

    def current_text(self) -> str:
        return self.message.text()


class SoftToolTip(QtWidgets.QFrame):
    """Frameless tooltip with the same glass language as the cards."""

    def __init__(self) -> None:
        super().__init__(
            None,
            QtCore.Qt.ToolTip
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setObjectName("SoftToolTip")
        self.setStyleSheet("QFrame#SoftToolTip { background: transparent; border: none; }")

        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(26)
        self.shadow.setOffset(0, 9)
        self.shadow.setColor(QtGui.QColor(0, 0, 0, 120))

        self.animation = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.animation.finished.connect(self._handle_animation_finished)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QtWidgets.QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.label.setGraphicsEffect(self.shadow)
        self.set_palette_colors("#0f1722", "#eef2ff", "rgba(148, 163, 184, 72)")
        layout.addWidget(self.label)

    def set_palette_colors(self, background: str, text: str, border: str) -> None:
        self.label.setStyleSheet(
            "QLabel {"
            f"background: {background}; color: {text};"
            f"border: 1px solid {border}; border-radius: 12px;"
            "padding: 13px 15px 14px 15px; font-size: 12px;"
            "}"
        )

    def show_tooltip(self, anchor_widget: QtWidgets.QWidget, html: str) -> None:
        width = 330
        self.label.setText(html)
        self.label.setFixedWidth(width)
        self.label.adjustSize()
        height = max(96, self.label.sizeHint().height() + 2)
        self.resize(width, height)

        anchor_global = anchor_widget.mapToGlobal(QtCore.QPoint(0, 0))
        pos = QtCore.QPoint(
            anchor_global.x() + anchor_widget.width() + 12, anchor_global.y() + 6
        )
        screen = QtWidgets.QApplication.screenAt(pos) or QtWidgets.QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            if pos.x() + self.width() > available.right() - 8:
                pos.setX(anchor_global.x() - self.width() - 12)
            x = min(max(pos.x(), available.left() + 8), available.right() - self.width() - 8)
            y = min(max(pos.y(), available.top() + 8), available.bottom() - self.height() - 8)
            pos = QtCore.QPoint(max(x, available.left() + 8), y)
        self.move(pos)
        self.show()
        self.raise_()
        self.animation.stop()
        self.opacity_effect.setOpacity(0.0)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(0.88)
        self.animation.start()

    def hide_tooltip(self) -> None:
        if not self.isVisible():
            return
        self.animation.stop()
        self.animation.setStartValue(self.opacity_effect.opacity())
        self.animation.setEndValue(0.0)
        self.animation.start()

    def _handle_animation_finished(self) -> None:
        if self.opacity_effect.opacity() <= 0.01:
            self.hide()


class NavTabBar(QtWidgets.QTabBar):
    """Tab bar that reserves room for every translated label and icon.

    Qt's stylesheet-driven tab size hint ignores the bold font weight used for
    painted tab labels, so long labels such as "Обработка" were clipped at both
    edges. Measuring with the same bold metrics fixes the width instead of
    relying on the default hint.
    """

    H_PADDING = 9
    ICON_GAP = 4
    SAFETY = 4
    MIN_WIDTH = 72
    MIN_HEIGHT = 38

    def tabSizeHint(self, index: int) -> QtCore.QSize:
        base = super().tabSizeHint(index)
        text = self.tabText(index).replace("&", "")
        font = QtGui.QFont(self.font())
        font.setWeight(QtGui.QFont.DemiBold)
        metrics = QtGui.QFontMetrics(font)
        width = metrics.horizontalAdvance(text) + self.H_PADDING * 2 + self.SAFETY
        if not self.tabIcon(index).isNull():
            width += self.iconSize().width() + self.ICON_GAP
        height = max(self.MIN_HEIGHT, metrics.height() + self.H_PADDING * 2 + 4)
        return QtCore.QSize(max(self.MIN_WIDTH, width), max(base.height(), height))


class PageScroll(QtWidgets.QScrollArea):
    """Scrollable settings page with cards stacked inside."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(12)
        self.setWidget(self.content)

    def add(self, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        self.content_layout.addWidget(widget)
        return widget

    def finish(self) -> None:
        self.content_layout.addStretch(1)


def button_row(*buttons: QtWidgets.QWidget) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for button in buttons:
        layout.addWidget(button)
    return widget
