import tempfile
import unittest
from pathlib import Path

from app.pipeline.stages.s03_separate import PrepareAudioStage


class PrepareAudioStageTests(unittest.TestCase):
    def test_stage_keeps_audio_path_without_legacy_aliases(self):
        stage = PrepareAudioStage()

        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = Path(tmp_dir) / "source.wav"
            audio_path.write_bytes(b"fake wav")

            context = {"audio_path": str(audio_path)}
            result = stage.run(Path(tmp_dir), context)

        self.assertEqual(str(audio_path), result["audio_path"])
        self.assertNotIn("speech_source_path", result)
        self.assertNotIn("original_audio_path", result)
        self.assertNotIn("vocals_path", result)
        self.assertNotIn("no_vocals_path", result)


if __name__ == "__main__":
    unittest.main()
