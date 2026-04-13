"""
Circular progress ring widget with percentage display.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QConicalGradient

from app.gui.theme import COLORS


class ProgressRing(QWidget):
    """A circular progress indicator with percentage text."""

    def __init__(self, size: int = 100, line_width: int = 8, parent=None):
        super().__init__(parent)
        self._size = size
        self._line_width = line_width
        self._progress = 0.0  # 0-100
        self._text = ""
        self.setFixedSize(size, size)

    def set_progress(self, value: float):
        """Set progress value (0-100)."""
        self._progress = max(0.0, min(100.0, value))
        self.update()

    def set_text(self, text: str):
        """Set center text override."""
        self._text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = self._line_width / 2 + 2
        rect = QRectF(margin, margin, self._size - 2 * margin, self._size - 2 * margin)

        # Background ring
        bg_pen = QPen(QColor(COLORS["bg_input"]), self._line_width)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress arc
        if self._progress > 0:
            gradient = QConicalGradient(rect.center(), 90)
            gradient.setColorAt(0.0, QColor(COLORS["accent"]))
            gradient.setColorAt(0.5, QColor(COLORS["accent_light"]))
            gradient.setColorAt(1.0, QColor(COLORS["accent"]))

            progress_pen = QPen(QColor(COLORS["accent"]), self._line_width)
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)

            span = int(-self._progress / 100.0 * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

        # Center text
        text = self._text if self._text else f"{int(self._progress)}%"
        font = QFont("Segoe UI", max(12, self._size // 6))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(COLORS["text_primary"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
