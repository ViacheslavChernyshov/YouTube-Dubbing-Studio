"""
Stage card widget — individual pipeline stage visualization.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPen, QFont

from app.gui.theme import COLORS


class StageCard(QWidget):
    """A card representing one pipeline stage with status, progress, and animation."""

    # States
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"

    STATE_COLORS = {
        PENDING: COLORS["pending"],
        RUNNING: COLORS["running"],
        COMPLETED: COLORS["success"],
        ERROR: COLORS["error"],
        SKIPPED: COLORS["text_muted"],
    }

    STATE_ICONS = {
        PENDING: "⏳",
        RUNNING: "⚡",
        COMPLETED: "✅",
        ERROR: "❌",
        SKIPPED: "⏭️",
    }

    def __init__(self, stage_number: int, stage_name: str, parent=None):
        super().__init__(parent)
        self._stage_number = stage_number
        self._stage_name = stage_name
        self._state = self.PENDING
        self._progress = 0.0
        self._message = ""
        self._elapsed = ""
        self._glow_opacity = 0.0
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._animate_glow)
        self._glow_increasing = True

        self.setFixedHeight(36)
        self.setMinimumWidth(180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        self._icon_label = QLabel(self.STATE_ICONS[self.PENDING])
        self._icon_label.setFixedWidth(20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)

        self._number_label = QLabel(f"{self._stage_number}.")
        self._number_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700;")
        self._number_label.setFixedWidth(18)
        layout.addWidget(self._number_label)

        self._name_label = QLabel(self._stage_name)
        self._name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self._name_label)
        
        self._message_label = QLabel("")
        self._message_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(self._message_label, 1)

        self._elapsed_label = QLabel("")
        self._elapsed_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self._elapsed_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._elapsed_label)

    def set_state(self, state: str):
        self._state = state
        self._icon_label.setText(self.STATE_ICONS.get(state, "⏳"))

        if state == self.RUNNING:
            self._glow_timer.start(50)
        elif state in (self.COMPLETED, self.ERROR):
            self._glow_timer.stop()
            self._glow_opacity = 0.0
            self._message_label.setText("")
        else:
            self._glow_timer.stop()
            self._glow_opacity = 0.0

        self.update()

    def set_progress(self, percent: float, message: str = ""):
        self._progress = percent
        if message:
            self._message_label.setText(message)
            self._message_label.setToolTip(message)
        elif percent > 0 and self._state == self.RUNNING:
            self._message_label.setText(f"{int(percent)}%")
            self._message_label.setToolTip("")
        self.update()

    def set_elapsed(self, elapsed_str: str):
        self._elapsed = elapsed_str
        self._elapsed_label.setText(elapsed_str)

    def set_stage_name(self, stage_name: str):
        self._stage_name = stage_name
        self._name_label.setText(stage_name)

    def reset(self):
        self._state = self.PENDING
        self._progress = 0.0
        self._message_label.setText("")
        self._message_label.setToolTip("")
        self._elapsed_label.setText("")
        self._icon_label.setText(self.STATE_ICONS[self.PENDING])
        self._glow_timer.stop()
        self._glow_opacity = 0.0
        self.update()

    def _animate_glow(self):
        step = 0.04
        if self._glow_increasing:
            self._glow_opacity += step
            if self._glow_opacity >= 0.6:
                self._glow_increasing = False
        else:
            self._glow_opacity -= step
            if self._glow_opacity <= 0.1:
                self._glow_increasing = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg_color = QColor(COLORS["bg_card"])
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 6, 6)
        
        # Progress fill
        if self._progress > 0 and self._state != self.COMPLETED:
            fill_width = int(rect.width() * (self._progress / 100.0))
            if fill_width > 0:
                fill_color = QColor(COLORS["accent"])
                fill_color.setAlphaF(0.15)
                painter.setBrush(fill_color)
                painter.drawRoundedRect(rect.adjusted(0, 0, -(rect.width() - fill_width), 0), 6, 6)

        # Border
        state_color = QColor(self.STATE_COLORS.get(self._state, COLORS["pending"]))
        if self._state == self.RUNNING:
            state_color.setAlphaF(0.5 + self._glow_opacity * 0.5)
            pen = QPen(state_color, 1.5)
        elif self._state in (self.COMPLETED, self.ERROR):
            pen = QPen(state_color, 1)
        else:
            pen = QPen(QColor(COLORS["border"]), 1)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)

        # Glow effect
        if self._state == self.RUNNING and self._glow_opacity > 0:
            glow = QColor(COLORS["accent"])
            glow.setAlphaF(self._glow_opacity * 0.1)
            painter.setPen(QPen(glow, 2))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)

        painter.end()
