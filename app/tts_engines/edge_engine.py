"""
Edge-TTS engine — clean preset-based speech synthesis without reference cloning.
"""
from pathlib import Path

from app.language_catalog import TARGET_LANGUAGE_ROWS, _get_target_language_label
from app.tts_engines.base_engine import BaseTTSEngine, TTSEngineRegistry
from app.tts_engines.common import COMMON_GENDER_LABELS, COMMON_VOICE_DESCRIPTION_TEMPLATE
from app.i18n import get_language, DEFAULT_INTERFACE_LANGUAGE, LANGUAGE_META

_EDGE_VOICE_META = {
    "en": (("en-US-JennyNeural", "Jenny", "f"), ("en-US-AriaNeural", "Aria", "f"), ("en-US-GuyNeural", "Guy", "m"), ("en-US-ChristopherNeural", "Christopher", "m")),
    "zh": (("zh-CN-XiaoxiaoNeural", "Xiaoxiao", "f"), ("zh-CN-YunjianNeural", "Yunjian", "m")),
    "hi": (("hi-IN-SwaraNeural", "Swara", "f"), ("hi-IN-MadhurNeural", "Madhur", "m")),
    "es": (("es-ES-XimenaNeural", "Ximena", "f"), ("es-ES-AlvaroNeural", "Alvaro", "m")),
    "fr": (("fr-FR-DeniseNeural", "Denise", "f"), ("fr-FR-HenriNeural", "Henri", "m")),
    "ar": (("ar-SA-ZariyahNeural", "Zariyah", "f"), ("ar-SA-HamedNeural", "Hamed", "m")),
    "bn": (("bn-BD-NabanitaNeural", "Nabanita", "f"), ("bn-BD-PradeepNeural", "Pradeep", "m")),
    "pt": (("pt-BR-FranciscaNeural", "Francisca", "f"), ("pt-BR-AntonioNeural", "Antonio", "m")),
    "ru": (("ru-RU-SvetlanaNeural", "Svetlana", "f"), ("ru-RU-DmitryNeural", "Dmitry", "m")),
    "uk": (("uk-UA-PolinaNeural", "Polina", "f"), ("uk-UA-OstapNeural", "Ostap", "m")),
}

EDGE_VOICE_CONFIGS = {
    "en-US-JennyNeural": {"rate": "-4%", "pitch": "-6Hz", "volume": "+0%"},
    "en-US-AriaNeural": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
    "en-US-GuyNeural": {"rate": "-6%", "pitch": "-10Hz", "volume": "+0%"},
    "en-US-ChristopherNeural": {"rate": "-2%", "pitch": "-2Hz", "volume": "+0%"},
}

EDGE_LEGACY_VOICE_ALIASES = {
    "female_warm": "en-US-JennyNeural",
    "female_clear": "en-US-AriaNeural",
    "male_medium": "en-US-GuyNeural",
    "male_deep": "en-US-ChristopherNeural",
}


@TTSEngineRegistry.register("edge-tts")
class EdgeTTSEngine(BaseTTSEngine):
    """Microsoft Edge neural voices for clean preset TTS."""

    engine_name = "Edge TTS (Online/API)"
    supported_languages = frozenset([t[0] for t in TARGET_LANGUAGE_ROWS])

    @classmethod
    def get_voice_catalog(cls, language_code: str = "en") -> dict[str, tuple[str, str]]:
        if language_code not in cls.supported_languages:
            return {}
        
        language = get_language()
        interface_language = language if language in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE
            
        gender_labels = COMMON_GENDER_LABELS.get(interface_language, COMMON_GENDER_LABELS["en"])
        language_label = _get_target_language_label(language_code, interface_language)
        template = COMMON_VOICE_DESCRIPTION_TEMPLATE.get(interface_language, COMMON_VOICE_DESCRIPTION_TEMPLATE["en"])
    
        catalog: dict[str, tuple[str, str]] = {}
        for voice_id, speaker_name, gender_code in _EDGE_VOICE_META.get(language_code, _EDGE_VOICE_META["en"]):
            emoji = "👩" if gender_code == "f" else "🎙"
            display_name = f"{emoji} {language_label} · {speaker_name}"
            description = template.format(
                language=language_label,
                gender=gender_labels.get(gender_code, gender_labels["voice"]),
            )
            catalog[voice_id] = (display_name, description)
        return catalog

    def __init__(self):
        self._edge_tts = None

    def load_model(self, device: str = "cuda"):
        """Validate that edge-tts is available. Device is not used here."""
        try:
            import edge_tts
        except ImportError:
            raise ImportError(
                "Edge-TTS не установлен. Установите: pip install edge-tts"
            )
        self._edge_tts = edge_tts

    def use_preset_voice(self, preset_id: str) -> dict:
        """Create an Edge neural voice configuration based on the model ID."""
        voice_id = EDGE_LEGACY_VOICE_ALIASES.get(preset_id, preset_id)
        config = dict(EDGE_VOICE_CONFIGS.get(voice_id, {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}))
        config["voice"] = voice_id
        return config

    def synthesize(
        self,
        text: str,
        voice_ref: dict,
        output_path: str,
        nfe_step: int = 32,
        speed: float = 1.0,
        seed: int | None = None,
    ) -> str:
        """Generate speech via Edge-TTS and convert it to WAV for the pipeline."""
        if self._edge_tts is None:
            raise RuntimeError("Модель Edge-TTS не загружена")

        from pydub import AudioSegment

        output_file = Path(output_path)
        temp_mp3 = output_file.with_suffix(".edge.mp3")

        try:
            communicate = self._edge_tts.Communicate(
                text=text,
                voice=voice_ref["voice"],
                rate=voice_ref.get("rate", "+0%"),
                pitch=voice_ref.get("pitch", "+0Hz"),
                volume=voice_ref.get("volume", "+0%"),
            )
            communicate.save_sync(str(temp_mp3))

            audio = AudioSegment.from_file(temp_mp3)
            audio = audio.set_channels(1).set_frame_rate(44100)
            audio.export(output_file, format="wav")
        finally:
            temp_mp3.unlink(missing_ok=True)

        return str(output_file)

    def unload_model(self):
        """Release references to the imported module."""
        self._edge_tts = None
