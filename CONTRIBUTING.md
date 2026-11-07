# Contributing

Thanks for improving **Tesseract OCR Studio**.

## Development setup

```bash
git clone https://github.com/Golybou/Tesseract_OCR_Studio.git
cd Tesseract_OCR_Studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

Tesseract OCR 5.x must be installed separately, see the setup section in
`README.md`.

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
  module; the language selector and the `--lang` flag are data-driven.

## Documentation

- Keep `README.md` bilingual: the Russian and English sections describe the same
  features and must be updated together.
- Do not use long dashes in documentation or in the interface copy. Use a plain
  hyphen. Two hyphens in a row are allowed only where they are part of real
  syntax, for example a command-line flag or a `pip` option.
- Every new screenshot belongs in `docs/screenshots/` and must be referenced from
  both language sections.
- The demo animation `docs/demo.gif` is produced by driving the real window and
  running a real OCR pass. Keep the captured frames free of local paths.

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
