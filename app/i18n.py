"""
Lightweight UI localization helpers for the desktop app.

Translations are loaded from ``locales/<lang>.json`` files that live next
to the project root.  The public API (``tr``, ``set_language``,
``get_language``, ``get_interface_language_options``, etc.) is unchanged.
"""
from __future__ import annotations

import json
import logging
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
_MODULE_DIR = Path(__file__).resolve().parent
_LOCALES_DIR = _MODULE_DIR.parent / "locales"

# ── Constants ──────────────────────────────────────────────────────────────
DEFAULT_INTERFACE_LANGUAGE = "en"
RTL_LANGUAGES = {"ar"}

LANGUAGE_META = OrderedDict(
    [
        ("en", {"native": "English", "english": "English"}),
        ("zh", {"native": "中文", "english": "Chinese"}),
        ("hi", {"native": "हिन्दी", "english": "Hindi"}),
        ("es", {"native": "Español", "english": "Spanish"}),
        ("ar", {"native": "العربية", "english": "Arabic"}),
        ("fr", {"native": "Français", "english": "French"}),
        ("bn", {"native": "বাংলা", "english": "Bengali"}),
        ("pt", {"native": "Português", "english": "Portuguese"}),
        ("ru", {"native": "Русский", "english": "Russian"}),
        ("uk", {"native": "Українська", "english": "Ukrainian"}),
    ]
)


# ── JSON-based translation loader ─────────────────────────────────────────

def _load_locale_json(lang_code: str) -> dict[str, str] | None:
    """Try to load translations for a language from its JSON file."""
    locale_file = _LOCALES_DIR / f"{lang_code}.json"
    if not locale_file.is_file():
        return None
    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load locale {lang_code}: {e}")
        return None


def _load_translations() -> dict[str, dict[str, str]]:
    """Load all translations from locales/*.json files."""
    result: dict[str, dict[str, str]] = {}
    if not _LOCALES_DIR.is_dir():
        logger.warning(f"Locales directory not found: {_LOCALES_DIR}")
        return result

    for lang_code in LANGUAGE_META:
        data = _load_locale_json(lang_code)
        if data is not None:
            result[lang_code] = data

    if result:
        logger.debug(f"Loaded {len(result)} locales from {_LOCALES_DIR}")
    else:
        logger.warning("No locale files found — UI will show raw keys")

    return result


# ── Load translations ─────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = _load_translations()


# ── Language manager ──────────────────────────────────────────────────────

class LanguageManager(QObject):
    language_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._language = DEFAULT_INTERFACE_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language_code: str, *, emit: bool = True):
        language = normalize_language(language_code)
        if language == self._language:
            return
        self._language = language
        if emit:
            self.language_changed.emit(language)


language_manager = LanguageManager()


# ── Public API ────────────────────────────────────────────────────────────

def normalize_language(language_code: str | None) -> str:
    code = str(language_code or "").strip().lower()
    return code if code in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE


def get_language() -> str:
    return language_manager.language


def set_language(language_code: str, *, emit: bool = True):
    language_manager.set_language(language_code, emit=emit)


def tr(key: str, default: str | None = None, **kwargs) -> str:
    language = get_language()
    value = TRANSLATIONS.get(language, {}).get(key, default if default is not None else key)
    try:
        return value.format(**kwargs)
    except Exception:
        return value


def get_layout_direction(language_code: str | None = None):
    language = normalize_language(language_code or get_language())
    return (
        Qt.LayoutDirection.RightToLeft
        if language in RTL_LANGUAGES
        else Qt.LayoutDirection.LeftToRight
    )


def get_interface_language_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for code, meta in LANGUAGE_META.items():
        native = meta["native"]
        english = meta["english"]
        label = native if native == english else f"{native} ({english})"
        options.append((code, label))
    return options
