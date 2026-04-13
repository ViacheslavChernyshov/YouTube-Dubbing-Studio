import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.config import AppSettings
from app.pipeline.stages.s08_mix import MixStage
from app.utils.audio import load_wav, mix_audio_tracks, normalize_audio, save_wav


class MixStageTests(unittest.TestCase):
    def test_keep_video_audio_mixes_with_original_track(self):
        stage = MixStage()
        sr = 44100
        voice = np.linspace(-0.25, 0.25, sr, dtype=np.float32)
        original_audio = np.full(sr, 0.15, dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            aligned_voice_path = job_dir / "aligned_voice.wav"
            original_audio_path = job_dir / "input_audio.wav"
            save_wav(aligned_voice_path, voice, sr=sr)
            save_wav(original_audio_path, original_audio, sr=sr)

            context = {
                "aligned_voice_path": str(aligned_voice_path),
                "audio_path": str(original_audio_path),
                "settings": AppSettings(
                    keep_original_audio=True,
                    original_audio_volume=100,
                ),
            }

            result = stage.run(job_dir, context)
            mixed, _ = load_wav(result["final_audio_path"], sr=sr)

        expected = mix_audio_tracks(
            voice=voice,
            background=original_audio,
            bg_volume_db=0.0,
            sr=sr,
        )
        self.assertTrue(np.allclose(mixed, expected, atol=2e-4))

    def test_mute_video_audio_outputs_voice_only(self):
        stage = MixStage()
        sr = 44100
        voice = np.linspace(-0.25, 0.25, sr, dtype=np.float32)
        original_audio = np.full(sr, 0.35, dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            aligned_voice_path = job_dir / "aligned_voice.wav"
            original_audio_path = job_dir / "input_audio.wav"
            save_wav(aligned_voice_path, voice, sr=sr)
            save_wav(original_audio_path, original_audio, sr=sr)

            context = {
                "aligned_voice_path": str(aligned_voice_path),
                "audio_path": str(original_audio_path),
                "settings": AppSettings(
                    keep_original_audio=False,
                    original_audio_volume=0,
                ),
            }

            result = stage.run(job_dir, context)
            mixed, _ = load_wav(result["final_audio_path"], sr=sr)

        expected = normalize_audio(voice, target_db=-1.0)
        self.assertTrue(np.allclose(mixed, expected, atol=2e-4))


if __name__ == "__main__":
    unittest.main()
