"""
Structured logging with stage prefixes, file + GUI output.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from app.config import LOGS_DIR


def _get_console_stream():
    """Return a stdout stream that tolerates Windows console encoding quirks."""
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
    return stream


class StageFormatter(logging.Formatter):
    """Custom formatter with stage prefix and colors for console."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors=True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record):
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        stage = getattr(record, "stage", "")
        stage_prefix = f"[{stage}] " if stage else ""

        msg = f"{ts} {stage_prefix}{record.getMessage()}"

        if self.use_colors:
            color = self.COLORS.get(record.levelno, "")
            msg = f"{color}{msg}{self.RESET}"

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg += f"\n{record.exc_text}"

        return msg


class GUILogHandler(logging.Handler):
    """Handler that forwards log records to a GUI callback."""

    def __init__(self, callback: Callable[[str, str], None]):
        super().__init__()
        self._callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            self._callback(msg, level)
        except Exception:
            self.handleError(record)


def setup_logger(
    name: str = "dubbing",
    log_file: Optional[str] = None,
    gui_callback: Optional[Callable] = None,
) -> logging.Logger:
    """Create and configure the application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler(_get_console_stream())
    console.setLevel(logging.INFO)
    console.setFormatter(StageFormatter(use_colors=True))
    logger.addHandler(console)

    # File handler
    if log_file is None:
        log_file = LOGS_DIR / f"dubbing_{datetime.now():%Y%m%d_%H%M%S}.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StageFormatter(use_colors=False))
    logger.addHandler(file_handler)

    # GUI handler
    if gui_callback:
        gui_handler = GUILogHandler(gui_callback)
        gui_handler.setLevel(logging.INFO)
        gui_handler.setFormatter(StageFormatter(use_colors=False))
        logger.addHandler(gui_handler)

    return logger


def get_logger(name: str = "dubbing") -> logging.Logger:
    """Get existing logger or create a basic one."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


def log_stage(logger: logging.Logger, stage: str, message: str, level=logging.INFO):
    """Log a message with stage context."""
    logger.log(level, message, extra={"stage": stage})
