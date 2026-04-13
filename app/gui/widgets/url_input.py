"""
URL input widget with validation and paste button.
"""
import re
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QClipboard

from app.gui.theme import COLORS
from app.config import settings
from app.i18n import language_manager, tr


YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]{11}"
)


class URLInput(QWidget):
    """URL input field with validation and start button."""

    url_submitted = Signal(str)  # emitted when user clicks Start
    state_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # URL input field
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("")
        self._url_input.setMinimumHeight(44)
        self._url_input.textChanged.connect(self._on_text_changed)
        self._url_input.returnPressed.connect(self._on_start)
        
        layout.addWidget(self._url_input, 1)

        # Paste button
        self._paste_btn = QPushButton("📋")
        self._paste_btn.setObjectName("btn_secondary")
        self._paste_btn.setFixedSize(44, 44)
        self._paste_btn.setToolTip("")
        self._paste_btn.clicked.connect(self._paste_from_clipboard)
        layout.addWidget(self._paste_btn)

        # Start button
        self._start_btn = QPushButton("")
        self._start_btn.setMinimumHeight(44)
        self._start_btn.setFixedWidth(120)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        layout.addWidget(self._start_btn)

        # Validation label
        self._validation_label = QLabel("")
        self._validation_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")

        # Устанавливаем текст после создания всех виджетов,
        # так как setText вызовет _on_text_changed, который обновляет _start_btn
        if getattr(settings, "last_url", ""):
            self._url_input.setText(settings.last_url)

    def retranslate_ui(self):
        self._url_input.setPlaceholderText(
            tr("url.placeholder", default="🔗 Paste a YouTube video link...")
        )
        self._url_input.setToolTip(
            tr(
                "url.input_tooltip",
                default=(
                    "Paste or type a full YouTube video link here. "
                    "The Start button becomes available as soon as the link is recognized."
                ),
            )
        )
        self._paste_btn.setToolTip(
            tr(
                "url.paste_tooltip_detail",
                default="Take the current text from the clipboard and place it into the link field.",
            )
        )
        self._start_btn.setText(
            f"▶ {tr('common.start', default='Start')}"
        )
        self._update_start_button_tooltip()

    def _on_text_changed(self, text: str):
        """Validate URL on text change."""
        is_valid = bool(YOUTUBE_PATTERN.search(text.strip()))
        self._start_btn.setEnabled(is_valid)

        if text.strip() and not is_valid:
            self._url_input.setStyleSheet(f"border-color: {COLORS['warning']};")
        elif is_valid:
            self._url_input.setStyleSheet(f"border-color: {COLORS['success']};")
        else:
            self._url_input.setStyleSheet("")
        self._update_start_button_tooltip(is_valid=is_valid)
        self.state_changed.emit()

    def _paste_from_clipboard(self):
        """Paste URL from clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self._url_input.setText(text.strip())

    def _on_start(self):
        """Emit the URL when start is clicked."""
        url = self._url_input.text().strip()
        if YOUTUBE_PATTERN.search(url):
            settings.last_url = url
            settings.save()
            self.url_submitted.emit(url)

    def paste_from_clipboard(self):
        """Public wrapper for menu actions."""
        self._paste_from_clipboard()

    def submit_current_url(self):
        """Public wrapper for menu actions."""
        self._on_start()

    def focus_input(self):
        """Move focus to the URL field."""
        self._url_input.setFocus()
        self._url_input.selectAll()

    def get_url(self) -> str:
        return self._url_input.text().strip()

    def has_valid_url(self) -> bool:
        """Return True when the current text matches a supported YouTube URL."""
        return bool(YOUTUBE_PATTERN.search(self._url_input.text().strip()))

    def is_input_enabled(self) -> bool:
        """Return True when the editable controls are available."""
        return self._url_input.isEnabled()

    def set_enabled(self, enabled: bool):
        """Enable/disable the input."""
        self._url_input.setEnabled(enabled)
        self._paste_btn.setEnabled(enabled)
        self._start_btn.setEnabled(enabled and bool(YOUTUBE_PATTERN.search(self._url_input.text().strip())))
        self._update_start_button_tooltip()
        self.state_changed.emit()

    def clear(self):
        self._url_input.clear()

    def _update_start_button_tooltip(self, is_valid: bool | None = None):
        if is_valid is None:
            is_valid = self.has_valid_url()

        enabled = self._url_input.isEnabled()
        if enabled and is_valid:
            text = tr(
                "url.start_tooltip_ready",
                default=(
                    "Start downloading, transcription, translation, voice generation, "
                    "and final assembly for the current video."
                ),
            )
        else:
            text = tr(
                "url.start_tooltip_waiting",
                default="Enter a valid YouTube video link to unlock processing.",
            )
        self._start_btn.setToolTip(text)
