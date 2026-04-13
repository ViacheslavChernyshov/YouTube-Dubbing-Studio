"""
Startup/runtime asset planning and preparation for the portable app.
"""
from __future__ import annotations

import importlib.util
import logging
import platform
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests
from PySide6.QtCore import QObject, Signal

from app.config import (
    WHISPER_MODEL,
    get_f5_cache_dir,
    get_ffmpeg_bin_dir,
    get_ffmpeg_path,
    get_huggingface_cache_dir,
    get_kokoro_models_dir,
    get_local_ffmpeg_exe,
    get_local_ffprobe_exe,
    get_nllb_model_dir,
    get_portable_config_snapshot,
    get_voice_presets_dir,
    get_whisper_models_dir,
    refresh_runtime_paths,
)
from app.translator.local_translator import ensure_model_downloaded as ensure_nllb_model_downloaded
from app.tts_engines.f5_engine import F5TTSEngine
from app.tts_engines.kokoro_engine import KokoroEngine
from app.tts_engines.voice_presets import generate_presets_with_tts
from app.utils.hf_download import snapshot_download_with_progress


logger = logging.getLogger(__name__)

FFMPEG_RELEASE_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
REQUEST_HEADERS = {
    "User-Agent": "YouTube-Dubbing-Studio/1.0",
    "Accept": "application/vnd.github+json",
}


@dataclass
class RuntimeAssetPlanItem:
    key: str
    name: str
    description: str
    optional: bool = False
    missing: bool = False
    detail: str = ""


@dataclass
class AssetStepResult:
    name: str
    ok: bool
    message: str
    optional: bool = False


ProgressCallback = Callable[[int | None, int | None, str], None]


def _emit_progress(callback: ProgressCallback | None, current: int | None, total: int | None, message: str):
    if callback is not None:
        callback(current, total, message)


def _resolve_existing_executable(path_value: str) -> Path | None:
    value = str(path_value or "").strip()
    if not value:
        return None

    path = Path(value)
    if path.is_absolute():
        return path if path.exists() else None

    resolved = shutil.which(value)
    return Path(resolved) if resolved else None


def _ffmpeg_arch_suffix() -> str:
    machine = platform.machine().lower()
    if "arm" in machine:
        return "winarm64"
    return "win64"


def _ffmpeg_fallback_url() -> str:
    arch = _ffmpeg_arch_suffix()
    return (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        f"ffmpeg-master-latest-{arch}-gpl-shared.zip"
    )


