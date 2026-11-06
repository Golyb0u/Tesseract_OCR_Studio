# Changelog

All notable changes to **Tesseract OCR Studio** are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.1.0] - 2026-11-06

### Added

- Complete Russian/English UI localization with a language selector in the toolbar
  and a `--lang ru|en` command-line flag.
- English contextual help (`help_texts_en.py`) and English translations for every
  status, dialog, diagnostic and OCR preset.
- GitHub release readiness: MIT license, `pyproject.toml`, CI matrix for Windows
  and Ubuntu, tag-driven Windows release workflow, issue templates and changelog.

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
