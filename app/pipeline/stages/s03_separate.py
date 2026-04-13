"""
Stage 3: Prepare audio references for downstream stages.
"""
from pathlib import Path

from app.pipeline.base_stage import BaseStage
from app.pipeline.context import PipelineContext
from app.i18n import tr


class PrepareAudioStage(BaseStage):
    def __init__(self):
        super().__init__(3, tr("s03.name", default="Prepare audio"), tr("s03.desc", default="Prepare source audio track for recognition and mixing"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        audio_path = context.audio_path
        if not audio_path or not Path(audio_path).is_file():
            raise FileNotFoundError(tr("s03.not_found", default="Audio track not found: {path}", path=audio_path))

        self.log(tr("s03.using_source", default="Using source audio track without separation"))
        self.report_progress(30, tr("s03.preparing", default="Preparing source track..."))
        self.check_cancelled()
        self.report_progress(100, tr("s03.ready", default="Source track is ready"))
        return context
