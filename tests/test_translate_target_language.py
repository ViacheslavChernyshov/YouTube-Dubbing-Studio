import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppSettings
from app.pipeline.stages.s05_translate import TranslateStage


class _FakeTranslator:
    last_call = None

    def __init__(self, device: str = "cpu"):
        self.device = device

    def batch_translate(self, texts: list[str], source_lang: str, target_lang: str):
        type(self).last_call = {
            "texts": list(texts),
            "source_lang": source_lang,
            "target_lang": target_lang,
        }
        return ["Привіт, світе."]

    def unload(self):
        return None


class TranslateTargetLanguageTests(unittest.TestCase):
    def test_stage_uses_selected_target_language_from_settings(self):
        stage = TranslateStage()
        segments = [{"text": "Hello, world."}]

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.translator.local_translator.LocalTranslator",
            _FakeTranslator,
        ):
            context = {
                "segments": segments,
                "source_language": "en",
                "device": "cpu",
                "settings": AppSettings(target_language="uk"),
            }
            result = stage.run(Path(tmp_dir), context)

        self.assertEqual("uk", _FakeTranslator.last_call["target_lang"])
        self.assertEqual("Привіт, світе.", result["segments"][0]["translated_text"])
        self.assertEqual("uk", result["target_language"])


if __name__ == "__main__":
    unittest.main()
