# Contributing

Thanks for improving **Tesseract OCR Studio**.

## Development setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS
pip install -r requirements-dev.txt
python main.py
```

## Tests

```bash
pytest tests -q
```

Tests run offscreen and use temporary profile/settings directories. Please add a
regression test for every behavioural fix and keep the English localization test
(`tests/test_i18n.py`) green.

## Localization

- The Russian source string is the translation key.
- Add English values to `tesseract_studio/translations_en.py`.
- Contextual help lives in `ui/help_texts.py` (RU) and `ui/help_texts_en.py` (EN).
- Run `pytest tests/test_i18n.py -q` after touching UI copy. It fails if English
  mode contains Cyrillic text or if a translation key is missing.
- When adding a new language, extend `i18n.LANGUAGES` and provide a catalogue
  module; the language selector and `--lang` flag are data-driven.

## Pull requests

- Keep changes focused and describe the user-visible effect.
- Run `python -m pytest tests -q` and `python -m pyflakes tesseract_studio tests`.
- Update `CHANGELOG.md` for user-visible changes.
- Do not commit `dist/`, virtual environments, caches or personal profiles.

## Release checklist

1. Bump `APP_VERSION` in `tesseract_studio/config.py` and `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Tag the commit: `git tag -a vX.Y.Z -m "vX.Y.Z"` and push the tag.
4. `.github/workflows/release.yml` builds the Windows executable and publishes
   the release assets automatically.
