"""
Stage 6: TTS — Generate speech from translated text.
Uses the selected preset voice from settings via TTSEngineRegistry.
"""
from pathlib import Path

from app.config import (
    DEFAULT_KOKORO_LANG,
    DEFAULT_KOKORO_SPEED,
    DEFAULT_TTS_NFE_STEPS,
    DEFAULT_TTS_SEED,
    DEFAULT_TTS_SPEED,
)
from app.language_catalog import (
    DEFAULT_TARGET_LANGUAGE,
    get_target_language_display_name,
)
from app.tts_engines.base_engine import TTSEngineRegistry
from app.utils.audio import get_duration
from app.pipeline.context import PipelineContext
from app.pipeline.base_stage import BaseStage
from app.i18n import tr


class TTSStage(BaseStage):
    def __init__(self):
        super().__init__(6, tr("s06.name", default="Speech Generation (TTS)"), tr("s06.desc", default="Speech synthesis using selected voice preset"))

    @staticmethod
    def _get_engine(engine_id: str):
        engine_cls = TTSEngineRegistry.get_engine_class(engine_id)
        return engine_cls()

    @staticmethod
    def _get_base_speed(job_settings, tts_engine: str | None = None) -> float:
        """Return the user-configured base TTS speed for the active engine."""
        engine_id = tts_engine or job_settings.tts_engine
        if engine_id == "kokoro-tts":
            speed = float(getattr(job_settings, "kokoro_speed", DEFAULT_KOKORO_SPEED))
            return max(0.5, min(2.0, speed))
        return DEFAULT_TTS_SPEED

    @staticmethod
    def _get_segment_speed(job_settings, speed: float, tts_engine: str | None = None) -> float:
        """Clamp engine-specific speed ranges before synthesis."""
        engine_id = tts_engine or job_settings.tts_engine
        if engine_id == "kokoro-tts":
            return max(0.5, min(2.0, speed))
        return speed

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        segments = context.segments
        device = context.device
        job_settings = context.settings

        target_language = getattr(job_settings, "target_language", DEFAULT_TARGET_LANGUAGE)
        tts_engine_id = getattr(job_settings, "tts_engine", "edge-tts")

        if not TTSEngineRegistry.is_language_supported(tts_engine_id, target_language):
            language_name = get_target_language_display_name(target_language)
            raise RuntimeError(
                tr(
                    "s06.not_supported",
                    default=(
                        "TTS '{engine}' does not support language {lang}. "
                        "Select a compatible model in Settings and try again."
                    ),
                    engine=tts_engine_id,
                    lang=language_name,
                )
            )

        engine_cls = TTSEngineRegistry.get_engine_class(tts_engine_id)
        engine = self._get_engine(tts_engine_id)

        voice_preset = job_settings.voice_preset
        available_voices = engine_cls.get_voice_catalog(target_language)
        if not voice_preset:
            raise RuntimeError(
                tr(
                    "s06.voice_missing",
                    default=(
                        "No voice preset is selected for TTS '{engine}'. "
                        "Choose a voice in Settings and try again."
                    ),
                    engine=tts_engine_id,
                )
            )
        if voice_preset not in available_voices:
            raise RuntimeError(
                tr(
                    "s06.voice_invalid",
                    default=(
                        "Voice preset '{preset}' is not available for TTS '{engine}' and language {lang}. "
                        "Choose another voice in Settings and try again."
                    ),
                    preset=voice_preset,
                    engine=tts_engine_id,
                    lang=get_target_language_display_name(target_language),
                )
            )

        base_speed = self._get_base_speed(job_settings, tts_engine_id)

        self.log(tr("s06.tts_info", default="TTS: {engine} | Language: {lang} | Voice: {voice} | Device: {dev}", engine=tts_engine_id, lang=get_target_language_display_name(target_language), voice=voice_preset, dev=device))
        self.log(tr("s06.seed", default="Fixed TTS seed: {seed}", seed=DEFAULT_TTS_SEED))
        if tts_engine_id == "kokoro-tts":
            kokoro_lang = getattr(job_settings, "kokoro_lang", DEFAULT_KOKORO_LANG)
            self.log(tr("s06.kokoro_info", default="Kokoro: accent {accent} | Speed {speed:.2f}x", accent=kokoro_lang, speed=base_speed))
            
        self.report_progress(5, tr("s06.loading_model", default="Loading speech model: {engine}...", engine=tts_engine_id))

        engine.load_model(device=device)

        try:
            self.report_progress(10, tr("s06.preparing_voice", default="Preparing voice..."))
            self.log(tr("s06.voice", default="Voice: preset '{preset}'", preset=voice_preset))
            try:
                voice_ref = engine.use_preset_voice(voice_preset)
                if tts_engine_id == "kokoro-tts":
                    # Inject accent parameter for Kokoro wrapper if needed
                    if not isinstance(voice_ref, dict):
                        voice_ref = {
                            "voice": voice_ref,
                            "lang": getattr(job_settings, "kokoro_lang", DEFAULT_KOKORO_LANG),
                            "remove_tts_silence": getattr(job_settings, "remove_tts_silence", True),
                            "kokoro_soft_trim": getattr(job_settings, "kokoro_soft_trim", True),
                        }
                    self.log(tr("s06.preset_loaded", default="Preset voice loaded"))
            except FileNotFoundError as e:
                raise RuntimeError(tr("s06.preset_error", default="Failed to load voice preset '{preset}': {err}", preset=voice_preset, err=e)) from e

            # Generate TTS for each segment
            tts_dir = job_dir / "tts_segments"
            tts_dir.mkdir(exist_ok=True)

            total = len(segments)
            tts_files = []

            for i, seg in enumerate(segments):
                self.check_cancelled()

                text = seg.get("translated_text", seg["text"])
                if not text.strip():
                    tts_files.append(None)
                    continue

                output_file = tts_dir / f"seg_{i:04d}.wav"
                pct = 10 + (i / total) * 85
                self.report_progress(pct, tr("s06.progress", default="[{current}/{total}] {text}", current=i+1, total=total, text=text))

                try:
                    engine.synthesize(
                        text=text,
                        voice_ref=voice_ref,
                        output_path=str(output_file),
                        nfe_step=getattr(job_settings, "f5_nfe_steps", DEFAULT_TTS_NFE_STEPS),
                        speed=base_speed,
                        seed=DEFAULT_TTS_SEED,
                    )
                    
                    # Adaptive speed
                    target_duration = seg["end"] - seg["start"]
                    actual_duration = get_duration(output_file)
                    overlap_margin = 0.2
                    
                    if tts_engine_id in ("f5-tts", "kokoro-tts") and actual_duration > target_duration + overlap_margin and target_duration > 0.5:
                        speed_factor = actual_duration / target_duration
                        
                        if getattr(job_settings, "smart_hybrid_alignment", True):
                            speed_factor = max(0.85, min(1.35, speed_factor))
                        
                        adjusted_speed = self._get_segment_speed(job_settings, base_speed * speed_factor, tts_engine_id)
                        self.log(
                            tr("s06.adapt_speed", default="  Adapting speed {speed:.2f}x ({actual:.1f}s -> ~{target:.1f}s)", speed=adjusted_speed, actual=actual_duration, target=actual_duration/speed_factor)
                        )
                        engine.synthesize(
                            text=text,
                            voice_ref=voice_ref,
                            output_path=str(output_file),
                            nfe_step=getattr(job_settings, "f5_nfe_steps", DEFAULT_TTS_NFE_STEPS),
                            speed=adjusted_speed,
                            seed=DEFAULT_TTS_SEED,
                        )

                    tts_files.append(str(output_file))
                    self.log(tr("s06.tts_done", default="  TTS [{current}/{total}]: {text}", current=i+1, total=total, text=text))
                except Exception as e:
                    self.log(tr("s06.tts_error", default="  TTS error segment {idx}: {err}", idx=i+1, err=e), level=30)
                    tts_files.append(None)

        finally:
            # Unload model to free memory
            engine.unload_model()

        generated = sum(1 for f in tts_files if f)
        self.log(tr("s06.generated", default="Generated {count} of {total} segments", count=generated, total=total))

        context.tts_files = tts_files
        return context
