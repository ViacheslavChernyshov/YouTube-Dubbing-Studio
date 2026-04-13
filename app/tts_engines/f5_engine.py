"""
F5-TTS engine — high-quality synthesis with preset reference voices.
"""
import logging

from app.config import DEFAULT_TTS_NFE_STEPS, DEFAULT_TTS_SPEED, get_f5_cache_dir
from app.tts_engines.base_engine import BaseTTSEngine, TTSEngineRegistry
from app.i18n import get_language, DEFAULT_INTERFACE_LANGUAGE, LANGUAGE_META

logger = logging.getLogger(__name__)

_F5_PRESET_LABELS = {
    "en": {"female_warm": "👩 Female (warm)", "female_clear": "💁 Female (clear)", "male_medium": "🗣 Male (medium)", "male_deep": "🎙 Male (deep)"},
    "ru": {"female_warm": "👩 Женский (тёплый)", "female_clear": "💁 Женский (чистый)", "male_medium": "🗣 Мужской (средний)", "male_deep": "🎙 Мужской (низкий)"},
    "uk": {"female_warm": "👩 Жіночий (теплий)", "female_clear": "💁 Жіночий (чистий)", "male_medium": "🗣 Чоловічий (середній)", "male_deep": "🎙 Чоловічий (низький)"},
    "zh": {"female_warm": "👩 女声（温暖）", "female_clear": "💁 女声（清晰）", "male_medium": "🗣 男声（中等）", "male_deep": "🎙 男声（低沉）"},
    "hi": {"female_warm": "👩 महिला (गर्म)", "female_clear": "💁 महिला (साफ़)", "male_medium": "🗣 पुरुष (मध्यम)", "male_deep": "🎙 पुरुष (गहरी)"},
    "es": {"female_warm": "👩 Femenina (cálida)", "female_clear": "💁 Femenina (clara)", "male_medium": "🗣 Masculina (media)", "male_deep": "🎙 Masculina (grave)"},
    "fr": {"female_warm": "👩 Féminine (chaleureuse)", "female_clear": "💁 Féminine (claire)", "male_medium": "🗣 Masculine (moyenne)", "male_deep": "🎙 Masculine (grave)"},
    "ar": {"female_warm": "👩 نسائي (دافئ)", "female_clear": "💁 نسائي (واضح)", "male_medium": "🗣 رجالي (متوسط)", "male_deep": "🎙 رجالي (عميق)"},
    "bn": {"female_warm": "👩 নারী (উষ্ণ)", "female_clear": "💁 নারী (স্বচ্ছ)", "male_medium": "🗣 পুরুষ (মাঝারি)", "male_deep": "🎙 পুরুষ (গভীর)"},
    "pt": {"female_warm": "👩 Feminina (quente)", "female_clear": "💁 Feminina (clara)", "male_medium": "🗣 Masculina (média)", "male_deep": "🎙 Masculina (grave)"},
}

_CLONED_VOICE_DESC = {
    "en": "Cloned voice (requires a local audio file).",
    "ru": "Клонированный голос (требует локальный аудиофайл).",
    "uk": "Клонований голос (потрібен локальний аудіофайл).",
    "zh": "克隆语音（需要本地音频文件）。",
    "hi": "क्लोन की गई आवाज़ (स्थानीय ऑडियो फ़ाइल आवश्यक)।",
    "es": "Voz clonada (requiere un archivo de audio local).",
    "fr": "Voix clonée (nécessite un fichier audio local).",
    "ar": "صوت مستنسخ (يتطلب ملفاً صوتياً محلياً).",
    "bn": "ক্লোন করা ভয়েস (লোকাল অডিও ফাইল প্রয়োজন)।",
    "pt": "Voz clonada (requer um arquivo de áudio local).",
}

