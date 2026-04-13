"""
Local neural machine translation using Meta's NLLB-200-distilled-1.3B model.
Runs fully offline on GPU (after first-time model download ~2.6GB).
Supports 200+ languages with a single model.
"""
import logging
from pathlib import Path

import torch
from typing import Optional

from app.config import get_huggingface_cache_dir, get_nllb_model_dir
from app.utils.hf_download import ProgressCallback, snapshot_download_with_progress


logger = logging.getLogger(__name__)


# NLLB-200 language codes (BCP-47 → FLORES-200)
_NLLB_LANG_CODES = {
    "ru": "rus_Cyrl",
    "uk": "ukr_Cyrl",
    "en": "eng_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "ar": "arb_Arab",
    "bn": "ben_Beng",
    "hi": "hin_Deva",
    "pl": "pol_Latn",
    "nl": "nld_Latn",
    "tr": "tur_Latn",
    "cs": "ces_Latn",
    "sv": "swe_Latn",
    "da": "dan_Latn",
    "fi": "fin_Latn",
    "no": "nob_Latn",
    "ro": "ron_Latn",
    "bg": "bul_Cyrl",
    "hr": "hrv_Latn",
    "sr": "srp_Cyrl",
    "sk": "slk_Latn",
    "sl": "slv_Latn",
    "et": "est_Latn",
    "lv": "lvs_Latn",
    "lt": "lit_Latn",
    "hu": "hun_Latn",
    "el": "ell_Grek",
    "he": "heb_Hebr",
    "th": "tha_Thai",
    "vi": "vie_Latn",
    "id": "ind_Latn",
    "ms": "zsm_Latn",
    "tl": "tgl_Latn",
    "ka": "kat_Geor",
    "hy": "hye_Armn",
    "az": "azj_Latn",
    "kk": "kaz_Cyrl",
    "uz": "uzn_Latn",
    "be": "bel_Cyrl",
}

MODEL_NAME = "facebook/nllb-200-distilled-1.3B"


def get_local_model_dir() -> Path:
    return get_nllb_model_dir()


