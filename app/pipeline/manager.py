"""
Pipeline manager — QThread wrapper for running the PipelineRunner in a GUI context.
"""
import logging
from PySide6.QtCore import QThread
from pathlib import Path

from app.config import JobSettings
from app.hardware import HardwareInfo
from app.pipeline.signals import PipelineSignals
from app.pipeline.runner import PipelineRunner


class PipelineManager(QThread):
    """Runs the PipelineRunner inside a background QThread, emitting Qt signals."""

    def __init__(
        self,
        url: str,
        hw_info: HardwareInfo,
        job_settings: JobSettings,
        logger: logging.Logger,
        parent=None,
    ):
        super().__init__(parent)
        self.signals = PipelineSignals()
        self._runner = PipelineRunner(
            url=url,
            hw_info=hw_info,
            job_settings=job_settings,
            logger=logger,
        )

        # Wire runner callbacks to Qt signals
        self._runner.on_stage_started = self.signals.stage_started.emit
        self._runner.on_stage_progress = self.signals.stage_progress.emit
        self._runner.on_stage_completed = self.signals.stage_completed.emit
        self._runner.on_stage_error = self.signals.stage_error.emit
        self._runner.on_segments_ready = self.signals.segments_ready.emit
        self._runner.on_pipeline_done = self.signals.pipeline_done.emit

    def cancel(self):
        """Request pipeline cancellation."""
        self._runner.cancel()

    @property
    def job_dir(self) -> Path:
        return self._runner.job_dir

    @property
    def job_settings(self) -> JobSettings:
        return self._runner.job_settings

    def run(self):
        """Execute the pipeline (runs in QThread)."""
        self._runner.run()
