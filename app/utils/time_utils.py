"""
ETA calculation using exponential moving average.
"""
import time
from typing import Optional


class ETACalculator:
    """Track progress and estimate remaining time."""

    def __init__(self, total_stages: int = 9):
        self.total_stages = total_stages
        self.stage_times: list[float] = []
        self._stage_start: Optional[float] = None
        self._overall_start: Optional[float] = None
        self._current_stage: int = 0
        self._alpha = 0.3  # EMA smoothing factor

    def start(self):
        """Start overall timing."""
        self._overall_start = time.time()

    def start_stage(self, stage_num: int):
        """Mark a stage as started."""
        self._current_stage = stage_num
        self._stage_start = time.time()

    def end_stage(self):
        """Mark current stage as completed."""
        if self._stage_start:
            elapsed = time.time() - self._stage_start
            self.stage_times.append(elapsed)
            self._stage_start = None

    def get_stage_elapsed(self) -> float:
        """Get elapsed time for current stage."""
        if self._stage_start:
            return time.time() - self._stage_start
        return 0.0

    def get_overall_elapsed(self) -> float:
        """Get overall elapsed time."""
        if self._overall_start:
            return time.time() - self._overall_start
        return 0.0

    def estimate_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if not self.stage_times:
            return None

        # Average time per completed stage (EMA)
        avg_time = self.stage_times[0]
        for t in self.stage_times[1:]:
            avg_time = self._alpha * t + (1 - self._alpha) * avg_time

        remaining_stages = self.total_stages - len(self.stage_times)

        # Add remaining time for current stage if running
        current_remaining = 0.0
        if self._stage_start:
            elapsed = self.get_stage_elapsed()
            # Estimate current stage will take avg_time
            current_remaining = max(0, avg_time - elapsed)
            remaining_stages -= 1  # Don't double-count current stage

        return current_remaining + remaining_stages * avg_time

    @staticmethod
    def format_time(seconds: Optional[float]) -> str:
        """Format seconds into human-readable string."""
        if seconds is None:
            return "рассчитывается..."

        seconds = int(seconds)
        if seconds < 60:
            return f"~{seconds} сек"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"~{minutes} мин {secs} сек"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"~{hours} ч {minutes} мин"

    @staticmethod
    def format_elapsed(seconds: float) -> str:
        """Format elapsed time."""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}с"
        elif seconds < 3600:
            return f"{seconds // 60}м {seconds % 60}с"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}ч {m}м"
