"""
Log viewer widget — real-time scrolling log output.
"""
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QColor, QFont

from app.gui.theme import COLORS


LEVEL_COLORS = {
    "debug": COLORS["text_muted"],
    "info": COLORS["text_secondary"],
    "warning": COLORS["warning"],
    "error": COLORS["error"],
    "critical": COLORS["error"],
}


class LogViewer(QPlainTextEdit):
    """Real-time log output viewer with color-coded levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(2000)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        font = QFont("Cascadia Code", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def append_log(self, message: str, level: str = "info"):
        """Append a log message with color-coded level."""
        color = LEVEL_COLORS.get(level, COLORS["text_secondary"])

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))

        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + "\n", fmt)

        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self):
        """Clear all log content."""
        self.clear()