def _pick_ffmpeg_asset_url() -> str:
    arch = _ffmpeg_arch_suffix()
    preferred_names = [
        f"ffmpeg-master-latest-{arch}-gpl-shared.zip",
        f"ffmpeg-master-latest-{arch}-lgpl-shared.zip",
        f"ffmpeg-n7.1-latest-{arch}-gpl-shared-7.1.zip",
        f"ffmpeg-n7.1-latest-{arch}-lgpl-shared-7.1.zip",
    ]

    try:
        response = requests.get(FFMPEG_RELEASE_API, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        release = response.json()
        assets = release.get("assets", [])
        asset_by_name = {asset.get("name"): asset.get("browser_download_url") for asset in assets}
        for asset_name in preferred_names:
            asset_url = asset_by_name.get(asset_name)
            if asset_url:
                return asset_url

        for asset in assets:
            asset_name = str(asset.get("name", ""))
            if arch in asset_name and asset_name.endswith(".zip") and "shared" in asset_name:
                asset_url = asset.get("browser_download_url")
                if asset_url:
                    return asset_url
    except Exception:
        pass

    return _ffmpeg_fallback_url()


def _download_to_file(url: str, target_path: Path, progress_callback: ProgressCallback | None = None):
    with requests.get(url, headers=REQUEST_HEADERS, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length") or 0)
        downloaded = 0
        with open(target_path, "wb") as file_obj:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                file_obj.write(chunk)
                downloaded += len(chunk)
                _emit_progress(
                    progress_callback,
                    downloaded,
                    total_size if total_size > 0 else None,
                    f"Скачивание: {target_path.name}",
                )


def _check_ffmpeg_state() -> tuple[bool, str]:
    config_snapshot = get_portable_config_snapshot()
    custom_ffmpeg_path = str(config_snapshot.get("ffmpeg_path", "") or "").strip()
    if custom_ffmpeg_path:
        resolved_custom = _resolve_existing_executable(custom_ffmpeg_path)
        if resolved_custom:
            return True, f"Используется пользовательский ffmpeg: {resolved_custom}"
        return False, "Пользовательский путь к ffmpeg недоступен, будет скачана portable-сборка"

    local_ffmpeg = get_local_ffmpeg_exe()
    local_ffprobe = get_local_ffprobe_exe()
    if local_ffmpeg.exists() and local_ffprobe.exists():
        return True, f"Локальная portable-сборка уже есть: {local_ffmpeg}"

    runtime_ffmpeg = _resolve_existing_executable(get_ffmpeg_path())
    if runtime_ffmpeg is not None:
        return True, f"Системный ffmpeg уже доступен: {runtime_ffmpeg}"

    return False, "Будет скачана локальная portable-сборка FFmpeg"


def _check_whisper_state() -> tuple[bool, str]:
    try:
        from faster_whisper import download_model

        model_path = download_model(
            WHISPER_MODEL,
            output_dir=str(get_whisper_models_dir()),
            cache_dir=str(get_huggingface_cache_dir()),
            local_files_only=True,
        )
        return True, f"Модель Whisper уже подготовлена: {model_path}"
    except Exception:
        return False, f"Будет скачана модель Whisper {WHISPER_MODEL}"


def _check_translation_state() -> tuple[bool, str]:
    model_dir = get_nllb_model_dir()
    tokenizer_candidates = (
        model_dir / "tokenizer.json",
        model_dir / "tokenizer_config.json",
        model_dir / "sentencepiece.bpe.model",
    )
    if (model_dir / "config.json").exists() and any(path.exists() for path in tokenizer_candidates):
        return True, f"Переводчик NLLB уже подготовлен: {model_dir}"
    return False, "Будет скачана локальная модель перевода NLLB-200"


def _check_kokoro_state() -> tuple[bool, str]:
    assets_dir = get_kokoro_models_dir()
    model_path = assets_dir / "kokoro-v1.0.onnx"
    voices_path = assets_dir / "voices-v1.0.bin"
    if model_path.exists() and voices_path.exists():
        return True, f"Ассеты Kokoro уже есть: {assets_dir}"
    return False, "Будут скачаны модель и голоса Kokoro"


def _check_f5_presets_state() -> tuple[bool, str]:
    preset_dir = get_voice_presets_dir()
    preset_names = ("male_deep", "male_medium", "female_warm", "female_clear")
    missing = [preset_id for preset_id in preset_names if not (preset_dir / f"{preset_id}.wav").exists()]
    if not missing:
        return True, f"Референсные пресеты F5 уже готовы: {preset_dir}"
    return False, "Будут подготовлены референсные пресеты F5"


def _check_f5_model_state() -> tuple[bool, str]:
    if importlib.util.find_spec("f5_tts") is None:
        return False, "Пакет f5_tts не установлен, автоматическая докачка модели недоступна"

    cache_dir = get_f5_cache_dir()
    has_model_files = any(cache_dir.rglob("model_*.safetensors")) or any(cache_dir.rglob("model_*.pt"))
    if has_model_files:
        return True, f"Кэш F5 уже подготовлен: {cache_dir}"
    return False, "Будет скачана базовая модель F5"


def build_runtime_asset_plan(device: str) -> list[RuntimeAssetPlanItem]:
    del device  # reserved for future device-specific checks

    definitions = [
        ("ffmpeg", "FFmpeg", "Нужен для извлечения аудио, финальной сборки и части TTS-пайплайна.", False, _check_ffmpeg_state),
        ("whisper", "Whisper", "Локальная модель распознавания речи для транскрибации.", False, _check_whisper_state),
        ("nllb", "NLLB", "Локальная модель перевода для офлайн-работы.", False, _check_translation_state),
        ("kokoro", "Kokoro", "Ассеты быстрой локальной озвучки Kokoro-TTS.", False, _check_kokoro_state),
        ("f5_presets", "F5 Presets", "Референсные WAV-пресеты для клонируемой озвучки F5.", True, _check_f5_presets_state),
        ("f5_model", "F5 Model", "Базовая модель F5-TTS для тяжёлой нейросетевой озвучки.", True, _check_f5_model_state),
    ]

    plan: list[RuntimeAssetPlanItem] = []
    for key, name, description, optional, checker in definitions:
        ready, detail = checker()
        plan.append(
            RuntimeAssetPlanItem(
                key=key,
                name=name,
                description=description,
                optional=optional,
                missing=not ready,
                detail=detail,
            )
        )
    return plan


def get_missing_runtime_assets(device: str) -> list[RuntimeAssetPlanItem]:
    return [item for item in build_runtime_asset_plan(device) if item.missing]


def ensure_ffmpeg_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """
    Ensure a local portable FFmpeg build exists unless the user explicitly selected
    a working custom ffmpeg path in portable_config.json or system ffmpeg is available.
    """
    active_logger = logger_instance or logger
    config_snapshot = get_portable_config_snapshot()
    custom_ffmpeg_path = str(config_snapshot.get("ffmpeg_path", "") or "").strip()
    if custom_ffmpeg_path:
        resolved_custom = _resolve_existing_executable(custom_ffmpeg_path)
        if resolved_custom:
            active_logger.info(f"FFmpeg: используется пользовательский путь ({resolved_custom})")
            return resolved_custom
        active_logger.warning("FFmpeg: пользовательский путь недоступен, скачиваю portable-сборку")

    local_ffmpeg = get_local_ffmpeg_exe()
    local_ffprobe = get_local_ffprobe_exe()
    if local_ffmpeg.exists() and local_ffprobe.exists():
        refresh_runtime_paths()
        active_logger.info(f"FFmpeg: локальная portable-сборка уже готова ({local_ffmpeg})")
        return local_ffmpeg

    runtime_ffmpeg = _resolve_existing_executable(get_ffmpeg_path())
    if runtime_ffmpeg is not None and runtime_ffmpeg.resolve() != local_ffmpeg.resolve():
        active_logger.info(f"FFmpeg: системный ffmpeg уже доступен ({runtime_ffmpeg})")
        return runtime_ffmpeg

    ffmpeg_bin_dir = get_ffmpeg_bin_dir()
    ffmpeg_root_dir = ffmpeg_bin_dir.parent
    download_url = _pick_ffmpeg_asset_url()
    active_logger.info("FFmpeg: скачивание portable-сборки для Windows...")

    with tempfile.TemporaryDirectory(dir=str(ffmpeg_root_dir.parent)) as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        archive_path = temp_dir / "ffmpeg.zip"
        extract_dir = temp_dir / "extract"
        _download_to_file(download_url, archive_path, progress_callback=progress_callback)
        _emit_progress(progress_callback, None, None, "Распаковка FFmpeg...")

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_dir)

        extracted_root = None
        for candidate in extract_dir.rglob("ffmpeg.exe"):
            bin_dir = candidate.parent
            if (bin_dir / "ffprobe.exe").exists():
                extracted_root = bin_dir.parent
                break

        if extracted_root is None:
            raise RuntimeError("Не удалось найти ffmpeg.exe внутри скачанного архива")

        if ffmpeg_root_dir.exists():
            shutil.rmtree(ffmpeg_root_dir)
        shutil.copytree(extracted_root, ffmpeg_root_dir)

    refresh_runtime_paths()
    active_logger.info(f"FFmpeg: portable-сборка готова ({local_ffmpeg})")
    return local_ffmpeg


def ensure_whisper_model_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    active_logger = logger_instance or logger
    whisper_dir = get_whisper_models_dir()
    active_logger.info(f"Whisper: проверка модели {WHISPER_MODEL}...")
    from faster_whisper.utils import _MODELS

    repo_id = WHISPER_MODEL if "/" in WHISPER_MODEL else _MODELS.get(WHISPER_MODEL)
    if repo_id is None:
        raise ValueError(f"Неизвестная модель Whisper: {WHISPER_MODEL}")

    model_path = snapshot_download_with_progress(
        repo_id=repo_id,
        local_dir=str(whisper_dir),
        cache_dir=str(get_huggingface_cache_dir()),
        local_files_only=False,
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ],
        progress_callback=progress_callback,
        progress_message=f"Скачивание Whisper {WHISPER_MODEL}",
    )
    return Path(model_path)


