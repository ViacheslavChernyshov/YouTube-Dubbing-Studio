"""
Main application window — assembles all widgets.

Menu construction and state synchronization are delegated to MenuManager.
"""
import os
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSplitter, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Slot, QTimer, Signal

from app.config import (
    APP_NAME,
    APP_VERSION,
    delete_cookies_file,
    get_data_dir,
    get_cookies_file,
    get_jobs_dir,
    get_logs_dir,
    migrate_legacy_runtime_data,
    save_portable_config,
    settings,
)
from app.hardware import detect_hardware, format_hardware_badge, HardwareInfo
from app.gui.theme import COLORS
from app.gui.bootstrap_controller import BootstrapController
from app.gui.menu_manager import MenuManager
from app.gui.widgets.cookies_import_dialog import CookiesImportDialog
from app.gui.widgets.docs_dialog import DocumentationDialog
from app.gui.widgets.portable_setup_dialog import PortableSetupDialog
from app.gui.widgets.runtime_update_dialog import RuntimeUpdateDialog
from app.gui.widgets.url_input import URLInput
from app.gui.widgets.pipeline_view import PipelineView
from app.gui.widgets.log_viewer import LogViewer
from app.gui.widgets.settings_panel import SettingsPanel
from app.gui.widgets.transcript_viewer import TranscriptViewer
from app.gui.pipeline_controller import PipelineController
from app.runtime_assets import StartupBootstrapWorker, build_runtime_asset_plan
from app.i18n import get_layout_direction, language_manager, tr
from app.utils.logger import setup_logger


