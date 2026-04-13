"""
Settings panel — simplified to voice/model selection plus source-audio removal.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox, QScrollArea, QCheckBox, QSlider
)
from PySide6.QtCore import Signal, Qt

from app.config import (
    DEFAULT_KOKORO_LANG,
    DEFAULT_KOKORO_SPEED,
    settings,
)
from app.language_catalog import (
    DEFAULT_TARGET_LANGUAGE,
    get_target_language_display_name,
    get_target_language_rows,
)
from app.tts_engines.kokoro_engine import (
    get_kokoro_lang_rows,
    get_kokoro_voice_sort_key,
)
from app.gui.theme import COLORS
from app.i18n import (
    get_interface_language_options,
    language_manager,
    set_language,
    tr,
)


from app.tts_engines.base_engine import TTSEngineRegistry

def tts_engine_supports_language(engine_id: str, language_code: str) -> bool:
    return TTSEngineRegistry.is_language_supported(engine_id, language_code)

def get_model_voice_catalog(engine_id: str, language_code: str) -> dict:
    try:
        engine_cls = TTSEngineRegistry.get_engine_class(engine_id)
        if hasattr(engine_cls, "get_voice_catalog"):
            return engine_cls.get_voice_catalog(language_code)
    except ValueError:
        pass
    return {}

class SettingsPanel(QWidget):
    """Right sidebar settings panel."""

    settings_changed = Signal()

    @property
    def TTS_MODELS(self) -> dict[str, str]:
        return {eid: ecls.engine_name for eid, ecls in TTSEngineRegistry.get_all_engines().items()}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.setMaximumWidth(360)
        self._setup_ui()
        self._refresh_interface_language_options()
        self._refresh_target_language_options()
        self._refresh_kokoro_lang_options()
        self._refresh_f5_nfe_options()
        self._apply_saved_settings()
        self.settings_changed.connect(settings.save)
        language_manager.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text_primary']};")
        outer_layout.addWidget(self._title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 4, 4, 0)
        layout.setSpacing(6)

        # 1. Interface language
        self._interface_group = QGroupBox("")
        interface_layout = QVBoxLayout(self._interface_group)
        interface_layout.setSpacing(6)

        self._interface_language_container = QWidget()
        interface_language_layout = QHBoxLayout(self._interface_language_container)
        interface_language_layout.setContentsMargins(0, 0, 0, 0)
        self._interface_language_label = QLabel("")
        self._interface_language_combo = QComboBox()
        self._interface_language_combo.currentIndexChanged.connect(self._on_interface_language_changed)
        interface_language_layout.addWidget(self._interface_language_label)
        interface_language_layout.addWidget(self._interface_language_combo)
        interface_layout.addWidget(self._interface_language_container)
        layout.addWidget(self._interface_group)

        # 2. Dubbing model
        self._model_group = QGroupBox("")
        model_layout = QVBoxLayout(self._model_group)
        model_layout.setSpacing(6)

        self._target_language_container = QWidget()
        target_language_layout = QHBoxLayout(self._target_language_container)
        target_language_layout.setContentsMargins(0, 0, 0, 0)
        self._target_language_label = QLabel("")
        self._target_language_combo = QComboBox()
        self._target_language_combo.currentIndexChanged.connect(self._on_target_language_changed)
        target_language_layout.addWidget(self._target_language_label)
        target_language_layout.addWidget(self._target_language_combo)
        model_layout.addWidget(self._target_language_container)

        self._tts_combo = QComboBox()
        for engine_id, engine_cls in TTSEngineRegistry.get_all_engines().items():
            self._tts_combo.addItem(engine_cls.engine_name, engine_id)
        self._tts_combo.currentIndexChanged.connect(self._on_tts_changed)
        model_layout.addWidget(self._tts_combo)

        self._model_hint = QLabel("")
        self._model_hint.setObjectName("label_muted")
        self._model_hint.setWordWrap(True)
        model_layout.addWidget(self._model_hint)
        
        self._remove_silence_checkbox = QCheckBox("")
        self._remove_silence_checkbox.toggled.connect(self._on_remove_silence_toggled)
        model_layout.addWidget(self._remove_silence_checkbox)
        
        self._kokoro_soft_trim_checkbox = QCheckBox("")
        self._kokoro_soft_trim_checkbox.toggled.connect(self._on_kokoro_soft_trim_toggled)
        model_layout.addWidget(self._kokoro_soft_trim_checkbox)

        self._kokoro_lang_container = QWidget()
        lang_layout = QHBoxLayout(self._kokoro_lang_container)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        self._kokoro_lang_label = QLabel("")
        self._kokoro_lang_combo = QComboBox()
        self._kokoro_lang_combo.currentIndexChanged.connect(self._on_kokoro_lang_changed)
        lang_layout.addWidget(self._kokoro_lang_label)
        lang_layout.addWidget(self._kokoro_lang_combo)
        model_layout.addWidget(self._kokoro_lang_container)

        self._kokoro_speed_container = QWidget()
        speed_layout = QHBoxLayout(self._kokoro_speed_container)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        self._kokoro_speed_label = QLabel("")
        self._kokoro_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._kokoro_speed_slider.setRange(50, 200)
        self._kokoro_speed_slider.setSingleStep(5)
        self._kokoro_speed_slider.setPageStep(10)
        self._kokoro_speed_slider.valueChanged.connect(self._on_kokoro_speed_changed)
        self._kokoro_speed_slider.sliderReleased.connect(self._on_kokoro_speed_released)
        self._kokoro_speed_value_label = QLabel("1.00x")
        self._kokoro_speed_value_label.setFixedWidth(48)
        self._kokoro_speed_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        speed_layout.addWidget(self._kokoro_speed_label)
        speed_layout.addWidget(self._kokoro_speed_slider)
        speed_layout.addWidget(self._kokoro_speed_value_label)
        model_layout.addWidget(self._kokoro_speed_container)

        self._f5_nfe_container = QWidget()
        f_layout = QHBoxLayout(self._f5_nfe_container)
        f_layout.setContentsMargins(0, 0, 0, 0)
        self._f5_nfe_label = QLabel("")
        self._f5_nfe_combo = QComboBox()
        self._f5_nfe_combo.currentIndexChanged.connect(self._on_f5_nfe_changed)
        f_layout.addWidget(self._f5_nfe_label)
        f_layout.addWidget(self._f5_nfe_combo)
        model_layout.addWidget(self._f5_nfe_container)
        
        layout.addWidget(self._model_group)

        # 3. Voice
        self._voice_group = QGroupBox("")
        voice_layout = QVBoxLayout(self._voice_group)
        voice_layout.setSpacing(6)

        self._voice_combo = QComboBox()
        self._voice_combo.setMaxVisibleItems(20)
        self._voice_combo.currentIndexChanged.connect(self._on_voice_preset_changed)
        voice_layout.addWidget(self._voice_combo)



        self._voice_desc = QLabel()
        self._voice_desc.setObjectName("label_muted")
        self._voice_desc.setWordWrap(True)
        voice_layout.addWidget(self._voice_desc)
        layout.addWidget(self._voice_group)

        # 4. Audio
        self._audio_group = QGroupBox("")
        audio_layout = QVBoxLayout(self._audio_group)
        audio_layout.setSpacing(6)

        self._smart_hybrid_checkbox = QCheckBox("")
        self._smart_hybrid_checkbox.toggled.connect(self._on_smart_hybrid_toggled)
        audio_layout.addWidget(self._smart_hybrid_checkbox)

        self._keep_original_audio_checkbox = QCheckBox("")
        self._keep_original_audio_checkbox.toggled.connect(self._on_keep_original_audio_toggled)
        audio_layout.addWidget(self._keep_original_audio_checkbox)

        self._volume_layout = QHBoxLayout()
        self._volume_label = QLabel("")
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        self._volume_slider.sliderReleased.connect(self._on_volume_released)
        
        self._volume_value_label = QLabel("10%")
        self._volume_value_label.setFixedWidth(40)
        self._volume_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self._volume_layout.addWidget(self._volume_label)
        self._volume_layout.addWidget(self._volume_slider)
        self._volume_layout.addWidget(self._volume_value_label)
        audio_layout.addLayout(self._volume_layout)

        self._jump_cut_checkbox = QCheckBox("")
        self._jump_cut_checkbox.toggled.connect(self._on_jump_cut_toggled)
        audio_layout.addWidget(self._jump_cut_checkbox)

        self._audio_hint = QLabel("")
        self._audio_hint.setObjectName("label_muted")
        self._audio_hint.setWordWrap(True)
        audio_layout.addWidget(self._audio_hint)
        layout.addWidget(self._audio_group)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll, 1)

    def _refresh_interface_language_options(self):
        current_language = getattr(settings, "interface_language", "ru")
        previous = self._interface_language_combo.blockSignals(True)
        self._interface_language_combo.clear()
        for code, label in get_interface_language_options():
            self._interface_language_combo.addItem(label, code)
        idx = self._interface_language_combo.findData(current_language)
        if idx >= 0:
            self._interface_language_combo.setCurrentIndex(idx)
        self._interface_language_combo.blockSignals(previous)

    def _refresh_target_language_options(self):
        current_language = getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE)
        previous = self._target_language_combo.blockSignals(True)
        self._target_language_combo.clear()
        for lang_code, label, native in get_target_language_rows():
            display_name = label if label == native else f"{label} ({native})"
            self._target_language_combo.addItem(display_name, lang_code)
        idx = self._target_language_combo.findData(current_language)
        if idx >= 0:
            self._target_language_combo.setCurrentIndex(idx)
        self._target_language_combo.blockSignals(previous)

    def _refresh_kokoro_lang_options(self):
        current = getattr(settings, "kokoro_lang", DEFAULT_KOKORO_LANG)
        previous = self._kokoro_lang_combo.blockSignals(True)
        self._kokoro_lang_combo.clear()
        for lang_code, title in get_kokoro_lang_rows():
            self._kokoro_lang_combo.addItem(title, lang_code)
        idx = self._kokoro_lang_combo.findData(current)
        if idx >= 0:
            self._kokoro_lang_combo.setCurrentIndex(idx)
        self._kokoro_lang_combo.blockSignals(previous)

    def _refresh_f5_nfe_options(self):
        current = getattr(settings, "f5_nfe_steps", 32)
        previous = self._f5_nfe_combo.blockSignals(True)
        self._f5_nfe_combo.clear()
        self._f5_nfe_combo.addItem(tr("settings.f5.fast", default="16 (Fast)"), 16)
        self._f5_nfe_combo.addItem(tr("settings.f5.standard", default="32 (Standard)"), 32)
        self._f5_nfe_combo.addItem(tr("settings.f5.high", default="64 (High)"), 64)
        self._f5_nfe_combo.addItem(tr("settings.f5.studio", default="128 (Studio)"), 128)
        idx = self._f5_nfe_combo.findData(current)
        if idx >= 0:
            self._f5_nfe_combo.setCurrentIndex(idx)
        self._f5_nfe_combo.blockSignals(previous)

    @staticmethod
    def _apply_tooltip(text: str, *widgets):
        for widget in widgets:
            widget.setToolTip(text)

    def retranslate_ui(self):
        self._title_label.setText(tr("settings.title", default="⚙ Settings"))
        self._interface_group.setTitle(tr("settings.interface_group", default="Interface"))
        self._interface_language_label.setText(
            tr("settings.interface_language", default="Interface language:")
        )
        self._model_group.setTitle(tr("settings.model_group", default="Dubbing model"))
        self._voice_group.setTitle(tr("settings.voice_group", default="Voice"))
        self._audio_group.setTitle(tr("settings.audio_group", default="Audio"))
        self._target_language_label.setText(
            tr("settings.dub_language", default="Dub language:")
        )
        self._remove_silence_checkbox.setText(
            tr("settings.remove_silence", default="Auto-trim pauses (silence)")
        )
        self._kokoro_soft_trim_checkbox.setText(
            tr("settings.soft_trim", default="Soft trim phrase endings")
        )
        self._kokoro_soft_trim_checkbox.setToolTip(
            tr(
                "settings.soft_trim_tip",
                default="Keeps the natural fade-out of the voice at the end of sentences",
            )
        )
        self._kokoro_lang_label.setText(tr("settings.accent", default="Accent:"))
        self._kokoro_speed_label.setText(tr("settings.speed", default="Speed:"))
        self._f5_nfe_label.setText(tr("settings.quality", default="Quality (NFE):"))

        self._smart_hybrid_checkbox.setText(
            tr("settings.smart_hybrid", default="Smooth audio dynamics")
        )
        self._keep_original_audio_checkbox.setText(
            tr("settings.keep_original_audio", default="Keep the original audio")
        )
        self._volume_label.setText(tr("settings.volume", default="Volume:"))
        self._jump_cut_checkbox.setText(
            tr("settings.jump_cut", default="Dynamic editing")
        )
        self._jump_cut_checkbox.setToolTip(
            tr(
                "settings.jump_cut_tip",
                default="Warning: final assembly will take longer because the video must be fully re-encoded.",
            )
        )
        self._refresh_interface_language_options()
        self._refresh_target_language_options()
        self._refresh_kokoro_lang_options()
        self._refresh_f5_nfe_options()
        self._update_voice_combo_options(settings.tts_engine)
        self._update_volume_ui_state()
        self._refresh_tooltips()

    def _refresh_tooltips(self):
        interface_tip = tr(
            "settings.interface_language_tip",
            default="Changes the language of menus, buttons, hints, and built-in dialogs in the app.",
        )
        self._apply_tooltip(interface_tip, self._interface_language_label, self._interface_language_combo)

        target_language_tip = tr(
            "settings.dub_language_tip",
            default="Choose the language into which the video's speech will be translated and dubbed.",
        )
        self._apply_tooltip(target_language_tip, self._target_language_label, self._target_language_combo)

        tts_tip = tr(
            "settings.tts_model_tip",
            default=(
                "Choose which speech engine will voice the translation. "
                "The available voices and advanced options below depend on this selection."
            ),
        )
        self._tts_combo.setToolTip(tts_tip)
        self._model_hint.setToolTip(tts_tip)

        self._remove_silence_checkbox.setToolTip(
            tr(
                "settings.remove_silence_tip",
                default=(
                    "Trims extra silent fragments in generated speech so phrases sound tighter "
                    "and the final result stays closer to the original timing."
                ),
            )
        )

        kokoro_lang_tip = tr(
            "settings.kokoro_lang_tip",
            default="Adjusts the pronunciation or accent variant used by Kokoro voices.",
        )
        self._apply_tooltip(kokoro_lang_tip, self._kokoro_lang_label, self._kokoro_lang_combo)

        kokoro_speed_tip = tr(
            "settings.kokoro_speed_tip",
            default="Sets how fast Kokoro voices speak relative to their default speed.",
        )
        self._apply_tooltip(
            kokoro_speed_tip,
            self._kokoro_speed_label,
            self._kokoro_speed_slider,
            self._kokoro_speed_value_label,
        )

        f5_quality_tip = tr(
            "settings.f5_quality_tip",
            default="Higher NFE improves quality and stability, but noticeably increases generation time.",
        )
        self._apply_tooltip(f5_quality_tip, self._f5_nfe_label, self._f5_nfe_combo)

        self._smart_hybrid_checkbox.setToolTip(
            tr(
                "settings.smart_hybrid_tip",
                default=(
                    "Smooths abrupt loudness changes so the dubbing and background audio "
                    "sound more even together."
                ),
            )
        )

        self._keep_original_audio_checkbox.setToolTip(
            tr(
                "settings.keep_original_audio_tip",
                default=(
                    "Keeps the source soundtrack under the dub. "
                    "Disable it if you want only the translated voice in the final video."
                ),
            )
        )

        self._update_voice_desc()
        self._refresh_volume_tooltip()

    def _update_tts_model_availability(self):
        target_language = getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE)
        model = self._tts_combo.model()
        for idx in range(self._tts_combo.count()):
            engine_id = self._tts_combo.itemData(idx)
            item = model.item(idx)
            if item is not None:
                item.setEnabled(tts_engine_supports_language(engine_id, target_language))

    def _sync_selected_tts_engine(self) -> bool:
        selected_engine = getattr(settings, "tts_engine", "")
        idx = self._tts_combo.findData(selected_engine)
        changed = False

        if idx < 0 and self._tts_combo.count() > 0:
            idx = 0
            settings.tts_engine = self._tts_combo.itemData(idx)
            changed = True

        if idx >= 0 and self._tts_combo.currentIndex() != idx:
            previous = self._tts_combo.blockSignals(True)
            self._tts_combo.setCurrentIndex(idx)
            self._tts_combo.blockSignals(previous)
        return changed

    def _update_voice_combo_options(self, current_tts: str):
        self._voice_combo.blockSignals(True)
        self._voice_combo.clear()

        target_language = getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE)
        voices = get_model_voice_catalog(current_tts, target_language)
        voice_items = list(voices.items())
        if current_tts == "kokoro-tts":
            voice_items.sort(key=lambda item: get_kokoro_voice_sort_key(item[0]))

        for voice_id, (name, _) in voice_items:
            self._voice_combo.addItem(name, voice_id)
            combo_index = self._voice_combo.count() - 1
            self._voice_combo.setItemData(combo_index, voices[voice_id][1], Qt.ItemDataRole.ToolTipRole)
            
        idx = self._voice_combo.findData(settings.voice_preset)
        if idx >= 0:
            self._voice_combo.setCurrentIndex(idx)
        elif self._voice_combo.count() > 0:
            self._voice_combo.setCurrentIndex(0)
            settings.voice_preset = self._voice_combo.currentData()

        self._voice_combo.blockSignals(False)
        self._update_voice_desc()

        language_name = get_target_language_display_name(target_language)
        if not tts_engine_supports_language(current_tts, target_language):
            self._model_hint.setText(
                tr(
                    "settings.model_hint.unsupported",
                    default=(
                        "The selected model does not support {language}. "
                        "Choose another dubbing model before starting."
                    ),
                    language=language_name,
                )
            )
        else:
            hints = {
                "kokoro-tts": tr(
                    "settings.model_hint.kokoro",
                    default="Kokoro is currently used for English dubbing. Voices are sorted from strongest to weakest.",
                ),
                "edge-tts": tr(
                    "settings.model_hint.edge",
                    default=f"Microsoft Edge-TTS (internet required): curated voices for {language_name}.",
                ),
                "f5-tts": tr(
                    "settings.model_hint.f5",
                    default="F5-TTS is currently kept for English dubbing from a reference WAV.",
                ),
            }
            self._model_hint.setText(hints.get(current_tts, ""))
        
        # Настраиваем видимость специфичных элементов
        self._f5_nfe_container.setVisible(current_tts == "f5-tts")
        self._kokoro_soft_trim_checkbox.setVisible(current_tts == "kokoro-tts")
        self._kokoro_lang_container.setVisible(current_tts == "kokoro-tts")
        self._kokoro_speed_container.setVisible(current_tts == "kokoro-tts")


    def _on_voice_preset_changed(self, idx):
        if idx < 0: return
        settings.voice_preset = self._voice_combo.currentData()
        self._update_voice_desc()
        self.settings_changed.emit()

    def _update_voice_desc(self):
        current_tts = self._tts_combo.currentData()
        preset_id = settings.voice_preset
        
        voices = get_model_voice_catalog(current_tts, getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE))
        if preset_id in voices:
            _, desc = voices[preset_id]
            self._voice_desc.setText(desc)
            combo_tip = tr(
                "settings.voice_tip",
                default=(
                    "Select the voice that will read the translated track. "
                    "The description below explains the current preset."
                ),
            )
            tooltip = f"{combo_tip}\n\n{desc}" if desc else combo_tip
            self._voice_combo.setToolTip(tooltip)
            self._voice_desc.setToolTip(tooltip)
        else:
            self._voice_desc.setText("")
            combo_tip = tr(
                "settings.voice_tip",
                default=(
                    "Select the voice that will read the translated track. "
                    "The description below explains the current preset."
                ),
            )
            self._voice_combo.setToolTip(combo_tip)
            self._voice_desc.setToolTip(combo_tip)

    def _on_target_language_changed(self, idx: int):
        if idx < 0:
            return
        settings.target_language = self._target_language_combo.currentData()
        self._update_tts_model_availability()
        self._update_voice_combo_options(settings.tts_engine)
        self.settings_changed.emit()

    def _on_interface_language_changed(self, idx: int):
        if idx < 0:
            return
        settings.interface_language = self._interface_language_combo.currentData()
        set_language(settings.interface_language)
        self.settings_changed.emit()

    def _on_tts_changed(self, idx):
        if idx < 0: return
        requested_engine = self._tts_combo.currentData()
        settings.tts_engine = requested_engine
        self._update_voice_combo_options(requested_engine)
        self.settings_changed.emit()

    def _on_remove_silence_toggled(self, checked: bool):
        settings.remove_tts_silence = checked
        self.settings_changed.emit()

    def _on_kokoro_soft_trim_toggled(self, checked: bool):
        settings.kokoro_soft_trim = checked
        self.settings_changed.emit()

    def _on_kokoro_lang_changed(self, idx: int):
        if idx < 0:
            return
        settings.kokoro_lang = self._kokoro_lang_combo.currentData()
        self.settings_changed.emit()

    def _on_kokoro_speed_changed(self, value: int):
        speed = value / 100.0
        settings.kokoro_speed = speed
        self._kokoro_speed_value_label.setText(f"{speed:.2f}x")

    def _on_kokoro_speed_released(self):
        self.settings_changed.emit()


    def _on_f5_nfe_changed(self, idx: int):
        if idx < 0: return
        settings.f5_nfe_steps = self._f5_nfe_combo.currentData()
        self.settings_changed.emit()

    def _on_smart_hybrid_toggled(self, checked: bool):
        settings.smart_hybrid_alignment = checked
        self.settings_changed.emit()

    def _on_keep_original_audio_toggled(self, checked: bool):
        settings.keep_original_audio = checked
        self._update_volume_ui_state()
        self.settings_changed.emit()

    def _on_jump_cut_toggled(self, checked: bool):
        settings.jump_cut_video = checked
        self.settings_changed.emit()

    def _on_volume_changed(self, value: int):
        settings.original_audio_volume = value
        self._volume_value_label.setText(f"{value}%")
        
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(QCursor.pos(), f"{value}%")

    def _on_volume_released(self):
        self.settings_changed.emit()

    def _update_volume_ui_state(self):
        is_kept = self._keep_original_audio_checkbox.isChecked()
        self._volume_label.setEnabled(is_kept)
        self._volume_slider.setEnabled(is_kept)
        self._volume_value_label.setEnabled(is_kept)
        if is_kept:
            self._audio_hint.setText(
                tr("settings.audio_mix_hint", default="Background audio will be mixed with the dub.")
            )
        else:
            self._audio_hint.setText(
                tr("settings.audio_only_hint", default="Only the dub will remain in the final video.")
            )
        self._refresh_volume_tooltip()

    def _refresh_volume_tooltip(self):
        if self._keep_original_audio_checkbox.isChecked():
            text = tr(
                "settings.volume_tip",
                default="Controls how loud the original background audio remains under the dub.",
            )
        else:
            text = tr(
                "settings.volume_tip_disabled",
                default="Enable 'Keep original audio' to adjust the background volume.",
            )
        self._apply_tooltip(text, self._volume_label, self._volume_slider, self._volume_value_label)

    def get_settings_summary(self) -> str:
        """Return a short summary for logs/status."""
        current_tts = settings.tts_engine
        voices = get_model_voice_catalog(current_tts, getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE))
        voice_info = voices.get(settings.voice_preset, (settings.voice_preset, ""))
        voice_name = voice_info[0]
        
        model_name = self.TTS_MODELS.get(current_tts, current_tts)
        language_name = get_target_language_display_name(getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE))
        audio_name = (
            f"original audio {settings.original_audio_volume}%"
            if settings.keep_original_audio
            else "dub only"
        )
        if current_tts == "kokoro-tts":
            return f"{voice_name} | {language_name} | {model_name} | {settings.kokoro_lang} | {settings.kokoro_speed:.2f}x | {audio_name}"
        return f"{voice_name} | {language_name} | {model_name} | {audio_name}"

    def _apply_saved_settings(self):
        widgets = [
            self._interface_language_combo, self._voice_combo, self._tts_combo, self._target_language_combo, self._smart_hybrid_checkbox,
            self._remove_silence_checkbox, self._keep_original_audio_checkbox, 
            self._volume_slider, self._jump_cut_checkbox, 
            self._kokoro_soft_trim_checkbox, self._kokoro_lang_combo,
            self._kokoro_speed_slider, self._f5_nfe_combo,
        ]
        corrected = False
        for widget in widgets:
            widget.blockSignals(True)

        target_language = getattr(settings, "target_language", DEFAULT_TARGET_LANGUAGE)
        target_language_idx = self._target_language_combo.findData(target_language)
        if target_language_idx >= 0:
            self._target_language_combo.setCurrentIndex(target_language_idx)
        else:
            self._target_language_combo.setCurrentIndex(0)
            settings.target_language = self._target_language_combo.currentData()
            corrected = True

        interface_language = getattr(settings, "interface_language", "ru")
        interface_language_idx = self._interface_language_combo.findData(interface_language)
        if interface_language_idx >= 0:
            self._interface_language_combo.setCurrentIndex(interface_language_idx)
        else:
            self._interface_language_combo.setCurrentIndex(0)
            settings.interface_language = self._interface_language_combo.currentData()
            corrected = True

        self._update_tts_model_availability()
        if self._sync_selected_tts_engine():
            corrected = True


            
        # Update voice combinations based on loaded model
        self._update_voice_combo_options(settings.tts_engine)

        voice_matched = False
        for i in range(self._voice_combo.count()):
            if self._voice_combo.itemData(i) == settings.voice_preset:
                self._voice_combo.setCurrentIndex(i)
                voice_matched = True
                break
        if not voice_matched and self._voice_combo.count():
            self._voice_combo.setCurrentIndex(0)
            settings.voice_preset = self._voice_combo.currentData()
            corrected = True

        self._smart_hybrid_checkbox.setChecked(settings.smart_hybrid_alignment)
        self._remove_silence_checkbox.setChecked(settings.remove_tts_silence)
        self._kokoro_soft_trim_checkbox.setChecked(settings.kokoro_soft_trim)
        kokoro_lang = getattr(settings, "kokoro_lang", DEFAULT_KOKORO_LANG)
        kokoro_lang_idx = self._kokoro_lang_combo.findData(kokoro_lang)
        if kokoro_lang_idx >= 0:
            self._kokoro_lang_combo.setCurrentIndex(kokoro_lang_idx)
        else:
            self._kokoro_lang_combo.setCurrentIndex(0)
            settings.kokoro_lang = self._kokoro_lang_combo.currentData()
            corrected = True
        self._keep_original_audio_checkbox.setChecked(settings.keep_original_audio)
        self._jump_cut_checkbox.setChecked(settings.jump_cut_video)
        self._volume_slider.setValue(settings.original_audio_volume)
        kokoro_speed = float(getattr(settings, "kokoro_speed", DEFAULT_KOKORO_SPEED))
        kokoro_speed = max(0.5, min(2.0, kokoro_speed))
        self._kokoro_speed_slider.setValue(int(round(kokoro_speed * 100)))
        settings.kokoro_speed = kokoro_speed
        
        f5_idx = self._f5_nfe_combo.findData(settings.f5_nfe_steps)
        if f5_idx >= 0:
            self._f5_nfe_combo.setCurrentIndex(f5_idx)
        else:
            self._f5_nfe_combo.setCurrentIndex(1)
             
        self._on_volume_changed(settings.original_audio_volume)
        self._on_kokoro_speed_changed(int(round(settings.kokoro_speed * 100)))
        self._update_volume_ui_state()

        for widget in widgets:
            widget.blockSignals(False)

        self._update_voice_desc()
        if corrected:
            settings.save()

    # ── Public control helpers for menus ──────────────────────────────────

    def set_tts_engine(self, engine_id: str):
        idx = self._tts_combo.findData(engine_id)
        if idx >= 0 and self._tts_combo.currentIndex() != idx:
            self._tts_combo.setCurrentIndex(idx)

    def set_interface_language(self, language_code: str):
        idx = self._interface_language_combo.findData(language_code)
        if idx >= 0 and self._interface_language_combo.currentIndex() != idx:
            self._interface_language_combo.setCurrentIndex(idx)

    def set_target_language(self, language_code: str):
        idx = self._target_language_combo.findData(language_code)
        if idx >= 0 and self._target_language_combo.currentIndex() != idx:
            self._target_language_combo.setCurrentIndex(idx)

    def set_remove_silence(self, checked: bool):
        if self._remove_silence_checkbox.isChecked() != checked:
            self._remove_silence_checkbox.setChecked(checked)

    def set_kokoro_soft_trim(self, checked: bool):
        if self._kokoro_soft_trim_checkbox.isChecked() != checked:
            self._kokoro_soft_trim_checkbox.setChecked(checked)

    def set_kokoro_lang(self, lang_code: str):
        idx = self._kokoro_lang_combo.findData(lang_code)
        if idx >= 0 and self._kokoro_lang_combo.currentIndex() != idx:
            self._kokoro_lang_combo.setCurrentIndex(idx)


    def set_f5_nfe_steps(self, value: int):
        idx = self._f5_nfe_combo.findData(value)
        if idx >= 0 and self._f5_nfe_combo.currentIndex() != idx:
            self._f5_nfe_combo.setCurrentIndex(idx)

    def set_smart_hybrid_alignment(self, checked: bool):
        if self._smart_hybrid_checkbox.isChecked() != checked:
            self._smart_hybrid_checkbox.setChecked(checked)

    def set_keep_original_audio(self, checked: bool):
        if self._keep_original_audio_checkbox.isChecked() != checked:
            self._keep_original_audio_checkbox.setChecked(checked)

    def set_jump_cut_video(self, checked: bool):
        if self._jump_cut_checkbox.isChecked() != checked:
            self._jump_cut_checkbox.setChecked(checked)
