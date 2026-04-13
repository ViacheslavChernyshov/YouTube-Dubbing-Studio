"""
Shared tooltip helpers for the desktop UI.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle


class TooltipProxyStyle(QProxyStyle):
    """Qt style proxy that applies a consistent tooltip delay."""

    def __init__(self, base_style=None, *, wake_up_delay_ms: int = 1000):
        super().__init__(base_style)
        self._wake_up_delay_ms = wake_up_delay_ms

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return self._wake_up_delay_ms
        return super().styleHint(hint, option, widget, returnData)


def install_tooltip_style(app: QApplication, *, wake_up_delay_ms: int = 1000) -> None:
    """Install the shared tooltip delay for the whole application."""
    app.setStyle(TooltipProxyStyle(app.style(), wake_up_delay_ms=wake_up_delay_ms))
