"""
Stage 9: Video mux — replace audio in original video with dubbed audio.
"""
import subprocess
from pathlib import Path

from app.config import DEFAULT_OUTPUT_AUDIO_BITRATE, get_ffmpeg_path
from app.pipeline.base_stage import BaseStage, PipelineCancelled
from app.utils.process import CancelledProcessError, run_command
from app.pipeline.context import PipelineContext
from app.i18n import tr


class MuxStage(BaseStage):
    def __init__(self):
        super().__init__(9, tr("s09.name", default="Final Video Assembly"), tr("s09.desc", default="Replacing audio in video via ffmpeg"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        input_video = context.input_video
        final_audio = context.final_audio_path
        output_video = job_dir / "output.mp4"

        self.log(tr("s09.assembling", default="Assembling final video..."))
        self.report_progress(10, tr("s09.start_ffmpeg", default="Starting ffmpeg..."))

        edits = context.video_edits
        if edits:
            self.log(tr("s09.jump_cut_encode", default="Transcoding video for dynamic jump-cut. This will take some time..."))
            self.report_progress(15, tr("s09.jump_cut_filter", default="Preparing video cut filters..."))
            
            filter_path = job_dir / "filter_graph.txt"
            filter_lines = []
            for i, (start, end) in enumerate(edits):
                filter_lines.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}];")
            
            concat_str = "".join(f"[v{i}]" for i in range(len(edits)))
            filter_lines.append(f"{concat_str}concat=n={len(edits)}:v=1:a=0[outv]")
            
            filter_path.write_text("\n".join(filter_lines), encoding="utf-8")
            
            cmd = [
                get_ffmpeg_path(),
                "-i", str(input_video),
                "-i", str(final_audio),
                "-filter_complex_script", str(filter_path),
                "-map", "[outv]",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", DEFAULT_OUTPUT_AUDIO_BITRATE,
                "-shortest",
                "-y",
                str(output_video),
            ]
        else:
            cmd = [
                get_ffmpeg_path(),
                "-i", str(input_video),
                "-i", str(final_audio),
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", DEFAULT_OUTPUT_AUDIO_BITRATE,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y",
                str(output_video),
            ]

        self.report_progress(30, tr("s09.muxing", default="Merging video and audio..."))

        try:
            run_command(cmd, cancel_event=self._cancel_event)
        except CancelledProcessError as exc:
            raise PipelineCancelled(tr("s09.cancelled", default="Video assembly stopped by user")) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(tr("s09.error", default="ffmpeg mux error: {err}", err=exc.output or ''))

        if not output_video.exists():
            raise FileNotFoundError(tr("s09.not_found", default="Final video not created"))

        file_size_mb = output_video.stat().st_size / (1024 * 1024)
        self.log(tr("s09.done", default="Done: {name} ({size:.1f} MB)", name=output_video.name, size=file_size_mb))

        context.output_video = str(output_video)
        return context