class MainWindow(QMainWindow):
    """Main application window for YouTube Dubbing Studio."""

    _hw_detected_signal = Signal(object)

    def __init__(self):
        super().__init__()
        self._hw_info: HardwareInfo = HardwareInfo()
        self._hw_detected_signal.connect(self._on_hw_detected)
        threading.Thread(target=self._detect_hw_thread, daemon=True).start()
        self._transcript_viewer: TranscriptViewer | None = None
        self._job_dir = None
        self._output_path = None
        self._docs_dialog: DocumentationDialog | None = None
        self._runtime_update_dialog: RuntimeUpdateDialog | None = None
        self._status_key = "status.ready"
        self._status_kwargs: dict[str, object] = {}
        self._logger = setup_logger(gui_callback=self._on_log_message)
        self._setup_window()
        self._setup_ui()

        # Connect bootstrap controller
        self._bootstrap = BootstrapController(
            parent=self,
            logger=self._logger,
            hw_info=self._hw_info,
            on_status_changed=self._on_bootstrap_status_changed,
            on_started=self._on_bootstrap_started,
            on_finished=self._on_bootstrap_finished,
        )

        # Pipeline controller — encapsulates business logic of running dubbing
        self._pipeline_controller = PipelineController(
            parent=self,
            logger=self._logger,
            hw_info=self._hw_info,
            url_input=self._url_input,
            settings_panel=self._settings_panel,
            pipeline_view=self._pipeline_view,
            log_viewer=self._log_viewer,
            on_status_changed=self._set_status_shortcut,
            on_state_changed=self._sync_menu_state,
            on_segments_ready=self._on_segments_ready,
            on_job_dir_available=self._set_job_dir,
            on_output_path_available=self._set_output_path,
        )

        # Menu manager — encapsulates menu construction and state sync
        self._menu = MenuManager(self, self._settings_panel, self._url_input)
        self._menu.connect_actions(
            on_stop=self._pipeline_controller.stop,
            on_show_transcript=self._show_transcript,
            on_open_original=self._open_original,
            on_open_output=self._open_output,
            on_clear_logs=self._clear_logs,
            on_open_jobs=self._open_jobs_folder,
            on_open_data=self._open_data_folder,
            on_open_logs=self._open_logs_folder,
            on_open_current_job=self._open_current_job_folder,
            on_prepare_runtime=self._trigger_runtime_bootstrap,
            on_portable_setup=self._show_portable_setup_dialog,
            on_import_cookies=self._show_cookies_import_dialog,
            on_reset_cookies=self._reset_cookies_file,
            on_show_documentation=self._show_documentation,
            on_about=self._show_about,
        )
        self._settings_panel.settings_changed.connect(self._sync_menu_state)
        language_manager.language_changed.connect(self._on_language_changed)
        self.retranslate_ui()
        self._sync_menu_state()
        self._logger.info("Application started | Detecting hardware...")
        QTimer.singleShot(0, lambda: self._bootstrap.trigger(initial=True, pipeline_running=False))

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(800, 550)
        self.resize(1200, 800)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 8, 16, 16)
        main_layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(12)

        self._title_label = QLabel("")
        self._title_label.setObjectName("label_title")
        header.addWidget(self._title_label)

        header.addStretch()

        self._hw_badge = QLabel(format_hardware_badge(self._hw_info))
        self._hw_badge.setObjectName("label_hardware")
        header.addWidget(self._hw_badge)

        main_layout.addLayout(header)

        # ── URL Input ──
        self._url_input = URLInput()
        self._url_input.url_submitted.connect(self._on_start)
        self._url_input.state_changed.connect(self._sync_menu_state)
        main_layout.addWidget(self._url_input)

        # ── Content area: pipeline + settings ──
        content = QHBoxLayout()
        content.setSpacing(12)

        # Left side: pipeline + logs (splitter)
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        self._pipeline_view = PipelineView()
        left_splitter.addWidget(self._pipeline_view)

        self._log_viewer = LogViewer()
        left_splitter.addWidget(self._log_viewer)

        left_splitter.setSizes([450, 200])
        content.addWidget(left_splitter, 1)

        # Right side: settings
        self._settings_panel = SettingsPanel()
        content.addWidget(self._settings_panel)

        main_layout.addLayout(content, 1)

        # ── Bottom bar: stop button + status ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._stop_btn = QPushButton("")
        self._stop_btn.setObjectName("btn_stop")
        self._stop_btn.setFixedWidth(140)
        self._stop_btn.clicked.connect(lambda: self._pipeline_controller.stop() if hasattr(self, "_pipeline_controller") else None)
        bottom.addWidget(self._stop_btn)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        bottom.addWidget(self._status_label, 1)

        self._transcript_btn = QPushButton("")
        self._transcript_btn.setObjectName("btn_secondary")
        self._transcript_btn.setFixedWidth(150)
        self._transcript_btn.setEnabled(False)
        self._transcript_btn.clicked.connect(self._show_transcript)
        bottom.addWidget(self._transcript_btn)

        self._open_original_btn = QPushButton("")
        self._open_original_btn.setObjectName("btn_secondary")
        self._open_original_btn.setFixedWidth(130)
        self._open_original_btn.setEnabled(False)
        self._open_original_btn.clicked.connect(self._open_original)
        bottom.addWidget(self._open_original_btn)

        self._open_output_btn = QPushButton("")
        self._open_output_btn.setObjectName("btn_secondary")
        self._open_output_btn.setFixedWidth(130)
        self._open_output_btn.setEnabled(False)
        self._open_output_btn.clicked.connect(self._open_output)
        bottom.addWidget(self._open_output_btn)

        main_layout.addLayout(bottom)
        self._set_status("status.ready", default="Ready to work")

    # ── Status helpers ─────────────────────────────────────────────────

    def _set_status(self, key: str, default: str, **kwargs):
        self._status_key = key
        self._status_kwargs = {"default": default, **kwargs}
        self._status_label.setText(tr(key, default=default, **kwargs))

    def _refresh_status_text(self):
        default = str(self._status_kwargs.get("default", self._status_key))
        kwargs = {key: value for key, value in self._status_kwargs.items() if key != "default"}
        self._status_label.setText(tr(self._status_key, default=default, **kwargs))

    def _set_status_shortcut(self, key: str, default_text: str):
        self._set_status(key, default=default_text)

    def _set_job_dir(self, job_dir):
        self._job_dir = job_dir
        self._sync_menu_state()

    def _set_output_path(self, output_path):
        self._output_path = output_path
        self._sync_menu_state()

    # ── Language change ────────────────────────────────────────────────

    def _on_language_changed(self, language_code: str):
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(get_layout_direction(language_code))
        self.retranslate_ui()

    # ── Hardware detection ─────────────────────────────────────────────

    def _detect_hw_thread(self):
        self._hw_detected_signal.emit(detect_hardware())

    @Slot(object)
    def _on_hw_detected(self, hw_info: HardwareInfo):
        self._hw_info = hw_info
        
        # Share hw info with bootstrap process
        self._bootstrap._hw_info = hw_info
        
        self._hw_badge.setText(format_hardware_badge(hw_info))
        self._logger.info(f"Hardware detected | {format_hardware_badge(hw_info)}")

    # ── Retranslation ──────────────────────────────────────────────────

    def retranslate_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self._title_label.setText(f"🎬 {APP_NAME}")
        if getattr(self._hw_info, 'gpu_name', 'N/A') == 'N/A':
            self._hw_badge.setText(tr("hw.detecting", default="Detecting hardware..."))
        else:
            self._hw_badge.setText(format_hardware_badge(self._hw_info))
        self._stop_btn.setText(f"⏹ {tr('common.stop', default='Stop')}")
        self._transcript_btn.setText(f"📝 {tr('common.transcript', default='Transcript')}")
        self._open_original_btn.setText(f"🎬 {tr('common.original', default='Original')}")
        self._open_output_btn.setText(f"📁 {tr('common.result', default='Result')}")
        self._refresh_tooltips()
        self._refresh_status_text()

        # Delegate menu retranslation
        self._menu.retranslate()

        current_interface_language = getattr(settings, "interface_language", "ru")
        # checked state is handled by _sync_menu_state

        if self._transcript_viewer is not None:
            self._transcript_viewer.retranslate_ui()
        if self._runtime_update_dialog is not None:
            self._runtime_update_dialog.retranslate_ui()
        if self._docs_dialog is not None:
            self._docs_dialog.retranslate_ui()

    def _refresh_tooltips(self):
        self._hw_badge.setToolTip(
            tr(
                "main.hardware_tooltip",
                default="Detected hardware that the app will use for downloading, speech processing, and dubbing.",
            )
        )
        self._pipeline_view.setToolTip(
            tr(
                "main.pipeline_tooltip",
                default="Shows all processing stages, the current step, progress, ETA, and service messages.",
            )
        )
        self._log_viewer.setToolTip(
            tr(
                "main.log_tooltip",
                default="Detailed log of downloads, model preparation, warnings, and errors.",
            )
        )
        self._stop_btn.setToolTip(
            tr(
                "main.stop_tooltip",
                default=(
                    "Stop the current pipeline. The app will cancel the job as safely "
                    "as possible after the active step responds."
                ),
            )
        )
        self._transcript_btn.setToolTip(
            tr(
                "main.transcript_tooltip",
                default="Open the recognized transcript and translation after text segments are ready.",
            )
        )
        self._open_original_btn.setToolTip(
            tr(
                "main.original_tooltip",
                default="Open the downloaded source video for the current job.",
            )
        )
        self._open_output_btn.setToolTip(
            tr(
                "main.output_tooltip",
                default="Open the final dubbed video after processing finishes.",
            )
        )

    # ── Pipeline Interaction ───────────────────────────────────────────

    @Slot(str)
    def _on_start(self, url: str):
        """Start the dubbing pipeline via the controller."""
        self._pipeline_controller.start(url)

    @Slot(list, str)
    def _on_segments_ready(self, segments: list, source_lang: str):
        """Handle segments data from pipeline — populate transcript viewer."""
        if not self._transcript_viewer:
            self._transcript_viewer = TranscriptViewer(self)
        self._transcript_viewer.load_segments(segments, source_lang)
        self._transcript_btn.setEnabled(True)
        self._logger.info(f"Transcript updated: {len(segments)} segments")
        self._sync_menu_state()



    # ── UI callbacks ───────────────────────────────────────────────────

    def _show_transcript(self):
        """Open the transcript viewer dialog."""
        if self._transcript_viewer:
            self._transcript_viewer.show()
            self._transcript_viewer.raise_()
            self._transcript_viewer.activateWindow()

    def _on_log_message(self, message: str, level: str):
        """Forward log messages to the log viewer."""
        self._log_viewer.append_log(message, level)

    def _open_jobs_folder(self):
        os.startfile(str(get_jobs_dir()))

    def _open_data_folder(self):
        os.startfile(str(get_data_dir()))

    def _open_logs_folder(self):
        os.startfile(str(get_logs_dir()))

    def _open_current_job_folder(self):
        if hasattr(self, "_job_dir") and self._job_dir and self._job_dir.is_dir():
            os.startfile(str(self._job_dir))
        else:
            self._logger.warning("Current job folder is not available yet")

    def _open_output(self):
        if hasattr(self, "_output_path") and os.path.isfile(self._output_path):
            os.startfile(self._output_path)

    def _open_original(self):
        """Open the downloaded original video."""
        if hasattr(self, "_job_dir") and self._job_dir:
            input_video = self._job_dir / "input.mp4"
            if input_video.is_file():
                os.startfile(str(input_video))
            else:
                self._logger.warning("Original video not found")

    def _clear_logs(self):
        self._log_viewer.clear_logs()
        self._logger.info("Log cleared by user")

    # ── Dialogs ────────────────────────────────────────────────────────

    def _show_documentation(self, section_id: str = "overview"):
        if self._docs_dialog is None:
            self._docs_dialog = DocumentationDialog(self)
        self._docs_dialog.open_section(section_id)
        self._docs_dialog.show()
        self._docs_dialog.raise_()
        self._docs_dialog.activateWindow()

    def _show_portable_setup_dialog(self):
        dialog = PortableSetupDialog(self, first_run=False)
        if not dialog.exec():
            return

        values = dialog.get_values()
        save_portable_config(
            data_dir=values["data_dir"],
            ffmpeg_path=str(values["ffmpeg_path"]),
            cookies_path=str(values["cookies_path"]),
            apply_now=False,
        )
        copied = []
        if values.get("copy_legacy"):
            copied = migrate_legacy_runtime_data(str(values["data_dir"]))

        copied_note = ""
        if copied:
            copied_note = "\n\nСкопированы данные: " + ", ".join(copied)

        QMessageBox.information(
            self,
            tr("common.save", default="Saved"),
            "New paths have been saved. Restart the app so they apply completely."
            + copied_note,
        )
        self._sync_menu_state()

    def _show_cookies_import_dialog(self):
        dialog = CookiesImportDialog(self)
        if not dialog.exec():
            return

        result = dialog.get_saved_result()
        cookies_path = get_cookies_file()
        if result is not None:
            self._logger.info(
                f"cookies.txt imported: {cookies_path} ({result.source_format})"
            )
        self._sync_menu_state()

    def _reset_cookies_file(self):
        cookies_path = get_cookies_file()
        action_title = tr("action.reset_cookies", default="Delete cookies.txt")

        if not cookies_path.exists():
            QMessageBox.information(
                self,
                action_title,
                tr(
                    "cookies.reset.missing",
                    default="cookies.txt was not found. There is nothing to delete.",
                ),
            )
            self._logger.info("cookies.txt reset skipped: file not found")
            self._sync_menu_state()
            return

        reply = QMessageBox.question(
            self,
            tr("common.confirmation", default="Confirmation"),
            tr(
                "cookies.reset.confirm",
                default=(
                    "Delete the saved cookies.txt file? "
                    "The next YouTube download may require logging in again."
                ),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = delete_cookies_file()
        except Exception as exc:
            self._logger.error(f"Failed to delete cookies.txt: {exc}")
            QMessageBox.critical(
                self,
                tr("common.error", default="Error"),
                tr(
                    "cookies.reset.failed",
                    default="Failed to delete cookies.txt:\n{error}",
                    error=str(exc),
                ),
            )
            self._sync_menu_state()
            return

        if deleted:
            self._logger.info(f"cookies.txt deleted: {cookies_path}")
            QMessageBox.information(
                self,
                action_title,
                tr(
                    "cookies.reset.success",
                    default="cookies.txt has been deleted.",
                ),
            )
        else:
            QMessageBox.information(
                self,
                action_title,
                tr(
                    "cookies.reset.missing",
                    default="cookies.txt was not found. There is nothing to delete.",
                ),
            )
        self._sync_menu_state()

    def _show_about(self):
        QMessageBox.about(
            self,
            tr("about.title", default="About"),
            tr(
                "about.body",
                default=(
                    "<h3>{app_name} v{version}</h3>"
                    "<p>Local application for dubbing YouTube videos.</p>"
                    "<p>GPU: {gpu}</p>"
                    "<p>RAM: {ram} GB</p>"
                ),
                app_name=APP_NAME,
                version=APP_VERSION,
                gpu=("✅ " + self._hw_info.gpu_name) if self._hw_info.gpu_available else "❌ No",
                ram=self._hw_info.ram_gb,
            ),
        )



    # ── Bootstrap Integration ──────────────────────────────────────────

    def _trigger_runtime_bootstrap(self):
        pipeline_running = self._pipeline_controller.is_running
        self._bootstrap.trigger(initial=False, pipeline_running=pipeline_running)

    def _on_bootstrap_started(self):
        self._url_input.set_enabled(False)
        self._settings_panel.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._sync_menu_state()

    def _on_bootstrap_status_changed(self, message: str):
        self._status_label.setText(message)

    def _on_bootstrap_finished(self, success: bool):
        self._url_input.set_enabled(True)
        self._settings_panel.setEnabled(True)
        self._sync_menu_state()

    # ── Menu state sync ────────────────────────────────────────────────

    def _sync_menu_state(self):
        _pipeline_running = self._pipeline_controller.is_running if hasattr(self, "_pipeline_controller") else False
        
        # Stage 0 completes when an original file is downloaded
        original_btn_enabled = False
        if hasattr(self, "_job_dir") and self._job_dir:
            if (self._job_dir / "input.mp4").is_file():
                original_btn_enabled = True

        self._menu.sync_state(
            settings_enabled=self._settings_panel.isEnabled(),
            bootstrap_active=self._bootstrap.is_active,
            pipeline_running=_pipeline_running,
            stop_btn_enabled=self._stop_btn.isEnabled(),
            transcript_btn_enabled=self._transcript_btn.isEnabled(),
            original_btn_enabled=original_btn_enabled,
            output_btn_enabled=self._open_output_btn.isEnabled(),
            has_job_dir=hasattr(self, "_job_dir") and bool(self._job_dir) and self._job_dir.is_dir(),
        )

    # ── Window lifecycle ───────────────────────────────────────────────

    def closeEvent(self, event):
        if not self._bootstrap.confirm_close():
            event.ignore()
            return

        if self._pipeline_controller.is_running:
            reply = QMessageBox.question(
                self,
                tr("common.confirmation", default="Confirmation"),
                "Processing is still running. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._pipeline_controller.confirm_stop()
            
        event.accept()
