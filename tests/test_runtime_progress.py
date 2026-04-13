import unittest
import io
from unittest.mock import patch

from app.gui.widgets.runtime_update_dialog import RuntimeUpdateDialog
from app.utils.hf_download import snapshot_download_with_progress


class SnapshotDownloadProgressTests(unittest.TestCase):
    def test_snapshot_download_reports_byte_progress_only(self):
        events = []

        def fake_snapshot_download(*args, **kwargs):
            tqdm_class = kwargs["tqdm_class"]
            sink = io.StringIO()

            files_bar = tqdm_class(total=3, initial=0, desc="Fetching 3 files", file=sink)
            files_bar.update(1)
            files_bar.close()

            bytes_bar = tqdm_class(total=200, initial=50, unit="B", desc="Downloading", file=sink)
            bytes_bar.update(25)
            bytes_bar.update(125)
            bytes_bar.close()
            return "model-path"

        with patch("app.utils.hf_download.snapshot_download", side_effect=fake_snapshot_download):
            result = snapshot_download_with_progress(
                repo_id="org/model",
                progress_callback=lambda current, total, message: events.append((current, total, message)),
                progress_message="Скачивание Whisper",
            )

        self.assertEqual(result, "model-path")
        self.assertEqual(
            events,
            [
                (50, 200, "Скачивание Whisper"),
                (75, 200, "Скачивание Whisper"),
                (200, 200, "Скачивание Whisper"),
            ],
        )


class RuntimeUpdateDialogProgressTests(unittest.TestCase):
    def test_calculate_overall_percent_uses_current_step_progress(self):
        self.assertEqual(RuntimeUpdateDialog._calculate_overall_percent(1, 4, 0), 0)
        self.assertEqual(RuntimeUpdateDialog._calculate_overall_percent(1, 4, 50), 12)
        self.assertEqual(RuntimeUpdateDialog._calculate_overall_percent(2, 4, 50), 37)
        self.assertEqual(RuntimeUpdateDialog._calculate_overall_percent(4, 4, 100), 100)


if __name__ == "__main__":
    unittest.main()
