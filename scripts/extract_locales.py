"""
One-time conversion script: extracts embedded translations from i18n.py
into separate locales/*.json files.

Usage:
    python scripts/extract_locales.py

After running, the `locales/` directory will contain one JSON file per
language, plus `_meta.json` with language metadata.
The embedded TRANSLATIONS dict in i18n.py can then be replaced by the
JSON loader.
"""
import json
import sys
from pathlib import Path

# Add project root to sys.path so imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock PySide6 to avoid GUI import errors
import types

pyside6 = types.ModuleType("PySide6")
qtcore = types.ModuleType("PySide6.QtCore")


class _MockQObject:
    pass


class _MockSignal:
    def __init__(self, *a, **kw):
        pass


class _MockQt:
    class LayoutDirection:
        RightToLeft = 1
        LeftToRight = 0


qtcore.QObject = _MockQObject
qtcore.Signal = _MockSignal
qtcore.Qt = _MockQt
sys.modules["PySide6"] = pyside6
sys.modules["PySide6.QtCore"] = qtcore

# Now safe to import
from app.i18n import TRANSLATIONS, LANGUAGE_META, RTL_LANGUAGES  # noqa: E402

LOCALES_DIR = PROJECT_ROOT / "locales"


def main():
    LOCALES_DIR.mkdir(exist_ok=True)

    # ── Per-language translation files ──────────────────────────────
    for lang_code, translations in TRANSLATIONS.items():
        out_path = LOCALES_DIR / f"{lang_code}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {out_path.name:>8s}  —  {len(translations)} keys")

    # ── Language metadata ──────────────────────────────────────────
    meta = {
        "languages": {
            code: info for code, info in LANGUAGE_META.items()
        },
        "rtl": sorted(RTL_LANGUAGES),
        "default": "en",
    }
    meta_path = LOCALES_DIR / "_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ {'_meta.json':>8s}  —  {len(meta['languages'])} languages")

    total_keys = sum(len(t) for t in TRANSLATIONS.values())
    print(f"\nDone: {len(TRANSLATIONS)} locales, {total_keys} total keys → {LOCALES_DIR}/")
    print("\nNext step: replace the embedded TRANSLATIONS dict in app/i18n.py")
    print("with the JSON loader. See app/i18n.py for the updated version.")


if __name__ == "__main__":
    main()