@TTSEngineRegistry.register("f5-tts")
class F5TTSEngine(BaseTTSEngine):
    """F5-TTS engine for preset-based speech synthesis."""

    engine_name = "F5-TTS (High Quality/Local)"
    supported_languages = frozenset({"en"})

    @classmethod
    def get_voice_catalog(cls, language_code: str = "en") -> dict[str, tuple[str, str]]:
        if language_code not in cls.supported_languages:
            return {}
            
        language = get_language()
        interface_language = language if language in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE
        
        labels = _F5_PRESET_LABELS.get(interface_language, _F5_PRESET_LABELS["en"])
        description = _CLONED_VOICE_DESC.get(interface_language, _CLONED_VOICE_DESC["en"])
        return {
            preset_id: (label, description)
            for preset_id, label in labels.items()
        }

    def __init__(self):
        self._model = None
        self._device = "cuda"
        self._sway_compat_logged = False

    def load_model(self, device: str = "cuda"):
        """Load F5-TTS model."""
        self._device = device
        # Try to find the preloaded model to prevent cached_path block
        ckpt_file = ""
        base_dir = get_f5_cache_dir() / "models--SWivid--F5-TTS" / "snapshots"
        if base_dir.exists():
            safetensors = list(base_dir.rglob("F5TTS_Base/model_1200000.safetensors"))
            if safetensors:
                ckpt_file = str(safetensors[0])

        try:
            from f5_tts.api import F5TTS
            self._model = F5TTS(
                device=device,
                hf_cache_dir=str(get_f5_cache_dir()),
                ckpt_file=ckpt_file,
            )
        except ImportError:
            raise ImportError(
                "F5-TTS не установлен. Установите: pip install f5-tts"
            )

    def use_preset_voice(self, preset_id: str) -> dict:
        """
        Load a preset voice reference.
        Returns dict with reference audio path and text.
        """
        from app.tts_engines.voice_presets import (
            get_preset_path, get_preset_ref_text, is_preset_available,
            generate_presets_with_tts,
        )

        if not is_preset_available(preset_id):
            # Try to generate the preset
            generate_presets_with_tts()

        preset_path = get_preset_path(preset_id)
        if preset_path is None:
            raise FileNotFoundError(
                f"Голосовой пресет '{preset_id}' не найден. "
                f"Поместите WAV-файл в models/voice_presets/{preset_id}.wav"
            )

        ref_text = get_preset_ref_text(preset_id)

        return {
            "ref_audio": str(preset_path),
            "ref_text": ref_text,
        }

    def synthesize(
        self,
        text: str,
        voice_ref: dict,
        output_path: str,
        nfe_step: int = DEFAULT_TTS_NFE_STEPS,
        speed: float = DEFAULT_TTS_SPEED,
        seed: int | None = None,
    ) -> str:
        """Synthesize speech using F5-TTS with the selected preset voice."""
        if self._model is None:
            raise RuntimeError("Модель F5-TTS не загружена")

        ref_audio = voice_ref["ref_audio"]
        ref_text = voice_ref.get("ref_text", "")

        infer_kwargs = dict(
            ref_file=ref_audio,
            ref_text=ref_text,
            gen_text=text,
            file_wave=output_path,
            cross_fade_duration=0.0,
            nfe_step=nfe_step,
            remove_silence=True,
            speed=speed,
            seed=0 if seed is None else seed,
        )
        if self._device.startswith("cuda") and nfe_step >= 96:
            # F5-TTS can build non-monotonic timesteps with sway sampling on fp16 CUDA at high NFE.
            infer_kwargs["sway_sampling_coef"] = None
            if not self._sway_compat_logged:
                logger.warning(
                    "F5-TTS: sway sampling disabled for CUDA NFE=%s to avoid timestep assertion",
                    nfe_step,
                )
                self._sway_compat_logged = True

        try:
            self._model.infer(**infer_kwargs)
        except AssertionError as exc:
            if "t must be strictly increasing or decreasing" not in str(exc):
                raise
            if "sway_sampling_coef" in infer_kwargs:
                raise
            logger.warning(
                "F5-TTS: retrying without sway sampling after timestep assertion at NFE=%s",
                nfe_step,
            )
            infer_kwargs["sway_sampling_coef"] = None
            self._model.infer(**infer_kwargs)

        return output_path

    def unload_model(self):
        """Free model resources."""
        if self._model is not None:
            del self._model
            self._model = None
            self._sway_compat_logged = False
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
