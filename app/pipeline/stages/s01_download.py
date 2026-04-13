"""
Stage 1: Download video from YouTube using yt-dlp.

Optimized 3-tier download strategy:
  Tier 1 — combined format string (single yt-dlp call, native "/" fallbacks)
  Tier 2 — explicit probe (dump-json → pick best format_id → download)
  Tier 3 — auto (no -f flag, let yt-dlp decide)

Each tier uses cookies when available. On total failure the whole chain
is retried once with a delay (2 top-level attempts max).
"""
import os
import subprocess
import re
import time
from pathlib import Path

from app.config import get_ffmpeg_path
from app.pipeline.context import PipelineContext
from app.pipeline.base_stage import BaseStage, PipelineCancelled
from app.utils.process import CancelledProcessError, run_command
from app.i18n import tr

from app.pipeline.stages.downloader.cookies import DownloadCookieManager
from app.pipeline.stages.downloader.format_selector import DownloadFormatSelector


class DownloadStage(BaseStage):
    # ── Combined format string ────────────────────────────────────────────
    # All fallbacks in ONE yt-dlp call (avoids rapid-fire API requests).
    _COMBINED_FORMAT = (
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
        "/best[ext=mp4]"
        "/bestvideo[ext=webm]+bestaudio[ext=webm]"
        "/best[ext=webm]"
        "/bestvideo+bestaudio"
        "/best"
    )

    # ── Retry settings ────────────────────────────────────────────────────
    _RETRY_DELAY_SECONDS = 5
    _MAX_TOP_LEVEL_RETRIES = 2
    _MIN_FILE_SIZE_BYTES = 100 * 1024  # 100 KB — anything smaller is garbage

    def __init__(self):
        super().__init__(1, tr("s01.name", default="Video download"), tr("s01.desc", default="Download video from YouTube using yt-dlp"))
        self._cookies: DownloadCookieManager | None = None

    # ══════════════════════════════════════════════════════════════════════
    #  Core download helpers
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_error_tail(exc: subprocess.CalledProcessError, n: int = 10) -> str:
        lines = (exc.output or "").splitlines()
        return "\n".join(lines[-n:])

    def _build_base_cmd(self, auth_args: list[str]) -> list[str]:
        """Base yt-dlp command shared by all tiers."""
        return [
            "yt-dlp",
            "--no-warnings",
            "--extractor-retries", "3",
            *auth_args,
        ]

    def _run_download(
        self,
        *,
        url: str,
        output_path: Path,
        auth_args: list[str],
        format_value: str | None,
        merge_output_format: str | None = None,
        label: str,
    ) -> tuple[bool, str]:
        """Execute a single yt-dlp download attempt.

        Returns (success, error_text).
        """
        self.check_cancelled()

        # Clean up previous partial downloads
        for leftover in output_path.parent.glob(f"{output_path.stem}*"):
            try:
                leftover.unlink()
            except OSError:
                pass

        cmd = self._build_base_cmd(auth_args)
        if format_value:
            cmd += ["-f", format_value]
        if merge_output_format:
            cmd += ["--merge-output-format", merge_output_format]
        cmd += [
            "--ffmpeg-location", get_ffmpeg_path(),
            "--newline",
            "-o", str(output_path),
            url,
        ]

        t0 = time.time()
        self.log(tr("s01.attempt", default="⬇ Attempt: {label}", label=label))

        def _on_line(line: str):
            m = re.search(r"(\d+\.?\d*)%", line)
            if m:
                pct = float(m.group(1))
                self.report_progress(10 + pct * 0.8, tr("s01.downloading", default="Downloading: {pct:.1f}%", pct=pct))
            elif "Merging" in line:
                self.report_progress(92, tr("s01.merging", default="Merging streams..."))
            elif "Destination" in line or "has already been downloaded" in line:
                self.report_progress(8, tr("s01.start_download", default="Starting download..."))

        try:
            run_command(cmd, cancel_event=self._cancel_event, line_callback=_on_line)
            elapsed = time.time() - t0
            self.log(tr("s01.success", default="✓ Success ({label}) in {elapsed:.1f}s", label=label, elapsed=elapsed))
            return True, ""
        except CancelledProcessError as exc:
            raise PipelineCancelled(tr("s01.cancelled", default="Download stopped by user")) from exc
        except subprocess.CalledProcessError as exc:
            elapsed = time.time() - t0
            error_tail = self._extract_error_tail(exc)
            err_msg = error_tail.splitlines()[-1] if error_tail else 'unknown'
            self.log(tr("s01.failed", default="✗ Failed ({label}) in {elapsed:.1f}s\n  Command: {cmd}\n  Error: {err}", label=label, elapsed=elapsed, cmd=' '.join(cmd[:6])+"...", err=err_msg), level=30)
            return False, error_tail

    def _dump_debug_log(self, job_dir: Path, label: str, error_text: str):
        """Save detailed error output to a debug file for troubleshooting."""
        try:
            debug_file = job_dir / "ytdlp_debug.log"
            with open(debug_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{time.strftime('%H:%M:%S')}] {label}\n")
                f.write(f"{'='*60}\n")
                f.write(error_text)
                f.write("\n")
        except OSError:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Download tiers
    # ══════════════════════════════════════════════════════════════════════

    def _tier1_combined_format(
        self, url: str, output_path: Path, auth_args: list[str],
    ) -> tuple[bool, str]:
        """Tier 1: Single yt-dlp call with combined format string + "/" fallbacks."""
        return self._run_download(
            url=url,
            output_path=output_path,
            auth_args=auth_args,
            format_value=self._COMBINED_FORMAT,
            merge_output_format="mp4",
            label=tr("s01.label_combined", default="combined format"),
        )

    def _tier2_explicit_probe(
        self, url: str, output_path: Path, auth_args: list[str],
    ) -> tuple[bool, str]:
        """Tier 2: Probe available formats via dump-json, then download by exact ID."""
        self.log(tr("s01.probe_formats", default="Probing available formats (dump-json)..."), level=30)

        probe_cmd = [
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            "--extractor-retries", "3",
            *auth_args,
            "--dump-single-json",
            "--skip-download",
            url,
        ]
        try:
            output = run_command(probe_cmd, cancel_event=self._cancel_event)
        except CancelledProcessError as exc:
            raise PipelineCancelled(tr("pipeline.cancelled_by_user", default="Cancelled by user")) from exc
        except subprocess.CalledProcessError as exc:
            error_tail = self._extract_error_tail(exc)
            err_msg = error_tail.splitlines()[-1] if error_tail else '?'
            self.log(tr("s01.probe_failed", default="Failed to probe formats: {error}", error=err_msg), level=30)
            return False, error_tail

        metadata = DownloadFormatSelector.parse_json_from_output(output)
        if metadata is None:
            self.log(tr("s01.invalid_json", default="yt-dlp returned invalid JSON during dump-json"), level=30)
            return False, ""

        fmt_id, merge_fmt = DownloadFormatSelector.select_best_format(metadata)
        if not fmt_id:
            self.log(tr("s01.no_format", default="Failed to determine suitable format from metadata"), level=30)
            return False, ""

        return self._run_download(
            url=url,
            output_path=output_path,
            auth_args=auth_args,
            format_value=fmt_id,
            merge_output_format=merge_fmt,
            label=f"explicit:{fmt_id}",
        )

    def _tier3_auto(
        self, url: str, output_path: Path, auth_args: list[str],
    ) -> tuple[bool, str]:
        """Tier 3: No -f flag — let yt-dlp auto-select."""
        return self._run_download(
            url=url,
            output_path=output_path,
            auth_args=auth_args,
            format_value=None,
            merge_output_format="mp4",
            label=tr("s01.label_auto", default="auto (yt-dlp decides)"),
        )

    # ══════════════════════════════════════════════════════════════════════
    #  Browser cookie escalation
    # ══════════════════════════════════════════════════════════════════════

    def _try_browser_cookies(
        self, url: str, output_path: Path, last_error: str,
    ) -> tuple[bool, str, list[str]]:
        """If yt-dlp is asking for auth, try cookies from installed browsers."""
        if not self._cookies.needs_browser_cookies(last_error):
            return False, last_error, []

        browsers = self._cookies.load_available_browsers()
        if not browsers:
            self.log(tr("s01.no_browsers", default="YouTube requires auth, but no local browsers found. Please specify cookies.txt in settings."), level=40)
            return False, last_error, []

        self.log(tr("s01.try_browsers", default="YouTube requested bot check. Trying cookies from browsers: {browsers}", browsers=', '.join(browsers)), level=30)

        for browser_name in browsers:
            browser_auth = ["--cookies-from-browser", browser_name]
            success, err = self._tier1_combined_format(url, output_path, browser_auth)
            if success:
                return True, "", browser_auth
            last_error = err or last_error

        return False, last_error, []

    # ══════════════════════════════════════════════════════════════════════
    #  Main download chain
    # ══════════════════════════════════════════════════════════════════════

    def _run_full_download_chain(
        self, url: str, job_dir: Path, output_path: Path,
    ) -> tuple[bool, str]:
        """Run download tiers.  Return (success, last_error)."""
        auth_args, auth_label = self._cookies.get_base_cookie_args()
        self.log(tr("s01.auth", default="Auth: {label}", label=auth_label))

        # ── Tier 1: combined format ───────────────────────────────────────
        success, last_error = self._tier1_combined_format(url, output_path, auth_args)
        if success:
            return True, ""

        # ── Fast path: cookies broke format selection → drop them ──────────
        if auth_args and DownloadFormatSelector.needs_explicit_format_probe(last_error):
            self.log(tr("s01.cookies_break", default="Cookies interfere with format selection - trying without auth..."), level=30)
            success, no_auth_error = self._tier1_combined_format(url, output_path, [])
            if success:
                return True, ""
            if no_auth_error:
                last_error = no_auth_error
            # From here on, use no-auth since cookies are clearly stale
            auth_args = []

        # ── Bot-check → try browser cookies ───────────────────────────────
        if self._cookies.needs_browser_cookies(last_error):
            success, last_error, browser_auth = self._try_browser_cookies(
                url, output_path, last_error,
            )
            if success:
                return True, ""
            if browser_auth:
                auth_args = browser_auth

        # ── Tier 2: explicit probe ────────────────────────────────────────
        success, probe_error = self._tier2_explicit_probe(url, output_path, auth_args)
        if success:
            return True, ""
        if probe_error:
            last_error = probe_error
            self._dump_debug_log(job_dir, "tier2_explicit_probe", probe_error)

        # ── Tier 3: auto ──────────────────────────────────────────────────
        success, auto_error = self._tier3_auto(url, output_path, auth_args)
        if success:
            return True, ""
        if auto_error:
            last_error = auto_error
            self._dump_debug_log(job_dir, "tier3_auto", auto_error)

        return False, last_error

    # ══════════════════════════════════════════════════════════════════════
    #  Output file resolution
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def _find_output_file(cls, job_dir: Path, stem: str = "input") -> Path | None:
        """Find the downloaded file. yt-dlp may change extension or add suffixes."""
        # Direct match first
        for ext in ("mp4", "mkv", "webm"):
            candidate = job_dir / f"{stem}.{ext}"
            if candidate.exists() and candidate.stat().st_size >= cls._MIN_FILE_SIZE_BYTES:
                return candidate

        # Glob fallback (handles edge cases like input.f399.mp4)
        for candidate in sorted(job_dir.glob(f"{stem}.*"), key=lambda p: p.stat().st_size, reverse=True):
            if candidate.suffix.lower() in (".mp4", ".mkv", ".webm", ".m4v"):
                if candidate.stat().st_size >= cls._MIN_FILE_SIZE_BYTES:
                    return candidate

        return None

    # ══════════════════════════════════════════════════════════════════════
    #  Stage entry point
    # ══════════════════════════════════════════════════════════════════════

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        url = context.url
        output_path = job_dir / "input.mp4"
        self._cookies = DownloadCookieManager(job_dir, lambda msg, lvl=20: self.log(msg, level=lvl))

        self.log(tr("s01.downloading_url", default="Downloading: {url}", url=url))
        self.report_progress(5, tr("s01.connecting", default="Connecting to YouTube..."))

        success = False
        last_error = ""

        for attempt in range(self._MAX_TOP_LEVEL_RETRIES):
            if attempt > 0:
                self.check_cancelled()
                self.log(tr("s01.retry", default="Retry ({attempt}/{max}) in {delay}s...", attempt=attempt+1, max=self._MAX_TOP_LEVEL_RETRIES, delay=self._RETRY_DELAY_SECONDS), level=30)
                time.sleep(self._RETRY_DELAY_SECONDS)

            success, last_error = self._run_full_download_chain(url, job_dir, output_path)
            if success:
                break

        if not success:
            # Dump final error for post-mortem
            self._dump_debug_log(job_dir, "FINAL_FAILURE", last_error)
            hint = self._cookies.generate_browser_fallback_hint(last_error)
            raise RuntimeError(f"yt-dlp: {tr('s01.all_failed', default='all download attempts failed')}.\n{last_error}{hint}")

        # Resolve actual output file
        resolved = self._find_output_file(job_dir)
        if resolved is None:
            raise FileNotFoundError(tr("s01.not_found", default="Video not found after download — yt-dlp exited successfully but file is missing or too small (<100KB)."))

        file_size_mb = resolved.stat().st_size / (1024 * 1024)
        self.log(tr("s01.downloaded", default="Downloaded: {name} ({size:.1f} MB)", name=resolved.name, size=file_size_mb))

        context.input_video = str(resolved)
        return context
