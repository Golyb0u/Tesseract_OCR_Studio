"""Tiny runtime translator for the Russian/English UI.

The Russian string is used as the message key. That keeps the source readable
and guarantees a safe fallback: if an English entry is missing the Russian text
is shown instead of a raw identifier. A test checks that English mode contains
no untranslated Cyrillic UI text.

Language is chosen at startup (``--lang`` / saved setting) and changing it
restarts the process, which keeps every page, help text and dialog consistent.
"""

from __future__ import annotations

import os
from typing import Any

from .translations_en import EN

DEFAULT_LANGUAGE = "ru"
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("ru", "Русский"),
    ("en", "English"),
)

_current = DEFAULT_LANGUAGE
_missing: set[str] = set()


def available_languages() -> tuple[tuple[str, str], ...]:
    return LANGUAGES


def set_language(language: str | None) -> str:
    global _current
    candidate = (language or "").strip().lower()
    if candidate not in {code for code, _ in LANGUAGES}:
        candidate = DEFAULT_LANGUAGE
    _current = candidate
    return _current


def get_language() -> str:
    return _current


def tr(text: str, **values: Any) -> str:
    """Return ``text`` in the active language, formatting named placeholders."""
    if not isinstance(text, str):
        return text
    translated = text
    if _current == "en" and any("\u0400" <= char <= "\u04ff" for char in text):
        value = EN.get(text)
        if value is None:
            _missing.add(text)
        else:
            translated = value
    if values:
        try:
            translated = translated.format(**values)
        except (KeyError, IndexError, ValueError):
            pass
    return translated


def missing_translations() -> set[str]:
    return set(_missing)


def clear_missing() -> None:
    _missing.clear()


def language_from_env() -> str | None:
    override = os.environ.get("TESSERACT_STUDIO_LANG", "").strip().lower()
    return override or None
