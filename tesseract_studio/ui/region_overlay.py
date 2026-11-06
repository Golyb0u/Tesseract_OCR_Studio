"""Full-screen region selection overlay."""

from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

from ..i18n import tr


class RegionSelectionOverlay(QtWidgets.QWidget):
    regionSelected = QtCore.pyqtSignal(dict)
    selectionCanceled = QtCore.pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.origin = QtCore.QPoint()
        self.current = QtCore.QPoint()
        self.selecting = False
        self._finished = False
        self._origin_global = QtCore.QPoint()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setWindowTitle(tr("Выбор области OCR"))

        screens = QtWidgets.QApplication.screens()
        if screens:
            geometry = QtCore.QRect(screens[0].geometry())
            for screen in screens[1:]:
                geometry = geometry.united(screen.geometry())
        else:
            geometry = QtWidgets.QApplication.primaryScreen().geometry()
        self.setGeometry(geometry)
        self._origin_global = geometry.topLeft()

        self.info_label = QtWidgets.QLabel(
            tr("Выделите область OCR мышью. Esc или правый клик — отмена."),
            self,
        )
        self.info_label.move(22, 22)
        self.info_label.setStyleSheet(
            "QLabel { background: rgba(12, 18, 25, 235); color: #eaf2fb;"
            " border: 1px solid rgba(55, 182, 214, 160); border-radius: 9px;"
            " padding: 10px 14px; font-size: 13px; font-weight: 600; }"
        )
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            self._finished = True
            self.selectionCanceled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.RightButton:
            self._finished = True
            self.selectionCanceled.emit()
            self.close()
            return
        if event.button() == QtCore.Qt.LeftButton:
            self.origin = event.pos()
            self.current = event.pos()
            self.selecting = True
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.selecting:
            self.current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton or not self.selecting:
            return
        self.current = event.pos()
        self.selecting = False
        rect = QtCore.QRect(self.origin, self.current).normalized()
        self._finished = True
        self.close()
        if rect.width() < 5 or rect.height() < 5:
            self.selectionCanceled.emit()
            return
        global_rect = rect.translated(self._origin_global)
        self.regionSelected.emit(
            {
                "left": int(global_rect.left()),
                "top": int(global_rect.top()),
                "width": int(global_rect.width()),
                "height": int(global_rect.height()),
            }
        )

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 145))
        if self.origin != self.current:
            rect = QtCore.QRect(self.origin, self.current).normalized()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            painter.setPen(QtGui.QPen(QtGui.QColor("#58d5ec"), 2))
            painter.drawRect(rect)
            label = f"{rect.width()} x {rect.height()}"
            label_rect = QtCore.QRect(rect.left() + 6, max(6, rect.top() - 26), 150, 22)
            painter.fillRect(label_rect, QtGui.QColor(12, 18, 25, 225))
            painter.setPen(QtGui.QColor("#eaf2fb"))
            painter.drawText(label_rect.adjusted(7, 0, 0, 0), QtCore.Qt.AlignVCenter, label)
        painter.end()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self.activateWindow()
        self.setFocus(QtCore.Qt.ActiveWindowFocusReason)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._finished:
            self._finished = True
            self.selectionCanceled.emit()
        super().closeEvent(event)
