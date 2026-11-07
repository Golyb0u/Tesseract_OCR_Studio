"""Application bootstrap: QApplication, CLI flags and the main window."""

from __future__ import annotations

import argparse
import sys

from PyQt5 import QtCore, QtGui, QtWidgets

from .config import APP_NAME, APP_VERSION, ORG_NAME, ensure_default_profile
from .singleton import acquire_single_instance, activate_running_instance
from .ui.icons import app_icon
from .ui.main_window import MainWindow
from .ui.theme import DEFAULT_TOKENS
from .ui.widgets import PopupThemeFilter


def build_app(argv: list[str] | None = None) -> QtWidgets.QApplication:
    if QtWidgets.QApplication.instance() is None:
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))
    font = QtGui.QFont(DEFAULT_TOKENS["font_family"], int(DEFAULT_TOKENS["font_size"]))
    font.setStyleStrategy(QtGui.QFont.PreferAntialias)
    font.setHintingPreference(QtGui.QFont.PreferFullHinting)
    app.setFont(font)
    app.setWindowIcon(app_icon())
    if getattr(app, "_popup_theme", None) is None:
        app._popup_theme = PopupThemeFilter(app)
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tesseract OCR Studio - desktop OCR workbench"
    )
    parser.add_argument("--light", action="store_true", help="start with the light palette")
    parser.add_argument("--dark", action="store_true", help="start with the dark palette")
    parser.add_argument(
        "--system",
        action="store_true",
        help="leave the platform style untouched instead of applying the theme",
    )
    parser.add_argument("--profile", default="", help="load a named profile from configs/")
    parser.add_argument(
        "--lang",
        choices=("ru", "en"),
        default=None,
        help="interface language: ru or en",
    )
    args, qt_args = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    ensure_default_profile()
    app = build_app([sys.argv[0], *qt_args])

    # Only one studio window may be open per machine. A second launch brings
    # the running window to the front and exits instead of opening a new one.
    guard = acquire_single_instance()
    if not guard.owns_lock:
        activate_running_instance()
        return 0
    app.aboutToQuit.connect(guard.release)

    variant = "light" if args.light else ("dark" if args.dark else None)
    window = MainWindow(
        variant=variant,
        apply_theme=not args.system,
        language=args.lang,
    )
    if args.profile:
        window.load_profile(args.profile)
    window.show()
    # Publish the window handle so a second launch can raise this window.
    guard.publish_window(int(window.winId()))
    return int(app.exec_())


if __name__ == "__main__":
    raise SystemExit(main())
