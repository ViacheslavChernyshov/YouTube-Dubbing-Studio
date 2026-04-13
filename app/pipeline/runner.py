"""
Pipeline runner — orchestrates all pipeline stages sequentially without any GUI dependencies.

It executes the stages, accumulates the context, and uses standard Python callbacks
to report progress and state, allowing it to be used in CLI, web servers, or GUI apps.
"""
import uuid
import shutil
import logging
import threading
from pathlib import Path
from typing import Callable, Any

from app.config import JOBS_DIR, JobSettings, DEFAULT_CLEANUP_TEMP_FILES
from app.hardware import HardwareInfo
from app.pipeline.context import PipelineContext
from app.pipeline.base_stage import BaseStage, PipelineCancelled
from app.i18n import tr


def cleanup_job_dir(
    job_dir: Path,
    keep_names: set[str],
    logger: logging.Logger,
) -> tuple[int, int]:
    """Delete intermediate files from a job directory and return removal counts."""
    removed_files = 0
    removed_dirs = 0
    resolved_job_dir = job_dir.resolve()

    for entry in list(job_dir.iterdir()):
        if entry.name in keep_names:
            continue

        try:
            resolved_entry = entry.resolve()
            if resolved_entry != resolved_job_dir and resolved_job_dir not in resolved_entry.parents:
                logger.warning(f"Cleanup skip outside job dir: {entry}")
                continue

            if entry.is_dir():
                shutil.rmtree(entry)
                removed_dirs += 1
            elif entry.exists():
                entry.unlink()
                removed_files += 1
        except Exception as exc:
            logger.warning(f"Cleanup skip {entry.name}: {exc}")

    return removed_files, removed_dirs


class PipelineRunner:
    """Runs the complete dubbing pipeline sequentially (blocking)."""

    def __init__(
        self,
        url: str,
        hw_info: HardwareInfo,
        job_settings: JobSettings,
        logger: logging.Logger,
    ):
        self._url = url
        self._hw_info = hw_info
        self._settings = job_settings
        self._logger = logger
        self._cancel_event = threading.Event()
        self._job_id = str(uuid.uuid4())[:8]
        self._job_dir = JOBS_DIR / self._job_id
        self._stages: list[BaseStage] = []
        
        # Callbacks intended to be overridden by the caller
        self.on_stage_started: Callable[[int], None] = lambda idx: None
        self.on_stage_progress: Callable[[int, float, str], None] = lambda idx, pct, msg: None
        self.on_stage_completed: Callable[[int], None] = lambda idx: None
        self.on_stage_error: Callable[[int, str], None] = lambda idx, err: None
        self.on_segments_ready: Callable[[list, str], None] = lambda segments, lang: None
        self.on_pipeline_done: Callable[[str], None] = lambda out_path: None

    def cancel(self):
        """Request pipeline cancellation."""
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def job_dir(self) -> Path:
        return self._job_dir

    @property
    def job_settings(self) -> JobSettings:
        return self._settings

    def _build_stages(self) -> list[BaseStage]:
        """Instantiate all pipeline stages."""
        from app.pipeline.stages.s01_download import DownloadStage
        from app.pipeline.stages.s02_extract_audio import ExtractAudioStage
        from app.pipeline.stages.s03_separate import PrepareAudioStage
        from app.pipeline.stages.s04_stt import STTStage
        from app.pipeline.stages.s05_translate import TranslateStage
        from app.pipeline.stages.s06_tts import TTSStage
        from app.pipeline.stages.s07_align import AlignStage
        from app.pipeline.stages.s08_mix import MixStage
        from app.pipeline.stages.s09_mux import MuxStage

        return [
            DownloadStage(),
            ExtractAudioStage(),
            PrepareAudioStage(),
            STTStage(),
            TranslateStage(),
            TTSStage(),
            AlignStage(),
            MixStage(),
            MuxStage(),
        ]

    def run(self):
        """Execute the pipeline sequentially (blocking)."""
        # Create job directory
        self._job_dir.mkdir(parents=True, exist_ok=True)
        (self._job_dir / "tts_segments").mkdir(exist_ok=True)

        self._logger.info(tr("pipeline.job_started", default="Job ID: {job_id} | Directory: {dir}", job_id=self._job_id, dir=self._job_dir))

        # Build stages
        self._stages = self._build_stages()

        # Context accumulates results between stages
        context = PipelineContext(
            url=self._url,
            job_id=self._job_id,
            hw_info=self._hw_info,
            device=self._hw_info.device,
            settings=self._settings,
        )

        for idx, stage in enumerate(self._stages):
            if self._cancel_event.is_set():
                self._logger.warning(tr("pipeline.cancelled", default="Pipeline cancelled"))
                return

            # Configure stage
            stage.set_logger(self._logger)
            stage.set_cancel_event(self._cancel_event)
            stage.set_progress_callback(
                lambda pct, msg, i=idx: self.on_stage_progress(i, pct, msg)
            )

            # Callback stage start
            self.on_stage_started(idx)

            try:
                context = stage.execute(self._job_dir, context)
            except PipelineCancelled:
                self._logger.warning(tr("pipeline.stopped_at_stage", default="Stopped at stage {stage}", stage=idx + 1))
                return
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self.on_stage_error(idx, error_msg)
                self._logger.error(f"Pipeline failed at stage {idx + 1}: {error_msg}")
                return

            # Callback stage complete
            self.on_stage_completed(idx)

            # Dispatch segments data after translate stage (idx=4) or STT (idx=3)
            if idx in (3, 4) and "segments" in context:
                source_lang = context.get("source_language", "")
                self.on_segments_ready(context["segments"], source_lang)

        # Pipeline done
        output_path = str(context.output_video or self._job_dir / "output.mp4")
        self.on_pipeline_done(output_path)

        # Cleanup temp files if enabled
        if DEFAULT_CLEANUP_TEMP_FILES:
            self._cleanup(context)

    def _cleanup(self, context: PipelineContext):
        """Remove intermediate files while keeping user-facing artifacts."""
        keep = {"output.mp4"}
        for key in ("input_video", "segments_file", "translated_file"):
            path_str = context.get(key)
            if not path_str:
                continue
            path = Path(path_str)
            try:
                if path.resolve().parent == self._job_dir.resolve():
                    keep.add(path.name)
            except Exception:
                continue

        try:
            removed_files, removed_dirs = cleanup_job_dir(self._job_dir, keep, self._logger)
            self._logger.info(
                tr("pipeline.cleanup_done", default="Cleanup: removed {files} files and {dirs} folders; kept {kept}", files=removed_files, dirs=removed_dirs, kept=', '.join(sorted(keep)))
            )
        except Exception as e:
            self._logger.warning(f"Cleanup error: {e}")
