import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.i18n import (
    TRANSLATIONS,
    get_interface_language_options,
    get_language,
    normalize_language,
    set_language,
)


def _collect_translation_keys(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        keys.add(node.value)
    for child in ast.iter_child_nodes(node):
        keys.update(_collect_translation_keys(child))
    return keys


def _used_tr_keys() -> set[str]:
    root = Path(__file__).resolve().parents[1]
    keys: set[str] = set()
    for path in (root / "app").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if func_name == "tr":
                keys.update(_collect_translation_keys(node.args[0]))
    return keys


class InterfaceLocalizationTests(unittest.TestCase):
    def test_supported_interface_languages_have_top10_count(self):
        codes = [code for code, _label in get_interface_language_options()]
        self.assertEqual(10, len(codes))
        self.assertIn("ru", codes)
        self.assertIn("uk", codes)
        self.assertEqual("ru", normalize_language("unknown"))

    def test_interface_language_persists_in_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            test_settings = config.AppSettings()
            test_settings.interface_language = "uk"

            with patch.object(config, "SETTINGS_FILE", settings_file):
                test_settings.save()
                loaded = config.AppSettings()
                loaded.interface_language = "ru"
                loaded.load()

            self.assertEqual("uk", loaded.interface_language)

    def test_stage_names_follow_selected_interface_language(self):
        previous_language = get_language()
        try:
            set_language("es", emit=False)
            names = config.get_stage_names()
            self.assertEqual("Descargar video", names[0])
            self.assertEqual("Generar video final", names[-1])
        finally:
            set_language(previous_language, emit=False)

    def test_all_locales_cover_the_same_translation_keys(self):
        used_keys = _used_tr_keys()
        base_keys = set(TRANSLATIONS["ru"])

        for code, translations in TRANSLATIONS.items():
            locale_keys = set(translations)
            missing_vs_base = sorted(base_keys - locale_keys)
            extra_vs_base = sorted(locale_keys - base_keys)
            missing_used = sorted(used_keys - locale_keys)

            self.assertEqual([], missing_vs_base, f"{code} missing keys: {missing_vs_base}")
            self.assertEqual([], extra_vs_base, f"{code} extra keys: {extra_vs_base}")
            self.assertEqual([], missing_used, f"{code} missing used keys: {missing_used}")


if __name__ == "__main__":
    unittest.main()
