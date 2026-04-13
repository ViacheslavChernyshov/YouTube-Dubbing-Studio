import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.config as config
from app.config import delete_cookies_file
from app.voice_catalog import (
    TARGET_LANGUAGE_INFO,
    get_default_voice_preset,
    get_kokoro_lang_rows,
    get_model_voice_catalog,
    get_target_language_display_name,
    tts_engine_supports_language,
)
from app.i18n import get_language, set_language


class MultilingualConfigTests(unittest.TestCase):
    def test_top_ten_languages_are_available(self):
        self.assertEqual(
            ["en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "uk"],
            list(TARGET_LANGUAGE_INFO.keys()),
        )

    def test_edge_catalog_contains_russian_and_ukrainian_voices(self):
        self.assertIn("ru-RU-SvetlanaNeural", get_model_voice_catalog("edge-tts", "ru"))
        self.assertIn("uk-UA-PolinaNeural", get_model_voice_catalog("edge-tts", "uk"))

    def test_only_edge_supports_russian_target_language(self):
        self.assertTrue(tts_engine_supports_language("edge-tts", "ru"))
        self.assertFalse(tts_engine_supports_language("kokoro-tts", "ru"))
        self.assertFalse(tts_engine_supports_language("f5-tts", "ru"))
        self.assertEqual("ru-RU-SvetlanaNeural", get_default_voice_preset("edge-tts", "ru"))

    def test_language_rows_follow_selected_interface_language(self):
        previous_language = get_language()
        try:
            set_language("en", emit=False)
            self.assertEqual("English", get_target_language_display_name("en"))
            self.assertEqual("Russian (Русский)", get_target_language_display_name("ru"))

            set_language("uk", emit=False)
            self.assertEqual("Англійська (English)", get_target_language_display_name("en"))
            self.assertEqual(
                ("en-us", "en-US (Американська)"),
                get_kokoro_lang_rows()[0],
            )
        finally:
            set_language(previous_language, emit=False)

    def test_voice_catalogs_follow_selected_interface_language(self):
        previous_language = get_language()
        try:
            set_language("en", emit=False)
            kokoro_desc = get_model_voice_catalog("kokoro-tts", "en")["af_heart"][1]
            f5_name = get_model_voice_catalog("f5-tts", "en")["female_warm"][0]
            edge_name = get_model_voice_catalog("edge-tts", "ru")["ru-RU-SvetlanaNeural"][0]
            self.assertIn("Profile:", kokoro_desc)
            self.assertIn("Recommendation:", kokoro_desc)
            self.assertEqual("👩 Female (warm)", f5_name)
            self.assertEqual("👩 Russian · Svetlana", edge_name)

            set_language("es", emit=False)
            kokoro_desc = get_model_voice_catalog("kokoro-tts", "en")["af_heart"][1]
            f5_name = get_model_voice_catalog("f5-tts", "en")["female_warm"][0]
            edge_name = get_model_voice_catalog("edge-tts", "uk")["uk-UA-PolinaNeural"][0]
            self.assertIn("Perfil:", kokoro_desc)
            self.assertEqual("👩 Femenina (cálida)", f5_name)
            self.assertEqual("👩 ucraniano · Polina", edge_name)
        finally:
            set_language(previous_language, emit=False)

    def test_delete_cookies_file_removes_configured_cookies_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cookies_path = Path(tmp_dir) / "cookies.txt"
            cookies_path.write_text("cookie=data", encoding="utf-8")

            with patch.object(config, "COOKIES_FILE", cookies_path):
                self.assertTrue(delete_cookies_file())
                self.assertFalse(cookies_path.exists())
                self.assertFalse(delete_cookies_file())


if __name__ == "__main__":
    unittest.main()
