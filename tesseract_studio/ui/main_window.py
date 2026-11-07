"""Main window: ported Qt UI Lab shell around the OCR workflow."""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from ..config import (
    APP_NAME,
    APP_VERSION,
    CONFIG_DIR,
    ORG_NAME,
    OCR_PRESETS,
    PSM_DESCRIPTIONS,
    AppConfig,
    ensure_default_profile,
    find_tessdata_dir,
    find_tesseract_executable,
    list_profiles,
    load_config_file,
    save_config_file,
    safe_profile_name,
)
from ..imaging import (
    grab_region_image,
    image_size_text,
    load_image_from_file,
    qimage_to_numpy,
)
from ..i18n import (
    available_languages,
    get_language,
    language_from_env,
    set_language,
    tr,
)
from ..ocr import preprocess_image
from ..singleton import release_single_instance
from ..worker import OCRWorker
from . import theme
from .activity import ActivityConsole
from .appearance import AppearanceDialog
from .help import HelpPanel
from .help_texts import register_help_targets
from .help_texts_en import register_help_targets as register_help_targets_en
from .icons import app_icon, make_icon
from .pages.capture_page import CapturePage
from .pages.ocr_page import OcrPage
from .pages.preprocess_page import PreprocessPage
from .pages.preview_panel import PreviewPanel
from .pages.profiles_page import ProfilesPage
from .region_overlay import RegionSelectionOverlay
from .widgets import HintLabel, NavTabBar, repolish


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        variant: Optional[str] = None,
        apply_theme: bool = True,
        language: Optional[str] = None,
    ) -> None:
        super().__init__()
        ensure_default_profile()
        self.setObjectName("MainWindow")
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setWindowIcon(app_icon())
        self.resize(1540, 960)
        self.setMinimumSize(1180, 760)

        settings_path = os.environ.get("TESSERACT_STUDIO_SETTINGS", "").strip()
        if settings_path:
            self._qsettings = QtCore.QSettings(settings_path, QtCore.QSettings.IniFormat)
        else:
            self._qsettings = QtCore.QSettings(ORG_NAME, APP_NAME)
        if language:
            self._qsettings.setValue("ui/language", language)
        self._language = set_language(
            language or language_from_env() or str(self._qsettings.value("ui/language", "ru"))
        )
        self._loading = False
        self._busy = False
        self._theme_applied = False
        self._welcome_shown = False
        self._ocr_started = 0.0

        self.raw_image: Optional[np.ndarray] = None
        self.processed_image: Optional[np.ndarray] = None
        self.overlay: Optional[RegionSelectionOverlay] = None
        self.ocr_thread: Optional[QtCore.QThread] = None
        self.ocr_worker: Optional[OCRWorker] = None
        self.current_config = AppConfig()

        self._variant = variant or str(self._qsettings.value("theme/variant", "dark"))
        if self._variant not in {"dark", "light"}:
            self._variant = "dark"
        self._accent = str(self._qsettings.value("theme/accent", theme.DEFAULT_TOKENS["accent"]))
        if not QtGui.QColor(self._accent).isValid():
            self._accent = theme.DEFAULT_TOKENS["accent"]
        self._radius = int(self._qsettings.value("theme/radius", theme.DEFAULT_TOKENS["radius"]))
        self._font_family = str(
            self._qsettings.value("theme/font_family", theme.DEFAULT_TOKENS["font_family"])
        )
        self._font_size = int(
            self._qsettings.value("theme/font_size", theme.DEFAULT_TOKENS["font_size"])
        )
        self._qss = ""
        self._icon_actions: dict[QtWidgets.QAction, str] = {}

        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(130)
        self._preview_timer.timeout.connect(self._update_processed_preview)

        self._build_ui()
        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_dock()
        self._connect_signals()
        self._register_help_targets()

        if apply_theme:
            self.apply_theme(announce=False)
        else:
            self._apply_font()
            native_dark = self.palette().color(QtGui.QPalette.Window).lightness() < 128
            self.help_panel.set_variant("dark" if native_dark else "light")
            self.activity.set_dark(native_dark)

        self.refresh_profiles()
        self.load_profile("default", silent=True)
        self.auto_detect_tesseract_resources(announce=False)
        self._restore_state()
        self._update_diagnostics()
        self._update_stats()
        self.help_panel.set_default_help()
        self._sync_theme_action()

    # ================================================================== build
    def _build_ui(self) -> None:
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setObjectName("workspaceSplitter")

        left = QtWidgets.QFrame()
        left.setProperty("role", "leftPanel")
        left.setMinimumWidth(430)
        left.setMaximumWidth(520)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(10, 12, 10, 10)
        left_layout.setSpacing(9)
        header = QtWidgets.QLabel(tr("ПАРАМЕТРЫ"))
        header.setProperty("role", "section")
        left_layout.addWidget(header)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(QtCore.Qt.ElideRight)
        self.tabs.setIconSize(QtCore.QSize(16, 16))
        self.tabs.setTabBar(NavTabBar(self.tabs))
        self.capture_page = CapturePage()
        self.ocr_page = OcrPage()
        self.preprocess_page = PreprocessPage()
        self.profiles_page = ProfilesPage()
        self._tab_icon_kinds = ("capture", "scan", "sliders", "profiles")
        for page, kind, title in (
            (self.capture_page, "capture", tr("Захват")),
            (self.ocr_page, "scan", "OCR"),
            (self.preprocess_page, "sliders", tr("Обработка")),
            (self.profiles_page, "profiles", tr("Профили")),
        ):
            self.tabs.addTab(page, make_icon(kind, "#7fb3c4"), title)
        left_layout.addWidget(self.tabs, 1)

        self.preview_panel = PreviewPanel()
        self.help_panel = HelpPanel()

        self.splitter.addWidget(left)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.addWidget(self.help_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([430, 750, 340])
        self.setCentralWidget(self.splitter)

    def _build_actions(self) -> None:
        def action(
            icon: str,
            text: str,
            slot,
            shortcut: str = "",
            checkable: bool = False,
            icon_text: str = "",
        ) -> QtWidgets.QAction:
            item = QtWidgets.QAction(make_icon(icon, "#bfd9e6"), text, self)
            self._icon_actions[item] = icon
            if icon_text:
                item.setIconText(icon_text)
            if shortcut:
                item.setShortcut(QtGui.QKeySequence(shortcut))
                item.setShortcutContext(QtCore.Qt.ApplicationShortcut)
                item.setToolTip(f"{text}  ({shortcut})")
            else:
                item.setToolTip(text)
            item.setCheckable(checkable)
            item.triggered.connect(slot)
            if checkable:
                self.addAction(item)
            else:
                self.addAction(item)
            return item

        self.act_select_region = action(
            "region", tr("Выбрать область"), self.select_region, "Ctrl+Shift+R", icon_text=tr("Область")
        )
        self.act_capture = action(
            "capture", tr("Захватить область"), self.capture_only, "F6", icon_text=tr("Захват")
        )
        self.act_open = action(
            "open", tr("Открыть изображение"), self.load_image_from_file_dialog, "Ctrl+O", icon_text=tr("Открыть")
        )
        self.act_paste = action(
            "paste", tr("Вставить из буфера"), self.load_image_from_clipboard, "Ctrl+Shift+V", icon_text=tr("Вставить")
        )
        self.act_ocr_current = action(
            "scan", tr("Распознать кадр"), self.run_ocr_on_current_image, "F5", icon_text=tr("OCR кадра")
        )
        self.act_ocr_region = action(
            "play", tr("Распознать область"), self.run_ocr, "Ctrl+Return", icon_text=tr("OCR области")
        )
        self.act_copy = action("copy", tr("Копировать текст"), self.copy_output, "Ctrl+Shift+C")
        self.act_save = action("save", tr("Сохранить текст"), self.save_output, "Ctrl+S")
        self.act_theme = action(
            "theme", tr("Сменить палитру"), self.toggle_variant, "Ctrl+T", icon_text=tr("Тема")
        )
        self.act_appearance = action(
            "settings", tr("Оформление…"), self.open_appearance, "Ctrl+,", icon_text=tr("Стиль")
        )
        self.act_activity = action(
            "log", tr("Журнал событий"), self._toggle_activity, "Ctrl+J", True, icon_text=tr("Журнал")
        )
        self.act_export_log = action("save", tr("Экспорт журнала"), self.export_log, "Ctrl+Shift+E")
        self.act_clear_log = action("clear", tr("Очистить журнал"), self.activity_clear, "Ctrl+L")
        self.act_shortcuts = action("info", tr("Горячие клавиши"), self.show_shortcuts, "Ctrl+/")
        self.act_about = action("info", tr("О программе"), self.show_about, "F1")

        self.act_close = QtWidgets.QAction(tr("Закрыть"), self)
        self.act_close.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape))
        self.act_close.setShortcutContext(QtCore.Qt.WindowShortcut)
        self.act_close.triggered.connect(self.close)
        self.addAction(self.act_close)

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu(tr("Файл"))
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_paste)
        file_menu.addSeparator()
        file_menu.addAction(self.act_copy)
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_export_log)
        file_menu.addSeparator()
        file_menu.addAction(self.act_close)

        ocr_menu = menu.addMenu("OCR")
        ocr_menu.addAction(self.act_select_region)
        ocr_menu.addAction(self.act_capture)
        ocr_menu.addSeparator()
        ocr_menu.addAction(self.act_ocr_current)
        ocr_menu.addAction(self.act_ocr_region)

        view_menu = menu.addMenu(tr("Вид"))
        view_menu.addAction(self.act_theme)
        view_menu.addAction(self.act_appearance)
        view_menu.addSeparator()
        view_menu.addAction(self.act_activity)
        view_menu.addAction(self.act_clear_log)

        help_menu = menu.addMenu(tr("Справка"))
        help_menu.addAction(self.act_shortcuts)
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        bar = QtWidgets.QToolBar(tr("Главная"))
        bar.setObjectName("mainToolBar")
        bar.setMovable(False)
        bar.setIconSize(QtCore.QSize(20, 20))
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toolbar = bar

        brand = QtWidgets.QFrame()
        brand.setObjectName("toolbarBrand")
        brand_layout = QtWidgets.QHBoxLayout(brand)
        brand_layout.setContentsMargins(4, 0, 8, 0)
        brand_layout.setSpacing(8)
        mark = QtWidgets.QLabel("T")
        mark.setProperty("role", "brandMark")
        mark.setAlignment(QtCore.Qt.AlignCenter)
        mark.setFixedWidth(28)
        name = QtWidgets.QLabel("TESSERACT STUDIO")
        name.setProperty("role", "brand")
        version = QtWidgets.QLabel(f"v{APP_VERSION}")
        version.setProperty("role", "version")
        brand_layout.addWidget(mark)
        brand_layout.addWidget(name)
        brand_layout.addWidget(version)
        bar.addWidget(brand)
        bar.addSeparator()

        bar.addAction(self.act_select_region)
        bar.addAction(self.act_capture)
        bar.addAction(self.act_open)
        bar.addAction(self.act_paste)
        bar.addSeparator()

        self.ocr_button = QtWidgets.QToolButton()
        self.ocr_button.setObjectName("primaryAction")
        self.ocr_button.setDefaultAction(self.act_ocr_current)
        self.ocr_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.ocr_button.setIcon(make_icon("play", "#04161c"))
        bar.addWidget(self.ocr_button)
        bar.addAction(self.act_ocr_region)
        bar.addSeparator()
        bar.addAction(self.act_theme)
        bar.addAction(self.act_appearance)
        bar.addAction(self.act_activity)
        bar.addSeparator()

        self.language_button = QtWidgets.QToolButton()
        self.language_button.setText(self._language.upper())
        self.language_button.setToolTip(tr("Язык интерфейса / UI language"))
        self.language_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.language_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.language_menu = QtWidgets.QMenu(self.language_button)
        self.language_group = QtWidgets.QActionGroup(self)
        for code, _label in available_languages():
            language_action = QtWidgets.QAction(code.upper(), self)
            language_action.setCheckable(True)
            language_action.setChecked(code == self._language)
            language_action.setData(code)
            language_action.triggered.connect(
                lambda _checked, lang=code: self._request_language(lang)
            )
            self.language_group.addAction(language_action)
            self.language_menu.addAction(language_action)
        self.language_button.setMenu(self.language_menu)
        bar.addWidget(self.language_button)
        self.addToolBar(QtCore.Qt.TopToolBarArea, bar)

    def _build_statusbar(self) -> None:
        status = QtWidgets.QStatusBar()
        self.setStatusBar(status)
        self.status_text = HintLabel(tr("Готов"))
        self.status_text.setWordWrap(False)
        self.region_status = HintLabel(tr("Область: -"))
        self.region_status.setWordWrap(False)
        self.region_status.setMinimumWidth(210)
        self.busy_bar = QtWidgets.QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(110)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setVisible(False)
        status.addWidget(self.status_text, 1)
        status.addPermanentWidget(self.region_status)
        status.addPermanentWidget(self.busy_bar)

    def _build_dock(self) -> None:
        self.activity = ActivityConsole()
        self.log_dock = QtWidgets.QDockWidget(tr("Журнал событий"), self)
        self.log_dock.setObjectName("activityDock")
        self.log_dock.setWidget(self.activity)
        self.log_dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.log_dock)
        self.resizeDocks([self.log_dock], [165], QtCore.Qt.Vertical)
        self.log_dock.visibilityChanged.connect(self._sync_activity_action)
        self.act_activity.setChecked(True)
        self.activity.export_requested.connect(self.export_log)

    # =============================================================== signals
    def _connect_signals(self) -> None:
        page = self.capture_page
        page.selectRegionRequested.connect(self.select_region)
        page.captureRequested.connect(self.capture_only)
        page.loadFileRequested.connect(self.load_image_from_file_dialog)
        page.pasteRequested.connect(self.load_image_from_clipboard)
        page.pickTesseractRequested.connect(self.pick_tesseract)
        page.pickTessdataRequested.connect(self.pick_tessdata)
        page.autoDetectRequested.connect(lambda: self.auto_detect_tesseract_resources(True))
        page.tesseract_edit.textChanged.connect(self._update_diagnostics)
        page.tessdata_edit.textChanged.connect(self._update_diagnostics)

        self.ocr_page.applyPresetRequested.connect(self.apply_preset)
        self.ocr_page.psm_combo.currentIndexChanged.connect(self._on_psm_changed)
        for widget in self.ocr_page.setting_widgets():
            self._wire_setting(widget)
        for widget in self.preprocess_page.setting_widgets():
            self._wire_setting(widget)

        profiles = self.profiles_page
        profiles.saveProfileRequested.connect(self.save_profile)
        profiles.loadProfileRequested.connect(self.load_profile_from_combo)
        profiles.refreshProfilesRequested.connect(self.refresh_profiles)
        profiles.openConfigDirRequested.connect(self.open_config_dir)
        profiles.appearanceRequested.connect(self.open_appearance)
        profiles.aboutRequested.connect(self.show_about)

        self.preview_panel.copyRequested.connect(self.copy_output)
        self.preview_panel.saveRequested.connect(self.save_output)
        self.preview_panel.clearRequested.connect(self.clear_output)
        self.preview_panel.fileDropped.connect(self._load_image_path)

    def _wire_setting(self, widget: QtWidgets.QWidget) -> None:
        if isinstance(widget, QtWidgets.QComboBox):
            widget.currentIndexChanged.connect(lambda _i: self._settings_changed())
            if widget.isEditable() and widget.lineEdit() is not None:
                widget.lineEdit().textChanged.connect(lambda _t: self._settings_changed())
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QSlider)):
            widget.valueChanged.connect(lambda _v: self._settings_changed())
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.toggled.connect(lambda _c: self._settings_changed())
        elif isinstance(widget, QtWidgets.QLineEdit):
            widget.textChanged.connect(lambda _t: self._settings_changed())

    def _on_psm_changed(self) -> None:
        self.ocr_page.update_psm_hint()
        try:
            value = int(self.ocr_page.psm_combo.currentText())
        except ValueError:
            value = 6
        self.help_panel.update_payload(
            self.ocr_page.psm_combo,
            description=tr(PSM_DESCRIPTIONS.get(value, "Описание недоступно.")),
            values=tr("0 - ориентация; 6 - блок; 7 - строка; 8 - слово; 10 - символ; 11 - разрозненный текст."),
        )
        self._settings_changed()

    def _settings_changed(self) -> None:
        if self._loading:
            return
        self._update_diagnostics()
        if self.raw_image is not None:
            self._preview_timer.start()

    # ================================================================== theme
    def _tokens(self) -> dict:
        tokens = dict(theme.DEFAULT_TOKENS)
        accent = QtGui.QColor(self._accent)
        if self._variant == "light" and accent.lightness() > 118:
            # The cyan that reads well on black is too pale on white; darken
            # the fill and use a darker hover so titles and toolbar labels stay
            # above AA contrast on the light shell.
            accent = accent.darker(136)
            hover = accent.darker(112)
        else:
            hover = accent.lighter(124)
        tokens["accent"] = accent.name()
        tokens["accent_hover"] = hover.name()
        tokens["radius"] = int(self._radius)
        tokens["font_family"] = self._font_family
        tokens["font_size"] = int(self._font_size)
        tokens["mono_family"] = "Cascadia Mono"
        if self._variant == "light":
            tokens["mark"] = theme.LIGHT_TOKENS["mark"]
            tokens["text"] = theme.LIGHT_TOKENS["text"]
            tokens["text_muted"] = theme.LIGHT_TOKENS["text_muted"]
        return tokens

    def _stylesheet(self) -> str:
        tokens = self._tokens()
        if self._variant == "light":
            return theme.light_stylesheet(tokens)
        return theme.tokens_to_qss(tokens)

    def apply_theme(self, announce: bool = True) -> None:
        self._qss = self._stylesheet()
        self.setStyleSheet(self._qss)
        self._apply_font()
        self.help_panel.set_variant(self._variant)
        self.activity.set_dark(self._variant != "light")
        self._apply_icon_palette()
        self._sync_theme_action()
        self._save_theme_settings()
        self._theme_applied = True
        if announce:
            self._show_status(
                tr(
                    "Тема: {variant}",
                    variant=tr("светлая") if self._variant == "light" else tr("тёмная"),
                ),
                "accent",
            )
            self._log(
                "info",
                tr("Оформление"),
                tr("Палитра: {variant}, акцент: {accent}", variant=self._variant, accent=self._accent),
            )

    def _apply_font(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        font = QtGui.QFont(self._font_family, int(self._font_size))
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        font.setHintingPreference(QtGui.QFont.PreferFullHinting)
        app.setFont(font)

    def _primary_icon_color(self) -> str:
        accent = QtGui.QColor(self._tokens()["accent"])
        return "#ffffff" if accent.lightness() < 128 else "#04161c"

    def _apply_icon_palette(self) -> None:
        action_color = "#3f6d7a" if self._variant == "light" else "#bfd9e6"
        for action, kind in self._icon_actions.items():
            action.setIcon(make_icon(kind, action_color))
        if hasattr(self, "ocr_button"):
            self.ocr_button.setIcon(make_icon("play", self._primary_icon_color()))
        page_color = "#3f6d7a" if self._variant == "light" else "#dff6fd"
        for button in self.findChildren(QtWidgets.QPushButton):
            kind = button.property("iconKind")
            if not kind:
                continue
            color = self._primary_icon_color() if button.objectName() == "accent" else page_color
            button.setIcon(make_icon(str(kind), color))
        tab_color = "#2f6b7a" if self._variant == "light" else "#7fb3c4"
        for index, kind in enumerate(getattr(self, "_tab_icon_kinds", ())):
            self.tabs.setTabIcon(index, make_icon(kind, tab_color))
        self._restyle_combo_popups()

    def _restyle_combo_popups(self) -> None:
        app = QtWidgets.QApplication.instance()
        theme_filter = getattr(app, "_popup_theme", None) if app is not None else None
        if theme_filter is not None:
            theme_filter.set_theme(self._variant, int(self._radius))

    def _sync_theme_action(self) -> None:
        if hasattr(self, "act_theme"):
            self.act_theme.setText(
                tr("Светлая палитра") if self._variant == "dark" else tr("Тёмная палитра")
            )

    def _save_theme_settings(self) -> None:
        self._qsettings.setValue("theme/variant", self._variant)
        self._qsettings.setValue("theme/accent", self._accent)
        self._qsettings.setValue("theme/radius", self._radius)
        self._qsettings.setValue("theme/font_family", self._font_family)
        self._qsettings.setValue("theme/font_size", self._font_size)

    def toggle_variant(self) -> None:
        self._variant = "light" if self._variant == "dark" else "dark"
        self.apply_theme()

    def apply_appearance(self, payload: dict) -> None:
        self._variant = payload.get("variant", self._variant)
        self._accent = payload.get("accent", self._accent)
        self._radius = int(payload.get("radius", self._radius))
        self._font_family = payload.get("font_family", self._font_family)
        self._font_size = int(payload.get("font_size", self._font_size))
        self.apply_theme(announce=False)
        self._show_status(tr("Оформление обновлено"), "accent")

    def _request_language(self, language: str) -> None:
        if not language or language == self._language:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            tr("Сменить язык интерфейса?"),
            tr("Для полного применения языка приложение будет перезапущено. Продолжить?"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            for action in self.language_group.actions():
                action.setChecked(action.data() == self._language)
            return
        self._qsettings.setValue("ui/language", language)
        self._qsettings.sync()
        if os.environ.get("TESSERACT_STUDIO_NO_RESTART"):
            self._language = set_language(language)
            return
        if self._restart_with_language(language):
            self._save_state()
            QtWidgets.QApplication.quit()
            return
        QtWidgets.QMessageBox.warning(
            self,
            tr("Не удалось перезапустить приложение"),
            tr("Язык сохранён. Закройте и откройте приложение вручную."),
        )
        for action in self.language_group.actions():
            action.setChecked(action.data() == self._language)

    def _restart_with_language(self, language: str) -> bool:
        if getattr(sys, "frozen", False):
            program = sys.executable
            raw_args = list(sys.argv[1:])
        else:
            program = sys.executable
            raw_args = [str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
        args: list[str] = []
        skip_next = False
        for argument in raw_args:
            if skip_next:
                skip_next = False
                continue
            if argument == "--lang":
                skip_next = True
                continue
            if argument.startswith("--lang="):
                continue
            args.append(argument)
        args.extend(["--lang", language])
        # The single instance lock has to be given up before the new process is
        # started, otherwise the replacement finds the lock taken by the
        # instance it is about to replace and refuses to start.
        release_single_instance()
        # The two-argument overload returns a plain bool, the three-argument one
        # returns a (bool, pid) tuple. Unpacking a bool raises TypeError and
        # used to crash the app right after the language was saved.
        try:
            started = QtCore.QProcess.startDetached(program, args, str(Path.cwd()))
        except TypeError:
            started = QtCore.QProcess.startDetached(program, args)
        if isinstance(started, tuple):
            started = started[0]
        return bool(started)

    def open_appearance(self) -> None:
        dialog = AppearanceDialog(
            variant=self._variant,
            accent=self._accent,
            radius=self._radius,
            font_family=self._font_family,
            font_size=self._font_size,
            apply_callback=self.apply_appearance,
            qss_provider=lambda: self._qss,
            parent=self,
        )
        dialog.exec_()

    # ================================================================== state
    def _restore_state(self) -> None:
        geometry = self._qsettings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self._qsettings.value("window/state")
        if state is not None:
            self.restoreState(state)
            self._sync_activity_action(not self.log_dock.isHidden())

    def _save_state(self) -> None:
        self._qsettings.setValue("window/geometry", self.saveGeometry())
        self._qsettings.setValue("window/state", self.saveState())
        self._qsettings.sync()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        if not self._welcome_shown:
            self._welcome_shown = True
            self.status_text.setText(
                tr("Готов. Выбери область, загрузи изображение или нажми F5 после захвата.")
            )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.ocr_thread is not None and self.ocr_thread.isRunning():
            self.ocr_thread.quit()
            self.ocr_thread.wait(2500)
        self._save_state()
        super().closeEvent(event)

    # ================================================================== status
    def _show_status(self, text: str, tone: str = "accent", timeout: int = 6000) -> None:
        self.status_text.setText(text)
        self.preview_panel.set_status(text, tone, timeout)

    def _log(self, level: str, source: str, message: str) -> None:
        self.activity.record(level, source, message)
        self.help_panel.set_stat("events", str(self.activity.count()))
        self._update_stats()

    def _update_stats(self) -> None:
        self.help_panel.set_stat("source", image_size_text(self.raw_image).replace(" px", ""))
        self.help_panel.set_stat("processed", image_size_text(self.processed_image).replace(" px", ""))
        self.help_panel.set_stat("events", str(self.activity.count()))

    # ============================================================== navigation
    def _toggle_activity(self, visible: bool) -> None:
        if hasattr(self, "log_dock"):
            self.log_dock.setVisible(bool(visible))
            if visible:
                self.log_dock.raise_()
        if visible:
            self.status_text.setText(tr("Журнал событий открыт"))

    def _sync_activity_action(self, visible: bool) -> None:
        if hasattr(self, "act_activity"):
            self.act_activity.blockSignals(True)
            self.act_activity.setChecked(bool(visible))
            self.act_activity.blockSignals(False)

    def activity_clear(self) -> None:
        self.activity.clear()
        self.help_panel.set_stat("events", "0")
        self._show_status(tr("Журнал очищен"), "accent")

    # ============================================================== capture
    def select_region(self) -> None:
        if self.overlay is not None:
            self.overlay.close()
        self._show_status(tr("Выделите область OCR на экране. Esc - отмена."), "accent")
        QtWidgets.QApplication.processEvents()
        self.hide()
        self.overlay = RegionSelectionOverlay()
        self.overlay.regionSelected.connect(self.on_region_selected)
        self.overlay.selectionCanceled.connect(self.on_region_selection_canceled)
        QtCore.QTimer.singleShot(0, self._show_overlay)

    def _show_overlay(self) -> None:
        if self.overlay is not None:
            self.overlay.show()
            self.overlay.raise_()
            self.overlay.activateWindow()

    def on_region_selected(self, region: dict) -> None:
        self.current_config.region = region
        self.capture_page.set_region(region)
        self._update_region_status()
        self.overlay = None
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._show_status(
            tr("Область сохранена. Теперь нажми «Захватить» или «Распознать область»."), "ok"
        )
        self._log(
            "info",
            tr("Область"),
            f"X={region['left']} Y={region['top']} W={region['width']} H={region['height']}",
        )
        self._update_diagnostics()

    def on_region_selection_canceled(self) -> None:
        self.overlay = None
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._show_status(tr("Выбор области отменён."), "warn")

    def _update_region_status(self) -> None:
        region = self.current_config.region
        if region:
            self.region_status.setText(
                tr(
                    "Область: {width}×{height} @ {left},{top}",
                    width=region["width"],
                    height=region["height"],
                    left=region["left"],
                    top=region["top"],
                )
            )
        else:
            self.region_status.setText(tr("Область: -"))

    def capture_only(self) -> None:
        if not self._ensure_region():
            return
        try:
            image = grab_region_image(self.current_config.region)
        except Exception as exc:  # noqa: BLE001
            self._show_status(tr("Не удалось захватить область: {error}", error=exc), "danger")
            self._log("error", tr("Захват"), str(exc))
            return
        self._set_source_image(image, tr("Область захвачена."))
        self._log(
            "info",
            tr("Захват"),
            tr("Кадр {width}×{height}", width=image.shape[1], height=image.shape[0]),
        )

    def _load_image_path(self, path: str) -> None:
        try:
            image = load_image_from_file(path)
        except Exception as exc:  # noqa: BLE001
            self._show_status(tr("Ошибка загрузки: {error}", error=exc), "danger")
            self._log("error", tr("Файл"), str(exc))
            QtWidgets.QMessageBox.critical(self, tr("Ошибка загрузки"), str(exc))
            return
        self._set_source_image(image, tr("Загружено: {name}", name=Path(path).name))
        self._log("success", tr("Файл"), str(path))

    def load_image_from_file_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            tr("Выберите изображение"),
            str(CONFIG_DIR.parent),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff);;All files (*.*)",
        )
        if path:
            self._load_image_path(path)

    def load_image_from_clipboard(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        mime = clipboard.mimeData()
        image = None
        if mime.hasImage():
            qimage = clipboard.image()
            if not qimage.isNull():
                image = qimage_to_numpy(qimage)
        elif mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if Path(path).suffix.lower() in {
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".bmp",
                        ".webp",
                        ".tif",
                        ".tiff",
                    }:
                        image = load_image_from_file(path)
                        break
        elif mime.hasText():
            text = mime.text().strip().strip('"')
            if text and Path(text).exists() and Path(text).suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".bmp",
                ".webp",
                ".tif",
                ".tiff",
            }:
                image = load_image_from_file(text)
        if image is None:
            QtWidgets.QMessageBox.information(
                self,
                tr("Буфер пуст"),
                tr("Скопируйте изображение или путь к файлу изображения, затем попробуйте снова."),
            )
            return
        self._set_source_image(image, tr("Изображение вставлено из буфера."))
        self._log("success", tr("Буфер"), tr("Изображение загружено"))

    def _set_source_image(self, image: np.ndarray, message: str) -> None:
        self.raw_image = image
        self.preview_panel.set_source(image)
        self._show_status(message, "ok")
        self._update_processed_preview()
        self._update_stats()
        self.help_panel.set_stat("ocr", "-")

    # ================================================================== preview
    def _update_processed_preview(self) -> None:
        if self.raw_image is None:
            self.preview_panel.set_processed(None)
            self.processed_image = None
            return
        try:
            processed = preprocess_image(
                self.raw_image.copy(), self._collect_runtime_settings()
            )
        except Exception as exc:  # noqa: BLE001
            self._show_status(tr("Ошибка предобработки: {error}", error=exc), "danger")
            return
        self.processed_image = processed
        self.preview_panel.set_processed(processed)
        self._update_stats()

    # ================================================================== OCR
    def run_ocr(self) -> None:
        if self._busy:
            return
        if not self._ensure_region() or not self._ensure_tesseract() or not self._ensure_language_files():
            return
        self._start_ocr(region=self.current_config.region)

    def run_ocr_on_current_image(self) -> None:
        if self._busy:
            return
        if self.raw_image is None:
            QtWidgets.QMessageBox.information(
                self,
                tr("Нет изображения"),
                tr("Сначала захватите область или загрузите изображение."),
            )
            return
        if not self._ensure_tesseract() or not self._ensure_language_files():
            return
        self._start_ocr(image=self.raw_image)

    def _start_ocr(self, region: Optional[dict] = None, image: Optional[np.ndarray] = None) -> None:
        self._set_busy(True)
        if image is not None:
            status = tr("OCR выполняется по кадру…")
            log_message = tr("Запуск по кадру")
        else:
            status = tr("OCR выполняется по области…")
            log_message = tr("Запуск по области")
        self._show_status(status, "accent", 0)
        self._log("info", "OCR", log_message)
        self._ocr_started = time.perf_counter()
        self.ocr_thread = QtCore.QThread(self)
        self.ocr_worker = OCRWorker(region, self._collect_runtime_settings(), image=image)
        self.ocr_worker.moveToThread(self.ocr_thread)
        self.ocr_thread.started.connect(self.ocr_worker.run)
        self.ocr_worker.finished.connect(self._finish_ocr)
        self.ocr_worker.error.connect(self._handle_error)
        self.ocr_worker.finished.connect(self.ocr_thread.quit)
        self.ocr_worker.error.connect(self.ocr_thread.quit)
        self.ocr_thread.finished.connect(self.ocr_worker.deleteLater)
        self.ocr_thread.finished.connect(self.ocr_thread.deleteLater)
        self.ocr_thread.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.busy_bar.setVisible(busy)
        self.act_ocr_current.setEnabled(not busy)
        self.act_ocr_region.setEnabled(not busy)
        if hasattr(self, "ocr_button"):
            self.ocr_button.setEnabled(not busy)

    def _finish_ocr(self, raw_image: np.ndarray, processed_image: np.ndarray, text: str) -> None:
        self._set_busy(False)
        self.raw_image = raw_image
        self.processed_image = processed_image
        self.preview_panel.set_source(raw_image)
        self.preview_panel.set_processed(processed_image)
        clean = text.strip() or tr("[OCR ничего не распознал]")
        self.preview_panel.set_text(clean)
        duration = time.perf_counter() - self._ocr_started
        self._show_status(tr("OCR завершён за {seconds} с", seconds=f"{duration:.2f}"), "ok")
        self._log(
            "success",
            "OCR",
            tr("Готово за {seconds} с, {count} символов", seconds=f"{duration:.2f}", count=len(text)),
        )
        self.help_panel.set_stat("ocr", tr("{seconds} с", seconds=f"{duration:.2f}"))
        self._update_stats()
        self.ocr_thread = None
        self.ocr_worker = None

    def _handle_error(self, message: str) -> None:
        self._set_busy(False)
        self._show_status(tr("Ошибка OCR. Проверьте настройки и пути."), "danger", 9000)
        self._log("error", "OCR", message)
        QtWidgets.QMessageBox.critical(self, tr("Ошибка OCR"), message)
        self.ocr_thread = None
        self.ocr_worker = None

    # ================================================================== output
    def copy_output(self) -> None:
        text = self.preview_panel.text()
        if not text:
            self._show_status(tr("Нечего копировать: текст пока пуст."), "warn")
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self._show_status(tr("Текст скопирован в буфер."), "ok")
        self._log("info", tr("Вывод"), tr("Текст скопирован"))

    def save_output(self) -> None:
        text = self.preview_panel.text()
        if not text:
            self._show_status(tr("Нечего сохранять: текст пока пуст."), "warn")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("Сохранить распознанный текст"),
            str(CONFIG_DIR.parent / "ocr-result.txt"),
            "Text (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, tr("Ошибка сохранения"), str(exc))
            return
        self._show_status(tr("Текст сохранён: {name}", name=Path(path).name), "ok")
        self._log("success", tr("Вывод"), tr("Сохранено: {path}", path=path))

    def clear_output(self) -> None:
        self.preview_panel.clear_output()
        self._show_status(tr("Вывод очищен."), "accent")
        self._log("info", tr("Вывод"), tr("Очищено"))

    def export_log(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            tr("Экспорт журнала"),
            str(CONFIG_DIR.parent / "activity-log.csv"),
            "CSV (*.csv);;Text (*.txt)",
        )
        if not path:
            return
        rows = self.activity.rows()
        try:
            if path.lower().endswith(".csv"):
                with open(path, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle, delimiter=";")
                    writer.writerow(["level", "timestamp", "source", "message"])
                    writer.writerows(rows)
            else:
                Path(path).write_text(self.activity.plain_text(), encoding="utf-8")
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, tr("Ошибка экспорта"), str(exc))
            return
        self._show_status(tr("Журнал сохранён: {name}", name=Path(path).name), "ok")

    # ============================================================== validation
    def _ensure_region(self) -> bool:
        if not self.current_config.region:
            QtWidgets.QMessageBox.warning(
                self, tr("Область не выбрана"), tr("Сначала выделите область захвата.")
            )
            self._show_status(tr("Сначала выберите область."), "warn")
            return False
        return True

    def _ensure_tesseract(self) -> bool:
        candidate = self.capture_page.tesseract_edit.text().strip()
        if not candidate:
            self.auto_detect_tesseract_resources(announce=False)
            candidate = self.capture_page.tesseract_edit.text().strip()
        if candidate and Path(candidate).exists():
            return True
        found = find_tesseract_executable(candidate)
        if found:
            self.capture_page.tesseract_edit.setText(str(found))
            return True
        QtWidgets.QMessageBox.warning(
            self,
            tr("Tesseract не найден"),
            tr("Укажите путь к tesseract.exe на вкладке «Захват»."),
        )
        self._show_status(tr("tesseract.exe не найден."), "danger")
        return False

    def _ensure_language_files(self) -> bool:
        tessdata_text = self.capture_page.tessdata_edit.text().strip()
        if not tessdata_text:
            return True
        tessdata_dir = Path(tessdata_text)
        if not tessdata_dir.exists():
            QtWidgets.QMessageBox.warning(
                self,
                tr("tessdata не найдена"),
                tr("Указанная папка tessdata не существует."),
            )
            return False
        languages = [
            item.strip()
            for item in self.ocr_page.language_combo.currentText().split("+")
            if item.strip()
        ]
        missing = [lang for lang in languages if not (tessdata_dir / f"{lang}.traineddata").exists()]
        if missing:
            QtWidgets.QMessageBox.warning(
                self,
                tr("Не хватает языковых файлов"),
                tr("В tessdata не найдены:\n{files}\n\nДобавьте файлы или смените язык OCR.",
                   files="\n".join(f"- {lang}.traineddata" for lang in missing)),
            )
            self._show_status(tr("Не хватает языковых файлов tessdata."), "danger")
            return False
        return True

    # =============================================================== settings
    def _collect_runtime_settings(self) -> dict:
        return {
            "tesseract_path": self.capture_page.tesseract_edit.text().strip(),
            "tessdata_dir": self.capture_page.tessdata_edit.text().strip(),
            "language": self.ocr_page.language_combo.currentText().strip(),
            "psm": int(self.ocr_page.psm_combo.currentText()),
            "oem": int(self.ocr_page.oem_combo.currentText()),
            "threshold_mode": self.preprocess_page.threshold_mode_combo.currentText(),
            "threshold_value": self.preprocess_page.threshold_slider.value(),
            "adaptive_block_size": self.preprocess_page.adaptive_block_spin.value(),
            "adaptive_c": self.preprocess_page.adaptive_c_spin.value(),
            "blur_kernel": int(self.preprocess_page.blur_combo.currentText()),
            "scale": float(self.preprocess_page.scale_combo.currentText()),
            "invert": self.preprocess_page.invert_check.isChecked(),
            "grayscale": self.preprocess_page.grayscale_check.isChecked(),
            "whitelist": self.ocr_page.whitelist_edit.text(),
            "blacklist": self.ocr_page.blacklist_edit.text(),
            "min_confidence": self.ocr_page.min_confidence_spin.value(),
            "preserve_spaces": self.ocr_page.preserve_spaces_check.isChecked(),
            "user_defined_dpi": self.ocr_page.user_dpi_spin.value(),
            "extra_config": self.ocr_page.extra_config_edit.text(),
        }

    def _collect_config(self) -> AppConfig:
        return AppConfig(
            profile_name=self.profiles_page.profile_name(),
            tesseract_path=self.capture_page.tesseract_edit.text().strip(),
            tessdata_dir=self.capture_page.tessdata_edit.text().strip(),
            language=self.ocr_page.language_combo.currentText().strip(),
            psm=int(self.ocr_page.psm_combo.currentText()),
            oem=int(self.ocr_page.oem_combo.currentText()),
            threshold_mode=self.preprocess_page.threshold_mode_combo.currentText(),
            threshold_value=self.preprocess_page.threshold_slider.value(),
            adaptive_block_size=self.preprocess_page.adaptive_block_spin.value(),
            adaptive_c=self.preprocess_page.adaptive_c_spin.value(),
            blur_kernel=int(self.preprocess_page.blur_combo.currentText()),
            scale=float(self.preprocess_page.scale_combo.currentText()),
            invert=self.preprocess_page.invert_check.isChecked(),
            grayscale=self.preprocess_page.grayscale_check.isChecked(),
            auto_ocr=False,
            auto_interval_ms=1500,
            whitelist=self.ocr_page.whitelist_edit.text(),
            blacklist=self.ocr_page.blacklist_edit.text(),
            min_confidence=self.ocr_page.min_confidence_spin.value(),
            preserve_spaces=self.ocr_page.preserve_spaces_check.isChecked(),
            user_defined_dpi=self.ocr_page.user_dpi_spin.value(),
            extra_config=self.ocr_page.extra_config_edit.text(),
            region=self.current_config.region,
        )

    def _apply_config(self, config: AppConfig) -> None:
        self._loading = True
        self.current_config = config
        self.profiles_page.profile_combo.setCurrentText(config.profile_name)
        self.capture_page.tesseract_edit.setText(config.tesseract_path)
        self.capture_page.tessdata_edit.setText(config.tessdata_dir)
        self.capture_page.tesseract_edit.setCursorPosition(0)
        self.capture_page.tessdata_edit.setCursorPosition(0)
        self.ocr_page.language_combo.setCurrentText(config.language)
        self.ocr_page.psm_combo.setCurrentText(str(config.psm))
        self.ocr_page.oem_combo.setCurrentText(str(config.oem))
        self.preprocess_page.threshold_mode_combo.setCurrentText(config.threshold_mode)
        self.preprocess_page.threshold_slider.setValue(int(config.threshold_value))
        self.preprocess_page.adaptive_block_spin.setValue(int(config.adaptive_block_size))
        self.preprocess_page.adaptive_c_spin.setValue(int(config.adaptive_c))
        self.preprocess_page.blur_combo.setCurrentText(str(config.blur_kernel))
        self.preprocess_page.scale_combo.setCurrentText(str(config.scale))
        self.preprocess_page.invert_check.setChecked(config.invert)
        self.preprocess_page.grayscale_check.setChecked(config.grayscale)
        self.ocr_page.whitelist_edit.setText(config.whitelist)
        self.ocr_page.blacklist_edit.setText(config.blacklist)
        self.ocr_page.min_confidence_spin.setValue(int(config.min_confidence))
        self.ocr_page.preserve_spaces_check.setChecked(config.preserve_spaces)
        self.ocr_page.user_dpi_spin.setValue(int(config.user_defined_dpi))
        self.ocr_page.extra_config_edit.setText(config.extra_config)
        self.capture_page.set_region(config.region)
        self._loading = False
        self.preprocess_page.update_threshold_visibility()
        self.ocr_page.update_psm_hint()
        self._update_region_status()
        self._update_diagnostics()
        self._settings_changed()

    def apply_preset(self, key: str) -> None:
        preset = OCR_PRESETS.get(key)
        if not preset:
            return
        values = preset["values"]
        self._loading = True
        self.ocr_page.language_combo.setCurrentText(values["language"])
        self.ocr_page.psm_combo.setCurrentText(str(values["psm"]))
        self.ocr_page.oem_combo.setCurrentText(str(values["oem"]))
        self.preprocess_page.threshold_mode_combo.setCurrentText(values["threshold_mode"])
        self.preprocess_page.threshold_slider.setValue(values["threshold_value"])
        self.preprocess_page.adaptive_block_spin.setValue(values["adaptive_block_size"])
        self.preprocess_page.adaptive_c_spin.setValue(values["adaptive_c"])
        self.preprocess_page.blur_combo.setCurrentText(str(values["blur_kernel"]))
        self.preprocess_page.scale_combo.setCurrentText(str(values["scale"]))
        self.preprocess_page.invert_check.setChecked(values["invert"])
        self.preprocess_page.grayscale_check.setChecked(values["grayscale"])
        self.ocr_page.whitelist_edit.setText(values["whitelist"])
        self.ocr_page.blacklist_edit.setText(values["blacklist"])
        self.ocr_page.min_confidence_spin.setValue(values["min_confidence"])
        self.ocr_page.preserve_spaces_check.setChecked(values["preserve_spaces"])
        self.ocr_page.user_dpi_spin.setValue(values["user_defined_dpi"])
        self.ocr_page.extra_config_edit.setText(values["extra_config"])
        self._loading = False
        self.preprocess_page.update_threshold_visibility()
        self.ocr_page.update_psm_hint()
        self._show_status(tr("Пресет применён: {title}", title=tr(preset["title"])), "ok")
        self._log("info", tr("Пресет"), tr(preset["title"]))
        self._settings_changed()

    # ================================================================ profiles
    def refresh_profiles(self) -> None:
        names = list_profiles()
        current = self.profiles_page.profile_name() if hasattr(self, "profiles_page") else ""
        if current and current not in names:
            names.append(current)
        self.profiles_page.set_profiles(names, current or "default")

    def save_profile(self) -> None:
        name = safe_profile_name(self.profiles_page.profile_name())
        config = self._collect_config()
        config.profile_name = name
        try:
            path = save_config_file(CONFIG_DIR / f"{name}.json", config)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, tr("Ошибка сохранения профиля"), str(exc))
            return
        self.current_config = config
        self.refresh_profiles()
        self.profiles_page.profile_combo.setCurrentText(name)
        self._show_status(tr("Профиль сохранён: {name}", name=path.name), "ok")
        self._log("success", tr("Профиль"), tr("Сохранён {name}", name=path.name))

    def load_profile_from_combo(self) -> None:
        self.load_profile(self.profiles_page.profile_name())

    def load_profile(self, name: str, silent: bool = False) -> None:
        name = safe_profile_name(name)
        path = CONFIG_DIR / f"{name}.json"
        if not path.exists():
            if not silent:
                QtWidgets.QMessageBox.information(
                    self,
                    tr("Профиль не найден"),
                    tr("Файл {name} пока не существует.", name=path.name),
                )
            return
        try:
            config = load_config_file(path)
        except (OSError, ValueError, TypeError) as exc:
            QtWidgets.QMessageBox.warning(self, tr("Ошибка профиля"), str(exc))
            return
        config.profile_name = name
        self._apply_config(config)
        self.refresh_profiles()
        self.profiles_page.profile_combo.setCurrentText(name)
        self._show_status(tr("Профиль загружен: {name}", name=path.name), "ok")
        self._log("info", tr("Профиль"), tr("Загружен {name}", name=path.name))

    def open_config_dir(self) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(CONFIG_DIR)))
        self._show_status(tr("Открыта папка: {path}", path=CONFIG_DIR), "accent")

    def pick_tesseract(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("Выберите tesseract.exe"), str(CONFIG_DIR.parent), "Executable (*.exe);;All files (*.*)"
        )
        if path:
            self.capture_page.tesseract_edit.setText(path)
            self._update_diagnostics()
            self._show_status(tr("Путь к Tesseract обновлён."), "ok")
            self._log("info", "Tesseract", path)

    def pick_tessdata(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, tr("Выберите папку tessdata"), str(CONFIG_DIR.parent)
        )
        if path:
            self.capture_page.tessdata_edit.setText(path)
            self._update_diagnostics()
            self._show_status(tr("Папка tessdata обновлена."), "ok")
            self._log("info", "tessdata", path)

    def auto_detect_tesseract_resources(self, announce: bool = True) -> None:
        found_tesseract = find_tesseract_executable(self.capture_page.tesseract_edit.text().strip())
        found_tessdata = find_tessdata_dir(
            self.capture_page.tessdata_edit.text().strip(), found_tesseract
        )
        if found_tesseract:
            self.capture_page.tesseract_edit.setText(str(found_tesseract))
            self.capture_page.tesseract_edit.setCursorPosition(0)
        if found_tessdata:
            self.capture_page.tessdata_edit.setText(str(found_tessdata))
            self.capture_page.tessdata_edit.setCursorPosition(0)
        if found_tesseract or found_tessdata:
            parts = []
            if found_tesseract:
                parts.append(f"tesseract: {found_tesseract}")
            if found_tessdata:
                parts.append(f"tessdata: {found_tessdata}")
            if announce:
                self._show_status(tr("Автопоиск: {parts}", parts=" | ".join(parts)), "ok" if found_tesseract else "warn")
                self._log("success", tr("Автопоиск"), " | ".join(parts))
        elif announce:
            self._show_status(tr("Автопоиск не нашёл Tesseract - укажите путь вручную."), "warn")
            self._log("warning", tr("Автопоиск"), tr("Tesseract не найден"))
        self._update_diagnostics()

    # ============================================================ diagnostics
    def _update_diagnostics(self) -> None:
        if not hasattr(self, "ocr_page"):
            return
        settings = self._collect_runtime_settings()
        good: list[str] = []
        risky: list[str] = []

        def mark(widget, state: str, good_text: str = "", risk_text: str = "") -> None:
            widget.setProperty("state", state)
            repolish(widget)
            if state == "ok" and good_text:
                good.append(tr(good_text))
            elif state in {"warn", "error"} and risk_text:
                risky.append(tr(risk_text))

        tess_path = self.capture_page.tesseract_edit.text().strip()
        tess_ok = bool(tess_path) and Path(tess_path).exists()
        mark(
            self.capture_page.tesseract_edit,
            "ok" if tess_ok else "warn",
            "Путь к Tesseract найден.",
            "Путь к Tesseract не задан или неверный.",
        )
        tessdata_path = self.capture_page.tessdata_edit.text().strip()
        tessdata_ok = bool(tessdata_path) and Path(tessdata_path).exists()
        mark(
            self.capture_page.tessdata_edit,
            "ok" if tessdata_ok else "warn",
            "Папка tessdata найдена.",
            "Папка tessdata не задана или недоступна.",
        )
        languages = [
            item.strip() for item in settings["language"].split("+") if item.strip()
        ]
        missing_languages = []
        if tessdata_ok and languages:
            missing_languages = [
                language
                for language in languages
                if not (Path(tessdata_path) / f"{language}.traineddata").exists()
            ]
        if missing_languages:
            mark(
                self.ocr_page.language_combo,
                "warn",
                risk_text=tr(
                    "В tessdata нет: {files}.",
                    files=", ".join(
                        f"{language}.traineddata" for language in missing_languages
                    ),
                ),
            )
        else:
            mark(
                self.ocr_page.language_combo,
                "ok" if "+" not in settings["language"] else "warn",
                "Один язык - обычно стабильнее.",
                "Несколько языков замедляют OCR и повышают число ошибок.",
            )
        mark(
            self.ocr_page.psm_combo,
            "ok" if settings["psm"] in {6, 7, 8, 10, 11} else "warn",
            "PSM практичен для прикладного OCR.",
            "Текущий PSM реже подходит для UI и короткого текста.",
        )
        mark(
            self.preprocess_page.scale_combo,
            "ok" if settings["scale"] >= 2.0 else "warn",
            "Масштаб подходит для мелкого текста.",
            "Маленький масштаб часто ухудшает мелкие символы.",
        )
        mark(
            self.ocr_page.min_confidence_spin,
            "warn" if settings["min_confidence"] > 75 else "ok",
            "Порог уверенности не слишком агрессивный.",
            "Слишком высокий min confidence скрывает нужный текст.",
        )
        mark(
            self.ocr_page.user_dpi_spin,
            "ok" if 200 <= settings["user_defined_dpi"] <= 400 else "warn",
            "DPI в практичном диапазоне.",
            "Нестандартный DPI может давать нестабильный OCR.",
        )
        for neutral in (
            self.ocr_page.whitelist_edit,
            self.ocr_page.blacklist_edit,
            self.ocr_page.extra_config_edit,
            self.preprocess_page.blur_combo,
            self.preprocess_page.threshold_mode_combo,
            self.preprocess_page.grayscale_check,
            self.preprocess_page.invert_check,
        ):
            neutral.setProperty("state", "")
            repolish(neutral)
        if settings["whitelist"].strip():
            good.append(tr("Whitelist ограничивает OCR и повышает точность."))
        if settings["blacklist"].strip():
            good.append(tr("Blacklist убирает частые ложные символы."))

        parts = []
        if risky:
            parts.append(
                f"<b style='color:#e07a72'>{tr('Рискованные настройки:')}</b><br>"
                + "<br>".join(f"• {text}" for text in risky[:4])
            )
        if good:
            parts.append(
                f"<b style='color:#5fc98a'>{tr('Удачные настройки:')}</b><br>"
                + "<br>".join(f"• {text}" for text in good[:4])
            )
        if not parts:
            parts.append(tr("Пока нет явных сигналов по настройкам."))
        self.help_panel.set_diagnostics("<br><br>".join(parts))

    # ================================================================== help
    def _register_help_targets(self) -> None:
        register = (
            register_help_targets_en
            if get_language() == "en"
            else register_help_targets
        )
        register(
            self.help_panel,
            self.capture_page,
            self.ocr_page,
            self.preprocess_page,
            self.profiles_page,
            self.preview_panel,
        )

    # ================================================================ dialogs
    def show_shortcuts(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            tr("Горячие клавиши"),
            tr(
                "<b>Захват и OCR</b><br>"
                "Ctrl+Shift+R - выбрать область<br>"
                "F6 - захватить область<br>"
                "F5 - распознать текущий кадр<br>"
                "Ctrl+Enter - распознать область<br><br>"
                "<b>Файлы и вывод</b><br>"
                "Ctrl+O - открыть изображение<br>"
                "Ctrl+Shift+V - вставить из буфера<br>"
                "Ctrl+Shift+C - копировать текст<br>"
                "Ctrl+S - сохранить текст<br><br>"
                "<b>Интерфейс</b><br>"
                "Ctrl+T - сменить палитру<br>"
                "Ctrl+, - оформление<br>"
                "Ctrl+J - журнал событий<br>"
                "Ctrl+L - очистить журнал<br>"
                "Ctrl+/ - эта справка<br>"
                "F1 - о программе"
            ),
        )

    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            tr("О программе {name}", name=APP_NAME),
            tr(
                "<h3>{name} {version}</h3>"
                "<p>OCR-студия на PyQt5 с интерфейсом, перенесённым из Qt UI Lab.</p>"
                "<p>Захват области экрана, живой предпросмотр обработки, профили, "
                "журнал событий и тёмная/светлая палитры.</p>"
                "<p>Профили: <code>{path}</code></p>",
                name=APP_NAME,
                version=APP_VERSION,
                path=CONFIG_DIR,
            ),
        )
