"""
Helpers for Hugging Face downloads with GUI-friendly progress callbacks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from huggingface_hub import snapshot_download
from tqdm.auto import tqdm


ProgressCallback = Callable[[int | None, int | None, str], None]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_progress_tqdm(
    progress_callback: ProgressCallback | None,
    *,
    progress_message: str,
):
    class ProgressTqdm(tqdm):
        def __init__(self, *args, **kwargs):
            # Accept and ignore unknown kwargs (e.g., 'name' from newer huggingface_hub)
            kwargs.pop("name", None)
            self._progress_callback = progress_callback
            self._progress_message = progress_message
            self._last_state: tuple[int | None, int | None, str] | None = None
            super().__init__(*args, **kwargs)
            self._emit_progress()

        def update(self, n=1):
            result = super().update(n)
            self._emit_progress()
            return result

        def refresh(self, *args, **kwargs):
            result = super().refresh(*args, **kwargs)
            self._emit_progress()
            return result

        def set_description(self, desc=None, refresh=True):
            result = super().set_description(desc=desc, refresh=refresh)
            self._emit_progress()
            return result

        def close(self):
            self._emit_progress()
            return super().close()

        def _emit_progress(self, *, force: bool = False):
            if self._progress_callback is None:
                return

            total = _as_int(getattr(self, "total", None))
            current = _as_int(getattr(self, "n", None))
            if total is not None and current is not None:
                current = min(current, total)

            state = (current, total, self._progress_message)
            if not force and state == self._last_state:
                return

            self._last_state = state
            self._progress_callback(current, total, self._progress_message)

    return ProgressTqdm


def snapshot_download_with_progress(
    *,
    repo_id: str,
    progress_callback: ProgressCallback | None = None,
    progress_message: str = "Скачивание...",
    cache_dir: str | Path | None = None,
    local_dir: str | Path | None = None,
    local_files_only: bool = False,
    allow_patterns: list[str] | str | None = None,
    ignore_patterns: list[str] | str | None = None,
    revision: str | None = None,
    force_download: bool = False,
    token: str | bool | None = None,
    max_workers: int = 8,
    repo_type: str | None = None,
    headers: dict[str, str] | None = None,
):
    """Wrap snapshot_download and expose byte progress through a callback."""
    progress_tqdm = _build_progress_tqdm(
        progress_callback,
        progress_message=progress_message,
    )
    return snapshot_download(
        repo_id=repo_id,
        repo_type=repo_type,
        revision=revision,
        cache_dir=cache_dir,
        local_dir=local_dir,
        local_files_only=local_files_only,
        allow_patterns=allow_patterns,
        ignore_patterns=ignore_patterns,
        force_download=force_download,
        token=token,
        max_workers=max_workers,
        headers=headers,
        tqdm_class=progress_tqdm,
    )
