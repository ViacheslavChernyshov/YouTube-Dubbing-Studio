"""
Pipeline view widget — displays all 9 stages with overall progress.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QFrame
)
from PySide6.QtCore import Qt

from app.config import NUM_STAGES, get_stage_names
from app.gui.theme import COLORS
from app.gui.widgets.stage_card import StageCard
from app.gui.widgets.progress_ring import ProgressRing
from app.i18n import language_manager, tr
from app.utils.time_utils import ETACalculator


class PipelineView(QWidget):
    """Visualization of the entire dubbing pipeline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stage_cards: list[StageCard] = []
        self._stage_names = get_stage_names()
        self._eta = ETACalculator(total_stages=NUM_STAGES)
        self._current_stage_idx: int | None = None
        self._error_stage_idx: int | None = None
        self._last_output_path = ""
        self._last_segment_text = ""
        self._done = False
        self._setup_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ── Header row: progress ring + info ──
        header = QHBoxLayout()
        header.setSpacing(16)

        self._progress_ring = ProgressRing(size=60, line_width=4)
        header.addWidget(self._progress_ring)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        info_layout.addWidget(self._title_label)

        self._eta_label = QLabel("")
        self._eta_label.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']};"
        )
        info_layout.addWidget(self._eta_label)

        self._segment_label = QLabel("")
        self._segment_label.setStyleSheet(
            f"font-size: 11px; color: {COLORS['text_muted']};"
        )
        self._segment_label.setWordWrap(True)
        info_layout.addWidget(self._segment_label)

        info_layout.addStretch()
        header.addLayout(info_layout, 1)
        layout.addLayout(header)

        # ── Overall progress bar ──
        self._overall_progress = QProgressBar()
        self._overall_progress.setRange(0, 100)
        self._overall_progress.setValue(0)
        self._overall_progress.setTextVisible(False)
        self._overall_progress.setFixedHeight(6)
        layout.addWidget(self._overall_progress)

        # ── Stage cards in scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        cards_widget = QWidget()
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 4, 0, 4)
        cards_layout.setSpacing(4)

        for i, name in enumerate(self._stage_names):
            card = StageCard(i + 1, name)
            self._stage_cards.append(card)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        layout.addWidget(scroll, 1)
        self.retranslate_ui()

    # ── Public API ────────────────────────────────────────

    def reset(self):
        """Reset all cards and progress."""
        for card in self._stage_cards:
            card.reset()
        self._current_stage_idx = None
        self._error_stage_idx = None
        self._last_output_path = ""
        self._last_segment_text = ""
        self._done = False
        self._progress_ring.set_progress(0)
        self._overall_progress.setValue(0)
        self._title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        self._title_label.setText(tr("pipeline.title_ready", default="Ready to work"))
        self._eta_label.setText("")
        self._segment_label.setText("")
        self._eta = ETACalculator(total_stages=NUM_STAGES)

    def start_pipeline(self):
        """Initialize the pipeline display."""
        self.reset()
        self._eta.start()
        self._title_label.setText(tr("pipeline.title_started", default="Processing started..."))

    def set_stage_started(self, stage_idx: int):
        """Mark a stage as running (0-based index)."""
        if 0 <= stage_idx < len(self._stage_cards):
            self._current_stage_idx = stage_idx
            self._error_stage_idx = None
            self._done = False
            self._stage_cards[stage_idx].set_state(StageCard.RUNNING)
            self._eta.start_stage(stage_idx)
            self._title_label.setStyleSheet(
                f"font-size: 14px; font-weight: 700; color: {COLORS['text_primary']};"
            )
            self._title_label.setText(
                tr(
                    "pipeline.stage_title",
                    default="Stage {current}/{total}: {stage}",
                    current=stage_idx + 1,
                    total=NUM_STAGES,
                    stage=self._stage_names[stage_idx],
                )
            )
            self._update_overall_progress(stage_idx)

    def set_stage_progress(self, stage_idx: int, percent: float, message: str = ""):
        """Update progress for a specific stage."""
        if 0 <= stage_idx < len(self._stage_cards):
            self._stage_cards[stage_idx].set_progress(percent, message)
            elapsed = self._eta.get_stage_elapsed()
            self._stage_cards[stage_idx].set_elapsed(
                ETACalculator.format_elapsed(elapsed)
            )
            self._update_overall_progress(stage_idx, percent)
            self._update_eta()

    def set_stage_completed(self, stage_idx: int):
        """Mark a stage as completed."""
        if 0 <= stage_idx < len(self._stage_cards):
            self._stage_cards[stage_idx].set_state(StageCard.COMPLETED)
            self._stage_cards[stage_idx].set_progress(100)
            elapsed = self._eta.get_stage_elapsed()
            self._stage_cards[stage_idx].set_elapsed(
                ETACalculator.format_elapsed(elapsed)
            )
            self._eta.end_stage()
            self._update_overall_progress(stage_idx + 1)
            self._update_eta()

    def set_stage_error(self, stage_idx: int, error_msg: str):
        """Mark a stage as failed."""
        if 0 <= stage_idx < len(self._stage_cards):
            self._error_stage_idx = stage_idx
            self._done = False
            self._stage_cards[stage_idx].set_state(StageCard.ERROR)
            self._stage_cards[stage_idx].set_progress(
                self._stage_cards[stage_idx]._progress, error_msg
            )
            self._title_label.setText(
                tr(
                    "pipeline.error_stage",
                    default="❌ Error at stage {stage}",
                    stage=stage_idx + 1,
                )
            )
            self._title_label.setStyleSheet(
                f"font-size: 16px; font-weight: 700; color: {COLORS['error']};"
            )

    def set_pipeline_done(self, output_path: str):
        """Mark entire pipeline as completed."""
        self._done = True
        self._last_output_path = output_path
        self._progress_ring.set_progress(100)
        self._overall_progress.setValue(100)
        elapsed = self._eta.get_overall_elapsed()
        self._title_label.setText(tr("pipeline.done", default="✅ Dubbing completed!"))
        self._title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {COLORS['success']};"
        )
        self._eta_label.setText(
            tr(
                "pipeline.elapsed",
                default="Time: {elapsed}",
                elapsed=ETACalculator.format_elapsed(elapsed),
            )
        )
        self._segment_label.setText(
            tr("pipeline.output_prefix", default="📁 {path}", path=output_path)
        )

    def set_current_segment(self, text: str):
        """Show current processing segment text."""
        self._last_segment_text = text
        self._segment_label.setText(
            tr("pipeline.segment_prefix", default="📝 {text}", text=text)
        )

    def retranslate_ui(self):
        self._stage_names = get_stage_names()
        for index, name in enumerate(self._stage_names):
            if index < len(self._stage_cards):
                self._stage_cards[index].set_stage_name(name)
        self._progress_ring.setToolTip(
            tr(
                "pipeline.progress_ring_tip",
                default="Overall progress of the entire dubbing pipeline from 0% to 100%.",
            )
        )
        self._overall_progress.setToolTip(
            tr(
                "pipeline.progress_bar_tip",
                default="Linear progress of all stages combined, including the active step.",
            )
        )
        self._segment_label.setToolTip(
            tr(
                "pipeline.segment_tip",
                default="Shows the current text fragment or the final output path, depending on the active stage.",
            )
        )

        if self._done and self._last_output_path:
            self.set_pipeline_done(self._last_output_path)
            return

        if self._error_stage_idx is not None:
            self._title_label.setText(
                tr(
                    "pipeline.error_stage",
                    default="❌ Error at stage {stage}",
                    stage=self._error_stage_idx + 1,
                )
            )
            return

        if self._current_stage_idx is not None:
            self._title_label.setText(
                tr(
                    "pipeline.stage_title",
                    default="Stage {current}/{total}: {stage}",
                    current=self._current_stage_idx + 1,
                    total=NUM_STAGES,
                    stage=self._stage_names[self._current_stage_idx],
                )
            )
            if self._last_segment_text:
                self._segment_label.setText(
                    tr("pipeline.segment_prefix", default="📝 {text}", text=self._last_segment_text)
                )
            self._update_eta()
            return

        self._title_label.setText(tr("pipeline.title_ready", default="Ready to work"))

    # ── Private helpers ───────────────────────────────────

    def _update_overall_progress(self, completed_stages: int, current_pct: float = 0.0):
        """Update overall progress based on completed stages."""
        if NUM_STAGES == 0:
            return
        overall = (completed_stages / NUM_STAGES) * 100
        if current_pct > 0 and completed_stages < NUM_STAGES:
            stage_weight = 100.0 / NUM_STAGES
            overall = ((completed_stages) / NUM_STAGES) * 100 + (current_pct / 100.0) * stage_weight
        self._overall_progress.setValue(int(overall))
        self._progress_ring.set_progress(overall)

    def _update_eta(self):
        """Update ETA display."""
        remaining = self._eta.estimate_remaining()
        self._eta_label.setText(
            tr(
                "pipeline.remaining",
                default="⏱ Remaining: {remaining}",
                remaining=ETACalculator.format_time(remaining),
            )
        )
