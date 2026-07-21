from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class VocabularyFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feedback = load_module(
            "apply_vocabulary_feedback",
            REPO_ROOT / "src" / "apply_vocabulary_feedback.py",
        )

    def test_manual_like_is_immediately_authoritative(self):
        words = {}
        count = self.feedback.apply_manual_known(words, ["core-0001"], "2026-07-21")
        self.assertEqual(count, 1)
        self.assertEqual(words["core-0001"]["status"], "known")
        self.assertEqual(words["core-0001"]["mastery"], 5)
        self.assertEqual(words["core-0001"]["known_source"], "manual_like")
        self.assertIsNone(words["core-0001"]["next_review"])

    def test_active_learning_requires_repeated_success(self):
        words = {}
        result = [{
            "id": "core-0002",
            "score": 4,
            "confidence": "easy",
            "recall_attempts": 1,
            "recall_correct": True,
            "recall_hint": False,
            "context_attempts": 1,
            "context_correct": True,
            "production_complete": True,
        }]

        mastered, learning = self.feedback.apply_v2(words, result, "2026-07-21")
        self.assertEqual((mastered, learning), (0, 1))
        self.assertEqual(words["core-0002"]["status"], "learning")
        self.assertEqual(words["core-0002"]["mastery"], 2)

        mastered, learning = self.feedback.apply_v2(words, result, "2026-07-28")
        self.assertEqual((mastered, learning), (0, 1))
        self.assertEqual(words["core-0002"]["status"], "learning")
        self.assertEqual(words["core-0002"]["mastery"], 4)

        mastered, learning = self.feedback.apply_v2(words, result, "2026-08-11")
        self.assertEqual((mastered, learning), (1, 0))
        self.assertEqual(words["core-0002"]["status"], "known")
        self.assertEqual(words["core-0002"]["known_source"], "adaptive_mastery")
        self.assertIsNone(words["core-0002"]["next_review"])

    def test_failed_recall_returns_next_day(self):
        words = {"core-0003": {"mastery": 3, "successful_sessions": 1}}
        result = [{
            "id": "core-0003",
            "score": 1,
            "confidence": "again",
            "recall_attempts": 3,
            "recall_correct": False,
            "recall_hint": True,
            "context_attempts": 2,
            "context_correct": False,
            "production_complete": True,
        }]
        mastered, learning = self.feedback.apply_v2(words, result, "2026-07-21")
        self.assertEqual((mastered, learning), (0, 1))
        self.assertEqual(words["core-0003"]["status"], "learning")
        self.assertEqual(words["core-0003"]["next_review"], "2026-07-22")


class VocabularyLessonBuilderTests(unittest.TestCase):
    def test_known_words_are_excluded_from_lesson(self):
        builder = load_module(
            "build_vocabulary_lesson",
            REPO_ROOT / "src" / "build_vocabulary_lesson.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            data = root / "docs" / "data"
            vocab = data / "vocabulary"
            config.mkdir(parents=True)
            vocab.mkdir(parents=True)
            bank = {
                "words": [
                    {"id": "w1", "word": "known", "hebrew": "ידוע", "example": "I know it."},
                    {"id": "w2", "word": "learn", "hebrew": "ללמוד", "example": "We learn daily."},
                ]
            }
            (config / "vocabulary_core_words_01.json").write_text(json.dumps(bank), encoding="utf-8")
            (data / "today.json").write_text('{"date":"2026-07-21"}', encoding="utf-8")
            (vocab / "learner-profile.json").write_text(
                json.dumps({
                    "version": 2,
                    "words": {"w1": {"status": "known", "known_source": "manual_like"}},
                }),
                encoding="utf-8",
            )

            builder.BANK_DIR = config
            builder.PROFILE_PATH = vocab / "learner-profile.json"
            builder.TODAY_PATH = vocab / "today.json"
            builder.ARCHIVE_DIR = vocab / "archive"
            builder.ARTICLE_TODAY_PATH = data / "today.json"
            builder.LESSON_SIZE = 10
            builder.MAX_REVIEW = 4
            builder.main()

            lesson = json.loads((vocab / "today.json").read_text(encoding="utf-8"))
            self.assertEqual([word["id"] for word in lesson["words"]], ["w2"])


if __name__ == "__main__":
    unittest.main()
