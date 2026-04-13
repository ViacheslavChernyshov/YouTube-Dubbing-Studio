import re
import unittest

from app.pipeline.stages.s05_translate import TranslateStage


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class TranslateMappingTests(unittest.TestCase):
    def setUp(self):
        self.stage = TranslateStage()

    def test_spanning_sentence_is_distributed_across_segments(self):
        segments = [
            {"text": "Этот салат едят те, кто хочет выглядеть дорого, но тратить"},
            {"text": "минимум времени на кухне."},
        ]

        full_text, seg_ranges = self.stage._build_full_text(segments)
        sentences = self.stage._split_sentences(full_text)
        self.assertEqual(1, len(sentences))

        translated = (
            "This salad is for people who want to look expensive but spend very little time in the kitchen."
        )
        sentences[0]["translated"] = translated

        self.stage._map_to_segments(segments, sentences, seg_ranges)

        combined = _normalize(
            f"{segments[0]['translated_text']} {segments[1]['translated_text']}"
        )
        self.assertEqual(_normalize(translated), combined)
        self.assertTrue(segments[0]["translated_text"])
        self.assertTrue(segments[1]["translated_text"])
        self.assertNotEqual(segments[0]["translated_text"], segments[0]["text"])
        self.assertNotEqual(segments[1]["translated_text"], segments[1]["text"])

    def test_single_segment_sentence_keeps_full_translation(self):
        segments = [{"text": "Привет, мир."}]
        full_text, seg_ranges = self.stage._build_full_text(segments)
        sentences = self.stage._split_sentences(full_text)
        sentences[0]["translated"] = "Hello, world."

        self.stage._map_to_segments(segments, sentences, seg_ranges)

        self.assertEqual("Hello, world.", segments[0]["translated_text"])


if __name__ == "__main__":
    unittest.main()
