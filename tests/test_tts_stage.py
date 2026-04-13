import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppSettings, DEFAULT_TTS_SEED
from app.pipeline.context import PipelineContext
from app.pipeline.stages.s06_tts import TTSStage


class _FakeEngine:
    def __init__(self):
        self.loaded_device = None
        self.preset_id = None
        self.calls = []
        self.unloaded = False

    def load_model(self, device: str = "cuda"):
        self.loaded_device = device

    def use_preset_voice(self, preset_id: str):
        self.preset_id = preset_id
        return {"ref_audio": "preset.wav", "ref_text": "hello"}

    def synthesize(
        self,
        text: str,
        voice_ref: dict,
        output_path: str,
        nfe_step: int = 32,
        speed: float = 1.0,
        seed: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "text": text,
                "voice_ref": voice_ref,
                "output_path": output_path,
                "nfe_step": nfe_step,
                "speed": speed,
                "seed": seed,
            }
        )
        return output_path

    def unload_model(self):
        self.unloaded = True


class TTSStageTests(unittest.TestCase):
    def test_stage_uses_same_seed_for_every_segment(self):
        stage = TTSStage()
        fake_engine = _FakeEngine()
        stage._get_engine = lambda _tts_engine: fake_engine

        segments = [
            {"text": "Привет", "translated_text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "Мир", "translated_text": "World", "start": 1.0, "end": 2.0},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s06_tts.get_duration",
            return_value=0.8,
        ):
            context = PipelineContext(
                segments=segments,
                device="cpu",
                settings=AppSettings(voice_preset="female_warm", tts_engine="f5-tts"),
            )
            result = stage.run(Path(tmp_dir), context)

        self.assertEqual("cpu", fake_engine.loaded_device)
        self.assertEqual("female_warm", fake_engine.preset_id)
        self.assertEqual(2, len(fake_engine.calls))
        self.assertTrue(fake_engine.unloaded)
        self.assertEqual(
            result["tts_files"],
            [
                str(Path(tmp_dir) / "tts_segments" / "seg_0000.wav"),
                str(Path(tmp_dir) / "tts_segments" / "seg_0001.wav"),
            ],
        )
        self.assertTrue(all(call["seed"] == DEFAULT_TTS_SEED for call in fake_engine.calls))

    def test_stage_raises_for_unsupported_language_in_strict_mode(self):
        stage = TTSStage()
        fake_engine = _FakeEngine()
        requested_engines = []

        def _get_engine(engine_id: str):
            requested_engines.append(engine_id)
            return fake_engine

        stage._get_engine = _get_engine

        segments = [
            {"text": "Hello", "translated_text": "Привет", "start": 0.0, "end": 1.0},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s06_tts.get_duration",
            return_value=0.9,
        ):
            context = PipelineContext(
                segments=segments,
                device="cpu",
                settings=AppSettings(
                    target_language="ru",
                    voice_preset="af_heart",
                    tts_engine="kokoro-tts",
                ),
            )
            with self.assertRaises(RuntimeError) as exc:
                stage.run(Path(tmp_dir), context)

        self.assertEqual([], requested_engines)
        self.assertIn("does not support language", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
