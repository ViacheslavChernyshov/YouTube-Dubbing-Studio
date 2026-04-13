"""
Kokoro-TTS engine (ONNX version) — lightning-fast, highly realistic, standalone TTS.
"""
import os
import requests
import soundfile as sf
import numpy as np
import librosa
import logging
from app.tts_engines.base_engine import BaseTTSEngine, TTSEngineRegistry
from app.tts_engines.common import COMMON_GENDER_LABELS
from app.config import DEFAULT_KOKORO_LANG, get_kokoro_models_dir, settings
from app.i18n import get_language, DEFAULT_INTERFACE_LANGUAGE, LANGUAGE_META

logger = logging.getLogger(__name__)

KOKORO_VOICE_IDS = (
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_kore", "af_nicole", "af_nova", "af_sarah",
    "am_fenrir", "am_michael", "am_puck", "bf_emma", "bf_isabella", "bm_fable", "bm_george",
    "ff_siwis", "hf_alpha", "hf_beta", "hm_omega", "hm_psi", "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_tebukuro",
)

KOKORO_LANGUAGE_INFO = {
    "a": {"label": "американский английский", "badge": "US", "family_note": "Самая предсказуемая группа для англоязычного дубляжа."},
    "b": {"label": "британский английский", "badge": "UK", "family_note": "Хороший вариант, если нужен британский оттенок речи."},
    "f": {"label": "французский профиль", "badge": "FR", "family_note": "На английском звучит интересно, но уже ближе к экспериментальному стилю."},
    "h": {"label": "хинди-профиль", "badge": "HI", "family_note": "Подходит для экспериментов с тембром; для нейтрального англоязычного дубляжа есть варианты сильнее."},
    "i": {"label": "итальянский профиль", "badge": "IT", "family_note": "На английском даёт более окрашенный тембр, чем английские семейства."},
    "j": {"label": "японский профиль", "badge": "JP", "family_note": "Лучше рассматривать как стилизованный тембр, а не как нейтральный английский дикторский голос."},
}

KOKORO_VOICE_QUALITY = {
    "af_heart": {"overall_grade": "A"}, "af_alloy": {"overall_grade": "C"}, "af_aoede": {"overall_grade": "C+"},
    "af_bella": {"overall_grade": "A-"}, "af_kore": {"overall_grade": "C+"}, "af_nicole": {"overall_grade": "B-"},
    "af_nova": {"overall_grade": "C"}, "af_sarah": {"overall_grade": "C+"}, "am_fenrir": {"overall_grade": "C+"},
    "am_michael": {"overall_grade": "C+"}, "am_puck": {"overall_grade": "C+"}, "bf_emma": {"overall_grade": "B-"},
    "bf_isabella": {"overall_grade": "C"}, "bm_fable": {"overall_grade": "C"}, "bm_george": {"overall_grade": "C"},
    "ff_siwis": {"overall_grade": "B-"}, "hf_alpha": {"overall_grade": "C"}, "hf_beta": {"overall_grade": "C"},
    "hm_omega": {"overall_grade": "C"}, "hm_psi": {"overall_grade": "C"}, "if_sara": {"overall_grade": "C"},
    "im_nicola": {"overall_grade": "C"}, "jf_alpha": {"overall_grade": "C+"}, "jf_gongitsune": {"overall_grade": "C"},
    "jf_tebukuro": {"overall_grade": "C"},
}

KOKORO_RECOMMENDED_VOICES = {"af_heart", "af_bella", "af_nicole", "bf_emma"}


_KOKORO_FAMILY_LABELS = {
    "en": {"a": "American English", "b": "British English", "f": "French profile", "h": "Hindi profile", "i": "Italian profile", "j": "Japanese profile"},
    "ru": {"a": "американский английский", "b": "британский английский", "f": "французский профиль", "h": "хинди-профиль", "i": "итальянский профиль", "j": "японский профиль"},
}

_KOKORO_UI_TEXT = {
    "en": {"unknown_profile": "unknown profile", "profile_line": "Profile: {profile}, {gender}.", "recommendation_line": "Recommendation: one of the best options for regular English dubbing.", "english_stable": "The most predictable family for English dubbing.", "british_tone": "A good choice if you want a British tone.", "stylized_family": "In English this family works more as a stylized timbre than a neutral narrator.", "accent_english_line": "The en-US / en-GB accent is adjusted separately and usually behaves predictably.", "accent_non_english_line": "The en-US / en-GB accent affects pronunciation, but it does not make the timbre neutral-English.", "voice_description_template": "{language} {gender} voice for dubbing.", "cloned_voice_description": "Cloned voice (requires a local audio file)."},
    "ru": {"unknown_profile": "неизвестный профиль", "profile_line": "Профиль: {profile}, {gender}.", "recommendation_line": "Рекомендация: один из самых удачных вариантов для обычной англоязычной озвучки.", "english_stable": "Самая предсказуемая группа для англоязычного дубляжа.", "british_tone": "Хороший вариант, если нужен британский оттенок речи.", "stylized_family": "На английском эта группа работает скорее как стилизованный тембр, чем как нейтральный диктор.", "accent_english_line": "Акцент en-US / en-GB меняется отдельно и обычно работает предсказуемо.", "accent_non_english_line": "Акцент en-US / en-GB влияет на произношение, но не делает тембр нейтрально-английским.", "voice_description_template": "{language} {gender} голос для озвучки.", "cloned_voice_description": "Клонированный голос (требует локальный аудиофайл)."},
}