def ensure_model_downloaded(
    logger_instance: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Download the NLLB model into the portable data directory if needed."""
    model_dir = get_local_model_dir()
    config_file = model_dir / "config.json"
    tokenizer_candidates = (
        model_dir / "tokenizer.json",
        model_dir / "tokenizer_config.json",
        model_dir / "sentencepiece.bpe.model",
    )

    if config_file.exists() and any(candidate.exists() for candidate in tokenizer_candidates):
        return model_dir

    active_logger = logger_instance or logger
    active_logger.info("Скачивание переводчика NLLB-200 (это самый крупный пакет, потребуется время)...")
    snapshot_download_with_progress(
        repo_id=MODEL_NAME,
        local_dir=model_dir,
        cache_dir=get_huggingface_cache_dir(),
        progress_callback=progress_callback,
        progress_message="Скачивание модели NLLB-200",
    )
    return model_dir


def _clean_text(text: str) -> str:
    """Preprocess text before translation for better quality."""
    import re
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove repeated punctuation (e.g. "..." -> ".")
    text = re.sub(r'([.!?])\1+', r'\1', text)
    # Ensure text ends with punctuation for better translation
    if text and text[-1] not in '.!?:;':
        text += '.'
    return text


class LocalTranslator:
    """GPU-accelerated local translator using NLLB-200-distilled-1.3B."""

    def __init__(self, device: str = "cpu"):
        self._device = device
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self):
        """Load model if not already loaded."""
        if self._model is not None:
            return

        # Free GPU memory from previous stages
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            import gc
            gc.collect()

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model_dir = ensure_model_downloaded()
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), local_files_only=True)

        if self._device == "cuda" and torch.cuda.is_available():
            try:
                self._model = self._model.half().to("cuda")
            except RuntimeError:
                # CUDA OOM — fallback to CPU
                torch.cuda.empty_cache()
                self._model = self._model.float().to("cpu")
                self._device = "cpu"
        else:
            self._model = self._model.to("cpu")

        self._model.eval()

    def _get_nllb_code(self, lang: str) -> str:
        """Convert ISO 639-1 code to NLLB FLORES-200 code."""
        code = _NLLB_LANG_CODES.get(lang)
        if not code:
            raise ValueError(
                f"Язык '{lang}' не поддерживается. "
                f"Доступные: {', '.join(sorted(_NLLB_LANG_CODES.keys()))}"
            )
        return code

    def translate(
        self,
        text: str,
        source_lang: str = "ru",
        target_lang: str = "en",
    ) -> str:
        """Translate a single text string."""
        if not text.strip():
            return ""

        self._ensure_loaded()

        src_code = self._get_nllb_code(source_lang)
        tgt_code = self._get_nllb_code(target_lang)

        # Clean input text
        cleaned = _clean_text(text)

        self._tokenizer.src_lang = src_code

        inputs = self._tokenizer(
            cleaned,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(self._model.device)

        # Dynamic output length based on input (capped to avoid OOM)
        input_len = inputs["input_ids"].shape[1]
        max_new_tokens = min(256, max(64, int(input_len * 2)))

        with torch.no_grad():
            translated_ids = self._model.generate(
                **inputs,
                forced_bos_token_id=self._tokenizer.convert_tokens_to_ids(tgt_code),
                num_beams=5,
                max_new_tokens=max_new_tokens,
                length_penalty=1.0,
                repetition_penalty=1.1,
                no_repeat_ngram_size=4,
                early_stopping=False,
            )

        result = self._tokenizer.decode(
            translated_ids[0], skip_special_tokens=True
        )
        return result.strip()

    def batch_translate(
        self,
        texts: list[str],
        source_lang: str = "ru",
        target_lang: str = "en",
        batch_size: int = 4,
    ) -> list[str]:
        """Translate a batch of texts efficiently."""
        if not texts:
            return []

        self._ensure_loaded()

        src_code = self._get_nllb_code(source_lang)
        tgt_code = self._get_nllb_code(target_lang)
        tgt_token_id = self._tokenizer.convert_tokens_to_ids(tgt_code)

        self._tokenizer.src_lang = src_code

        # Separate empty and non-empty
        indexed_texts = [(i, t) for i, t in enumerate(texts)]
        results = [""] * len(texts)

        non_empty = [(i, t) for i, t in indexed_texts if t.strip()]
        if not non_empty:
            return results

        # Process in mini-batches to manage VRAM
        for batch_start in range(0, len(non_empty), batch_size):
            batch = non_empty[batch_start:batch_start + batch_size]
            indices, batch_texts = zip(*batch)

            # Clean input texts
            cleaned_texts = [_clean_text(t) for t in batch_texts]

            inputs = self._tokenizer(
                list(cleaned_texts),
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(self._model.device)

            # Dynamic output length based on longest input in batch (capped)
            max_input_len = inputs["input_ids"].shape[1]
            max_new_tokens = min(256, max(64, int(max_input_len * 2)))

            try:
                with torch.no_grad():
                    translated_ids = self._model.generate(
                        **inputs,
                        forced_bos_token_id=tgt_token_id,
                        num_beams=5,
                        max_new_tokens=max_new_tokens,
                        length_penalty=1.0,
                        repetition_penalty=1.1,
                        no_repeat_ngram_size=4,
                        early_stopping=False,
                    )
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    # OOM: fallback to CPU for this batch
                    torch.cuda.empty_cache()
                    inputs = inputs.to("cpu")
                    self._model = self._model.float().to("cpu")
                    self._device = "cpu"
                    with torch.no_grad():
                        translated_ids = self._model.generate(
                            **inputs,
                            forced_bos_token_id=tgt_token_id,
                            num_beams=4,
                            max_new_tokens=max_new_tokens,
                            length_penalty=1.0,
                            repetition_penalty=1.1,
                            no_repeat_ngram_size=4,
                            early_stopping=False,
                        )
                else:
                    raise

            translations = self._tokenizer.batch_decode(
                translated_ids, skip_special_tokens=True
            )

            for idx, trans in zip(indices, translations):
                results[idx] = trans.strip()

        return results

    def unload(self):
        """Free model resources."""
        if self._model is not None:
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