def ensure_translation_model_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    active_logger = logger_instance or logger
    model_dir = ensure_nllb_model_downloaded(active_logger, progress_callback=progress_callback)
    active_logger.info(f"Переводчик NLLB: модель готова ({model_dir})")
    return model_dir


def ensure_kokoro_assets_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    active_logger = logger_instance or logger
    engine = KokoroEngine()
    engine.ensure_assets(progress_callback=progress_callback)
    active_logger.info("Kokoro: модель и голосовые ассеты готовы")
    return get_kokoro_models_dir()


def ensure_f5_presets_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, bool]:
    del progress_callback
    active_logger = logger_instance or logger
    active_logger.info("F5: подготовка референсных пресетов голоса...")
    results = generate_presets_with_tts(logger=active_logger)
    failures = [preset_id for preset_id, ok in results.items() if not ok]
    if failures:
        raise RuntimeError("Не удалось подготовить пресеты: " + ", ".join(failures))
    active_logger.info("F5: референсные пресеты готовы")
    return results


def ensure_f5_model_downloaded(
    device: str,
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    active_logger = logger_instance or logger
    active_logger.info("F5: проверка и докачка базовой модели...")
    
    try:
        snapshot_download_with_progress(
            repo_id="SWivid/F5-TTS",
            cache_dir=str(get_f5_cache_dir()),
            local_dir=None,
            local_files_only=False,
            allow_patterns=["F5TTS_Base/model_1200000.safetensors"],
            progress_callback=progress_callback,
            progress_message="Скачивание базовой модели",
        )
    except Exception as exc:
        active_logger.warning(f"Ошибка при предварительном скачивании F5-TTS: {exc}")
    engine = F5TTSEngine()
    try:
        engine.load_model(device=device)
    finally:
        engine.unload_model()
    active_logger.info(f"F5: модель готова ({get_f5_cache_dir()})")
    return get_f5_cache_dir()


def prepare_runtime_assets(
    *,
    device: str,
    plan: list[RuntimeAssetPlanItem],
    logger_instance: logging.Logger | None = None,
    step_started_callback: Callable[[int, int, RuntimeAssetPlanItem], None] | None = None,
    step_progress_callback: Callable[[RuntimeAssetPlanItem, int | None, int | None, str], None] | None = None,
    overall_progress_callback: Callable[[int, int, RuntimeAssetPlanItem], None] | None = None,
) -> list[AssetStepResult]:
    active_logger = logger_instance or logger
    handlers = {
        "ffmpeg": lambda callback: ensure_ffmpeg_downloaded(active_logger, callback),
        "whisper": lambda callback: ensure_whisper_model_downloaded(active_logger, callback),
        "nllb": lambda callback: ensure_translation_model_downloaded(active_logger, callback),
        "kokoro": lambda callback: ensure_kokoro_assets_downloaded(active_logger, callback),
        "f5_presets": lambda callback: ensure_f5_presets_downloaded(active_logger, callback),
        "f5_model": lambda callback: ensure_f5_model_downloaded(device, active_logger, callback),
    }

    results: list[AssetStepResult] = []
    total = len(plan)
    if total == 0:
        return results

    completed = 0
    for index, item in enumerate(plan, start=1):
        if step_started_callback is not None:
            step_started_callback(index, total, item)

        handler = handlers[item.key]

        def _item_progress(current: int | None, total_bytes: int | None, message: str, asset=item):
            if step_progress_callback is not None:
                step_progress_callback(asset, current, total_bytes, message)

        try:
            handler(_item_progress)
            results.append(AssetStepResult(name=item.name, ok=True, message="Готово", optional=item.optional))
        except Exception as exc:
            message = str(exc)
            if item.optional:
                active_logger.warning(f"{item.name}: пропущено ({message})")
            else:
                active_logger.warning(f"{item.name}: не удалось подготовить автоматически ({message})")
            results.append(AssetStepResult(name=item.name, ok=False, message=message, optional=item.optional))

        completed += 1
        if overall_progress_callback is not None:
            overall_progress_callback(completed, total, item)

    return results


class StartupBootstrapWorker(QObject):
    """Background startup preparation of missing models/tools."""

    status_changed = Signal(str)
    step_started = Signal(object)
    step_progress = Signal(object)
    overall_progress = Signal(object)
    bootstrap_finished = Signal(object)

    def __init__(
        self,
        *,
        device: str,
        plan: list[RuntimeAssetPlanItem],
        logger_instance: logging.Logger | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._device = device
        self._plan = list(plan)
        self._logger = logger_instance or logger
        self._thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running():
            return
        self._thread = threading.Thread(target=self._run, name="startup-bootstrap", daemon=True)
        self._thread.start()

    def _on_step_started(self, index: int, total: int, item: RuntimeAssetPlanItem):
        self.status_changed.emit(f"Подготовка: {item.name}...")
        self.step_started.emit(
            {
                "index": index,
                "total": total,
                "item": item,
            }
        )

    def _on_step_progress(
        self,
        item: RuntimeAssetPlanItem,
        current: int | None,
        total_bytes: int | None,
        message: str,
    ):
        percent = None
        if current is not None and total_bytes and total_bytes > 0:
            percent = max(0, min(100, int(current * 100 / total_bytes)))
        self.step_progress.emit(
            {
                "item": item,
                "current": current,
                "total": total_bytes,
                "percent": percent,
                "message": message,
            }
        )

    def _on_overall_progress(self, completed: int, total: int, item: RuntimeAssetPlanItem):
        percent = int(completed * 100 / total) if total > 0 else 100
        self.overall_progress.emit(
            {
                "completed": completed,
                "total": total,
                "percent": percent,
                "item": item,
            }
        )

    def _run(self):
        if not self._plan:
            self.status_changed.emit("Все компоненты уже готовы")
            self.bootstrap_finished.emit([])
            return

        self.status_changed.emit("Подготовка недостающих компонентов...")
        results = prepare_runtime_assets(
            device=self._device,
            plan=self._plan,
            logger_instance=self._logger,
            step_started_callback=self._on_step_started,
            step_progress_callback=self._on_step_progress,
            overall_progress_callback=self._on_overall_progress,
        )
        self.bootstrap_finished.emit(results)
