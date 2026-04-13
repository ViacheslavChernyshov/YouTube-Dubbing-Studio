"""
Pipeline Controller — handles the lifecycle of the dubbing pipeline from the GUI.

Extracted from MainWindow to isolate business logic from UI assembly.
"""
from pathlib import Path
from PySide6.QtCore import QObject, Slot
from typing import Callable

from app.config import settings
from app.hardware import HardwareInfo
from app.pipeline.manager import PipelineManager
from app.gui.widgets.pipeline_view import PipelineView
from app.gui.widgets.log_viewer import LogViewer
from app.gui.widgets.url_input import URLInput
from app.gui.widgets.settings_panel import SettingsPanel


class PipelineController(QObject):
    """Manages the creation, execution, and state handling of the UI pipeline."""

    def __init__(
        self,
        parent: QObject,
        logger,
        hw_info: HardwareInfo,
        url_input: URLInput,
        settings_panel: SettingsPanel,
        pipeline_view: PipelineView,
        log_viewer: LogViewer,
        on_status_changed: Callable[[str, str], None],  # (key, default_text)
        on_state_changed: Callable[[], None],
        on_segments_ready: Callable[[list, str], None],
        on_job_dir_available: Callable[[Path], None],
        on_output_path_available: Callable[[str], None],
    ):
        super().__init__(parent)
        self._logger = logger
        self._hw_info = hw_info
        self._url_input = url_input
        self._settings_panel = settings_panel
        self._pipeline_view = pipeline_view
        self._log_viewer = log_viewer

        self._on_status_changed = on_status_changed
        self._on_state_changed = on_state_changed
        self._on_segments_ready = on_segments_ready
        self._on_job_dir_available = on_job_dir_available
        self._on_output_path_available = on_output_path_available

        self._pipeline: PipelineManager | None = None
        self._cancel_requested = False
        self._had_error = False
        self._succeeded = False

        # Connect url input
        self._url_input.url_submitted.connect(self.start)

    @property
    def is_running(self) -> bool:
        return self._pipeline is not None and self._pipeline.isRunning()

    @property
    def pipeline(self) -> PipelineManager | None:
        return self._pipeline

    @Slot(str)
    def start(self, url: str):
        """Start the dubbing pipeline."""
        if self.is_running:
            self._logger.warning("Pipeline is already running.")
            return

        self._logger.info(f"Processing started: {url}")
        
        self._cancel_requested = False
        self._had_error = False
        self._succeeded = False
        
        self._log_viewer.clear_logs()
        self._pipeline_view.start_pipeline()
        self._on_status_changed("status.processing", "Processing...")
        self._on_state_changed()

        # Build pipeline using immutable snapshot
        self._pipeline = PipelineManager(
            url=url,
            hw_info=self._hw_info,
            job_settings=settings.snapshot(),
            logger=self._logger,
        )

        # Connect signals
        self._pipeline.signals.stage_started.connect(self._pipeline_view.set_stage_started)
        self._pipeline.signals.stage_progress.connect(self._on_stage_progress)
        self._pipeline.signals.stage_completed.connect(self._pipeline_view.set_stage_completed)
        self._pipeline.signals.stage_completed.connect(self._on_stage_completed)
        self._pipeline.signals.stage_error.connect(self._on_stage_error)
        self._pipeline.signals.pipeline_done.connect(self._on_pipeline_done)
        self._pipeline.signals.current_segment.connect(self._pipeline_view.set_current_segment)
        
        # Connect callbacks
        self._pipeline.signals.segments_ready.connect(self._on_segments_ready_internal)
        self._pipeline.finished.connect(self._on_pipeline_finished)
        
        # Expose job directory immediately
        if hasattr(self._pipeline, "job_dir"):
            self._on_job_dir_available(self._pipeline.job_dir)
            
        self._pipeline.start()

    @Slot()
    def stop(self):
        """Stop the pipeline."""
        if self.is_running:
            self._cancel_requested = True
            self._logger.warning("Stop requested by user...")
            self._pipeline.cancel()
            self._on_status_changed("status.stopping", "Stopping...")
            self._on_state_changed()

    def confirm_stop(self) -> bool:
        """Helper to conditionally stop pipeline and wait if needed."""
        if self.is_running:
            self._pipeline.cancel()
            self._pipeline.wait(3000)
            return True
        return False

    # ── Internal Slots ──────────────────────────────────────────────────

    @Slot(int, float, str)
    def _on_stage_progress(self, stage_idx: int, percent: float, message: str):
        self._pipeline_view.set_stage_progress(stage_idx, percent, message)

    @Slot(int, str)
    def _on_stage_error(self, stage_idx: int, error_msg: str):
        self._had_error = True
        self._pipeline_view.set_stage_error(stage_idx, error_msg)
        self._logger.error(f"Stage {stage_idx + 1} error: {error_msg}")
        self._on_status_changed("status.error_stage", f"Error at stage {stage_idx + 1}")
        self._on_state_changed()

    @Slot(str)
    def _on_pipeline_done(self, output_path: str):
        self._succeeded = True
        self._pipeline_view.set_pipeline_done(output_path)
        self._logger.info(f"Done! Result: {output_path}")
        self._on_status_changed("status.done", "✅ Dubbing completed!")
        self._on_output_path_available(output_path)
        self._on_state_changed()

    @Slot()
    def _on_pipeline_finished(self):
        if self._cancel_requested and not self._had_error and not self._succeeded:
            self._on_status_changed("status.stopped", "Stopped")
        self._pipeline = None
        self._on_state_changed()

    @Slot(list, str)
    def _on_segments_ready_internal(self, segments: list, source_lang: str):
        self._on_segments_ready(segments, source_lang)
        self._on_state_changed()

    @Slot(int)
    def _on_stage_completed(self, stage_idx: int):
        self._on_state_changed()
