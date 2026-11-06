"""Flat theme engine ported from Qt UI Lab into Tesseract OCR Studio.

The original design system (tokens, QSS renderer, painted checkmarks) is kept
intact and extended with OCR-studio-specific selectors.  Keeping one sheet for
the whole application means the accent, radius and typeface recolour cards,
inputs, tabs, docks and the activity console at the same time.

Design rules:
  * one global diagonal gradient on the shell, with translucent panels layered
    on top of it instead of opaque blocks;
  * a real type scale (display / title / body / caption / mono) driven by
    FONT_STACK so a single family change re-renders the whole sheet;
  * translucency only through rgba(), never through window opacity, so the
    global gradient stays visible through docks, toolbars and cards.
  * every interactive element carries hover / pressed / focus / checked /
    disabled states, and every colour resolves from a token so that changing
    the accent recolours selection, hover text, sliders and scrollbars too.

BASE_QSS holds the shell + surfaces, CONTROL_QSS the interactive controls.
tokens_to_qss() re-derives every accent/font/radius rule from a token dict so
the inspector and the live QSS editor stay in sync.
"""

from __future__ import annotations

import atexit
import json
import tempfile
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen

try:  # Qt >= 5.13 has an antialiasing flag on QImage; older builds do not.
    from PyQt5.QtGui import QImage
    from PyQt5.QtCore import QSize
except ImportError:  # pragma: no cover - PyQt5 always ships these
    QImage = QSize = None

# Typography: one stack for UI text, one for numerics, plus a modular scale.
FONT_STACK = '"Segoe UI Variable Display", "Segoe UI", "Inter", "SF Pro Text", sans-serif'
MONO_STACK = '"Cascadia Mono", "JetBrains Mono", Consolas, "Courier New", monospace'

FONT_SIZE_BODY = 10     # pt - base size for every control
FONT_SIZE_CAPTION = 9   # pt - hints, badges, secondary metadata
FONT_SIZE_TITLE = 11    # pt - group captions, dock titles
FONT_SIZE_MONO = 9      # pt - log console and numeric readouts

# Layered glass tokens: rgba over the global gradient.
BG_SHELL_0 = "#23282f"
BG_SHELL_1 = "#171b20"
BG_SHELL_2 = "#0a0c0f"
PANEL = "rgba(255, 255, 255, 0.035)"
PANEL_HOVER = "rgba(255, 255, 255, 0.065)"
PANEL_ACTIVE = "rgba(55, 182, 214, 0.16)"
WELL = "rgba(0, 0, 0, 0.34)"
WELL_DEEP = "rgba(0, 0, 0, 0.46)"
HAIRLINE = "rgba(255, 255, 255, 0.07)"
HAIRLINE_STRONG = "rgba(255, 255, 255, 0.12)"

# Ambient surfaces. Shell stops are also reused by MDI/wizard backgrounds so
# detached surfaces never look flat grey next to the main gradient.
SHELL_TOP = "#262c33"
SHELL_MID = "#1d2228"
SHELL_LOW = "#14181c"
SHELL_BOTTOM = "#090b0e"

TOOLBAR_FILL = "rgba(255, 255, 255, 0.025)"
HEADER_FILL = "rgba(255, 255, 255, 0.045)"
ROW_ALT = "rgba(255, 255, 255, 0.022)"
POPUP = "rgba(20, 25, 30, 0.985)"

# Wells / tracks / rails stay purely neutral so the accent reads as the only
# coloured thing on screen.
TRACK = "rgba(255, 255, 255, 0.10)"
TRACK_HOVER = "rgba(255, 255, 255, 0.14)"
RAIL = "rgba(0, 0, 0, 0.18)"
SCROLL_HANDLE = "rgba(255, 255, 255, 0.16)"
PRESSED_FILL = "rgba(0, 0, 0, 0.34)"
DISABLED_FILL = "rgba(255, 255, 255, 0.022)"
DISABLED_FILL_STRONG = "rgba(255, 255, 255, 0.10)"
READONLY_FILL = "rgba(255, 255, 255, 0.02)"

# Light palette mirror: the same token names, re-derived from a bright shell so
# ``render_qss(tokens)`` can produce a full light sheet without a second QSS.
LIGHT_TOKENS = {
    "accent": "#0f8fb3",
    "accent_hover": "#0a7c9c",
    "text": "#14181d",
    "text_muted": "rgba(30, 40, 50, 0.84)",
    "surface": "#eef1f4",
    "surface_alt": "#e2e7ec",
    "border": "rgba(15, 20, 25, 0.10)",
    "danger": "#c0504a",
    "success": "#2f8f5b",
    "radius": 4,
    "font_family": "Segoe UI Variable Display",
    "font_size": 9,
    "mono_family": "Cascadia Mono",
    "mark": "#ffffff",
}

# Overrides applied on top of the dark sheet when rendering the light variant.
LIGHT_OVERRIDES = {
    "TEXT": "#14181d",
    "TEXT_SOFT": "rgba(24, 30, 36, 0.92)",
    "TEXT_MUTED": "rgba(30, 40, 50, 0.84)",
    "TEXT_DISABLED": "rgba(60, 70, 80, 0.40)",
    "ACCENT_TEXT": "#08323f",
    "MONO_TEXT": "#0a6f7d",
    "PANEL": "rgba(255, 255, 255, 0.72)",
    "PANEL_HOVER": "rgba(255, 255, 255, 0.94)",
    "PANEL_ACTIVE": "rgba(15, 143, 179, 0.16)",
    "WELL": "rgba(255, 255, 255, 0.60)",
    "WELL_DEEP": "rgba(255, 255, 255, 0.80)",
    "HAIRLINE": "rgba(15, 20, 25, 0.09)",
    "HAIRLINE_STRONG": "rgba(15, 20, 25, 0.16)",
    "TOOLBAR_FILL": "rgba(255, 255, 255, 0.55)",
    "HEADER_FILL": "rgba(255, 255, 255, 0.70)",
    "ROW_ALT": "rgba(15, 20, 25, 0.035)",
    "POPUP": "rgba(250, 251, 252, 0.99)",
    "TRACK": "rgba(15, 20, 25, 0.12)",
    "TRACK_HOVER": "rgba(15, 20, 25, 0.18)",
    "RAIL": "rgba(15, 20, 25, 0.06)",
    "SCROLL_HANDLE": "rgba(15, 20, 25, 0.22)",
    "PRESSED_FILL": "rgba(15, 20, 25, 0.12)",
    "DISABLED_FILL": "rgba(15, 20, 25, 0.05)",
    "DISABLED_FILL_STRONG": "rgba(15, 20, 25, 0.12)",
    "READONLY_FILL": "rgba(15, 20, 25, 0.035)",
    "SHELL_TOP": "#f7f9fb",
    "SHELL_MID": "#eef1f4",
    "SHELL_LOW": "#e4e9ee",
    "SHELL_BOTTOM": "#d8dee5",
    "DANGER_TEXT": "#8f2f28",
    "WARN_TEXT": "#7a5a12",
    "SUCCESS_TEXT": "#1d6b40",
    "ACCENT_GLASS_ALPHA": "0.38",
    "ACCENT_GLASS_ALPHA_BRIGHT": "0.52",
}


# Text ramp. Every label colour comes from here so the palette stays coherent.
TEXT = "#e2e7ec"
TEXT_SOFT = "rgba(224, 232, 239, 0.92)"
TEXT_MUTED = "rgba(196, 207, 218, 0.70)"
TEXT_DISABLED = "rgba(190, 201, 212, 0.32)"
ACCENT_TEXT = "#dff6fd"
MONO_TEXT = "#7ce8d6"

