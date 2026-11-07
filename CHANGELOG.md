# Changelog

All notable changes to **Tesseract OCR Studio** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- The application no longer flashes a dozen empty windows while it starts. Card
  titles, card hints and the status banner were made visible before they had a
  parent, and a parentless widget that is shown turns into its own top-level
  window. The labels are now added to their layout before they are shown.
- Switching the interface language no longer crashes the application. The
  restart helper unpacked the result of `QProcess.startDetached` as a tuple,
  but the two-argument overload returns a plain bool, which raised a
  `TypeError` right after the language had been saved.
- A package installed with `pip install .` no longer writes its profiles into
  `site-packages`. The profile folder now resolves to
  `%LOCALAPPDATA%\TesseractStudio\configs` when the application runs from an
  installed package, while a source checkout and the packaged executable keep
  their previous locations.

### Removed

- The legacy `app.py` entry point and every trace of it. It only forwarded to
  `main.py`, so `python main.py` and the `tesseract-ocr-studio` console script
  are now the only supported ways to start the application.

### Added

- Single instance guard. A second launch now brings the running window to the
  front and exits instead of opening another window. The lock is a named
  shared memory segment, because `QLocalServer` lets two processes in the same
  Windows session listen on the same name.
- Demo animation `docs/demo.gif` that records a real OCR run against Tesseract
  5.x: frame loading, parameter setup and the recognised text.

### Changed

- Repository prepared for the public GitHub release: screenshots moved to
  `docs/screenshots/`, `.gitignore` extended with secrets, coverage and OS
  artefacts, README restructured with badges, environment variables, usage
  examples, limitations and roadmap.
- Windows is now the only supported platform: the CI matrix, documentation,
  issue templates and package classifiers drop Linux and macOS.
- Long dashes were replaced with plain hyphens in the interface copy and the
  documentation. The Russian string is the translation key, so the Russian and
  English catalogues were updated together.
- The three README screenshots were re-captured from the current build so the
  visible text matches the shipped interface.

## [2.1.0] - 2026-11-06

### Added

- Complete Russian/English UI localization with a language selector in the toolbar
  and a `--lang ru|en` command-line flag.
- English contextual help (`help_texts_en.py`) and English translations for every
  status, dialog, diagnostic and OCR preset.
- GitHub release readiness: MIT license, `pyproject.toml`, CI matrix for Windows,
  tag-driven Windows release workflow, issue templates and changelog.

### Changed

- Version bumped to 2.1.0.
- Language changes restart the application cleanly so every page, help text and
  dialog is rebuilt in the selected language.
- README expanded with language switching, release and localization instructions.

### Fixed

- Status bar messages no longer overlap the permanent status labels.
- Light theme accent colours are darkened for readable titles and toolbar labels.
- Missing `rus.traineddata` is reported explicitly by the diagnostics panel.
- ComboBox popups no longer show white platform bands around the dark rounded
  list; the popup container follows the active palette.
- Tab labels such as “Обработка” no longer clip at the edges; the navigation
  tabs now reserve room for bold translated text and carry matching icons.
- The settings column keeps enough width for buttons and wrapped hints at the
  minimum window size.

## [2.0.0] - 2026-11-06

### Added

- GUI ported from **Qt UI Lab**: token-based dark/light theme, gradient shell,
  flat cards, painted indicators, appearance inspector, activity console,
  live help and rich tooltips.
- Modular `tesseract_studio` package split from the old monolithic `app.py`.
- Bilingual RU/EN README, screenshots and a sample OCR image.
- Pytest suite covering configuration, preprocessing, theme, window and profiles.

### Changed

- New entry point `main.py`; `app.py` remains a compatibility wrapper.
- Updated PyInstaller spec and runtime requirements.