def _build_kokoro_voice_catalog() -> dict[str, tuple[str, str]]:
    language = get_language()
    interface_language = language if language in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE
    ui_text = _KOKORO_UI_TEXT.get(interface_language, _KOKORO_UI_TEXT["en"])
    
    voices: dict[str, tuple[str, str]] = {}
    for voice_id in KOKORO_VOICE_IDS:
        family_code = voice_id[0]
        gender_code = voice_id[1]
        raw_name = voice_id.split("_", 1)[1].replace("_", " ").title()
        language_info = {
            "label": _KOKORO_FAMILY_LABELS.get(interface_language, _KOKORO_FAMILY_LABELS["en"]).get(
                family_code, ui_text["unknown_profile"]
            ),
            "badge": KOKORO_LANGUAGE_INFO.get(family_code, {}).get("badge", family_code.upper()),
        }
        emoji = "👩" if gender_code == "f" else "🎙"
        overall_grade = KOKORO_VOICE_QUALITY.get(voice_id, {}).get("overall_grade")
        parts = [raw_name, language_info["badge"]]
        if overall_grade:
            parts.append(overall_grade)
            
        display_name = f"{emoji} {' · '.join(parts)}"
        
        # Build description
        gender_label = COMMON_GENDER_LABELS.get(interface_language, COMMON_GENDER_LABELS["en"]).get(
            gender_code, COMMON_GENDER_LABELS.get(interface_language, COMMON_GENDER_LABELS["en"])["voice"]
        )
        lines = [
            f"{raw_name} ({voice_id})" + (f" · {overall_grade}" if overall_grade else ""),
            ui_text["profile_line"].format(profile=language_info["label"], gender=gender_label),
        ]
        if voice_id in KOKORO_RECOMMENDED_VOICES:
            lines.append(ui_text["recommendation_line"])
        else:
            if family_code == "a": lines.append(ui_text["english_stable"])
            elif family_code == "b": lines.append(ui_text["british_tone"])
            else: lines.append(ui_text["stylized_family"])
        if family_code in {"a", "b"}:
            lines.append(ui_text["accent_english_line"])
        else:
            lines.append(ui_text["accent_non_english_line"])
            
        voices[voice_id] = (display_name, "\n".join(lines))
    return voices


_KOKORO_ACCENT_LABELS = {
    "en": {"en-us": "en-US (American)", "en-gb": "en-GB (British)"},
    "ru": {"en-us": "en-US (Американский)", "en-gb": "en-GB (Британский)"},
}

def get_kokoro_lang_rows() -> tuple[tuple[str, str], ...]:
    language = get_language()
    interface_language = language if language in LANGUAGE_META else DEFAULT_INTERFACE_LANGUAGE
    table = _KOKORO_ACCENT_LABELS.get(interface_language, _KOKORO_ACCENT_LABELS["en"])
    
    return (
        ("en-us", table.get("en-us", "en-US (American)")),
        ("en-gb", table.get("en-gb", "en-GB (British)")),
    )

KOKORO_GRADE_SORT_ORDER = {"A": 900, "A-": 850, "B-": 700, "C+": 600, "C": 500, None: 300}
KOKORO_VOICE_INDEX = {vid: i for i, vid in enumerate(KOKORO_VOICE_IDS)}

def get_kokoro_voice_sort_key(voice_id: str) -> tuple[int, int, int]:
    quality_info = KOKORO_VOICE_QUALITY.get(voice_id, {})
    overall_grade = quality_info.get("overall_grade")
    grade_rank = KOKORO_GRADE_SORT_ORDER.get(overall_grade, KOKORO_GRADE_SORT_ORDER[None])
    english_family_rank = 0 if voice_id[:1] in {"a", "b"} else 1
    source_order = KOKORO_VOICE_INDEX.get(voice_id, len(KOKORO_VOICE_INDEX))
    return (-grade_rank, english_family_rank, source_order)