DANGER = "#c0504a"
DANGER_WASH = "rgba(162, 56, 47, 0.28)"
DANGER_WASH_STRONG = "rgba(192, 80, 74, 0.45)"
DANGER_TEXT = "#f5bdb6"
WARN = "#b08b3e"
WARN_WASH = "rgba(176, 139, 62, 0.20)"
WARN_TEXT = "#f2d79a"
SUCCESS_WASH = "rgba(63, 154, 90, 0.22)"
SUCCESS_TEXT = "#b6e8c3"

BASE_QSS = """
*, QWidget {
    background: transparent;
    color: __TEXT__;
    font-family: __FONT__;
    font-size: __BODY__pt;
}

/* ---- global background: a wide diagonal gradient so every panel has depth.
       Child widgets stay transparent and layer translucent fills on top.
       The stops double as the ambient light the translucent panels sit in. ---- */
QWidget#MainWindow, QMainWindow, QDialog, QWizard, QWizardPage {
    background: qlineargradient(x1:0, y1:0, x2:0.85, y2:1,
                stop:0    __SHELL_TOP__,
                stop:0.28 __SHELL_MID__,
                stop:0.62 __SHELL_LOW__,
                stop:1    __SHELL_BOTTOM__);
}
QWidget#centralHost { background: transparent; }
QLabel, QAbstractButton { background: transparent; }

QDockWidget { background: transparent; border: none; titlebar-close-icon: none; titlebar-normal-icon: none; }
QDockWidget > QWidget { background: transparent; }
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent; border: none; icon-size: 0px; padding: 0; width: 0; height: 0;
}
QMainWindow::separator { background: transparent; width: 0; height: 0; }

QScrollArea, QAbstractScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QStackedWidget { background: transparent; }
QFrame[role="sep"] { background: __HAIRLINE__; max-height: 1px; border: none; }
QFrame[frameShape="4"], QFrame[frameShape="5"] { background: __HAIRLINE__; border: none; max-height: 1px; }

QToolTip {
    background: __POPUP__; color: __ACCENT_TEXT__;
    border: none; border-left: 2px solid __ACCENT__; border-radius: 2px;
    padding: 6px 10px; font-size: __CAPTION__pt;
}

/* ---- group boxes: frameless caption band over the shared background ---- */
QGroupBox {
    background: transparent;
    border: none;
    margin-top: 4px;
    padding: __GROUP_PAD__ 0 0 0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0; padding: 0 0 6px 0;
    color: __ACCENT_HOVER__;
    font-weight: 600;
    font-size: __TITLE__pt;
    letter-spacing: 0.3px;
}
QGroupBox[role="card"] {
    background: __PANEL__;
    border-radius: __RADIUS__px;
    padding: __GROUP_PAD__ __GROUP_PAD__ 0 __GROUP_PAD__;
}
QGroupBox::indicator {
    width: __INDICATOR__px; height: __INDICATOR__px;
    border: 1px solid __HAIRLINE_STRONG__; border-radius: __INDICATOR_RADIUS__px;
    background: __WELL__; margin-right: 8px;
}
QGroupBox::indicator:hover { border: 1px solid __ACCENT__; background: __ACCENT_WASH__; }
QGroupBox::indicator:checked {
    image: url("__CHECK_IMG__");
    border: 1px solid __ACCENT__; background: __ACCENT__;
}
QGroupBox::indicator:disabled {
    border: 1px solid __HAIRLINE__; background: __DISABLED_FILL__;
}
QGroupBox[flat="true"] { margin-top: 0; }

QLabel { background: transparent; }
QLabel[role="hint"] {
    color: __TEXT_MUTED__;
    font-size: __CAPTION__pt;
}
QLabel[role="section"] {
    color: __ACCENT_HOVER__;
    font-weight: 700; font-size: __CAPTION__pt;
    text-transform: uppercase; letter-spacing: 1.5px;
    padding: 2px 0;
}
QLabel[role="value"] {
    color: __MONO_TEXT__; font-family: __MONO__; font-size: __MONO_SIZE__pt;
    background: __WELL__;
    border: none; border-left: 2px solid __ACCENT__;
    border-radius: __RADIUS_SM__px; padding: 3px 10px;
}
QLabel[role="swatch"] {
    border: none; border-radius: __RADIUS__px; background: __WELL__;
    min-width: 46px; min-height: 20px;
}
QLabel[role="badge"] {
    color: __MARK__; background: __ACCENT__;
    border-radius: __BADGE_RADIUS__px; padding: 1px 8px;
    font-size: __CAPTION__pt; font-weight: 700;
}
QLabel[role="chip"] {
    color: __TEXT__; background: __PANEL_HOVER__;
    border: none; border-radius: __BADGE_RADIUS__px; padding: 1px 8px;
    font-size: __CAPTION__pt; font-weight: 600;
}
QLabel[role="chip"][tone="ok"]       { background: __SUCCESS_WASH__; color: __SUCCESS_TEXT__; }
QLabel[role="chip"][tone="warn"]     { background: __WARN_WASH__;    color: __WARN_TEXT__; }
QLabel[role="chip"][tone="danger"]   { background: __DANGER_WASH__;  color: __DANGER_TEXT__; }
QLabel[role="chip"][tone="accent"]   { background: __ACCENT_WASH__;  color: __ACCENT_TEXT__; }
QLabel[role="title"] {
    color: __ACCENT_TEXT__; font-weight: 600; font-size: __TITLE__pt;
}
QLabel[role="mono"] { font-family: __MONO__; font-size: __MONO_SIZE__pt; color: __MONO_TEXT__; }
QLabel[role="toast"] {
    background: __PANEL_HOVER__;
    color: __TEXT__;
    border: none; border-left: 2px solid __ACCENT__;
    border-radius: __RADIUS__px;
    padding: 8px 12px;
    font-weight: 600;
}
QLabel[role="toast"][tone="ok"]     { border-left-color: __SUCCESS_TEXT__; background: __SUCCESS_WASH__; }
QLabel[role="toast"][tone="warn"]   { border-left-color: __WARN__;     background: __WARN_WASH__; }
QLabel[role="toast"][tone="danger"] { border-left-color: __DANGER__;   background: __DANGER_WASH__; }
QLabel[role="toast"][tone="accent"] { border-left-color: __ACCENT__;   background: __ACCENT_WASH__; }
QLabel:disabled { color: __TEXT_DISABLED__; }

/* ---- banner: full-width status strip over the shared background ---- */
QFrame#banner {
    background: __ACCENT_WASH__;
    border: none; border-left: 3px solid __ACCENT__;
    border-radius: __RADIUS__px;
}
QFrame#banner QLabel { color: __ACCENT_TEXT__; font-weight: 600; }

/* ---- flat tabs: translucent chips, cyan underline when active ---- */
QTabWidget::pane { background: transparent; border: none; top: 0; }
QTabWidget::tab-bar { alignment: left; }
QTabWidget > QWidget { background: transparent; }
QTabBar { background: transparent; qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent;
    color: __TEXT_MUTED__;
    padding: 8px 9px;
    margin-right: 4px;
    margin-bottom: 0;
    border: none;
    border-bottom: 2px solid transparent;
    border-top-left-radius: __RADIUS__px;
    border-top-right-radius: __RADIUS__px;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    color: __TEXT__; background: __PANEL__;
    border-bottom: 2px solid __HAIRLINE_STRONG__;
}
QTabBar::tab:selected {
    color: __ACCENT_HOVER__;
    background: __PANEL__;
    border-bottom: 2px solid __ACCENT__;
}
QTabBar::tab:!selected:hover { border-bottom: 2px solid __HAIRLINE_STRONG__; }
QTabBar::tab:disabled { color: __TEXT_DISABLED__; }
QTabBar::tab:selected:focus { border-bottom: 2px solid __ACCENT_HOVER__; }
QTabBar::close-button {
    subcontrol-position: right; background: transparent; border: none;
    image: none; width: 12px; height: 12px; margin-left: 6px;
}
QTabBar::close-button:hover { background: __DANGER_WASH__; border-radius: __RADIUS_SM__px; }
QTabBar QToolButton {
    background: transparent; border: none; color: __TEXT_MUTED__; padding: 2px 6px;
}
QTabBar QToolButton:hover { color: __ACCENT_HOVER__; background: __PANEL__; }

/* ---- toolbars and menus: translucent glass strips ---- */
QToolBar {
    background: __TOOLBAR_FILL__;
    border: none; border-bottom: 1px solid __HAIRLINE__;
    spacing: 3px; padding: 6px 9px;
}
QToolBar::separator {
    background: __HAIRLINE_STRONG__; width: 1px; margin: 5px 7px;
}
QToolBar::handle { background: transparent; width: 6px; }
QToolButton {
    background: transparent; border: none;
    border-radius: __RADIUS__px; padding: 7px 11px;
    color: __TEXT_SOFT__;
    font-weight: 500;
}
QToolButton:hover { background: __PANEL_HOVER__; color: __ACCENT_TEXT__; }
QToolButton:pressed { background: __PRESSED_FILL__; }
QToolButton:checked { background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__; }
QToolButton:checked:hover { background: __ACCENT_WASH_SOLID__; }
QToolButton:disabled { color: __TEXT_DISABLED__; background: transparent; }
/* A focus border on a rounded button is drawn incompletely by Qt, so the
   focused state is expressed as a fill instead: it stays flat and intact. */
QToolButton:focus { background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__; }
QToolButton:focus:hover { background: __ACCENT_WASH_SOLID__; }
QToolButton[popupMode="1"], QToolButton[popupMode="2"] { padding-right: 7px; }
QToolButton[popupMode="1"]::menu-indicator,
QToolButton[popupMode="2"]::menu-indicator {
    image: none; subcontrol-origin: padding; subcontrol-position: right center;
    width: 0; height: 0;
    border-left: 3px solid transparent; border-right: 3px solid transparent;
    border-top: 4px solid __ACCENT_HOVER__; margin-right: 4px;
}
QToolButton[popupMode="0"]::menu-indicator { image: none; width: 0; height: 0; }

QMenuBar {
    background: __TOOLBAR_FILL__; color: __TEXT_SOFT__;
    border-bottom: 1px solid __HAIRLINE__;
}
QMenuBar::item { padding: 8px 13px; background: transparent; border-radius: __RADIUS_SM__px; margin: 2px; }
QMenuBar::item:selected { background: __PANEL_HOVER__; color: __ACCENT_HOVER__; }
QMenuBar::item:pressed { background: __PANEL_ACTIVE__; }
QMenuBar::item:disabled { color: __TEXT_DISABLED__; }

QMenu {
    background: __POPUP__; border: none;
    padding: 7px; border-radius: __RADIUS__px;
}
QMenu::item { padding: 8px 26px 8px 22px; border-radius: __RADIUS_SM__px; color: __TEXT__; }
QMenu::item:selected { background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__; }
QMenu::item:disabled { color: __TEXT_DISABLED__; }
QMenu::separator { height: 1px; background: __HAIRLINE__; margin: 6px 11px; }
QMenu::icon { left: 8px; }
QMenu::indicator { width: __INDICATOR__px; height: __INDICATOR__px; }
QMenu::indicator:exclusive:checked { image: url("__DOT_IMG__"); }
QMenu::indicator:checked { image: url("__CHECK_IMG__"); }
QMenu::right-arrow {
    image: none; subcontrol-origin: padding; subcontrol-position: right center;
    width: 0; height: 0; margin-right: 10px;
    border-top: 4px solid transparent; border-bottom: 4px solid transparent;
    border-left: 5px solid __TEXT_MUTED__;
}

QStatusBar {
    background: __TOOLBAR_FILL__; color: __TEXT_MUTED__;
    border: none; border-top: 1px solid __HAIRLINE__;
    font-size: __CAPTION__pt;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { color: __TEXT_MUTED__; font-size: __CAPTION__pt; }

/* ---- item views: translucent sunken wells over the global gradient ---- */
QAbstractItemView {
    background: __WELL__;
    alternate-background-color: __ROW_ALT__;
    border: none;
    border-radius: __RADIUS__px;
    selection-background-color: __SELECTION__;
    selection-color: __ACCENT_TEXT__;
    outline: none;
}
QTableView, QTreeView, QListView, QTableWidget, QTreeWidget, QListWidget,
QColumnView, QUndoView, QHelpContentWidget {
    background: __WELL__;
    alternate-background-color: __ROW_ALT__;
    border: none;
    border-radius: __RADIUS__px;
    selection-background-color: __SELECTION__;
    selection-color: __ACCENT_TEXT__;
    outline: none;
}
QAbstractItemView:disabled { color: __TEXT_DISABLED__; }

QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: __HEADER_FILL__;
    color: __TEXT_MUTED__;
    padding: 8px 11px;
    border: none; border-bottom: 1px solid __HAIRLINE_STRONG__;
    font-weight: 600; font-size: __CAPTION__pt;
    text-transform: uppercase; letter-spacing: 0.6px;
}
QHeaderView::section:hover { background: __PANEL_HOVER__; color: __TEXT__; }
QHeaderView::section:pressed { background: __PANEL_ACTIVE__; }
QHeaderView::section:checked { color: __ACCENT_HOVER__; }
QHeaderView::down-arrow, QHeaderView::up-arrow {
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 0; height: 0; margin-right: 7px;
    image: none;
}
QHeaderView::down-arrow {
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid __ACCENT_HOVER__;
}
QHeaderView::up-arrow {
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid __ACCENT_HOVER__;
}
QTableView QTableCornerButton::section {
    background: __HEADER_FILL__; border: none;
}

QTableView::item, QTreeView::item, QListView::item,
QTableWidget::item, QTreeWidget::item, QListWidget::item, QColumnView::item {
    padding: 7px 9px; border: none;
}
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected,
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected,
QColumnView::item:selected {
    background: __SELECTION__; color: __ACCENT_TEXT__;
}
QTableView::item:hover, QTreeView::item:hover, QListView::item:hover,
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover,
QColumnView::item:hover { background: __PANEL_HOVER__; }
QTableView::item:disabled, QTreeView::item:disabled, QListView::item:disabled,
QTableWidget::item:disabled, QTreeWidget::item:disabled, QListWidget::item:disabled {
    color: __TEXT_DISABLED__;
}

/* Check indicators inside item views need their own glyph rules, otherwise the
   view falls back to the native style and breaks the flat look. */
QAbstractItemView::indicator, QListView::indicator, QTreeView::indicator,
QTableView::indicator, QListWidget::indicator, QTreeWidget::indicator {
    width: __INDICATOR__px; height: __INDICATOR__px;
    border: 1px solid __HAIRLINE_STRONG__;
    border-radius: __INDICATOR_RADIUS__px;
    background: __WELL__;
}
QAbstractItemView::indicator:hover, QListView::indicator:hover,
QTreeView::indicator:hover, QTableView::indicator:hover {
    border: 1px solid __ACCENT__; background: __ACCENT_WASH__;
}
QAbstractItemView::indicator:checked, QListView::indicator:checked,
QTreeView::indicator:checked, QTableView::indicator:checked {
    image: url("__CHECK_IMG__");
    border: 1px solid __ACCENT__;
    background: __ACCENT__;
}
QAbstractItemView::indicator:indeterminate, QListView::indicator:indeterminate,
QTreeView::indicator:indeterminate, QTableView::indicator:indeterminate {
    image: url("__DASH_IMG__");
    border: none;
    background: transparent;
}
QAbstractItemView::indicator:disabled {
    border: 1px solid __HAIRLINE__; background: __DISABLED_FILL__;
}
QTreeView::branch { background: transparent; }
QTreeView::branch:hover { background: transparent; }

QSplitter { background: transparent; }
QSplitter::handle { background: __HAIRLINE__; }
QSplitter::handle:hover { background: __ACCENT__; }
QSplitter::handle:pressed { background: __ACCENT_HOVER__; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }

QDockWidget::title {
    background: transparent; color: __TEXT_MUTED__;
    padding: 9px 4px 7px 4px; border: none;
    font-weight: 700; letter-spacing: 0.9px; text-transform: uppercase;
    font-size: __CAPTION__pt;
}
QDockWidget::title:hover { color: __ACCENT_HOVER__; }

/* ---- toolbox: flat accordion, cyan rail on the active page ---- */
QToolBox { background: transparent; border: none; }
QToolBox::tab {
    background: __PANEL__;
    border: none; border-left: 2px solid transparent;
    border-radius: __RADIUS_SM__px;
    color: __TEXT_SOFT__;
    padding: 8px 12px; margin: 1px 0;
    font-weight: 600;
}
QToolBox::tab:hover { background: __PANEL_HOVER__; color: __ACCENT_TEXT__; }
QToolBox::tab:selected {
    background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__;
    border-left: 2px solid __ACCENT__;
}
QToolBox::tab:disabled { color: __TEXT_DISABLED__; }
QToolBox > QWidget { background: transparent; }

/* ---- calendar: flat grid, accent selection, quiet header ---- */
QCalendarWidget { background: transparent; border: none; }
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: __PANEL__; border: none; border-radius: __RADIUS__px;
}
QCalendarWidget QToolButton {
    background: transparent; border: none; border-radius: __RADIUS_SM__px;
    color: __TEXT__; padding: 6px 10px; font-weight: 600;
}
QCalendarWidget QToolButton:hover { background: __PANEL_HOVER__; color: __ACCENT_HOVER__; }
QCalendarWidget QToolButton:pressed { background: __PANEL_ACTIVE__; }
QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }
QCalendarWidget QMenu { background: __POPUP__; }
QCalendarWidget QSpinBox {
    background: transparent; border: none; border-bottom: 1px solid __HAIRLINE__;
    border-radius: 0; color: __TEXT__; selection-background-color: __SELECTION__;
}
QCalendarWidget QAbstractItemView {
    background: __WELL__;
    alternate-background-color: __ROW_ALT__;
    color: __TEXT__;
    selection-background-color: __ACCENT__;
    selection-color: __MARK__;
    outline: none;
    border: none;
}
QCalendarWidget QAbstractItemView:enabled {
    background: __WELL__; color: __TEXT__;
    selection-background-color: __ACCENT__; selection-color: __MARK__;
}
QCalendarWidget QAbstractItemView:disabled { color: __TEXT_DISABLED__; }
QCalendarWidget QWidget { alternate-background-color: __ROW_ALT__; }

QTextBrowser, QTextBrowser#log, QTextEdit#log {
    background: __WELL_DEEP__; border: none; border-radius: __RADIUS__px;
    font-family: __MONO__; font-size: __MONO_SIZE__pt;
}

/* ---- graphics view: no native frame, translucent canvas ---- */
QGraphicsView {
    background: __WELL_DEEP__;
    border: none; border-radius: __RADIUS__px;
    selection-background-color: __SELECTION__;
}
QGraphicsView::rubberband { background: __ACCENT_WASH__; border: 1px solid __ACCENT__; }

/* ---- MDI / wizard surfaces inherit the shell gradient ---- */
QMdiArea { background: qlineargradient(x1:0, y1:0, x2:0.85, y2:1,
                stop:0 __SHELL_TOP__, stop:1 __SHELL_BOTTOM__); border: none; }
QMdiSubWindow { background: transparent; border: none; }
"""


