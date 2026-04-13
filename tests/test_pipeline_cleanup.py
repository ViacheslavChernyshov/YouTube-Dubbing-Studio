import logging
import tempfile
import unittest
from pathlib import Path

from app.pipeline.manager import cleanup_job_dir


class PipelineCleanupTests(unittest.TestCase):
    def test_cleanup_removes_intermediates_and_keeps_user_files(self):
        logger = logging.getLogger("pipeline-cleanup-test")

        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir)
            keep_files = {
                "output.mp4",
                "input.webm",
                "segments.json",
                "segments_translated.json",
            }
            for name in keep_files:
                (job_dir / name).write_text(name, encoding="utf-8")

            (job_dir / "audio.wav").write_text("temp", encoding="utf-8")
            (job_dir / "aligned_voice.wav").write_text("temp", encoding="utf-8")
            tts_dir = job_dir / "tts_segments"
            tts_dir.mkdir()
            (tts_dir / "seg_0000.wav").write_text("temp", encoding="utf-8")

            removed_files, removed_dirs = cleanup_job_dir(job_dir, keep_files, logger)

            self.assertEqual(2, removed_files)
            self.assertEqual(1, removed_dirs)
            for name in keep_files:
                self.assertTrue((job_dir / name).exists())
            self.assertFalse((job_dir / "audio.wav").exists())
            self.assertFalse((job_dir / "aligned_voice.wav").exists())
            self.assertFalse(tts_dir.exists())


if __name__ == "__main__":
    unittest.main()
