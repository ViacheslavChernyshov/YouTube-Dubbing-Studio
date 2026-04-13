"""
Format parsing and selection for yt-dlp metadata.

Extracts the best possible video/audio formats from the yt-dlp 
metadata dump payload, allowing precise format selection instead of
relying on default combined strings which might fail.
"""
import json


class DownloadFormatSelector:
    """Parses yt-dlp JSON dumps and selects the optimal format ID."""

    _FORMAT_UNAVAILABLE_PATTERNS = (
        "requested format is not available",
        "use --list-formats for a list of available formats",
    )

    @classmethod
    def needs_explicit_format_probe(cls, error_text: str) -> bool:
        """Check if format error requires a manual JSON dump probe."""
        lowered = (error_text or "").lower()
        return any(p in lowered for p in cls._FORMAT_UNAVAILABLE_PATTERNS)

    @staticmethod
    def parse_json_from_output(output: str) -> dict | None:
        """Safely parse yt-dlp's single JSON object output, ignoring debug prefixes."""
        raw = (output or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
            
        # yt-dlp sometimes prepends debug lines — search from bottom up
        for line in reversed(raw.splitlines()):
            candidate = line.strip()
            if not candidate or candidate == "null":
                continue
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _format_sort_key(fmt: dict) -> tuple[float, float, float, float]:
        return (
            float(fmt.get("height") or 0),
            float(fmt.get("fps") or 0),
            float(fmt.get("tbr") or 0),
            float(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
        )

    @classmethod
    def select_best_format(cls, metadata: dict) -> tuple[str | None, str | None]:
        """Pick the best explicit format from yt-dlp metadata.

        Returns (format_string, merge_output_format_or_None).
        """
        # 1) Check requested_downloads first (yt-dlp's own best pick)
        requested = (metadata.get("requested_downloads") or [None])[0]
        if requested:
            fid = requested.get("format_id")
            if fid:
                merge = "mp4" if "+" in fid else None
                return str(fid), merge

        # 2) Manual pick from format list
        formats = metadata.get("formats") or []
        if not isinstance(formats, list):
            return None, None

        video_only = [f for f in formats
                      if f.get("format_id") and f.get("vcodec") not in (None, "none")
                      and f.get("acodec") in (None, "none")]
        audio_only = [f for f in formats
                      if f.get("format_id") and f.get("acodec") not in (None, "none")
                      and f.get("vcodec") in (None, "none")]
        muxed = [f for f in formats
                 if f.get("format_id") and f.get("vcodec") not in (None, "none")
                 and f.get("acodec") not in (None, "none")]

        def _best(pool, ext=None):
            filtered = [f for f in pool if f.get("ext") == ext] if ext else pool
            return sorted(filtered, key=cls._format_sort_key, reverse=True)

        # Priority: mp4+m4a → mp4 muxed → webm+webm → webm muxed → any v+a → any muxed
        mp4v, m4a = _best(video_only, "mp4"), _best(audio_only, "m4a")
        if mp4v and m4a:
            return f"{mp4v[0]['format_id']}+{m4a[0]['format_id']}", "mp4"

        mp4m = _best(muxed, "mp4")
        if mp4m:
            return str(mp4m[0]["format_id"]), None

        webmv, weba = _best(video_only, "webm"), _best(audio_only, "webm")
        if webmv and weba:
            return f"{webmv[0]['format_id']}+{weba[0]['format_id']}", "mp4"

        webmm = _best(muxed, "webm")
        if webmm:
            return str(webmm[0]["format_id"]), None

        anyv, anya = _best(video_only), _best(audio_only)
        if anyv and anya:
            return f"{anyv[0]['format_id']}+{anya[0]['format_id']}", "mp4"

        anym = _best(muxed)
        if anym:
            return str(anym[0]["format_id"]), None

        return None, None
