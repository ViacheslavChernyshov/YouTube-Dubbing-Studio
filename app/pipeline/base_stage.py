"""
Abstract base class for pipeline stages.
"""
import time
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

from app.utils.logger import log_stage
from app.pipeline.context import PipelineContext
from app.i18n import tr


class BaseStage(ABC):
    """Abstract base stage for the dubbing pipeline."""

    def __init__(
        self,
        stage_number: int,
        name: str,
        description: str = "",
    ):
        self.stage_number = stage_number
        self.name = name
        self.description = description
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        self._cancel_event = threading.Event()
        self._start_time: Optional[float] = None
        self._logger: Optional[logging.Logger] = None

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback for progress updates: callback(percent, message)."""
        self._progress_callback = callback

    def set_cancel_event(self, event: threading.Event):
        """Set the cancellation event."""
        self._cancel_event = event

    def set_logger(self, logger: logging.Logger):
        """Set the logger instance."""
        self._logger = logger

    def report_progress(self, percent: float, message: str = ""):
        """Report progress to the pipeline manager."""
        if self._progress_callback:
            self._progress_callback(percent, message)

    def log(self, message: str, level: int = logging.INFO):
        """Log a message with stage context."""
        if self._logger:
            log_stage(self._logger, self.name, message, level)

    def is_cancelled(self) -> bool:
        """Check if the pipeline has been cancelled."""
        return self._cancel_event.is_set()

    def check_cancelled(self):
        """Raise exception if cancelled."""
        if self.is_cancelled():
            raise PipelineCancelled(tr("pipeline.stage_cancelled", default="Cancelled at stage: {name}", name=self.name))

    def execute(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        """
        Execute the stage with timing and error handling.
        Returns updated context.
        """
        self._start_time = time.time()
        self.log(tr("pipeline.stage_start", default="Starting stage: {name}", name=self.name))
        self.report_progress(0, tr("pipeline.stage_starting", default="Starting..."))

        try:
            result = self.run(job_dir, context)
            elapsed = time.time() - self._start_time
            self.log(tr("pipeline.stage_done", default="Completed in {elapsed:.1f}s", elapsed=elapsed))
            self.report_progress(100, tr("pipeline.stage_ready", default="Ready"))
            return result
        except PipelineCancelled:
            self.log(tr("pipeline.cancelled_by_user", default="Cancelled by user"), logging.WARNING)
            raise
        except Exception as e:
            elapsed = time.time() - self._start_time
            self.log(tr("pipeline.stage_error", default="Error after {elapsed:.1f}s: {error}", elapsed=elapsed, error=str(e)), logging.ERROR)
            raise

    @abstractmethod
    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        """
        Implement the stage logic.
        
        Args:
            job_dir: Path to the job directory
            context: PipelineContext with accumulated results from previous stages
            
        Returns:
            Updated PipelineContext with this stage's outputs
        """
        ...


class PipelineCancelled(Exception):
    """Raised when the pipeline is cancelled by the user."""
    pass
