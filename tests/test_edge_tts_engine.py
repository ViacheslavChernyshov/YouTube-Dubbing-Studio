import unittest

from app.tts_engines.base_engine import TTSEngineRegistry


class EdgeTTSEngineTests(unittest.TestCase):
    def test_registry_autoloads_edge_engine(self):
        engine_cls = TTSEngineRegistry.get_engine_class("edge-tts")

        self.assertEqual("EdgeTTSEngine", engine_cls.__name__)

    def test_legacy_preset_voice_uses_edge_voice_mapping(self):
        engine = TTSEngineRegistry.get_engine_class("edge-tts")()

        voice_ref = engine.use_preset_voice("female_warm")

        self.assertEqual("en-US-JennyNeural", voice_ref["voice"])
        self.assertEqual("-4%", voice_ref["rate"])
        self.assertEqual("-6Hz", voice_ref["pitch"])

    def test_direct_voice_id_is_preserved_for_multilingual_voices(self):
        engine = TTSEngineRegistry.get_engine_class("edge-tts")()

        voice_ref = engine.use_preset_voice("uk-UA-PolinaNeural")

        self.assertEqual("uk-UA-PolinaNeural", voice_ref["voice"])
        self.assertEqual("+0%", voice_ref["rate"])
        self.assertEqual("+0Hz", voice_ref["pitch"])


if __name__ == "__main__":
    unittest.main()
