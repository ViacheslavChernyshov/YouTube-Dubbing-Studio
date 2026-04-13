"""
Typed pipeline context — explicit contract between pipeline stages.

Replaces the untyped `dict` that was previously passed between stages,
providing IDE autocompletion, type checking, and clear documentation
of what each stage produces and consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import JobSettings
from app.hardware import HardwareInfo


@dataclass
class PipelineContext:
    """Typed container for data that flows through the pipeline stages.

    Initial fields (set by PipelineManager before the first stage):
        url, job_id, hw_info, device, settings

    Each stage reads its inputs and writes its outputs as typed fields.
    """

    # ── Immutable inputs (set once by PipelineManager) ──────────────
    url: str = ""
    job_id: str = ""
    hw_info: HardwareInfo | None = None
    device: str = "cpu"
    settings: JobSettings | None = None

    # ── S01 Download ────────────────────────────────────────────────
    input_video: str | None = None
    """Path to the downloaded (or local) video file."""

    # ── S02 Extract Audio ───────────────────────────────────────────
    audio_path: str | None = None
    """Path to the extracted full audio track."""

    audio_duration: float = 0.0
    """Duration of the audio in seconds."""

    # ── S03 Prepare Audio (separation) ──────────────────────────────
    # Uses audio_path, may update it in-place.

    # ── S04 STT ─────────────────────────────────────────────────────
    segments: list[dict[str, Any]] | None = None
    """Transcribed segments: list of dicts with 'start', 'end', 'text', etc."""

    segments_file: str | None = None
    """Path to the JSON file with saved segments."""

    source_language: str = ""
    """Auto-detected source language code (e.g. 'en', 'ru')."""

    # ── S05 Translate ───────────────────────────────────────────────
    translated_file: str | None = None
    """Path to the JSON file with translated segments."""

    target_language: str = ""
    """Target language code used for translation."""

    # ── S06 TTS ─────────────────────────────────────────────────────
    tts_files: list[str | None] | None = None
    """List of generated TTS audio file paths (one per segment, None if skipped)."""

    # ── S07 Align ───────────────────────────────────────────────────
    aligned_voice_path: str | None = None
    """Path to the time-aligned dubbed voice track."""

    cut_bg_audio_path: str | None = None
    """Path to the background audio after jump-cut editing (optional)."""

    video_edits: list[Any] | None = None
    """List of video edit instructions for jump-cut mode (optional)."""

    # ── S08 Mix ─────────────────────────────────────────────────────
    final_audio_path: str | None = None
    """Path to the final mixed audio (dub + background)."""

    # ── S09 Mux ─────────────────────────────────────────────────────
    output_video: str | None = None
    """Path to the final output video file."""

    # ── Dict compatibility layer ────────────────────────────────────
    # These methods allow stages to continue using dict-style access
    # during gradual migration to typed attribute access.

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"PipelineContext has no field '{key}'. "
                       f"Available: {[f.name for f in self.__dataclass_fields__.values()]}")

    def __setitem__(self, key: str, value: Any) -> None:
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise KeyError(f"PipelineContext has no field '{key}'. "
                           f"Cannot add arbitrary keys — define the field first.")

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) and getattr(self, key) is not None

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            value = getattr(self, key)
            if value is not None:
                return value
        return default
