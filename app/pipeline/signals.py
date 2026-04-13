"""
Qt signals for pipeline progress reporting.
"""
from PySide6.QtCore import QObject, Signal


class PipelineSignals(QObject):
    """Signals emitted by the pipeline manager to update the GUI."""

    # stage_idx (0-based)
    stage_started = Signal(int)
    # stage_idx, percent (0-100), message
    stage_progress = Signal(int, float, str)
    # stage_idx
    stage_completed = Signal(int)
    # stage_idx, error_message
    stage_error = Signal(int, str)
    # output_path
    pipeline_done = Signal(str)
    # log_message
    log_message = Signal(str)
    # current segment text being processed
    current_segment = Signal(str)
    # segments data ready for transcript viewer (segments_list, source_lang)
    segments_ready = Signal(list, str)
