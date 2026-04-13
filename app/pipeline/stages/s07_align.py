"""
Stage 7: Align TTS segments to the original segment timestamps.
"""
import numpy as np
from pathlib import Path

from app.config import DEFAULT_SEGMENT_FADE_MS, DEFAULT_TIME_STRETCH_LIMIT, DEFAULT_SEGMENT_NORMALIZE_DB
from app.utils.audio import (
    load_wav, save_wav, time_stretch_segment,
    trim_trailing_silence, trim_leading_silence,
    apply_fade_edges, normalize_audio,
)
from app.pipeline.base_stage import BaseStage
from app.pipeline.context import PipelineContext
from app.i18n import tr


class AlignStage(BaseStage):
    def __init__(self):
        super().__init__(7, tr("s07.name", default="Time Alignment"), tr("s07.desc", default="Adapting TTS to original timecodes"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        segments = context.segments
        tts_files = context.tts_files
        audio_duration = context.audio_duration or 0.0

        self.log(tr("s07.aligning", default="Aligning {count} segments", count=len(tts_files)))
        self.report_progress(5, tr("s07.preparing", default="Preparing timeline..."))

        sr = 44100
        tts_data = []
        for i, _seg in enumerate(segments):
            if i >= len(tts_files) or tts_files[i] is None:
                tts_data.append(None)
                continue

            try:
                audio, _ = load_wav(tts_files[i], sr=sr)
                if audio.ndim > 1:
                    audio = np.mean(audio, axis=1)

                audio, _lead_trimmed = trim_leading_silence(audio, sr=sr)
                audio = trim_trailing_silence(audio, sr=sr, min_silence_ms=30)
                # Отключаем пофразовую нормализацию пиков, так как она вызывает скачки общей громкости:
                # Нормализация финальной склейки целиком делается в s08_mix.py
                # audio = normalize_audio(audio, target_db=DEFAULT_SEGMENT_NORMALIZE_DB)
                tts_data.append(audio)
            except Exception as e:
                self.log(tr("s07.load_error", default="  Error loading TTS segment {idx}: {err}", idx=i + 1, err=e), level=30)
                tts_data.append(None)

        smart_hybrid = getattr(context.settings, "smart_hybrid_alignment", True)
        jump_cut_video = getattr(context.settings, "jump_cut_video", False)

        if jump_cut_video:
            original_audio_path = context.audio_path
            original_audio = None
            if original_audio_path:
                original_audio, _ = load_wav(original_audio_path, sr=sr)
                if original_audio.ndim > 1:
                    original_audio = np.mean(original_audio, axis=1)
                    
            timeline, bg_timeline, edits = self._align_jump_cut(
                segments, tts_data, original_audio, audio_duration, sr
            )
            
            if bg_timeline is not None:
                cut_bg_path = job_dir / "jump_cut_bg.wav"
                save_wav(cut_bg_path, bg_timeline, sr=sr)
                context.cut_bg_audio_path = str(cut_bg_path)
                
            context.video_edits = edits
            self.log(tr("s07.jump_cut", default="Jump-Cut: created {count} video edits", count=len(edits)))
        else:
            timeline = self._align_sync(segments, tts_data, audio_duration, sr, smart_hybrid)

        aligned_path = job_dir / "aligned_voice.wav"
        save_wav(aligned_path, timeline, sr=sr)

        context.aligned_voice_path = str(aligned_path)
        return context

    def _align_jump_cut(
        self, segments: list, tts_data: list, original_audio: np.ndarray, audio_duration: float, sr: int
    ) -> tuple[np.ndarray, np.ndarray, list]:
        timeline = []
        bg_timeline = []
        edits = []
        
        def add_chunk(start, end, voice_audio=None):
            dur = end - start
            if dur <= 0: return
            edits.append((start, end))
            
            if original_audio is not None:
                start_s = int(start * sr)
                end_s = int(end * sr)
                bg_chunk = original_audio[start_s:end_s]
                req_s = end_s - start_s
                if len(bg_chunk) < req_s:
                    pad = np.zeros(req_s - len(bg_chunk), dtype=np.float32)
                    bg_chunk = np.concatenate([bg_chunk, pad])
                bg_timeline.append(bg_chunk)
            
            req_samples = int(dur * sr)
            if voice_audio is not None:
                v = np.zeros(req_samples, dtype=np.float32)
                copy_len = min(req_samples, len(voice_audio))
                v[:copy_len] = voice_audio[:copy_len]
                timeline.append(v)
            else:
                timeline.append(np.zeros(req_samples, dtype=np.float32))

        if not segments:
            return np.zeros(0, dtype=np.float32), None, []

        add_chunk(0.0, segments[0]["start"])
        
        for i, seg in enumerate(segments):
            self.check_cancelled()
            audio = tts_data[i] if tts_data[i] is not None else np.zeros(0, dtype=np.float32)
            
            res_len = len(audio) / sr
            actual_speech_end = seg["start"] + res_len
            
            if i + 1 < len(segments):
                actual_speech_end = min(actual_speech_end, segments[i+1]["start"])
            else:
                if audio_duration > 0:
                    actual_speech_end = min(actual_speech_end, audio_duration)
            
            add_chunk(seg["start"], actual_speech_end, audio)
            
            if i + 1 < len(segments):
                pause_start = max(seg["end"], actual_speech_end)
                pause_end = segments[i+1]["start"]
                if pause_end > pause_start:
                    add_chunk(pause_start, pause_end)
                    
        total_pauses = 0.0
        pause_count = 0
        for i in range(len(segments) - 1):
            p = segments[i+1]["start"] - segments[i]["end"]
            if p > 0:
                total_pauses += p
                pause_count += 1
                
        avg_pause = total_pauses / pause_count if pause_count > 0 else 0.5
        avg_pause = max(0.2, min(avg_pause, 1.5))
        
        last_seg = segments[-1]
        actual_speech_end = last_seg["start"] + (len(tts_data[-1])/sr if tts_data[-1] is not None else 0)
        pause_start = max(last_seg["end"], actual_speech_end)
        pause_end = pause_start + avg_pause
        if audio_duration > 0:
            pause_end = min(pause_end, audio_duration)
            
        if pause_end > pause_start:
            add_chunk(pause_start, pause_end)
            
        final_timeline = np.concatenate(timeline) if timeline else np.zeros(0, dtype=np.float32)
        final_bg = np.concatenate(bg_timeline) if bg_timeline else None
        
        return final_timeline, final_bg, edits

    def _align_sync(
        self,
        segments: list,
        tts_data: list,
        audio_duration: float,
        sr: int,
        smart_hybrid: bool = True,
    ) -> np.ndarray:
        """Keep each segment at its original timestamp."""
        total = len(segments)

        total_samples = int(audio_duration * sr)
        if total_samples == 0:
            if segments:
                last_end = max(segment["end"] for segment in segments)
                total_samples = int(last_end * sr) + sr
            else:
                total_samples = sr * 60

        timeline = np.zeros(total_samples, dtype=np.float32)
        aligned_count = 0
        compressed_count = 0
        natural_count = 0
        trimmed_count = 0

        for i, seg in enumerate(segments):
            self.check_cancelled()

            if tts_data[i] is None:
                continue

            audio = tts_data[i]
            target_start = seg["start"]
            target_end = seg["end"]
            target_duration = target_end - target_start

            if target_duration <= 0:
                continue

            pct = 5 + (i / total) * 90
            self.report_progress(pct, tr("s07.segment", default="Segment {current}/{total}", current=i + 1, total=total))

            next_start = None
            if i + 1 < total:
                next_start = segments[i + 1]["start"]

            audio, fit_mode = self._fit_segment_audio(
                audio=audio,
                target_start=target_start,
                target_end=target_end,
                next_start=next_start,
                audio_duration=audio_duration,
                sr=sr,
                smart_hybrid=smart_hybrid,
            )
            if len(audio) == 0:
                continue

            if fit_mode == "compressed":
                compressed_count += 1
            elif fit_mode == "overlapping":
                trimmed_count += 1  # reused stat logic for legacy
            else:
                natural_count += 1

            start_sample = int(target_start * sr)
            end_sample = start_sample + len(audio)

            if end_sample > len(timeline):
                extension = np.zeros(end_sample - len(timeline), dtype=np.float32)
                timeline = np.concatenate([timeline, extension])

            # Математическое наслаивание звука или жесткая перезапись
            if smart_hybrid:
                timeline[start_sample:start_sample + len(audio)] += audio
            else:
                timeline[start_sample:start_sample + len(audio)] = audio
            aligned_count += 1

        self.log(tr("s07.stats", default="Aligned: {aligned}/{total} | Natural: {natural} | Compressed: {compressed} | Overlapped: {trimmed}", aligned=aligned_count, total=total, natural=natural_count, compressed=compressed_count, trimmed=trimmed_count))
        return timeline

    def _fit_segment_audio(
        self,
        *,
        audio: np.ndarray,
        target_start: float,
        target_end: float,
        next_start: float | None,
        audio_duration: float,
        sr: int,
        smart_hybrid: bool = True,
    ) -> tuple[np.ndarray, str]:
        """Fit a generated segment into the timeline while prioritizing audio quality."""
        target_duration = target_end - target_start
        current_duration = len(audio) / sr

        # Preserve natural audio whenever it already fits the segment
        # or the pause before the next phrase gives us enough room.
        available_end = target_end
        if next_start is not None:
            available_end = max(available_end, next_start - 0.02)
        elif audio_duration > 0:
            available_end = max(available_end, audio_duration)

        available_duration = max(0.0, available_end - target_start)
        if available_duration <= 0:
            return np.array([], dtype=np.float32), "skipped"

        if current_duration <= target_duration + 0.01:
            return apply_fade_edges(audio, sr=sr, fade_ms=DEFAULT_SEGMENT_FADE_MS), "natural"

        if current_duration <= available_duration + 0.01:
            return apply_fade_edges(audio, sr=sr, fade_ms=DEFAULT_SEGMENT_FADE_MS), "natural"

        compression_needed = abs(1.0 - (available_duration / current_duration))
        if DEFAULT_TIME_STRETCH_LIMIT > 0 and compression_needed <= DEFAULT_TIME_STRETCH_LIMIT:
            stretched, success = time_stretch_segment(
                audio,
                available_duration,
                current_duration,
                sr=sr,
                max_stretch=DEFAULT_TIME_STRETCH_LIMIT,
            )
            if success:
                return apply_fade_edges(
                    stretched,
                    sr=sr,
                    fade_ms=DEFAULT_SEGMENT_FADE_MS,
                ), "compressed"

        if smart_hybrid:
            # Smart Hybrid: Больше не обрезаем звук.
            return apply_fade_edges(audio, sr=sr, fade_ms=DEFAULT_SEGMENT_FADE_MS), "overlapping"
        else:
            # Классическое жесткое обрезание
            max_samples = max(1, int(available_duration * sr))
            trimmed = audio[:max_samples]
            return apply_fade_edges(trimmed, sr=sr, fade_ms=DEFAULT_SEGMENT_FADE_MS), "trimmed"
