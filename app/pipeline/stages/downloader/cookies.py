"""
YouTube Download Cookie Manager.

Handles reading cookies.txt, detecting bot checks, and extracting 
cookies from installed local browsers.
"""
import os
from pathlib import Path
from typing import Callable

from app.config import get_cookies_file
from app.utils.cookies import normalize_cookie_text


class DownloadCookieManager:
    """Manages yt-dlp cookie authentication and browser fallback."""

    _BOT_CHECK_PATTERNS = (
        "sign in to confirm you're not a bot",
        "sign in to confirm you\u2019re not a bot",
        "use --cookies-from-browser or --cookies",
    )

    _BROWSER_COOKIE_SOURCES = (
        ("edge", lambda: Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"),
        ("chrome", lambda: Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"),
        ("brave", lambda: Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "User Data"),
        ("firefox", lambda: Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"),
    )

    def __init__(self, job_dir: Path, logger_callback: Callable[[str, int], None]):
        self._job_dir = job_dir
        self._log = logger_callback

    def get_base_cookie_args(self) -> tuple[list[str], str]:
        """Return yt-dlp cookie args based on cookies.txt and a human-readable label."""
        cookies_file = get_cookies_file()
        if not cookies_file.exists():
            self._log("cookies.txt не найден — скачивание без авторизации", 30)
            return [], "без авторизации"

        try:
            content = cookies_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""

        normalized = normalize_cookie_text(content) if content else None
        if normalized is not None and normalized.source_format != "netscape":
            converted_path = self._job_dir / "cookies.converted.txt"
            converted_path.write_text(normalized.netscape_text, encoding="utf-8")
            fmt_label = f"cookies.txt ({normalized.source_format}→netscape)"
            self._log(f"Конвертированы cookies: {fmt_label}", 20)
            return ["--cookies", str(converted_path)], fmt_label

        self._log(f"Используем cookies: {cookies_file.name}", 20)
        return ["--cookies", str(cookies_file)], "cookies.txt"

    def needs_browser_cookies(self, error_text: str) -> bool:
        """Check if yt-dlp suggests we need fresh browser cookies."""
        lowered = (error_text or "").lower()
        return any(p in lowered for p in self._BOT_CHECK_PATTERNS)

    def load_available_browsers(self) -> list[str]:
        """Detect installed browsers that might contain YouTube cookies."""
        available: list[str] = []
        for name, path_factory in self._BROWSER_COOKIE_SOURCES:
            try:
                if path_factory().exists():
                    available.append(name)
            except Exception:
                continue
        return available

    def generate_browser_fallback_hint(self, error_text: str) -> str:
        """Generate a user-friendly hint if bot protection triggered."""
        if self.needs_browser_cookies(error_text):
            return (
                "\nПодсказка: YouTube запросил подтверждение входа. "
                "Добавьте cookies.txt в настройках или войдите в YouTube "
                "в одном из локальных браузеров (Edge/Chrome/Firefox)."
            )
        return ""