@TTSEngineRegistry.register("kokoro-tts")
class KokoroEngine(BaseTTSEngine):
    """Kokoro-TTS ONNX engine for highly realistic synthesis without PyTorch dependency."""

    engine_name = "Kokoro TTS (Fast/Local)"
    supported_languages = frozenset({"en"})

    MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
    VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

    @classmethod
    def get_voice_catalog(cls, language_code: str = "en") -> dict[str, tuple[str, str]]:
        if language_code not in cls.supported_languages:
            return {}
        return _build_kokoro_voice_catalog()

    def __init__(self):
        self._kokoro = None
        self._assets_dir = get_kokoro_models_dir()
        self._model_path = self._assets_dir / "kokoro-v1.0.onnx"
        self._voices_path = self._assets_dir / "voices-v1.0.bin"

    @staticmethod
    def _emit_progress(progress_callback, current, total, message: str):
        if progress_callback is not None:
            progress_callback(current, total, message)

    def ensure_assets(self, progress_callback=None):
        """Download ONNX model and voices if they don't exist."""
        self._assets_dir.mkdir(parents=True, exist_ok=True)
        
        for name, url, path in [
            ("Model", self.MODEL_URL, self._model_path),
            ("Voices", self.VOICES_URL, self._voices_path)
        ]:
            if not path.exists():
                logger.info(f"Скачивание Kokoro {name} (может занять время)...")
                try:
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # Create intermediate file then rename to avoid corruption
                    tmp_path = str(path) + ".tmp"
                    
                    with open(tmp_path, "wb") as f:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                self._emit_progress(
                                    progress_callback,
                                    downloaded,
                                    total_size if total_size > 0 else None,
                                    f"Kokoro {name}: {path.name}",
                                )
                                
                    os.rename(tmp_path, path)
                    logger.info(f"Kokoro {name} успешно скачан в {path}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки Kokoro {name}: {e}")
                    if path.exists():
                        path.unlink() # cleanup
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise RuntimeError(f"Не удалось скачать {name} для Kokoro: {e}")

    def load_model(self, device: str = "cpu"):
        """Load Kokoro-ONNX pipeline."""
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise ImportError(
                "Kokoro-ONNX не установлен. Выполните: pip install kokoro-onnx soundfile requests numpy"
            )

        self.ensure_assets()
        
        # Load the ONNX model into memory
        logger.info(f"Загрузка модели Kokoro-ONNX (device={device})...")
        try:
            self._kokoro = Kokoro(str(self._model_path), str(self._voices_path))
        except Exception as e:
            raise RuntimeError(f"Ошибка инициализации Kokoro-ONNX: {e}\nУбедитесь, что onnxruntime установлен.")

    def use_preset_voice(self, preset_id: str) -> str:
        """Return the raw Kokoro voice ID passed from the GUI."""
        return preset_id

    def synthesize(
        self,
        text: str,
        voice_ref: str | dict,
        output_path: str,
        nfe_step: int = 32, # Ignored for Kokoro
        speed: float = 1.0,
        seed: int | None = None,
    ) -> str:
        """Synthesize speech using Kokoro-ONNX."""
        if self._kokoro is None:
            raise RuntimeError("Модель Kokoro-ONNX не загружена")
             
        try:
            if isinstance(voice_ref, dict):
                voice_id = voice_ref.get("voice", "")
                lang = voice_ref.get("lang", DEFAULT_KOKORO_LANG)
                remove_tts_silence = voice_ref.get("remove_tts_silence", True)
                soft_trim = voice_ref.get("kokoro_soft_trim", True)
            else:
                voice_id = voice_ref
                lang = DEFAULT_KOKORO_LANG
                remove_tts_silence = True
                soft_trim = True
             
            samples, sample_rate = self._kokoro.create(
                text,
                voice=voice_id,
                speed=speed,
                lang=lang,
            )
            
            if samples is None or len(samples) == 0:
                logger.warning(f"Kokoro-ONNX вернул пустой аудио поток: {text}")
                samples = np.zeros(24000, dtype=np.float32)
                sample_rate = 24000
            else:
                # Удаляем макроблоки тишины в начале и конце
                if remove_tts_silence:
                    top_db = 45 if soft_trim else 35
                    samples, _ = librosa.effects.trim(samples, top_db=top_db)
                
            sf.write(output_path, samples, sample_rate)
            return output_path
        except Exception as e:
            logger.error(f"Ошибка генерации Kokoro-ONNX: {e}")
            raise RuntimeError(f"Ошибка при синтезе речи (Kokoro-ONNX): {e}")

    def unload_model(self):
        """Free memory."""
        if self._kokoro is not None:
            del self._kokoro
            self._kokoro = None