CONTROL_QSS = """
/* ---- buttons: one flat fill, interaction only changes its lightness ---- */
QPushButton {
    background: __PANEL__;
    border: none;
    border-radius: __RADIUS__px;
    padding: 8px 18px; color: __TEXT_SOFT__;
    min-height: 18px;
    font-weight: 500;
}
QPushButton:hover { background: __PANEL_HOVER__; color: __ACCENT_TEXT__; }
QPushButton:pressed { background: __PRESSED_FILL__; }
QPushButton:focus { background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__; }
QPushButton:disabled {
    background: __DISABLED_FILL__; color: __TEXT_DISABLED__;
}
QPushButton:checked {
    background: __PANEL_ACTIVE__; color: __ACCENT_HOVER__; font-weight: 600;
}
QPushButton:checked:hover { background: __ACCENT_WASH_SOLID__; }
/* Accent button: pure flat fill - no gradient, no bevel, no shadow. */
QPushButton#accent {
    background: __ACCENT__;
    border: none; color: __MARK__; font-weight: 700;
    padding: 8px 18px;
}
QPushButton#accent:hover { background: __ACCENT_HOVER__; }
QPushButton#accent:pressed { background: __ACCENT_MUTED__; }
QPushButton#accent:disabled {
    background: __DISABLED_FILL__; color: __TEXT_DISABLED__;
}
QPushButton#accent:focus { background: __ACCENT_HOVER__; }
QPushButton#danger { background: __DANGER_WASH__; color: __DANGER_TEXT__; }
QPushButton#danger:hover { background: __DANGER_WASH_STRONG__; color: #ffffff; }
QPushButton#danger:pressed { background: __DANGER__; color: #ffffff; }
QPushButton#danger:disabled { background: __DISABLED_FILL__; color: __TEXT_DISABLED__; }
QPushButton[flat="true"] {
    background: transparent; border: none; padding: 6px 4px; color: __ACCENT_HOVER__;
}
QPushButton[flat="true"]:hover { background: transparent; color: __ACCENT_TEXT__; text-decoration: underline; }
QPushButton[flat="true"]:pressed { color: __ACCENT_MUTED__; }
QPushButton[flat="true"]:disabled { color: __TEXT_DISABLED__; }
QCommandLinkButton {
    background: transparent; border: none; border-radius: __RADIUS__px;
    padding: 9px 12px; color: __TEXT__; text-align: left;
}
QCommandLinkButton:hover { background: __PANEL_HOVER__; }
QCommandLinkButton:pressed { background: __PANEL_ACTIVE__; }
QCommandLinkButton:focus { background: __PANEL__; color: __ACCENT_HOVER__; }

QDialogButtonBox { background: transparent; }
QDialogButtonBox QPushButton { min-width: 84px; }

/* ---- inputs: translucent wells with a cyan underline on focus ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit,
QTimeEdit, QDateTimeEdit, QComboBox {
    background: __WELL__;
    border: none;
    border-bottom: 1px solid __HAIRLINE__;
    border-top-left-radius: __RADIUS__px;
    border-top-right-radius: __RADIUS__px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    padding: 7px 8px;
    selection-background-color: __SELECTION__;
    selection-color: __ACCENT_TEXT__;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QDateEdit:hover, QTimeEdit:hover, QDateTimeEdit:hover, QPlainTextEdit:hover,
QTextEdit:hover {
    border-bottom-color: __HAIRLINE_STRONG__;
    color: __ACCENT_TEXT__;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus,
QComboBox:focus, QComboBox:on {
    border-bottom: 2px solid __ACCENT__;
    padding-bottom: 6px;
}
QPlainTextEdit, QTextEdit {
    background: __WELL_DEEP__; border: none; padding: 8px 10px;
    border-radius: __RADIUS__px;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QDateEdit:disabled, QTimeEdit:disabled, QDateTimeEdit:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {
    color: __TEXT_DISABLED__; background: __DISABLED_FILL__;
}
QLineEdit[state="error"], QComboBox[state="error"], QSpinBox[state="error"] {
    border-bottom: 2px solid __DANGER__; background: __DANGER_WASH__;
}
QLineEdit[state="ok"] { border-bottom: 2px solid __ACCENT__; }
QLineEdit[state="warn"] { border-bottom: 2px solid __WARN__; background: __WARN_WASH__; }
QLineEdit[readOnly="true"] { color: __TEXT_MUTED__; background: __READONLY_FILL__; }
QLineEdit::placeholder { color: __TEXT_DISABLED__; }

QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: center right;
    border: none; width: 26px;
}
QComboBox::drop-down:hover { background: __PANEL__; border-top-right-radius: __RADIUS__px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid __ACCENT_HOVER__;
    width: 0; height: 0; margin-right: 9px;
}
QComboBox::down-arrow:disabled { border-top-color: __TEXT_DISABLED__; }
QComboBox QAbstractItemView {
    background: __POPUP__; border: none; border-radius: __RADIUS__px;
    selection-background-color: __SELECTION__; selection-color: __ACCENT_TEXT__;
    outline: none; padding: 5px;
}
QComboBox QAbstractItemView::item { padding: 6px 8px; border-radius: __RADIUS_SM__px; min-height: 20px; }
QComboBox QAbstractItemView::item:selected { background: __SELECTION__; color: __ACCENT_TEXT__; }
QComboBox QAbstractItemView::item:hover { background: __PANEL_HOVER__; }

/* ---- toggles: compact flat wells, real glyphs painted as images.
       Deliberately small (__INDICATOR__px): a checkbox is a marker, not a
       button, so it stays visually subordinate to the label next to it. ---- */
QCheckBox, QRadioButton {
    spacing: 7px; background: transparent;
    padding: 2px 0; color: __TEXT__;
}
QCheckBox:hover, QRadioButton:hover { color: __ACCENT_TEXT__; }
QCheckBox:disabled, QRadioButton:disabled { color: __TEXT_DISABLED__; }
QCheckBox::indicator, QRadioButton::indicator { width: __INDICATOR__px; height: __INDICATOR__px; }

QCheckBox::indicator {
    border: 1px solid __HAIRLINE_STRONG__;
    border-radius: __INDICATOR_RADIUS__px;
    background: __WELL__;
}
QCheckBox::indicator:hover { border: 1px solid __ACCENT__; background: __ACCENT_WASH__; }
QCheckBox::indicator:checked {
    image: url("__CHECK_IMG__");
    border: 1px solid __ACCENT__;
    background: __ACCENT__;
}
QCheckBox::indicator:checked:hover { background: __ACCENT_HOVER__; }
QCheckBox::indicator:indeterminate {
    image: url("__DASH_IMG__");
    border: none;
    background: transparent;
}
QCheckBox::indicator:indeterminate:hover { image: url("__DASH_HOVER_IMG__"); }
QCheckBox::indicator:disabled {
    border: 1px solid __HAIRLINE__;
    background: __DISABLED_FILL__;
}

QRadioButton::indicator {
    border: 1px solid __HAIRLINE_STRONG__;
    border-radius: __HALF_INDICATOR__px;
    background: __WELL__;
}
QRadioButton::indicator:hover { border: 1px solid __ACCENT__; background: __ACCENT_WASH__; }
QRadioButton::indicator:checked {
    image: url("__DOT_IMG__");
    border: 1px solid __ACCENT__;
    background: __ACCENT_WASH__;
}
QRadioButton::indicator:checked:hover { border: 1px solid __ACCENT_HOVER__; }
QRadioButton::indicator:disabled {
    border: 1px solid __HAIRLINE__;
    background: __DISABLED_FILL__;
}

/* ---- sliders: flat track, accent handle ---- */
QSlider { background: transparent; min-height: 22px; }
QSlider::groove:horizontal {
    height: 3px; background: __TRACK__; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: __ACCENT__; border-radius: 2px; }
QSlider::add-page:horizontal { background: __TRACK__; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 13px; height: 13px; margin: -5px 0; border-radius: 7px;
    background: __ACCENT__; border: none;
}
QSlider::handle:horizontal:hover { background: __ACCENT_HOVER__; }
QSlider::handle:horizontal:pressed { background: __ACCENT_MUTED__; }
QSlider::handle:horizontal:disabled { background: __DISABLED_FILL_STRONG__; }
QSlider::groove:vertical {
    width: 3px; background: __TRACK__; border-radius: 2px;
}
QSlider::add-page:vertical { background: __TRACK__; border-radius: 2px; }
QSlider::sub-page:vertical { background: __ACCENT__; border-radius: 2px; }
QSlider::handle:vertical {
    width: 13px; height: 13px; margin: 0 -5px; border-radius: 7px;
    background: __ACCENT__; border: none;
}
QSlider::handle:vertical:hover { background: __ACCENT_HOVER__; }
QSlider::handle:vertical:pressed { background: __ACCENT_MUTED__; }
QSlider::handle:vertical:disabled { background: __DISABLED_FILL_STRONG__; }
QSlider:focus { outline: none; }

QProgressBar {
    background: __TRACK__;
    border: none;
    border-radius: 3px; text-align: center;
    color: __ACCENT_TEXT__; height: 22px;
    font-size: __CAPTION__pt; font-weight: 600;
}
/* The filled portion is translucent glass, not an opaque slab: the ambient
   gradient of the shell stays visible through the bar, so it reads as a
   measurement over the surface rather than a sticker on top of it.
   The alpha ramp left-to-right keeps the leading edge slightly brighter so a
   filling bar reads as motion even when it is standing still.
   Note: extra state selectors on ::chunk (:hover, :indeterminate) break the
   fill-width calculation in QStyleSheetStyle - the chunk is then painted
   across the whole widget at every value. Only the base ::chunk rule and the
   :disabled background may be declared here; hover feedback lives on the bar
   itself. */
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 __ACCENT_GLASS__,
        stop:1 __ACCENT_GLASS_BRIGHT__);
    border: none; border-radius: 3px;
}
QProgressBar:hover { background: __TRACK_HOVER__; }
QProgressBar:focus { background: __TRACK_HOVER__; }
QProgressBar:disabled { color: __TEXT_DISABLED__; background: __DISABLED_FILL__; }
QProgressBar:disabled::chunk { background: __DISABLED_FILL_STRONG__; }

/* ---- scrollbars: slim translucent rails, accent handle on hover ---- */
QScrollBar:vertical {
    background: __RAIL__; width: 10px; margin: 0; border: none;
}
QScrollBar::handle:vertical {
    background: __SCROLL_HANDLE__; min-height: 30px;
    border-radius: 3px; margin: 2px;
}
QScrollBar::handle:vertical:hover { background: __ACCENT__; }
QScrollBar::handle:vertical:pressed { background: __ACCENT_HOVER__; }
QScrollBar:horizontal {
    background: __RAIL__; height: 10px; margin: 0; border: none;
}
QScrollBar::handle:horizontal {
    background: __SCROLL_HANDLE__; min-width: 30px;
    border-radius: 3px; margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: __ACCENT__; }
QScrollBar::handle:horizontal:pressed { background: __ACCENT_HOVER__; }
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0; width: 0; border: none; background: transparent; image: none;
}
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:disabled { background: transparent; }
QScrollBar::handle:disabled { background: __HAIRLINE__; }

/* ---- spin boxes: bare chevrons, no button chrome ---- */
QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit { padding-right: 22px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button,
QDateEdit::up-button, QDateEdit::down-button,
QTimeEdit::up-button, QTimeEdit::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {
    subcontrol-origin: border; width: 20px; border: none;
    background: transparent; border-radius: 0;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QDateEdit::up-button, QTimeEdit::up-button, QDateTimeEdit::up-button {
    subcontrol-position: top right;
}
QSpinBox::down-button, QDoubleSpinBox::down-button,
QDateEdit::down-button, QTimeEdit::down-button, QDateTimeEdit::down-button {
    subcontrol-position: bottom right;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover,
QDateEdit::up-button:hover, QDateEdit::down-button:hover,
QTimeEdit::up-button:hover, QTimeEdit::down-button:hover,
QDateTimeEdit::up-button:hover, QDateTimeEdit::down-button:hover {
    background: __PANEL_HOVER__;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed,
QDateEdit::up-button:pressed, QDateEdit::down-button:pressed,
QTimeEdit::up-button:pressed, QTimeEdit::down-button:pressed,
QDateTimeEdit::up-button:pressed, QDateTimeEdit::down-button:pressed {
    background: __PANEL_ACTIVE__;
}
QSpinBox::up-button:disabled, QSpinBox::down-button:disabled,
QDoubleSpinBox::up-button:disabled, QDoubleSpinBox::down-button:disabled,
QDateEdit::up-button:disabled, QDateEdit::down-button:disabled,
QTimeEdit::up-button:disabled, QTimeEdit::down-button:disabled,
QDateTimeEdit::up-button:disabled, QDateTimeEdit::down-button:disabled {
    background: transparent;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QDateEdit::up-arrow, QTimeEdit::up-arrow, QDateTimeEdit::up-arrow {
    image: none; width: 0; height: 0; margin-bottom: 3px;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid __ACCENT_HOVER__;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow,
QDateEdit::down-arrow, QTimeEdit::down-arrow, QDateTimeEdit::down-arrow {
    image: none; width: 0; height: 0; margin-top: 3px;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid __ACCENT_HOVER__;
}
QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled,
QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QDateEdit::up-arrow:disabled, QDateEdit::down-arrow:disabled,
QTimeEdit::up-arrow:disabled, QTimeEdit::down-arrow:disabled {
    border-bottom-color: __TEXT_DISABLED__; border-top-color: __TEXT_DISABLED__;
}

/* ---- LCD readouts: flat well, accent digits ---- */
QLCDNumber {
    background: __WELL_DEEP__; border: none; border-radius: __RADIUS__px;
    color: __ACCENT_HOVER__;
}

/* ---- dials get a plain transparent plate so the groove below shows ---- */
QDial { background: transparent; }
"""


