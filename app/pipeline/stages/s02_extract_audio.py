"""
Stage 2: Extract audio from video using ffmpeg.
"""
import subprocess
from pathlib import Path

from app.config import get_ffmpeg_path
from app.pipeline.context import PipelineContext
from app.pipeline.base_stage import BaseStage, PipelineCancelled
from app.utils.process import CancelledProcessError, run_command
from app.i18n import tr


class ExtractAudioStage(BaseStage):
    def __init__(self):
        super().__init__(2, tr("s02.name", default="Extract audio"), tr("s02.desc", default="Extract audio track from video"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        input_video = context.input_video
        output_audio = job_dir / "audio.wav"

        self.report_progress(10, tr("s02.start", default="Starting ffmpeg..."))

        cmd = [
            get_ffmpeg_path(),
            "-i", str(input_video),
            "-vn",                    # no video
            "-acodec", "pcm_s16le",   # 16-bit PCM
            "-ar", "44100",           # 44.1kHz
            "-ac", "2",               # stereo
            "-y",                     # overwrite
            str(output_audio),
        ]

        self.log(tr("s02.extracting", default="Extracting audio from {name}", name=Path(input_video).name))
        self.report_progress(30, tr("s02.processing", default="Processing audio..."))

        try:
            run_command(cmd, cancel_event=self._cancel_event)
        except CancelledProcessError as exc:
            raise PipelineCancelled(tr("s02.cancelled", default="Audio extraction stopped by user")) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(tr("s02.error", default="ffmpeg error: {err}", err=exc.output or ''))

        if not output_audio.exists():
            raise FileNotFoundError(tr("s02.not_found", default="Audio file not created"))

        self.report_progress(90, tr("s02.done", default="Audio extracted"))

        # Get duration
        from app.utils.audio import get_duration
        duration = get_duration(output_audio)
        self.log(tr("s02.result", default="Audio: {duration:.1f}s, {size:.1f} MB", duration=duration, size=output_audio.stat().st_size / (1024*1024)))

        context.audio_path = str(output_audio)
        context.audio_duration = duration
        return context
