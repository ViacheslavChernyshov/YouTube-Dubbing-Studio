"""
Stage 5: Translation via local NLLB-200-1.3B — accurate, fast, fully offline.

Approach: concatenate all segments → split into proper sentences →
translate each sentence → map back to original segments by character position.
This prevents fragment loss when Whisper splits mid-sentence.
"""
import re
import json
from pathlib import Path

from app.language_catalog import DEFAULT_TARGET_LANGUAGE
from app.pipeline.base_stage import BaseStage
from app.pipeline.context import PipelineContext
from app.i18n import tr


class TranslateStage(BaseStage):
    def __init__(self):
        super().__init__(5, tr("s05.name", default="Text Translation"), tr("s05.desc", default="Accurate translation using neural network"))

    def run(self, job_dir: Path, context: PipelineContext) -> PipelineContext:
        segments = context.segments
        source_lang = context.source_language or "ru"
        device = context.device or "cpu"
        job_settings = context.settings
        target_lang = getattr(job_settings, "target_language", DEFAULT_TARGET_LANGUAGE)

        if source_lang == target_lang:
            self.log(tr("s05.same_lang", default="Source language is already '{lang}', no translation needed", lang=target_lang))
            for seg in segments:
                seg["translated_text"] = seg["text"]
            context.segments = segments
            return context

        self.log(tr("s05.translating", default="Translating {count} segments: {src} → {tgt}", count=len(segments), src=source_lang, tgt=target_lang))
        self.report_progress(5, tr("s05.loading_model", default="Loading translation model..."))

        from app.translator.local_translator import LocalTranslator
        translator = LocalTranslator(device=device)

        self.log(tr("s05.model_info", default="Model: NLLB-200-1.3B, device: {dev}", dev=device))

        try:
            # ── Step 1: Build full text with segment character offsets ──
            self.report_progress(10, tr("s05.analyzing", default="Analyzing sentences..."))
            full_text, seg_ranges = self._build_full_text(segments)
            self.log(tr("s05.text_length", default="Full text: {count} characters", count=len(full_text)))
    
            # ── Step 2: Split into sentences ──
            sentences = self._split_sentences(full_text)
            self.log(tr("s05.split_count", default="Split into {count} sentences", count=len(sentences)))

            # ── Step 3: Translate each sentence ──
            sentence_texts = [s["text"] for s in sentences]
    
            self.report_progress(15, tr("s05.batch", default="Translating {count} sentences...", count=len(sentence_texts)))

            try:
                translated_list = translator.batch_translate(
                    texts=sentence_texts,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
            except Exception as e:
                self.log(tr("s05.batch_error", default="Batch translation error: {err}, switching to single-sentence mode", err=e), level=30)
                translated_list = []
            for i, text in enumerate(sentence_texts):
                self.check_cancelled()
                pct = 15 + (i / len(sentence_texts)) * 75
                self.report_progress(pct, f"[{i+1}/{len(sentence_texts)}]")
                try:
                        translated_list.append(
                            translator.translate(text, source_lang, target_lang)
                        )
                    except Exception as te:
                        self.log(tr("s05.single_error", default="  Error in sentence {idx}: {err}", idx=i+1, err=te), level=30)
                        translated_list.append(text)
    
            # Store translations in sentence dicts
            for sent, trans in zip(sentences, translated_list):
                sent["translated"] = trans if trans else sent["text"]
    
            self.report_progress(85, tr("s05.mapping", default="Mapping to segments..."))
    
            # ── Step 4: Map sentences back to segments ──
            self._map_to_segments(segments, sentences, seg_ranges)
    
            self.report_progress(90, tr("s05.saving", default="Saving..."))
    
            for seg in segments:
                orig = seg["text"]
                trans = seg.get("translated_text", "")
                self.log(f"  {orig} → {trans}")
                
        finally:
            translator.unload()

        translated_file = job_dir / "segments_translated.json"
        with open(translated_file, "w", encoding="utf-8") as f:
            json.dump({
                "source_language": source_lang,
                "target_language": target_lang,
                "segments": segments,
            }, f, ensure_ascii=False, indent=2)

        self.log(tr("s05.done", default="Translated {count} segments", count=len(segments)))
        context.segments = segments
        context.translated_file = str(translated_file)
        context.target_language = target_lang
        return context

    # ── Build full text with tracked character positions ──

    def _build_full_text(self, segments: list) -> tuple:
        """
        Concatenate all segment texts into one string.
        Returns (full_text, seg_ranges) where seg_ranges[i] = (start, end)
        is the character range of segment i within full_text.
        """
        parts = []
        seg_ranges = []
        offset = 0

        for seg in segments:
            text = seg["text"].strip()
            if parts:
                parts.append(" ")
                offset += 1
            start = offset
            parts.append(text)
            offset += len(text)
            seg_ranges.append((start, offset))

        full_text = "".join(parts)
        return full_text, seg_ranges

    def _split_sentences(self, text: str) -> list:
        """
        Split text into sentences, tracking character positions.
        Returns list of {"text": str, "start": int, "end": int}.
        """
        # Split on sentence-ending punctuation followed by space or end
        pattern = re.compile(r'(?<=[.!?…])\s+')
        sentences = []
        last_end = 0

        for match in pattern.finditer(text):
            sent_text = text[last_end:match.start()].strip()
            if sent_text:
                sentences.append({
                    "text": sent_text,
                    "start": last_end,
                    "end": match.start(),
                })
            last_end = match.end()

        # Last sentence (or the only one if no splits)
        remaining = text[last_end:].strip()
        if remaining:
            sentences.append({
                "text": remaining,
                "start": last_end,
                "end": len(text),
            })

        return sentences

    def _map_to_segments(
        self,
        segments: list,
        sentences: list,
        seg_ranges: list,
    ):
        """
        Map translated sentences back to segments.
        If one source sentence spans several Whisper segments, split the
        translated sentence proportionally so no segment falls back to the
        original language.
        """
        # For each segment, collect list of assigned translations
        seg_translations: dict[int, list[str]] = {i: [] for i in range(len(segments))}

        for sent in sentences:
            overlaps: list[tuple[int, int]] = []

            for seg_idx, (seg_start, seg_end) in enumerate(seg_ranges):
                overlap_start = max(seg_start, sent["start"])
                overlap_end = min(seg_end, sent["end"])

                if overlap_start < overlap_end:
                    overlaps.append((seg_idx, overlap_end - overlap_start))

            if not overlaps:
                continue

            translated = sent.get("translated", "").strip() or sent["text"].strip()
            if len(overlaps) == 1:
                seg_translations[overlaps[0][0]].append(translated)
                continue

            chunks = self._split_translation_by_overlap(
                translated,
                [overlap for _, overlap in overlaps],
            )
            for (seg_idx, _), chunk in zip(overlaps, chunks):
                if chunk:
                    seg_translations[seg_idx].append(chunk)

        # Apply to segments
        for seg_idx in range(len(segments)):
            translations = seg_translations[seg_idx]
            if translations:
                segments[seg_idx]["translated_text"] = " ".join(translations).strip()
            else:
                segments[seg_idx]["translated_text"] = segments[seg_idx]["text"]

    def _split_translation_by_overlap(self, translated: str, overlaps: list[int]) -> list[str]:
        """Split translated text into contiguous chunks based on source overlap."""
        normalized = re.sub(r"\s+", " ", translated).strip()
        if not normalized:
            return [""] * len(overlaps)
        if len(overlaps) == 1:
            return [normalized]

        weights = [max(1, overlap) for overlap in overlaps]
        total_weight = sum(weights)
        enforce_min_chunk = len(normalized) >= len(overlaps)

        cuts = [0]
        running_weight = 0
        for idx, weight in enumerate(weights[:-1], start=1):
            running_weight += weight
            raw_target = int(round(len(normalized) * running_weight / total_weight))

            if enforce_min_chunk:
                min_index = cuts[-1] + 1
                remaining_chunks = len(overlaps) - idx
                max_index = len(normalized) - remaining_chunks
            else:
                min_index = cuts[-1]
                max_index = len(normalized)

            raw_target = max(min_index, min(raw_target, max_index))
            cut = self._snap_split_index(normalized, raw_target, min_index, max_index)
            cuts.append(cut)
        cuts.append(len(normalized))

        return [normalized[cuts[i]:cuts[i + 1]].strip() for i in range(len(overlaps))]

    @staticmethod
    def _snap_split_index(text: str, target: int, min_index: int, max_index: int, window: int = 12) -> int:
        """Snap a split boundary to nearby whitespace when possible."""
        target = max(min_index, min(target, max_index))
        left = max(min_index, target - window)
        right = min(max_index, target + window)

        best_index = target
        best_distance = None
        for idx in range(left, right + 1):
            if idx < len(text) and text[idx].isspace():
                distance = abs(idx - target)
                if best_distance is None or distance < best_distance:
                    best_index = idx
                    best_distance = distance

        return best_index