# OCR Studio additions.  They only use existing tokens, so the dark/light
# variants, custom accents and radius changes keep working automatically.
APP_QSS = """
/* ---- cards: the main layout unit; a translucent plate over the gradient ---- */
QFrame[role="card"] {
    background: __PANEL__;
    border: 1px solid __HAIRLINE__;
    border-radius: __RADIUS__px;
}
QFrame[role="card"][tone="well"] {
    background: __WELL__;
}
QFrame[role="sidePanel"] {
    background: __TOOLBAR_FILL__;
    border: none;
    border-left: 1px solid __HAIRLINE__;
}
QFrame[role="leftPanel"] {
    background: __TOOLBAR_FILL__;
    border: none;
    border-right: 1px solid __HAIRLINE__;
}
QFrame[role="separator"] {
    background: __HAIRLINE__;
    border: none;
    max-height: 1px;
    min-height: 1px;
}
QLabel[role="cardTitle"] {
    color: __ACCENT_HOVER__;
    font-size: __TITLE__pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}
QLabel[role="cardHint"] {
    color: __TEXT_MUTED__;
    font-size: __CAPTION__pt;
}
QLabel[role="metric"] {
    color: __MONO_TEXT__;
    font-family: __MONO__;
    font-size: __MONO_SIZE__pt;
}
QLabel[role="brand"] {
    color: __ACCENT_TEXT__;
    font-size: __TITLE__pt;
    font-weight: 700;
    letter-spacing: 2.4px;
}
QLabel[role="brandMark"] {
    background: __ACCENT__;
    color: __MARK__;
    border-radius: __RADIUS_SM__px;
    padding: 4px 7px;
    font-weight: 800;
    font-size: __TITLE__pt;
}
QLabel[role="version"] {
    color: __TEXT_MUTED__;
    background: __PANEL__;
    border-radius: __BADGE_RADIUS__px;
    padding: 1px 8px;
    font-size: __CAPTION__pt;
    font-weight: 600;
}

/* ---- image wells and output surfaces ---- */
QLabel#previewLabel {
    background: __WELL_DEEP__;
    border: 1px dashed __HAIRLINE_STRONG__;
    border-radius: __RADIUS__px;
    color: __TEXT_MUTED__;
    padding: 12px;
}
QLabel#previewLabel[hasImage="true"] {
    border: 1px solid __HAIRLINE__;
}
QTextEdit#outputText {
    background: __WELL_DEEP__;
    border: none;
    border-radius: __RADIUS__px;
    padding: 10px 12px;
    color: __TEXT__;
    font-family: __MONO__;
    font-size: __MONO_SIZE__pt;
}
QTextBrowser#helpBrowser {
    background: transparent;
    border: none;
    padding: 0;
}
QPlainTextEdit#activityView {
    background: __WELL_DEEP__;
    border: none;
    border-radius: __RADIUS__px;
    padding: 8px 10px;
    color: __TEXT_SOFT__;
}

/* ---- status banner: a quiet strip that never shifts the layout ---- */
QFrame#statusBanner {
    background: __PANEL__;
    border: none;
    border-left: 3px solid __ACCENT__;
    border-radius: __RADIUS__px;
}
QFrame#statusBanner[tone="ok"]     { border-left-color: __SUCCESS_TEXT__; background: __SUCCESS_WASH__; }
QFrame#statusBanner[tone="warn"]   { border-left-color: __WARN__;         background: __WARN_WASH__; }
QFrame#statusBanner[tone="danger"] { border-left-color: __DANGER__;       background: __DANGER_WASH__; }
QFrame#statusBanner QLabel { color: __TEXT__; }

/* ---- navigation rail ---- */
QListWidget#navList {
    background: transparent;
    border: none;
    outline: none;
    padding: 2px;
}
QListWidget#navList::item {
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: __RADIUS_SM__px;
    color: __TEXT_MUTED__;
    padding: 10px 12px;
    margin: 1px 0;
    font-weight: 600;
}
QListWidget#navList::item:hover {
    background: __PANEL_HOVER__;
    color: __TEXT__;
}
QListWidget#navList::item:selected {
    background: __PANEL_ACTIVE__;
    border-left: 2px solid __ACCENT__;
    color: __ACCENT_HOVER__;
}

/* ---- setting validation replaces the original custom state names ---- */
QLineEdit[state="ok"], QComboBox[state="ok"], QSpinBox[state="ok"] {
    border-bottom: 2px solid __ACCENT__;
}
QLineEdit[state="warn"], QComboBox[state="warn"], QSpinBox[state="warn"] {
    border-bottom: 2px solid __WARN__;
    background: __WARN_WASH__;
}
QLineEdit[state="error"], QComboBox[state="error"], QSpinBox[state="error"] {
    border-bottom: 2px solid __DANGER__;
    background: __DANGER_WASH__;
}

/* ---- toolbar labels and compact buttons ---- */
QToolBar QLabel { background: transparent; }
QToolBar QLabel[role="brand"] { padding: 0 2px; }
QToolButton#primaryAction {
    background: __ACCENT__;
    color: __MARK__;
    border-radius: __RADIUS__px;
    padding: 7px 16px;
    font-weight: 700;
}
QToolButton#primaryAction:hover { background: __ACCENT_HOVER__; }
QToolButton#primaryAction:pressed { background: __ACCENT_MUTED__; }
QToolButton#primaryAction:disabled { background: __DISABLED_FILL__; color: __TEXT_DISABLED__; }
QFrame#toolbarBrand {
    background: transparent;
    border: none;
    padding: 0 6px;
}
"""


