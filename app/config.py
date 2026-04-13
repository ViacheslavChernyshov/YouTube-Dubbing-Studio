"""
Application configuration — paths, constants, model identifiers.
"""
import os
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, fields, replace

from app.i18n import DEFAULT_INTERFACE_LANGUAGE, LANGUAGE_META, get_language, tr
from app.language_catalog import DEFAULT_TARGET_LANGUAGE


# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
PORTABLE_CONFIG_FILE = BASE_DIR / "portable_config.json"
DEFAULT_DATA_DIR = BASE_DIR / "data"


def _resolve_user_path(value: str | Path | None, default: Path) -> Path:
    if value is None or str(value).strip() == "":
        return default.resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _serialize_user_path(value: str | Path, *, prefer_relative: bool = True) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    else:
        path = path.resolve()

    if prefer_relative:
        try:
            return str(path.relative_to(BASE_DIR)).replace("\\", "/")
        except ValueError:
            pass
    return str(path)


def _load_portable_config() -> dict:
    defaults = {
        "data_dir": "data",
        "ffmpeg_path": "",
        "cookies_path": "",
    }
    if not PORTABLE_CONFIG_FILE.exists():
        return defaults

    try:
        with open(PORTABLE_CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return defaults
        return {
            "data_dir": str(loaded.get("data_dir", defaults["data_dir"]) or defaults["data_dir"]),
            "ffmpeg_path": str(loaded.get("ffmpeg_path", defaults["ffmpeg_path"]) or ""),
            "cookies_path": str(loaded.get("cookies_path", defaults["cookies_path"]) or ""),
        }
    except Exception:
        return defaults


def _prepend_to_path(path: Path):
    try:
        resolved = path.resolve()
    except Exception:
        return
    if not resolved.exists():
        return

    current_path = os.environ.get("PATH", "")
    parts = [part for part in current_path.split(os.pathsep) if part]
    resolved_norm = os.path.normcase(str(resolved))
    if any(os.path.normcase(part) == resolved_norm for part in parts):
        return

    os.environ["PATH"] = (
        f"{resolved}{os.pathsep}{current_path}" if current_path else str(resolved)
    )


def _find_ffmpeg_default(data_dir: Path) -> str:
    """Locate ffmpeg binary."""
    local_ffmpeg = data_dir / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.is_file():
        return str(local_ffmpeg)

    path = shutil.which("ffmpeg")
    if path:
        return path
    # Fallback common locations on Windows
    for candidate in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return "ffmpeg"  # hope it's on PATH at runtime


def _resolve_ffmpeg_path(portable_config: dict, data_dir: Path) -> str:
    custom = str(portable_config.get("ffmpeg_path", "") or "").strip()
    if custom:
        resolved = _resolve_user_path(custom, Path(custom))
        if resolved.exists():
            return str(resolved)
    return _find_ffmpeg_default(data_dir)


def _resolve_cookies_file(portable_config: dict, data_dir: Path) -> Path:
    custom = str(portable_config.get("cookies_path", "") or "").strip()
    if custom:
        return _resolve_user_path(custom, data_dir / "cookies.txt")
    return (data_dir / "cookies.txt").resolve()


def _apply_runtime_paths(portable_config: dict):
    global PORTABLE_CONFIG, DATA_DIR, JOBS_DIR, MODELS_DIR, LOGS_DIR
    global SETTINGS_FILE, VOICE_PRESETS_DIR, FFMPEG_PATH, COOKIES_FILE
    global TOOLS_DIR, DOWNLOADS_DIR, CACHE_DIR, FFMPEG_DIR, FFMPEG_BIN_DIR
    global FFMPEG_LOCAL_EXE, FFMPEG_LOCAL_PROBE
    global HUGGINGFACE_HOME_DIR, HUGGINGFACE_HUB_DIR, HUGGINGFACE_TRANSFORMERS_DIR
    global WHISPER_MODELS_DIR, TRANSLATION_MODELS_DIR, NLLB_MODEL_DIR
    global KOKORO_MODELS_DIR, F5_CACHE_DIR

    PORTABLE_CONFIG = dict(portable_config)
    DATA_DIR = _resolve_user_path(PORTABLE_CONFIG.get("data_dir"), DEFAULT_DATA_DIR)
    JOBS_DIR = DATA_DIR / "jobs"
    MODELS_DIR = DATA_DIR / "models"
    LOGS_DIR = DATA_DIR / "logs"
    TOOLS_DIR = DATA_DIR / "tools"
    DOWNLOADS_DIR = DATA_DIR / "downloads"
    CACHE_DIR = DATA_DIR / "cache"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    VOICE_PRESETS_DIR = MODELS_DIR / "voice_presets"
    FFMPEG_DIR = TOOLS_DIR / "ffmpeg"
    FFMPEG_BIN_DIR = FFMPEG_DIR / "bin"
    FFMPEG_LOCAL_EXE = FFMPEG_BIN_DIR / "ffmpeg.exe"
    FFMPEG_LOCAL_PROBE = FFMPEG_BIN_DIR / "ffprobe.exe"
    HUGGINGFACE_HOME_DIR = CACHE_DIR / "huggingface"
    HUGGINGFACE_HUB_DIR = HUGGINGFACE_HOME_DIR / "hub"
    HUGGINGFACE_TRANSFORMERS_DIR = HUGGINGFACE_HOME_DIR / "transformers"
    WHISPER_MODELS_DIR = MODELS_DIR / "whisper"
    TRANSLATION_MODELS_DIR = MODELS_DIR / "translation"
    NLLB_MODEL_DIR = TRANSLATION_MODELS_DIR / "nllb-200-distilled-1.3B"
    KOKORO_MODELS_DIR = MODELS_DIR / "kokoro"
    F5_CACHE_DIR = MODELS_DIR / "f5_tts" / "hf_cache"
    COOKIES_FILE = _resolve_cookies_file(PORTABLE_CONFIG, DATA_DIR)
    FFMPEG_PATH = _resolve_ffmpeg_path(PORTABLE_CONFIG, DATA_DIR)

    for runtime_dir in (
        DATA_DIR,
        JOBS_DIR,
        MODELS_DIR,
        LOGS_DIR,
        TOOLS_DIR,
        DOWNLOADS_DIR,
        CACHE_DIR,
        VOICE_PRESETS_DIR,
        FFMPEG_DIR,
        FFMPEG_BIN_DIR,
        HUGGINGFACE_HOME_DIR,
        HUGGINGFACE_HUB_DIR,
        HUGGINGFACE_TRANSFORMERS_DIR,
        WHISPER_MODELS_DIR,
        TRANSLATION_MODELS_DIR,
        NLLB_MODEL_DIR,
        KOKORO_MODELS_DIR,
        F5_CACHE_DIR,
    ):
        runtime_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(HUGGINGFACE_HOME_DIR)
    os.environ["HF_HUB_CACHE"] = str(HUGGINGFACE_HUB_DIR)
    os.environ["TRANSFORMERS_CACHE"] = str(HUGGINGFACE_TRANSFORMERS_DIR)
    os.environ["XDG_CACHE_HOME"] = str(CACHE_DIR)

    _prepend_to_path(FFMPEG_BIN_DIR)


def get_data_dir() -> Path:
    return DATA_DIR


def get_jobs_dir() -> Path:
    return JOBS_DIR


def get_models_dir() -> Path:
    return MODELS_DIR


def get_logs_dir() -> Path:
    return LOGS_DIR


def get_tools_dir() -> Path:
    return TOOLS_DIR


def get_downloads_dir() -> Path:
    return DOWNLOADS_DIR


def get_cache_dir() -> Path:
    return CACHE_DIR


def get_settings_file() -> Path:
    return SETTINGS_FILE


def get_ffmpeg_path() -> str:
    return FFMPEG_PATH


def get_ffmpeg_dir() -> Path:
    return FFMPEG_DIR


def get_ffmpeg_bin_dir() -> Path:
    return FFMPEG_BIN_DIR


def get_local_ffmpeg_exe() -> Path:
    return FFMPEG_LOCAL_EXE


def get_local_ffprobe_exe() -> Path:
    return FFMPEG_LOCAL_PROBE


def get_cookies_file() -> Path:
    return COOKIES_FILE


def delete_cookies_file() -> bool:
    if not COOKIES_FILE.exists():
        return False
    COOKIES_FILE.unlink()
    return True


def get_huggingface_cache_dir() -> Path:
    return HUGGINGFACE_HOME_DIR


def get_whisper_models_dir() -> Path:
    return WHISPER_MODELS_DIR


def get_translation_models_dir() -> Path:
    return TRANSLATION_MODELS_DIR


def get_nllb_model_dir() -> Path:
    return NLLB_MODEL_DIR


def get_kokoro_models_dir() -> Path:
    return KOKORO_MODELS_DIR


def get_f5_cache_dir() -> Path:
    return F5_CACHE_DIR


def get_voice_presets_dir() -> Path:
    return VOICE_PRESETS_DIR


def refresh_runtime_paths():
    _apply_runtime_paths(PORTABLE_CONFIG)


def get_portable_config_snapshot() -> dict[str, str]:
    return {
        "data_dir": str(DATA_DIR),
        "ffmpeg_path": str(PORTABLE_CONFIG.get("ffmpeg_path", "") or ""),
        "cookies_path": str(PORTABLE_CONFIG.get("cookies_path", "") or ""),
    }


def is_portable_setup_needed() -> bool:
    return not PORTABLE_CONFIG_FILE.exists()


def has_legacy_runtime_data(target_data_dir: str | Path | None = None) -> bool:
    target_root = _resolve_user_path(target_data_dir, DATA_DIR) if target_data_dir else DATA_DIR
    if target_root.resolve() == BASE_DIR.resolve():
        return False

    legacy_items = [
        BASE_DIR / "models",
        BASE_DIR / "jobs",
        BASE_DIR / "logs",
        BASE_DIR / "settings.json",
        BASE_DIR / "cookies.txt",
    ]
    for item in legacy_items:
        if not item.exists():
            continue
        try:
            if target_root.resolve() == item.resolve() or target_root.resolve() in item.resolve().parents:
                continue
        except Exception:
            pass
        return True
    return False


def migrate_legacy_runtime_data(target_data_dir: str | Path | None = None) -> list[str]:
    target_root = _resolve_user_path(target_data_dir, DATA_DIR) if target_data_dir else DATA_DIR
    target_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    mapping = [
        (BASE_DIR / "models", target_root / "models"),
        (BASE_DIR / "jobs", target_root / "jobs"),
        (BASE_DIR / "logs", target_root / "logs"),
        (BASE_DIR / "settings.json", target_root / "settings.json"),
        (BASE_DIR / "cookies.txt", target_root / "cookies.txt"),
    ]

    for source, target in mapping:
        if not source.exists():
            continue
        try:
            if source.resolve() == target.resolve():
                continue
        except Exception:
            pass

        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(source, target)
            else:
                continue
        copied.append(source.name)

    return copied


def save_portable_config(
    *,
    data_dir: str | Path,
    ffmpeg_path: str = "",
    cookies_path: str = "",
    apply_now: bool = True,
):
    config_data = {
        "data_dir": _serialize_user_path(data_dir, prefer_relative=True),
        "ffmpeg_path": _serialize_user_path(ffmpeg_path, prefer_relative=False) if str(ffmpeg_path).strip() else "",
        "cookies_path": _serialize_user_path(cookies_path, prefer_relative=True) if str(cookies_path).strip() else "",
    }
    with open(PORTABLE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
    if apply_now:
        _apply_runtime_paths(config_data)


PORTABLE_CONFIG = _load_portable_config()
_apply_runtime_paths(PORTABLE_CONFIG)


# ── FFmpeg ─────────────────────────────────────────────────────────────────
# Filled by _apply_runtime_paths()


# ── Model identifiers ─────────────────────────────────────────────────────
WHISPER_MODEL = "large-v3"
EDGE_TTS_MODEL = "Edge-TTS"
F5_TTS_MODEL = "F5-TTS"

# ── Voice presets ─────────────────────────────────────────────────────────
# Each preset: (display_name, description)
# Reference samples are stored in models/voice_presets/<id>.wav
# Filled by _apply_runtime_paths()



# ── Pipeline stages metadata ──────────────────────────────────────────────
STAGE_NAME_KEYS = (
    "stage.download",
    "stage.extract_audio",
    "stage.prepare_audio",
    "stage.stt",
    "stage.translate",
    "stage.tts",
    "stage.align",
    "stage.mix",
    "stage.mux",
)


def get_stage_names() -> list[str]:
    return [
        tr("stage.download", default="Download video"),
        tr("stage.extract_audio", default="Extract audio"),
        tr("stage.prepare_audio", default="Prepare audio"),
        tr("stage.stt", default="Speech recognition"),
        tr("stage.translate", default="Translate text"),
        tr("stage.tts", default="Generate speech (TTS)"),
        tr("stage.align", default="Time alignment"),
        tr("stage.mix", default="Audio mixing"),
        tr("stage.mux", default="Build final video"),
    ]

STAGE_ICONS = [
    "download", "audio", "audio", "speech",
    "translate", "tts", "align", "mix", "video",
]

NUM_STAGES = len(STAGE_ICONS)


# ── Internal pipeline defaults ────────────────────────────────────────────
DEFAULT_TTS_NFE_STEPS = 32
DEFAULT_TTS_SPEED = 1.0
DEFAULT_TTS_SEED = 1337
DEFAULT_KOKORO_SPEED = 1.0
DEFAULT_KOKORO_LANG = "en-us"
DEFAULT_TIME_STRETCH_LIMIT = 0.0
DEFAULT_SEGMENT_NORMALIZE_DB = -1.0
DEFAULT_SEGMENT_FADE_MS = 12
DEFAULT_BACKGROUND_VOLUME_DB = -3.0
DEFAULT_OUTPUT_AUDIO_BITRATE = "192k"
DEFAULT_CLEANUP_TEMP_FILES = True


# ── App settings (defaults) ───────────────────────────────────────────────
# Filled by _apply_runtime_paths()

@dataclass(frozen=True)
class JobSettings:
    """Immutable snapshot of settings for a single pipeline run.

    Created by ``AppSettings.snapshot()`` before the pipeline thread starts.
    Being frozen guarantees no accidental mutation from the GUI thread.
    """
    target_language: str = DEFAULT_TARGET_LANGUAGE
    interface_language: str = DEFAULT_INTERFACE_LANGUAGE
    voice_preset: str = "af_heart"
    tts_engine: str = "kokoro-tts"
    smart_hybrid_alignment: bool = True
    remove_tts_silence: bool = True
    keep_original_audio: bool = True
    original_audio_volume: int = 10
    jump_cut_video: bool = False
    f5_nfe_steps: int = 32
    kokoro_soft_trim: bool = True
    kokoro_speed: float = DEFAULT_KOKORO_SPEED
    kokoro_lang: str = DEFAULT_KOKORO_LANG


@dataclass
class AppSettings:
    """User-facing settings exposed in the simplified GUI."""
    target_language: str = DEFAULT_TARGET_LANGUAGE
    interface_language: str = DEFAULT_INTERFACE_LANGUAGE
    voice_preset: str = "af_heart"
    tts_engine: str = "kokoro-tts"
    smart_hybrid_alignment: bool = True
    remove_tts_silence: bool = True
    keep_original_audio: bool = True
    original_audio_volume: int = 10
    jump_cut_video: bool = False
    f5_nfe_steps: int = 32
    kokoro_soft_trim: bool = True
    kokoro_speed: float = DEFAULT_KOKORO_SPEED
    kokoro_lang: str = DEFAULT_KOKORO_LANG
    last_url: str = ""

    @staticmethod
    def _persist_fields() -> list[str]:
        """Return the list of field names to persist (auto-derived from dataclass)."""
        return [f.name for f in fields(AppSettings) if not f.name.startswith("_")]

    def save(self):
        """Save current settings to JSON file."""
        import json
        data = {k: getattr(self, k) for k in self._persist_fields()}
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load(self):
        """Load settings from JSON file, keeping defaults for missing keys."""
        import json
        if not SETTINGS_FILE.exists():
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            persist = set(self._persist_fields())
            for key, value in data.items():
                if key in persist and hasattr(self, key):
                    default_val = getattr(self, key)
                    if isinstance(value, type(default_val)):
                        setattr(self, key, value)
                    elif isinstance(default_val, float) and isinstance(value, int):
                        setattr(self, key, float(value))
        except Exception:
            pass

    def snapshot(self) -> JobSettings:
        """Return a frozen copy for use by the pipeline thread."""
        return JobSettings(
            **{f.name: getattr(self, f.name) for f in fields(JobSettings)}
        )


# Global settings instance
settings = AppSettings()
settings.load()


# ── App metadata ──────────────────────────────────────────────────────────
APP_NAME = "YouTube Dubbing Studio"
APP_VERSION = "1.0.0"
APP_AUTHOR = "YouTube Dubbing Studio"
