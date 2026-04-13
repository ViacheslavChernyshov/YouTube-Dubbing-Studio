"""
Menu bar manager — creates, translates, and synchronizes the application menu.

Extracted from MainWindow to reduce its responsibilities.
"""
from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtGui import QAction, QActionGroup

from app.config import APP_NAME, APP_VERSION, settings
from app.language_catalog import (
    DEFAULT_TARGET_LANGUAGE,
    get_target_language_rows,
)
from app.tts_engines.kokoro_engine import get_kokoro_lang_rows
from app.tts_engines.base_engine import TTSEngineRegistry
from app.i18n import get_interface_language_options, tr


class MenuManager:
    """Builds and manages the main menu bar for the application window."""

    def __init__(self, window: QMainWindow, settings_panel, url_input):
        self._window = window
        self._settings_panel = settings_panel
        self._url_input = url_input

        # Action registries (populated during setup)
        self._interface_language_actions: dict[str, QAction] = {}
        self._target_language_actions: dict[str, QAction] = {}
        self._tts_actions: dict[str, QAction] = {}
        self._kokoro_lang_actions: dict[str, QAction] = {}
        self._f5_nfe_actions: dict[int, QAction] = {}

        self._setup_menu()

    # ── Menu Construction ──────────────────────────────────────────────

    def _setup_menu(self):
        menubar = self._window.menuBar()
        menubar.clear()

        # File menu
        self._file_menu = menubar.addMenu("")

        self._action_open_jobs = QAction("", self._window)
        self._file_menu.addAction(self._action_open_jobs)

        self._action_open_data = QAction("", self._window)
        self._file_menu.addAction(self._action_open_data)

        self._action_open_logs = QAction("", self._window)
        self._file_menu.addAction(self._action_open_logs)

        self._action_open_current_job = QAction("", self._window)
        self._file_menu.addAction(self._action_open_current_job)

        self._file_menu.addSeparator()

        self._quit_action = QAction("", self._window)
        self._quit_action.setShortcut("Ctrl+Q")
        self._quit_action.triggered.connect(self._window.close)
        self._file_menu.addAction(self._quit_action)

        # Actions menu
        self._actions_menu = menubar.addMenu("")

        self._action_focus_url = QAction("", self._window)
        self._action_focus_url.setShortcut("Ctrl+L")
        self._action_focus_url.triggered.connect(self._url_input.focus_input)
        self._actions_menu.addAction(self._action_focus_url)

        self._action_paste_url = QAction("", self._window)
        self._action_paste_url.triggered.connect(self._url_input.paste_from_clipboard)
        self._actions_menu.addAction(self._action_paste_url)

        self._action_start = QAction("", self._window)
        self._action_start.setShortcut("Ctrl+Return")
        self._action_start.triggered.connect(self._url_input.submit_current_url)
        self._actions_menu.addAction(self._action_start)

        self._action_stop = QAction("", self._window)
        self._action_stop.setShortcut("Esc")
        self._actions_menu.addAction(self._action_stop)

        self._actions_menu.addSeparator()

        self._action_show_transcript = QAction("", self._window)
        self._action_show_transcript.setShortcut("Ctrl+T")
        self._actions_menu.addAction(self._action_show_transcript)

        self._action_open_original = QAction("", self._window)
        self._actions_menu.addAction(self._action_open_original)

        self._action_open_output = QAction("", self._window)
        self._actions_menu.addAction(self._action_open_output)

        self._actions_menu.addSeparator()

        self._action_clear_logs = QAction("", self._window)
        self._actions_menu.addAction(self._action_clear_logs)

        # Settings menu
        self._settings_menu = menubar.addMenu("")

        self._interface_language_menu = self._settings_menu.addMenu("")
        self._interface_language_group = QActionGroup(self._window)
        self._interface_language_group.setExclusive(True)
        for language_code, label in get_interface_language_options():
            action = QAction(label, self._window)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, lang=language_code: checked and self._settings_panel.set_interface_language(lang)
            )
            self._interface_language_group.addAction(action)
            self._interface_language_menu.addAction(action)
            self._interface_language_actions[language_code] = action

        self._target_language_menu = self._settings_menu.addMenu("")
        self._target_language_group = QActionGroup(self._window)
        self._target_language_group.setExclusive(True)
        for lang_code, label, native in get_target_language_rows():
            display_name = label if label == native else f"{label} ({native})"
            action = QAction(display_name, self._window)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, lang=lang_code: checked and self._settings_panel.set_target_language(lang)
            )
            self._target_language_group.addAction(action)
            self._target_language_menu.addAction(action)
            self._target_language_actions[lang_code] = action

        self._tts_menu = self._settings_menu.addMenu("")
        self._tts_action_group = QActionGroup(self._window)
        self._tts_action_group.setExclusive(True)
        for model_id, name in self._settings_panel.TTS_MODELS.items():
            action = QAction(name, self._window)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, model=model_id: checked and self._settings_panel.set_tts_engine(model)
            )
            self._tts_action_group.addAction(action)
            self._tts_menu.addAction(action)
            self._tts_actions[model_id] = action

        self._audio_menu = self._settings_menu.addMenu("")

        self._action_remove_silence = QAction("", self._window)
        self._action_remove_silence.setCheckable(True)
        self._action_remove_silence.triggered.connect(self._settings_panel.set_remove_silence)
        self._audio_menu.addAction(self._action_remove_silence)

        self._action_smart_hybrid = QAction("", self._window)
        self._action_smart_hybrid.setCheckable(True)
        self._action_smart_hybrid.triggered.connect(self._settings_panel.set_smart_hybrid_alignment)
        self._audio_menu.addAction(self._action_smart_hybrid)

        self._action_keep_original_audio = QAction("", self._window)
        self._action_keep_original_audio.setCheckable(True)
        self._action_keep_original_audio.triggered.connect(self._settings_panel.set_keep_original_audio)
        self._audio_menu.addAction(self._action_keep_original_audio)

        self._action_jump_cut = QAction("", self._window)
        self._action_jump_cut.setCheckable(True)
        self._action_jump_cut.triggered.connect(self._settings_panel.set_jump_cut_video)
        self._audio_menu.addAction(self._action_jump_cut)

        self._kokoro_menu = self._settings_menu.addMenu("")

        self._action_kokoro_soft_trim = QAction("", self._window)
        self._action_kokoro_soft_trim.setCheckable(True)
        self._action_kokoro_soft_trim.triggered.connect(self._settings_panel.set_kokoro_soft_trim)
        self._kokoro_menu.addAction(self._action_kokoro_soft_trim)

        self._kokoro_lang_menu = self._kokoro_menu.addMenu("")
        self._kokoro_lang_group = QActionGroup(self._window)
        self._kokoro_lang_group.setExclusive(True)
        for lang_code, title in get_kokoro_lang_rows():
            action = QAction(title, self._window)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, lang=lang_code: checked and self._settings_panel.set_kokoro_lang(lang)
            )
            self._kokoro_lang_group.addAction(action)
            self._kokoro_lang_menu.addAction(action)
            self._kokoro_lang_actions[lang_code] = action

        self._f5_menu = self._settings_menu.addMenu("")
        self._f5_nfe_group = QActionGroup(self._window)
        self._f5_nfe_group.setExclusive(True)
        for value, title in (
            (16, tr("settings.f5.fast", default="16 (Fast)")),
            (32, tr("settings.f5.standard", default="32 (Standard)")),
            (64, tr("settings.f5.high", default="64 (High)")),
            (128, tr("settings.f5.studio", default="128 (Studio)")),
        ):
            action = QAction(title, self._window)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, nfe=value: checked and self._settings_panel.set_f5_nfe_steps(nfe)
            )
            self._f5_nfe_group.addAction(action)
            self._f5_menu.addAction(action)
            self._f5_nfe_actions[value] = action

        self._settings_menu.addSeparator()
        self._action_prepare_runtime = QAction("", self._window)
        self._settings_menu.addAction(self._action_prepare_runtime)

        self._action_portable_setup = QAction("", self._window)
        self._settings_menu.addAction(self._action_portable_setup)

        self._action_import_cookies = QAction("", self._window)
        self._settings_menu.addAction(self._action_import_cookies)

        self._action_reset_cookies = QAction("", self._window)
        self._settings_menu.addAction(self._action_reset_cookies)

        # Docs menu
        self._docs_menu = menubar.addMenu("")

        self._action_docs_overview = QAction("", self._window)
        self._action_docs_overview.setShortcut("F1")
        self._docs_menu.addAction(self._action_docs_overview)

        self._action_docs_quick_start = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_quick_start)

        self._action_docs_menu_guide = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_menu_guide)

        self._action_docs_interface = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_interface)

        self._action_docs_settings = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_settings)

        self._action_docs_voices = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_voices)

        self._action_docs_pipeline = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_pipeline)

        self._action_docs_faq = QAction("", self._window)
        self._docs_menu.addAction(self._action_docs_faq)

        self._docs_menu.addSeparator()

        self._action_about = QAction("", self._window)
        self._docs_menu.addAction(self._action_about)

    # ── Connect callbacks (called by MainWindow) ───────────────────────

    def connect_actions(
        self,
        *,
        on_stop,
        on_show_transcript,
        on_open_original,
        on_open_output,
        on_clear_logs,
        on_open_jobs,
        on_open_data,
        on_open_logs,
        on_open_current_job,
        on_prepare_runtime,
        on_portable_setup,
        on_import_cookies,
        on_reset_cookies,
        on_show_documentation,
        on_about,
    ):
        """Connect menu actions to MainWindow callbacks."""
        self._action_open_jobs.triggered.connect(on_open_jobs)
        self._action_open_data.triggered.connect(on_open_data)
        self._action_open_logs.triggered.connect(on_open_logs)
        self._action_open_current_job.triggered.connect(on_open_current_job)
        self._action_stop.triggered.connect(on_stop)
        self._action_show_transcript.triggered.connect(on_show_transcript)
        self._action_open_original.triggered.connect(on_open_original)
        self._action_open_output.triggered.connect(on_open_output)
        self._action_clear_logs.triggered.connect(on_clear_logs)
        self._action_prepare_runtime.triggered.connect(on_prepare_runtime)
        self._action_portable_setup.triggered.connect(on_portable_setup)
        self._action_import_cookies.triggered.connect(on_import_cookies)
        self._action_reset_cookies.triggered.connect(on_reset_cookies)
        self._action_docs_overview.triggered.connect(lambda: on_show_documentation("overview"))
        self._action_docs_quick_start.triggered.connect(lambda: on_show_documentation("quick_start"))
        self._action_docs_menu_guide.triggered.connect(lambda: on_show_documentation("menu_guide"))
        self._action_docs_interface.triggered.connect(lambda: on_show_documentation("interface"))
        self._action_docs_settings.triggered.connect(lambda: on_show_documentation("settings"))
        self._action_docs_voices.triggered.connect(lambda: on_show_documentation("voices"))
        self._action_docs_pipeline.triggered.connect(lambda: on_show_documentation("pipeline"))
        self._action_docs_faq.triggered.connect(lambda: on_show_documentation("faq"))
        self._action_about.triggered.connect(on_about)

    # ── Retranslation ──────────────────────────────────────────────────

    def retranslate(self):
        """Update all menu texts for the current language."""
        self._file_menu.setTitle(tr("menu.file", default="File"))
        self._actions_menu.setTitle(tr("menu.actions", default="Actions"))
        self._settings_menu.setTitle(tr("menu.settings", default="Settings"))
        self._docs_menu.setTitle(tr("menu.docs", default="Documentation"))
        self._interface_language_menu.setTitle(
            tr("menu.interface_language", default="Interface language")
        )
        self._target_language_menu.setTitle(tr("settings.dub_language", default="Dub language"))
        self._tts_menu.setTitle(tr("menu.tts_model", default="Dubbing model"))
        self._audio_menu.setTitle(tr("menu.audio", default="Audio and editing"))
        self._kokoro_menu.setTitle(tr("menu.kokoro", default="Kokoro"))
        self._kokoro_lang_menu.setTitle(tr("menu.kokoro_accent", default="Accent"))
        self._f5_menu.setTitle(tr("menu.f5", default="F5"))

        self._action_open_jobs.setText(tr("action.open_jobs", default="📂 Open jobs folder"))
        self._action_open_data.setText(tr("action.open_data", default="🗃 Open data folder"))
        self._action_open_logs.setText(tr("action.open_logs", default="📜 Open logs folder"))
        self._action_open_current_job.setText(
            tr("action.open_current_job", default="🗂 Open current job")
        )
        self._quit_action.setText(tr("common.exit", default="Exit"))
        self._action_focus_url.setText(tr("action.focus_url", default="🔗 Focus link field"))
        self._action_paste_url.setText(tr("action.paste_url", default="📋 Paste link from clipboard"))
        self._action_start.setText(tr("action.start_processing", default="▶ Start processing"))
        self._action_stop.setText(tr("action.stop_processing", default="⏹ Stop processing"))
        self._action_show_transcript.setText(
            tr("action.open_transcript", default="📝 Open transcript")
        )
        self._action_open_original.setText(tr("action.open_original", default="🎬 Open original"))
        self._action_open_output.setText(tr("action.open_output", default="📁 Open result"))
        self._action_clear_logs.setText(tr("action.clear_logs", default="🧹 Clear log"))
        self._action_remove_silence.setText(
            tr("settings.remove_silence", default="Auto-trim pauses")
        )
        self._action_smart_hybrid.setText(
            tr("settings.smart_hybrid", default="Smooth audio dynamics")
        )
        self._action_keep_original_audio.setText(
            tr("settings.keep_original_audio", default="Keep the original audio")
        )
        self._action_jump_cut.setText(tr("settings.jump_cut", default="Dynamic editing"))
        self._action_kokoro_soft_trim.setText(
            tr("settings.soft_trim", default="Soft trim phrase endings")
        )
        self._action_prepare_runtime.setText(
            tr("action.prepare_runtime", default="Check and download components")
        )
        self._action_portable_setup.setText(
            tr("action.portable_paths", default="Data folder and paths...")
        )
        self._action_import_cookies.setText(
            tr("action.import_cookies", default="📥 Import cookies...")
        )
        self._action_reset_cookies.setText(
            tr("action.reset_cookies", default="🗑 Delete cookies.txt")
        )
        for lang_code, label, native in get_target_language_rows():
            action = self._target_language_actions.get(lang_code)
            if action is not None:
                action.setText(label if label == native else f"{label} ({native})")
        for lang_code, title in get_kokoro_lang_rows():
            action = self._kokoro_lang_actions.get(lang_code)
            if action is not None:
                action.setText(title)
        f5_titles = {
            16: tr("settings.f5.fast", default="16 (Fast)"),
            32: tr("settings.f5.standard", default="32 (Standard)"),
            64: tr("settings.f5.high", default="64 (High)"),
            128: tr("settings.f5.studio", default="128 (Studio)"),
        }
        for value, action in self._f5_nfe_actions.items():
            action.setText(f5_titles.get(value, str(value)))
        self._action_docs_overview.setText(
            tr("action.docs.overview", default="Program overview")
        )
        self._action_docs_quick_start.setText(
            tr("action.docs.quick_start", default="Quick start")
        )
        self._action_docs_menu_guide.setText(
            tr("action.docs.menu_guide", default="Menu guide")
        )
        self._action_docs_interface.setText(
            tr("action.docs.interface", default="Interface and main sections")
        )
        self._action_docs_settings.setText(
            tr("action.docs.settings", default="Settings and features")
        )
        self._action_docs_voices.setText(
            tr("action.docs.voices", default="How to choose a model and voice")
        )
        self._action_docs_pipeline.setText(
            tr("action.docs.pipeline", default="How the program works")
        )
        self._action_docs_faq.setText(tr("action.docs.faq", default="Tips and FAQ"))
        self._action_about.setText(tr("action.about", default="About"))

    # ── State Synchronization ──────────────────────────────────────────

    def sync_state(
        self,
        *,
        settings_enabled: bool,
        bootstrap_active: bool,
        pipeline_running: bool,
        stop_btn_enabled: bool,
        transcript_btn_enabled: bool,
        original_btn_enabled: bool,
        output_btn_enabled: bool,
        has_job_dir: bool,
    ):
        """Synchronize menu action states with the current application state."""
        from app.config import get_cookies_file

        current_tts = settings.tts_engine
        target_language = getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE)

        self._settings_menu.setEnabled(settings_enabled)
        self._interface_language_menu.setEnabled(settings_enabled)
        self._target_language_menu.setEnabled(settings_enabled)
        self._tts_menu.setEnabled(settings_enabled)
        self._audio_menu.setEnabled(settings_enabled)
        self._kokoro_menu.setEnabled(settings_enabled and current_tts == "kokoro-tts")
        self._f5_menu.setEnabled(settings_enabled and current_tts == "f5-tts")
        self._action_prepare_runtime.setEnabled(not bootstrap_active and not pipeline_running)
        self._action_portable_setup.setEnabled(not bootstrap_active and settings_enabled)
        self._action_import_cookies.setEnabled(not bootstrap_active and settings_enabled)
        self._action_reset_cookies.setEnabled(
            not bootstrap_active and settings_enabled and get_cookies_file().exists()
        )

        self._set_action_checked(self._tts_actions.get(current_tts), True)
        for model_id, action in self._tts_actions.items():
            action.setEnabled(settings_enabled and TTSEngineRegistry.is_language_supported(model_id, target_language))
            if model_id != current_tts:
                self._set_action_checked(action, False)

        for lang_code, action in self._target_language_actions.items():
            self._set_action_checked(action, lang_code == target_language)

        current_interface_language = getattr(settings, "interface_language", "ru")
        for lang_code, action in self._interface_language_actions.items():
            self._set_action_checked(action, lang_code == current_interface_language)

        self._set_action_checked(self._action_remove_silence, settings.remove_tts_silence)
        self._set_action_checked(self._action_smart_hybrid, settings.smart_hybrid_alignment)
        self._set_action_checked(self._action_keep_original_audio, settings.keep_original_audio)
        self._set_action_checked(self._action_jump_cut, settings.jump_cut_video)
        self._set_action_checked(self._action_kokoro_soft_trim, settings.kokoro_soft_trim)

        current_kokoro_lang = getattr(settings, "kokoro_lang", "en-us")
        for lang_code, action in self._kokoro_lang_actions.items():
            self._set_action_checked(action, lang_code == current_kokoro_lang)

        current_nfe = getattr(settings, "f5_nfe_steps", 32)
        for nfe_value, action in self._f5_nfe_actions.items():
            self._set_action_checked(action, nfe_value == current_nfe)

        is_input_enabled = self._url_input.is_input_enabled()
        self._action_focus_url.setEnabled(is_input_enabled)
        self._action_paste_url.setEnabled(is_input_enabled)
        self._action_start.setEnabled(
            not bootstrap_active and is_input_enabled and self._url_input.has_valid_url()
        )
        self._action_stop.setEnabled(stop_btn_enabled)
        self._action_show_transcript.setEnabled(transcript_btn_enabled)
        self._action_open_original.setEnabled(original_btn_enabled)
        self._action_open_output.setEnabled(output_btn_enabled)
        self._action_open_current_job.setEnabled(has_job_dir)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _set_action_checked(action: QAction | None, checked: bool):
        if action is None:
            return
        previous = action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(previous)