# --------------------------------------------------------------------------- glyphs
# QSS alone cannot draw a checkmark, so checked indicators are painted into PNGs
# once per process and referenced by URL in the sheet. This keeps the widgets
# flat (no native style chrome) while still showing a real mark.

_IMAGE_DIR: Path | None = None
_IMAGE_CACHE: dict[tuple[str, str], str] = {}
# Indicator metrics: a checkbox is a small marker, so the box is deliberately
# compact and its corner radius scales with it instead of the global radius.
INDICATOR_PX = 13
INDICATOR_RADIUS = 3
INDICATOR_HALF = 7


def _image_dir() -> Path:
    global _IMAGE_DIR
    if _IMAGE_DIR is None:
        _IMAGE_DIR = Path(tempfile.mkdtemp(prefix="tesseract_studio_glyphs_"))
        atexit.register(lambda: _cleanup(_IMAGE_DIR))
    return _IMAGE_DIR


def _cleanup(directory: Path | None) -> None:
    if directory is None:
        return
    for entry in directory.glob("*.png"):
        try:
            entry.unlink()
        except OSError:
            pass
    try:
        directory.rmdir()
    except OSError:
        pass


def _canvas(size: int) -> tuple["QImage", QPainter]:
    image = QImage(QSize(size, size), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    return image, painter


def _checkmark(color: str, size: int = INDICATOR_PX) -> "QImage":
    image, painter = _canvas(size)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.6, size * 0.13))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    path = QPainterPath(QPointF(size * 0.24, size * 0.52))
    path.lineTo(QPointF(size * 0.43, size * 0.71))
    path.lineTo(QPointF(size * 0.78, size * 0.30))
    painter.drawPath(path)
    painter.end()
    return image


