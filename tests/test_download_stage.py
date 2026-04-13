import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.pipeline.stages.s01_download as download_stage_module
from app.pipeline.stages.s01_download import DownloadStage


class DownloadStageTests(unittest.TestCase):
    def test_stage_converts_json_cookie_export_for_ytdlp(self):
        stage = DownloadStage()
        inspected_cookie_files: list[Path] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            cookie_path = Path(cmd[cmd.index("--cookies") + 1])
            inspected_cookie_files.append(cookie_path)
            cookie_text = cookie_path.read_text(encoding="utf-8")
            self.assertTrue(cookie_text.startswith("# Netscape HTTP Cookie File"))
            self.assertIn("#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1810041452\t__Secure-3PSID\tvalue123", cookie_text)
            self.assertIn(".youtube.com\tTRUE\t/\tTRUE\t1810041475\tPREF\tf4=4000000", cookie_text)

            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.write_bytes(b"fake mp4")
            return "ok"

        with tempfile.TemporaryDirectory() as tmp_dir:
            cookies_path = Path(tmp_dir) / "cookies.txt"
            cookies_path.write_text(
                json.dumps(
                    [
                        {
                            "domain": ".youtube.com",
                            "expirationDate": 1810041452.36,
                            "hostOnly": False,
                            "httpOnly": True,
                            "name": "__Secure-3PSID",
                            "path": "/",
                            "secure": True,
                            "session": False,
                            "value": "value123",
                        },
                        {
                            "domain": ".youtube.com",
                            "expirationDate": 1810041475.51,
                            "hostOnly": False,
                            "httpOnly": False,
                            "name": "PREF",
                            "path": "/",
                            "secure": True,
                            "session": False,
                            "value": "f4=4000000",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "app.pipeline.stages.s01_download.get_cookies_file",
                return_value=cookies_path,
            ), patch(
                "app.pipeline.stages.s01_download.get_ffmpeg_path",
                return_value="ffmpeg",
            ), patch.object(
                download_stage_module,
                "run_command",
                side_effect=fake_run_ytdlp,
            ):
                result = stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})

            self.assertTrue(Path(result["input_video"]).exists())

        self.assertEqual(1, len(inspected_cookie_files))
        self.assertEqual("cookies.converted.txt", inspected_cookie_files[0].name)

    def test_stage_converts_raw_cookie_header_file_for_ytdlp(self):
        stage = DownloadStage()
        inspected_cookie_files: list[Path] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            cookie_path = Path(cmd[cmd.index("--cookies") + 1])
            inspected_cookie_files.append(cookie_path)
            cookie_text = cookie_path.read_text(encoding="utf-8")
            self.assertTrue(cookie_text.startswith("# Netscape HTTP Cookie File"))
            self.assertIn("\tSAPISID\t", cookie_text)

            output_path = Path(cmd[cmd.index("-o") + 1])
            output_path.write_bytes(b"fake mp4")
            return "ok"

        with tempfile.TemporaryDirectory() as tmp_dir:
            cookies_path = Path(tmp_dir) / "cookies.txt"
            cookies_path.write_text(
                "SAPISID=value123; __Secure-1PSID=secret456; PREF=f4=4000000",
                encoding="utf-8",
            )

            with patch(
                "app.pipeline.stages.s01_download.get_cookies_file",
                return_value=cookies_path,
            ), patch(
                "app.pipeline.stages.s01_download.get_ffmpeg_path",
                return_value="ffmpeg",
            ), patch.object(
                download_stage_module,
                "run_command",
                side_effect=fake_run_ytdlp,
            ):
                result = stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})

            self.assertTrue(Path(result["input_video"]).exists())

        self.assertEqual(1, len(inspected_cookie_files))
        self.assertEqual("cookies.converted.txt", inspected_cookie_files[0].name)

    def test_stage_retries_with_browser_cookies_after_youtube_bot_check(self):
        stage = DownloadStage()
        commands: list[list[str]] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)
            if "--cookies-from-browser" in cmd:
                output_path = Path(cmd[cmd.index("-o") + 1])
                output_path.write_bytes(b"fake mp4")
                return "ok"
            raise subprocess.CalledProcessError(
                1,
                cmd,
                output=(
                    "[youtube] Downloading webpage\n"
                    "ERROR: [youtube] id: Sign in to confirm you're not a bot. "
                    "Use --cookies-from-browser or --cookies for the authentication."
                ),
            )

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s01_download.get_cookies_file",
            return_value=Path(tmp_dir) / "missing-cookies.txt",
        ), patch(
            "app.pipeline.stages.s01_download.get_ffmpeg_path",
            return_value="ffmpeg",
        ), patch.object(
            download_stage_module,
            "run_command",
            side_effect=fake_run_ytdlp,
        ), patch.object(
            DownloadStage,
            "_detect_browser_cookie_sources",
            return_value=["edge"],
        ):
            result = stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})
            self.assertTrue(Path(result["input_video"]).exists())

        self.assertTrue(any("--cookies-from-browser" in cmd for cmd in commands))
        self.assertTrue(any("edge" in cmd for cmd in commands if "--cookies-from-browser" in cmd))

    def test_stage_does_not_touch_browser_cookies_for_non_auth_errors(self):
        stage = DownloadStage()
        commands: list[list[str]] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)
            raise subprocess.CalledProcessError(
                1,
                cmd,
                output="ERROR: Requested format is not available",
            )

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s01_download.get_cookies_file",
            return_value=Path(tmp_dir) / "missing-cookies.txt",
        ), patch(
            "app.pipeline.stages.s01_download.get_ffmpeg_path",
            return_value="ffmpeg",
        ), patch.object(
            download_stage_module,
            "run_command",
            side_effect=fake_run_ytdlp,
        ), patch.object(
            DownloadStage,
            "_detect_browser_cookie_sources",
            return_value=["edge"],
        ):
            with self.assertRaises(RuntimeError):
                stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})

        self.assertFalse(any("--cookies-from-browser" in cmd for cmd in commands))

    def test_stage_falls_back_to_explicit_format_probe_after_selector_failure(self):
        stage = DownloadStage()
        commands: list[list[str]] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)

            if "--dump-single-json" in cmd:
                return json.dumps(
                    {
                        "requested_downloads": [
                            {
                                "format_id": "399+251",
                                "ext": "webm",
                            }
                        ]
                    }
                )

            if "-f" in cmd and cmd[cmd.index("-f") + 1] == "399+251":
                output_path = Path(cmd[cmd.index("-o") + 1])
                output_path.with_suffix(".webm").write_bytes(b"fake webm")
                return "ok"

            raise subprocess.CalledProcessError(
                1,
                cmd,
                output="ERROR: [youtube] id: Requested format is not available. Use --list-formats for a list of available formats",
            )

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s01_download.get_cookies_file",
            return_value=Path(tmp_dir) / "missing-cookies.txt",
        ), patch(
            "app.pipeline.stages.s01_download.get_ffmpeg_path",
            return_value="ffmpeg",
        ), patch.object(
            download_stage_module,
            "run_command",
            side_effect=fake_run_ytdlp,
        ):
            result = stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})
            self.assertTrue(Path(result["input_video"]).exists())

        self.assertTrue(any("--dump-single-json" in cmd for cmd in commands))
        explicit_commands = [
            cmd for cmd in commands
            if "-f" in cmd and cmd[cmd.index("-f") + 1] == "399+251"
        ]
        self.assertEqual(1, len(explicit_commands))
        self.assertNotIn("--merge-output-format", explicit_commands[0])

    def test_stage_falls_back_to_tv_downgraded_client_after_probe_failure(self):
        stage = DownloadStage()
        commands: list[list[str]] = []

        def fake_run_ytdlp(command, **_kwargs):
            cmd = list(command)
            commands.append(cmd)

            if "--extractor-args" in cmd:
                extractor_value = cmd[cmd.index("--extractor-args") + 1]
                if extractor_value == "youtube:player_client=tv_downgraded":
                    # Check if it's a format attempt (either the new complex string or 'best')
                    if "-f" in cmd:
                        format_value = cmd[cmd.index("-f") + 1]
                        if "bestvideo" in format_value or format_value == "best":
                            output_path = Path(cmd[cmd.index("-o") + 1])
                            output_path.write_bytes(b"fake mp4")
                            return "ok"
                raise subprocess.CalledProcessError(
                    1,
                    cmd,
                    output="ERROR: [youtube] id: Requested format is not available. Use --list-formats for a list of available formats",
                )

            raise subprocess.CalledProcessError(
                1,
                cmd,
                output="ERROR: [youtube] id: Requested format is not available. Use --list-formats for a list of available formats",
            )

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "app.pipeline.stages.s01_download.get_cookies_file",
            return_value=Path(tmp_dir) / "missing-cookies.txt",
        ), patch(
            "app.pipeline.stages.s01_download.get_ffmpeg_path",
            return_value="ffmpeg",
        ), patch.object(
            download_stage_module,
            "run_command",
            side_effect=fake_run_ytdlp,
        ):
            result = stage.run(Path(tmp_dir), {"url": "https://www.youtube.com/shorts/test-id"})
            self.assertTrue(Path(result["input_video"]).exists())

        tv_commands = [
            cmd for cmd in commands
            if "--extractor-args" in cmd
            and cmd[cmd.index("--extractor-args") + 1] == "youtube:player_client=tv_downgraded"
        ]
        self.assertTrue(tv_commands)
        self.assertFalse(
            any(
                "--extractor-args" in cmd
                and cmd[cmd.index("--extractor-args") + 1] == "youtube:player_client=web"
                for cmd in commands
            )
        )


if __name__ == "__main__":
    unittest.main()
