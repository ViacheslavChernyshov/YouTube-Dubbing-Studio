"""
Stage 8: Mix translated voice with the instrumental/background track.
"""
import numpy as np
from pathlib import Path

from app.config import DEFAULT_BACKGROUND_VOLUME_DB
from app.utils.audio import load_wav, save_wav, mix_audio_tracks, normalize_audio
from app.pipeline.base_stage import BaseStage
from app.pipeline.context import PipelineContext
from app.i18n import tr


class MixStage(BaseStage):
    def __init__(self):
        super().__init__(8, tr("s08.name", default="Audio Mixing"), tr("s08.desc", default="Mixing voice with background track"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        aligned_voice_path = context.aligned_voice_path
        original_audio_path = context.cut_bg_audio_path or context.audio_path
        job_settings = context.settings

        sr = 44100

        self.log(tr("s08.loading", default="Loading audio tracks..."))
        self.report_progress(10, tr("s08.loading_voice", default="Loading voice track..."))

        voice, _ = load_wav(aligned_voice_path, sr=sr)
        if voice.ndim > 1:
            voice = np.mean(voice, axis=1)

        if not job_settings.keep_original_audio or job_settings.original_audio_volume == 0:
            self.report_progress(50, tr("s08.removing_bg", default="Removing original audio..."))
            self.check_cancelled()
            mixed = normalize_audio(voice, target_db=-1.0)
            self.log(tr("s08.bg_removed", default="Original audio muted, saving only generated voice"))
        else:
            self.report_progress(30, tr("s08.loading_original", default="Loading original video audio..."))
            original_audio, _ = load_wav(original_audio_path, sr=sr)
            if original_audio.ndim > 1:
                original_audio = np.mean(original_audio, axis=1)

            self.report_progress(50, tr("s08.mixing", default="Mixing..."))
            self.check_cancelled()
            
            vol_percent = job_settings.original_audio_volume
            bg_volume_db = 20.0 * np.log10(vol_percent / 100.0) if vol_percent > 0 else -100.0
            
            self.log(tr("s08.mixing_stats", default="Mixing: original {percent}% ({db:.1f} dB)", percent=vol_percent, db=bg_volume_db))
            mixed = mix_audio_tracks(
                voice=voice,
                background=original_audio,
                bg_volume_db=bg_volume_db,
                sr=sr,
            )
            self.log(tr("s08.mixed", default="Mixed: {dur:.1f}s, original audio: {db:.1f} dB", dur=len(mixed) / sr, db=bg_volume_db))

        self.report_progress(80, tr("s08.saving", default="Saving..."))

        output_path = job_dir / "final_audio.wav"
        save_wav(output_path, mixed, sr=sr)

        context.final_audio_path = str(output_path)
        return context