def _dash(color: str, size: int = INDICATOR_PX, plate: int = 46) -> "QImage":
    """Indeterminate mark: a dash on its own translucent plate.

    Qt forces an opaque light plate behind ``:indeterminate`` indicators when a
    ``background`` is combined with ``image``, which made the dash vanish against
    it. The plate is therefore baked into the glyph and the sheet sets neither
    border nor background for that state.
    """
    image, painter = _canvas(size)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, plate))
    painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), size * 0.2, size * 0.2)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(
        QRectF(size * 0.26, size * 0.42, size * 0.48, max(2.0, size * 0.17)),
        size * 0.08,
        size * 0.08,
    )
    painter.end()
    return image


def _radio_dot(color: str, size: int = INDICATOR_PX) -> "QImage":
    image, painter = _canvas(size)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    inset = size * 0.28
    painter.drawEllipse(QRectF(inset, inset, size - 2 * inset, size - 2 * inset))
    painter.end()
    return image


def _save(name: str, image: "QImage") -> str:
    directory = _image_dir()
    target = directory / f"{name}.png"
    image.save(str(target), "PNG")
    return target.as_posix()


def indicator_paths(accent: str, mark: str = "#04161c") -> dict[str, str]:
    """Absolute PNG paths for check / dash / radio-dot glyphs (cached)."""
    key = (accent, mark)
    cached = _IMAGE_CACHE.get(key)
    if cached is not None:
        return json.loads(cached)
    paths = {
        "check": _save(f"check_{accent.strip('#')}_{mark.strip('#')}", _checkmark(mark)),
        "dash": _save(f"dash_{accent.strip('#')}_{mark.strip('#')}", _dash(mark)),
        "dash_hover": _save(
            f"dashh_{accent.strip('#')}_{mark.strip('#')}",
            _dash(_lighten(accent, 1.2), plate=86),
        ),
        "dot": _save(f"dot_{accent.strip('#')}_{mark.strip('#')}", _radio_dot(mark)),
    }
    _IMAGE_CACHE[key] = json.dumps(paths)
    return paths


