import unittest

import numpy as np

from app.pipeline.stages.s07_align import AlignStage


class AlignStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = AlignStage()

    def test_shorter_segment_keeps_natural_duration(self):
        audio = np.ones(1000, dtype=np.float32)

        fitted, mode = self.stage._fit_segment_audio(
            audio=audio,
            target_start=0.0,
            target_end=2.0,
            next_start=2.5,
            audio_duration=3.0,
            sr=1000,
        )

        self.assertEqual("natural", mode)
        self.assertEqual(len(audio), len(fitted))

    def test_longer_segment_can_use_pause_without_stretch(self):
        audio = np.ones(1800, dtype=np.float32)

        fitted, mode = self.stage._fit_segment_audio(
            audio=audio,
            target_start=0.0,
            target_end=1.0,
            next_start=2.0,
            audio_duration=3.0,
            sr=1000,
        )

        self.assertEqual("natural", mode)
        self.assertEqual(len(audio), len(fitted))

    def test_large_overflow_is_trimmed_when_compression_would_be_too_aggressive(self):
        audio = np.ones(2000, dtype=np.float32)

        fitted, mode = self.stage._fit_segment_audio(
            audio=audio,
            target_start=0.0,
            target_end=1.0,
            next_start=1.2,
            audio_duration=2.0,
            sr=1000,
            smart_hybrid=False,
        )

        self.assertEqual("trimmed", mode)
        self.assertLess(len(fitted), len(audio))
        self.assertEqual(1180, len(fitted))


if __name__ == "__main__":
    unittest.main()
