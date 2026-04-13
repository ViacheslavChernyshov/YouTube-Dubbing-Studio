"""
Portable setup dialog — lets the user configure data folder and optional system paths.
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import (
    DEFAULT_DATA_DIR,
    get_portable_config_snapshot,
    has_legacy_runtime_data,
)
from app.gui.theme import COLORS
from app.i18n import language_manager, tr


class PortableSetupDialog(QDialog):
    """Portable configuration dialog shown on first run and available from the menu."""

    def __init__(self, parent=None, *, first_run: bool = False):
        super().__init__(parent)
        self._first_run = first_run
        self.setMinimumWidth(760)
        self.resize(860, 420)
        self._setup_ui()
        self._load_defaults()
        self._refresh_copy_hint()
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

        form_wrap = QWidget()
        form = QFormLayout(form_wrap)
        form.setContentsMargins(0, 6, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(form.labelAlignment())

        self._data_dir_edit = QLineEdit()
        self._data_dir_edit.textChanged.connect(self._refresh_copy_hint)
        data_row = self._build_path_row(self._data_dir_edit, self._browse_data_dir)
        self._data_dir_label = QLabel("")
        form.addRow(self._data_dir_label, data_row)

        self._ffmpeg_edit = QLineEdit()
        ffmpeg_row = self._build_path_row(self._ffmpeg_edit, self._browse_ffmpeg)
        self._ffmpeg_label = QLabel("")
        form.addRow(self._ffmpeg_label, ffmpeg_row)

        self._cookies_edit = QLineEdit()
        cookies_row = self._build_path_row(self._cookies_edit, self._browse_cookies)
        self._cookies_label = QLabel("")
        form.addRow(self._cookies_label, cookies_row)

        layout.addWidget(form_wrap)

        self._portable_note = QLabel("")
        self._portable_note.setWordWrap(True)
        self._portable_note.setObjectName("label_muted")
        layout.addWidget(self._portable_note)

        self._copy_legacy_checkbox = QCheckBox("")
        layout.addWidget(self._copy_legacy_checkbox)

        self._copy_hint = QLabel("")
        self._copy_hint.setWordWrap(True)
        self._copy_hint.setObjectName("label_muted")
        layout.addWidget(self._copy_hint)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self._defaults_btn = QPushButton("")
        self._defaults_btn.setObjectName("btn_secondary")
        self._defaults_btn.clicked.connect(self._use_defaults)
        buttons.addWidget(self._defaults_btn)

        self._cancel_btn = QPushButton("")
        self._cancel_btn.setObjectName("btn_secondary")
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton("")
        self._apply_btn.clicked.connect(self._accept_if_valid)
        buttons.addWidget(self._apply_btn)

        layout.addLayout(buttons)

    def _build_path_row(self, line_edit: QLineEdit, browse_handler) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(line_edit, 1)

        browse_btn = QPushButton("")
        browse_btn.setObjectName("btn_secondary")
        browse_btn.setFixedWidth(110)
        browse_btn.clicked.connect(browse_handler)
        row_layout.addWidget(browse_btn)
        row._browse_btn = browse_btn
        return row

    def retranslate_ui(self):
        self.setWindowTitle(
            tr("portable.window_title", default="Portable setup")
        )
        self._title_label.setText(
            tr("portable.title", default="Portable mode and data paths")
        )
        self._intro_label.setText(
            tr(
                "portable.intro_first_run" if self._first_run else "portable.intro_restart",
                default=(
                    "The app can store all user data in a separate folder: settings, models, logs, jobs and cookies."
                ),
            )
        )
        self._data_dir_label.setText(tr("portable.data_dir", default="Data folder:"))
        self._ffmpeg_label.setText(tr("portable.ffmpeg_path", default="Path to ffmpeg.exe:"))
        self._cookies_label.setText(tr("portable.cookies_path", default="Path to cookies.txt:"))
        self._ffmpeg_edit.setPlaceholderText(
            tr("portable.ffmpeg_placeholder", default="Optional. Leave empty for auto-detection.")
        )
        self._data_dir_edit.setToolTip(
            tr(
                "portable.data_dir_tip",
                default=(
                    "Folder where the app stores models, jobs, logs, settings, and optional cookies "
                    "when portable mode is used."
                ),
            )
        )
        self._cookies_edit.setPlaceholderText(
            tr("portable.cookies_placeholder", default="Optional. You can pick cookies.txt later.")
        )
        self._ffmpeg_edit.setToolTip(
            tr(
                "portable.ffmpeg_tip",
                default=(
                    "Optional manual path to ffmpeg.exe. Set it only if automatic detection "
                    "cannot find ffmpeg on this PC."
                ),
            )
        )
        self._cookies_edit.setToolTip(
            tr(
                "portable.cookies_tip",
                default=(
                    "Optional path to cookies.txt for YouTube downloads that require authorization."
                ),
            )
        )
        self._portable_note.setText(
            tr(
                "portable.note",
                default="The data folder will store models, logs, jobs, settings.json and optionally cookies.txt.",
            )
        )
        self._copy_legacy_checkbox.setText(
            tr("portable.copy_legacy", default="Copy current local data into the new portable folder")
        )
        self._copy_legacy_checkbox.setToolTip(
            tr(
                "portable.copy_tip",
                default="Useful if models, logs, jobs, settings.json or cookies.txt used to live next to the app.",
            )
        )
        self._defaults_btn.setText(tr("common.defaults", default="Defaults"))
        self._defaults_btn.setToolTip(
            tr(
                "portable.defaults_tip",
                default="Restore the recommended portable paths and clear optional custom files.",
            )
        )
        self._cancel_btn.setText(tr("common.cancel", default="Cancel"))
        self._apply_btn.setText(
            tr(
                "common.save_continue" if self._first_run else "common.save",
                default="Save and continue" if self._first_run else "Save",
            )
        )
        self._apply_btn.setToolTip(
            tr(
                "portable.apply_tip",
                default="Save the selected portable settings. A restart may be required for all changes to apply.",
            )
        )
        browse_tips = {
            self._data_dir_edit.parentWidget(): tr(
                "portable.browse_data_tip",
                default="Choose the portable data folder from the file system.",
            ),
            self._ffmpeg_edit.parentWidget(): tr(
                "portable.browse_ffmpeg_tip",
                default="Choose the ffmpeg.exe file manually.",
            ),
            self._cookies_edit.parentWidget(): tr(
                "portable.browse_cookies_tip",
                default="Choose the cookies.txt file manually.",
            ),
        }
        for row, tooltip in browse_tips.items():
            browse_btn = getattr(row, "_browse_btn", None)
            if browse_btn is not None:
                browse_btn.setText(tr("common.browse", default="Browse..."))
                browse_btn.setToolTip(tooltip)
        self._refresh_copy_hint()

    def _load_defaults(self):
        snapshot = get_portable_config_snapshot()
        data_dir = snapshot.get("data_dir") or str(DEFAULT_DATA_DIR)
        self._data_dir_edit.setText(data_dir)
        self._ffmpeg_edit.setText(snapshot.get("ffmpeg_path", ""))
        self._cookies_edit.setText(snapshot.get("cookies_path", ""))

    def _refresh_copy_hint(self):
        data_dir = self._data_dir_edit.text().strip() or str(DEFAULT_DATA_DIR)
        has_legacy = has_legacy_runtime_data(data_dir)
        self._copy_legacy_checkbox.setVisible(has_legacy)
        self._copy_hint.setVisible(has_legacy)
        if has_legacy:
            self._copy_hint.setText(
                tr(
                    "portable.copy_hint",
                    default="Local project data was found. You can copy it into the new portable folder so nothing has to be configured again.",
                )
            )
            if self._first_run:
                self._copy_legacy_checkbox.setChecked(True)
        else:
            self._copy_legacy_checkbox.setChecked(False)
            self._copy_hint.setText("")

    def _browse_data_dir(self):
        current = self._data_dir_edit.text().strip() or str(DEFAULT_DATA_DIR)
        selected = QFileDialog.getExistingDirectory(
            self,
            tr("portable.data_dir", default="Data folder:").rstrip(":"),
            current,
        )
        if selected:
            self._data_dir_edit.setText(selected)

    def _browse_ffmpeg(self):
        current = self._ffmpeg_edit.text().strip()
        selected, _ = QFileDialog.getOpenFileName(
            self,
            tr("portable.ffmpeg_path", default="Path to ffmpeg.exe:").rstrip(":"),
            current or str(Path(self._data_dir_edit.text().strip() or DEFAULT_DATA_DIR)),
            "FFmpeg executable (ffmpeg.exe);;Executable (*.exe);;All files (*.*)",
        )
        if selected:
            self._ffmpeg_edit.setText(selected)

    def _browse_cookies(self):
        current = self._cookies_edit.text().strip()
        selected, _ = QFileDialog.getOpenFileName(
            self,
            tr("portable.cookies_path", default="Path to cookies.txt:").rstrip(":"),
            current or str(Path(self._data_dir_edit.text().strip() or DEFAULT_DATA_DIR)),
            "Cookies (*.txt);;Text (*.txt);;All files (*.*)",
        )
        if selected:
            self._cookies_edit.setText(selected)

    def _use_defaults(self):
        self._data_dir_edit.setText(str(DEFAULT_DATA_DIR))
        self._ffmpeg_edit.clear()
        self._cookies_edit.clear()
        self._refresh_copy_hint()

    def _accept_if_valid(self):
        data_dir = self._data_dir_edit.text().strip()
        if not data_dir:
            QMessageBox.warning(
                self,
                tr("portable.data_dir", default="Data folder:").rstrip(":"),
                tr(
                    "portable.warning_data_dir",
                    default="Specify the folder where portable data will be stored.",
                ),
            )
            return
        self.accept()

    def get_values(self) -> dict[str, str | bool]:
        return {
            "data_dir": self._data_dir_edit.text().strip() or str(DEFAULT_DATA_DIR),
            "ffmpeg_path": self._ffmpeg_edit.text().strip(),
            "cookies_path": self._cookies_edit.text().strip(),
            "copy_legacy": self._copy_legacy_checkbox.isChecked() and self._copy_legacy_checkbox.isVisible(),
        }

    def get_default_values(self) -> dict[str, str | bool]:
        return {
            "data_dir": str(DEFAULT_DATA_DIR),
            "ffmpeg_path": "",
            "cookies_path": "",
            "copy_legacy": has_legacy_runtime_data(DEFAULT_DATA_DIR),
        }