DEFAULT_TOKENS = {
    "accent": "#37b6d6",
    "accent_hover": "#58d5ec",
    "surface": BG_SHELL_1,
    "surface_alt": BG_SHELL_2,
    "border": "rgba(255, 255, 255, 0.07)",
    "text": "#e2e7ec",
    "text_muted": "rgba(190, 201, 212, 0.62)",
    "danger": "#c0504a",
    "success": "#37b6d6",
    "radius": 4,
    "font_family": "Segoe UI Variable Display",
    "font_size": FONT_SIZE_BODY,
    "mono_family": "Cascadia Mono",
}


def _darken(color: str, factor: float = 0.85) -> str:
    """Multiply an #rrggbb colour towards black; non-hex input passes through."""
    text = color.strip()
    if not text.startswith("#") or len(text) not in (7, 9):
        return color
    try:
        rgb = [int(text[i : i + 2], 16) for i in (1, 3, 5)]
    except ValueError:
        return color
    scaled = [max(0, min(255, round(channel * factor))) for channel in rgb]
    return "#" + "".join(f"{channel:02x}" for channel in scaled)


def _blend(base: str, over: str, alpha: float) -> str:
    """Composite ``over`` onto ``base`` at ``alpha`` and return #rrggbb.

    Used to derive translucent accent washes from an arbitrary accent colour,
    so a custom accent keeps the same visual weight as the default one.
    """
    try:
        base_rgb = [int(base.strip().lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
        over_rgb = [int(over.strip().lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    except (ValueError, IndexError):
        return over
    mixed = [
        max(0, min(255, round(b + (o - b) * alpha)))
        for b, o in zip(base_rgb, over_rgb)
    ]
    return "#" + "".join(f"{c:02x}" for c in mixed)


def _rgba(color: str, alpha: float) -> str:
    """Turn ``#rrggbb`` into an ``rgba(...)`` string with the given alpha."""
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return color
    try:
        r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return color
    return f"rgba({r}, {g}, {b}, {alpha:g})"


def _lighten(color: str, factor: float = 1.2) -> str:
    """Scale an ``#rrggbb`` colour towards white; non-hex input passes through."""
    text = color.strip()
    if not text.startswith("#") or len(text) != 7:
        return color
    try:
        rgb = [int(text[i : i + 2], 16) for i in (1, 3, 5)]
    except ValueError:
        return color
    scaled = [max(0, min(255, round(channel * factor))) for channel in rgb]
    return "#" + "".join(f"{channel:02x}" for channel in scaled)


def _substitutions(tokens: dict) -> dict[str, str]:
    """Map every __NAME__ placeholder to its value for the current tokens.

    Surface tokens fall back to the module globals, but any value supplied in
    ``tokens`` under the matching upper-case name wins. That is what lets the
    light variant reuse the exact same sheet with re-derived translucencies.
    """
    def surface(name: str, default: str) -> str:
        return str(tokens.get(name.lower(), tokens.get(name, default)))

    accent = str(tokens["accent"])
    hover = str(tokens["accent_hover"])
    family = str(tokens.get("font_family", "Segoe UI Variable Display"))
    mono = str(tokens.get("mono_family", "Cascadia Mono"))
    body = int(tokens.get("font_size", FONT_SIZE_BODY))
    text = str(tokens.get("text", TEXT))
    muted = str(tokens.get("text_muted", TEXT_MUTED))
    mark = str(tokens.get("mark", "#04161c"))
    radius = int(tokens.get("radius", 4))
    radius_sm = max(0, radius - 1)
    badge_radius = max(2, radius + 5)
    return {
        "__FONT__": f'"{family}", {FONT_STACK.split(",", 1)[1].strip()}',
        "__MONO__": f'"{mono}", {MONO_STACK.split(",", 1)[1].strip()}',
        "__BODY__": str(body),
        "__TITLE__": str(body + 1),
        "__CAPTION__": str(FONT_SIZE_CAPTION) if body == FONT_SIZE_BODY else str(body - 1),
        "__MONO_SIZE__": str(FONT_SIZE_MONO) if body == FONT_SIZE_BODY else str(body),
        "__ACCENT__": accent,
        "__ACCENT_HOVER__": hover,
        "__ACCENT_MUTED__": _darken(accent, 0.82),
        "__ACCENT_TEXT__": surface("ACCENT_TEXT", ACCENT_TEXT),
        "__ACCENT_WASH__": _rgba(accent, 0.14),
        "__ACCENT_WASH_SOLID__": _rgba(accent, 0.24),
        # A translucent alpha ramp keeps the bar glassy; the light variant uses
        # the same idea with its own alphas so the fill stays visible on white.
        "__ACCENT_GLASS__": _rgba(accent, float(tokens.get("ACCENT_GLASS_ALPHA", 0.44))),
        "__ACCENT_GLASS_BRIGHT__": _rgba(
            _lighten(accent, 1.15), float(tokens.get("ACCENT_GLASS_ALPHA_BRIGHT", 0.58))
        ),
        "__SELECTION__": _rgba(accent, 0.32),
        "__MARK__": mark,
        "__MONO_TEXT__": surface("MONO_TEXT", MONO_TEXT),
        "__CHECK_IMG__": indicator_paths(accent, mark)["check"],
        "__DASH_IMG__": indicator_paths(accent, mark)["dash"],
        "__DASH_HOVER_IMG__": indicator_paths(accent, mark)["dash_hover"],
        "__DOT_IMG__": indicator_paths(accent, mark)["dot"],
        "__PANEL__": surface("PANEL", PANEL),
        "__PANEL_HOVER__": surface("PANEL_HOVER", PANEL_HOVER),
        "__PANEL_ACTIVE__": surface("PANEL_ACTIVE", PANEL_ACTIVE),
        "__WELL__": surface("WELL", WELL),
        "__WELL_DEEP__": surface("WELL_DEEP", WELL_DEEP),
        "__HAIRLINE__": surface("HAIRLINE", HAIRLINE),
        "__HAIRLINE_STRONG__": surface("HAIRLINE_STRONG", HAIRLINE_STRONG),
        "__SHELL_TOP__": surface("SHELL_TOP", SHELL_TOP),
        "__SHELL_MID__": surface("SHELL_MID", SHELL_MID),
        "__SHELL_LOW__": surface("SHELL_LOW", SHELL_LOW),
        "__SHELL_BOTTOM__": surface("SHELL_BOTTOM", SHELL_BOTTOM),
        "__TOOLBAR_FILL__": surface("TOOLBAR_FILL", TOOLBAR_FILL),
        "__HEADER_FILL__": surface("HEADER_FILL", HEADER_FILL),
        "__ROW_ALT__": surface("ROW_ALT", ROW_ALT),
        "__POPUP__": surface("POPUP", POPUP),
        "__TRACK__": surface("TRACK", TRACK),
        "__TRACK_HOVER__": surface("TRACK_HOVER", TRACK_HOVER),
        "__RAIL__": surface("RAIL", RAIL),
        "__SCROLL_HANDLE__": surface("SCROLL_HANDLE", SCROLL_HANDLE),
        "__PRESSED_FILL__": surface("PRESSED_FILL", PRESSED_FILL),
        "__DISABLED_FILL__": surface("DISABLED_FILL", DISABLED_FILL),
        "__DISABLED_FILL_STRONG__": surface("DISABLED_FILL_STRONG", DISABLED_FILL_STRONG),
        "__READONLY_FILL__": surface("READONLY_FILL", READONLY_FILL),
        "__INDICATOR__": str(int(tokens.get("indicator_size", INDICATOR_PX))),
        "__INDICATOR_RADIUS__": str(INDICATOR_RADIUS),
        "__HALF_INDICATOR__": str(INDICATOR_HALF),
        "__RADIUS__": str(radius),
        "__RADIUS_SM__": str(radius_sm),
        "__BADGE_RADIUS__": str(badge_radius),
        "__GROUP_PAD__": str(max(10, radius * 3)),
        "__DANGER__": DANGER,
        "__DANGER_WASH__": DANGER_WASH,
        "__DANGER_WASH_STRONG__": DANGER_WASH_STRONG,
        "__DANGER_TEXT__": surface("DANGER_TEXT", DANGER_TEXT),
        "__WARN__": WARN,
        "__WARN_WASH__": WARN_WASH,
        "__WARN_TEXT__": surface("WARN_TEXT", WARN_TEXT),
        "__SUCCESS_WASH__": SUCCESS_WASH,
        "__SUCCESS_TEXT__": surface("SUCCESS_TEXT", SUCCESS_TEXT),
        "__TEXT__": text,
        "__TEXT_MUTED__": muted,
        "__TEXT_SOFT__": surface("TEXT_SOFT", TEXT_SOFT),
        "__TEXT_DISABLED__": surface("TEXT_DISABLED", TEXT_DISABLED),
    }


def render_qss(tokens: dict | None = None) -> str:
    """Render the full sheet, resolving every __TOKEN__ placeholder."""
    sheet = BASE_QSS + CONTROL_QSS + APP_QSS
    for key, value in _substitutions(dict(DEFAULT_TOKENS, **(tokens or {}))).items():
        sheet = sheet.replace(key, value)
    return sheet


def full_stylesheet(variant: str = "dark") -> str:
    """Render the default sheet for the requested palette variant."""
    if variant == "light":
        return light_stylesheet()
    return render_qss()


def light_tokens(overrides: dict | None = None) -> dict:
    """Token set for the light palette, merged with the dark defaults."""
    tokens = dict(DEFAULT_TOKENS)
    tokens.update(LIGHT_TOKENS)
    tokens.update(overrides or {})
    return tokens


def light_stylesheet(overrides: dict | None = None) -> str:
    """Render the light sheet.

    The light variant reuses the dark sheet verbatim but re-derives every
    surface token, so the two palettes can never drift apart: a change to the
    layout or a new selector applies to both automatically.
    """
    tokens = light_tokens(overrides)
    for name, value in LIGHT_OVERRIDES.items():
        tokens.setdefault(name, value)
    return render_qss(tokens)


def tokens_to_qss(tokens: dict) -> str:
    """Regenerate the sheet from a token dict (accent, font, radius)."""
    return render_qss(tokens)


def popup_stylesheet(variant: str = "dark", radius: int | None = None) -> str:
    """Style the QComboBox popup container window.

    Qt paints the popup frame around the item view with the platform window
    colour, so the transparent margins around a rounded, dark item view show up
    as white bands. Styling the internal container closes that gap.
    """
    corner = DEFAULT_TOKENS["radius"] if radius is None else int(radius)
    if variant == "light":
        background = LIGHT_OVERRIDES["POPUP"]
        border = LIGHT_OVERRIDES["HAIRLINE_STRONG"]
    else:
        background = POPUP
        border = HAIRLINE_STRONG
    return (
        "QComboBoxPrivateContainer {"
        f" background: {background};"
        f" border: 1px solid {border};"
        f" border-radius: {corner}px;"
        " }"
    )


def save_theme(path: str | Path, extra: str = "", variant: str = "dark") -> Path:
    target = Path(path)
    target.write_text(full_stylesheet(variant) + extra, encoding="utf-8")
    return target


def load_theme(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def export_tokens(path: str | Path, tokens: dict) -> Path:
    target = Path(path)
    target.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    return target


def resolve_font(tokens: dict | None = None) -> tuple[str, int]:
    """Return the (family, point size) a QApplication font should use."""
    merged = dict(DEFAULT_TOKENS, **(tokens or {}))
    return str(merged["font_family"]), int(merged["font_size"])
