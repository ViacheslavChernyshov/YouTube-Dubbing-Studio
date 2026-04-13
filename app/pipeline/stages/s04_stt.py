"""
Stage 4: Speech-to-text using faster-whisper with word-level timestamps.
"""
import json
from pathlib import Path

from app.config import WHISPER_MODEL, get_whisper_models_dir
from app.hardware import get_whisper_compute_type
from app.pipeline.base_stage import BaseStage
from app.pipeline.context import PipelineContext
from app.runtime_assets import ensure_whisper_model_downloaded
from app.i18n import tr


class STTStage(BaseStage):
    def __init__(self):
        super().__init__(4, tr("s04.name", default="Speech Recognition"), tr("s04.desc", default="Transcription via faster-whisper"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        audio_path = context.audio_path
        device = context.device
        compute_type = get_whisper_compute_type(device)

        self.log(tr("s04.loading_whisper", default="Loading Whisper {model} ({dev}, {ctype})", model=WHISPER_MODEL, dev=device, ctype=compute_type))
        self.report_progress(5, tr("s04.loading_model", default="Loading Whisper model..."))

        def report_model_download(current: int | None, total: int | None, message: str):
            if total and total > 0 and current is not None:
                pct = 5 + (current / total) * 15
                self.report_progress(min(20, pct), message)
            else:
                self.report_progress(5, message)

        ensure_whisper_model_downloaded(
            logger_instance=self._logger,
            progress_callback=report_model_download,
        )

        from faster_whisper import WhisperModel

        model = WhisperModel(
            WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
            download_root=str(get_whisper_models_dir()),
            # local_files_only removed - allow download if needed
        )

        try:
            self.report_progress(20, tr("s04.transcribing", default="Transcribing audio..."))
            self.check_cancelled()

            # Determine language
            segments_iter, info = model.transcribe(
                audio_path,
                word_timestamps=True,
                language=None,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                ),
            )

            detected_language = info.language
            self.log(tr("s04.detected_language", default="Detected language: {lang} (probability: {prob:.2f})", lang=detected_language, prob=info.language_probability))

            # Collect segments
            segments = []
            total_duration = context.audio_duration or 0.0
            
            for seg in segments_iter:
                self.check_cancelled()

                words = []
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word": w.word,
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                        })

                segment_data = {
                    "id": seg.id,
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                    "words": words,
                }
                segments.append(segment_data)

                # Progress based on timestamp
                if total_duration > 0:
                    pct = min(95, 20 + (seg.end / total_duration) * 75)
                    self.report_progress(pct, tr("s04.segment", default="Segment {id}: {text}", id=seg.id, text=seg.text))

            # Save segments to JSON
            segments_file = job_dir / "segments.json"
            with open(segments_file, "w", encoding="utf-8") as f:
                json.dump({
                    "language": detected_language,
                    "language_probability": info.language_probability,
                    "segments": segments,
                }, f, ensure_ascii=False, indent=2)

            self.log(tr("s04.recognized", default="Recognized {count} segments, language: {lang}", count=len(segments), lang=detected_language))

            context.segments_file = str(segments_file)
            context.segments = segments
            context.source_language = detected_language
            return context

        finally:
            # Free model memory
            del model
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
