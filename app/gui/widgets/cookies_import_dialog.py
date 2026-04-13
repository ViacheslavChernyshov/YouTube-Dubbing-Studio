"""
Dialog for importing cookies from clipboard or file into cookies.txt.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.config import get_cookies_file
from app.gui.theme import COLORS
from app.i18n import language_manager, tr
from app.utils.cookies import CookieNormalizationResult, save_normalized_cookie_text


class CookiesImportDialog(QDialog):
    """Import cookies from clipboard or file and normalize them for yt-dlp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._destination_path = get_cookies_file()
        self._saved_result: CookieNormalizationResult | None = None
        self.setMinimumWidth(780)
        self.resize(900, 560)
        self._setup_ui()
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']};"
        )
        layout.addWidget(self._title_label)

        self._intro_label = QLabel("")
        self._intro_label.setWordWrap(True)
        self._intro_label.setObjectName("label_secondary")
        layout.addWidget(self._intro_label)

        destination_row = QHBoxLayout()
        destination_row.setSpacing(8)

        self._destination_label = QLabel("")
        self._destination_label.setStyleSheet(f"font-weight: 600; color: {COLORS['text_primary']};")
        destination_row.addWidget(self._destination_label)

        self._destination_value = QLabel(str(self._destination_path))
        self._destination_value.setWordWrap(True)
        self._destination_value.setObjectName("label_secondary")
        self._destination_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        destination_row.addWidget(self._destination_value, 1)

        layout.addLayout(destination_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self._paste_btn = QPushButton("")
        self._paste_btn.setObjectName("btn_secondary")
        self._paste_btn.clicked.connect(self._paste_from_clipboard)
        actions_row.addWidget(self._paste_btn)

        self._load_btn = QPushButton("")
        self._load_btn.setObjectName("btn_secondary")
        self._load_btn.clicked.connect(self._load_from_file)
        actions_row.addWidget(self._load_btn)

        self._clear_btn = QPushButton("")
        self._clear_btn.setObjectName("btn_secondary")
        actions_row.addWidget(self._clear_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        self._editor = QPlainTextEdit()
        self._editor.setMinimumHeight(340)
        layout.addWidget(self._editor, 1)
        self._clear_btn.clicked.connect(self._editor.clear)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self._cancel_btn = QPushButton("")
        self._cancel_btn.setObjectName("btn_secondary")
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("")
        self._save_btn.clicked.connect(self._save_cookies)
        buttons.addWidget(self._save_btn)

        layout.addLayout(buttons)

    def retranslate_ui(self):
        title = tr("cookies.import.title", default="Import cookies")
        self.setWindowTitle(title)
        self._title_label.setText(title)
        self._intro_label.setText(
            tr(
                "cookies.import.intro",
                default=(
                    "Paste cookies from the clipboard or load a file. "
                    "Supported formats: Netscape cookies.txt, raw Cookie header, and JSON export."
                ),
            )
        )
        self._destination_label.setText(
            tr("cookies.import.destination", default="Destination:")
        )
        self._editor.setPlaceholderText(
            tr(
                "cookies.import.placeholder",
                default="Paste cookies here or load them from a file.",
            )
        )
        self._editor.setToolTip(
            tr(
                "cookies.import.editor_tip",
                default="Paste raw Cookie header, Netscape cookies.txt, or JSON export here before import.",
            )
        )
        self._paste_btn.setText(tr("cookies.import.paste", default="Paste from clipboard"))
        self._paste_btn.setToolTip(
            tr(
                "cookies.import.paste_tip",
                default="Paste copied cookies text from the clipboard into the editor.",
            )
        )
        self._load_btn.setText(tr("cookies.import.load_file", default="Load from file..."))
        self._load_btn.setToolTip(
            tr(
                "cookies.import.load_tip",
                default="Open cookies from a .txt or .json file and place them into the editor.",
            )
        )
        self._clear_btn.setText(tr("cookies.import.clear", default="Clear"))
        self._clear_btn.setToolTip(
            tr(
                "cookies.import.clear_tip",
                default="Clear the editor if you want to paste or load another cookies set.",
            )
        )
        self._cancel_btn.setText(tr("common.cancel", default="Cancel"))
        self._save_btn.setText(tr("action.import_cookies", default="📥 Import cookies..."))
        self._save_btn.setToolTip(
            tr(
                "cookies.import.save_tip",
                default="Normalize the cookies and save them into the app's working cookies.txt file.",
            )
        )

    def _paste_from_clipboard(self):
        app = QApplication.instance()
        clipboard = app.clipboard() if app is not None else None
        clipboard_text = clipboard.text() if clipboard is not None else ""
        if not clipboard_text.strip():
            QMessageBox.information(
                self,
                tr("cookies.import.title", default="Import cookies"),
                tr(
                    "cookies.import.clipboard_empty",
                    default="The clipboard is empty. Copy cookies first.",
                ),
            )
            return
        self._editor.setPlainText(clipboard_text)

    def _load_from_file(self):
        selected, _ = QFileDialog.getOpenFileName(
            self,
            tr("cookies.import.load_file", default="Load from file...").rstrip("."),
            str(self._destination_path.parent),
            "Cookies (*.txt *.json);;JSON (*.json);;Text (*.txt);;All files (*.*)",
        )
        if not selected:
            return

        try:
            content = Path(selected).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("common.error", default="Error"),
                tr(
                    "cookies.import.file_failed",
                    default="Failed to open or save the cookies file:\n{error}",
                    error=str(exc),
                ),
            )
            return

        self._editor.setPlainText(content)

    def _save_cookies(self):
        raw_text = self._editor.toPlainText()
        if not raw_text.strip():
            QMessageBox.warning(
                self,
                tr("cookies.import.title", default="Import cookies"),
                tr(
                    "cookies.import.empty",
                    default="Paste cookies or load them from a file first.",
                ),
            )
            return

        try:
            self._saved_result = save_normalized_cookie_text(raw_text, self._destination_path)
        except ValueError:
            QMessageBox.warning(
                self,
                tr("cookies.import.title", default="Import cookies"),
                tr(
                    "cookies.import.invalid",
                    default=(
                        "Unsupported cookies format. Expected Netscape cookies.txt, "
                        "raw Cookie header, or JSON export."
                    ),
                ),
            )
            return
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("common.error", default="Error"),
                tr(
                    "cookies.import.file_failed",
                    default="Failed to open or save the cookies file:\n{error}",
                    error=str(exc),
                ),
            )
            return

        QMessageBox.information(
            self,
            tr("cookies.import.title", default="Import cookies"),
            tr(
                "cookies.import.saved",
                default="Cookies were saved to:\n{path}",
                path=str(self._destination_path),
            ),
        )
        self.accept()

    def get_saved_result(self) -> CookieNormalizationResult | None:
        return self._saved_result
