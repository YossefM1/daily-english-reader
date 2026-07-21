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


class ListeningBuilderTests(unittest.TestCase):
    def test_builder_prefers_unseen_lesson(self):
        builder = load_module("build_listening_lesson", REPO_ROOT / "src" / "build_listening_lesson.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            data = root / "docs" / "data"
            listening = data / "listening"
            config.mkdir(parents=True)
            listening.mkdir(parents=True)
            library = {"version": 1, "lessons": [{"id": "done", "title": "Done"}, {"id": "new", "title": "New"}]}
            (config / "listening_library.json").write_text(json.dumps(library), encoding="utf-8")
            (data / "today.json").write_text('{"date":"2026-07-21"}', encoding="utf-8")
            (listening / "profile.json").write_text(json.dumps({"lessons": {"done": {"completed": True, "best_percent": 90, "last_seen": "2026-07-20"}}}), encoding="utf-8")
            builder.LIBRARY_SOURCE = config / "listening_library.json"
            builder.LIBRARY_PUBLIC = listening / "library.json"
            builder.PROFILE_PATH = listening / "profile.json"
            builder.TODAY_PATH = listening / "today.json"
            builder.ARTICLE_TODAY_PATH = data / "today.json"
            builder.main()
            today = json.loads((listening / "today.json").read_text(encoding="utf-8"))
            self.assertEqual(today["lesson_id"], "new")
            self.assertEqual(today["profile_summary"]["completed_count"], 1)

    def test_builder_returns_low_score_for_review(self):
        builder = load_module("build_listening_review", REPO_ROOT / "src" / "build_listening_lesson.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            data = root / "docs" / "data"
            listening = data / "listening"
            config.mkdir(parents=True)
            listening.mkdir(parents=True)
            library = {"version": 1, "lessons": [{"id": "weak", "title": "Weak"}, {"id": "strong", "title": "Strong"}]}
            (config / "listening_library.json").write_text(json.dumps(library), encoding="utf-8")
            (data / "today.json").write_text('{"date":"2026-07-22"}', encoding="utf-8")
            (listening / "profile.json").write_text(json.dumps({"lessons": {"weak": {"completed": False, "best_percent": 50}, "strong": {"completed": True, "best_percent": 90}}}), encoding="utf-8")
            builder.LIBRARY_SOURCE = config / "listening_library.json"
            builder.LIBRARY_PUBLIC = listening / "library.json"
            builder.PROFILE_PATH = listening / "profile.json"
            builder.TODAY_PATH = listening / "today.json"
            builder.ARTICLE_TODAY_PATH = data / "today.json"
            builder.main()
            today = json.loads((listening / "today.json").read_text(encoding="utf-8"))
            self.assertEqual(today["lesson_id"], "weak")


class ListeningFeedbackTests(unittest.TestCase):
    def test_feedback_records_success_and_shadowing(self):
        feedback = load_module("apply_listening_feedback", REPO_ROOT / "src" / "apply_listening_feedback.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library_path = root / "library.json"
            profile_path = root / "profile.json"
            event_path = root / "event.json"
            library_path.write_text(json.dumps({"lessons": [{"id": "lesson-1"}]}), encoding="utf-8")
            profile_path.write_text(json.dumps({"lessons": {}, "processed_issue_numbers": []}), encoding="utf-8")
            payload = {"kind": "listening_feedback", "version": 1, "date": "2026-07-21", "lesson_id": "lesson-1", "score": 80, "completed": True, "shadowing_repetitions": 3, "first_watch_captions": False, "second_watch_captions": True, "self_rating": 4}
            event_path.write_text(json.dumps({"issue": {"number": 42, "body": "```json\n" + json.dumps(payload) + "\n```"}}), encoding="utf-8")
            feedback.LIBRARY_PATH = library_path
            feedback.PROFILE_PATH = profile_path
            feedback.main(str(event_path))
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            item = profile["lessons"]["lesson-1"]
            self.assertTrue(item["completed"])
            self.assertEqual(item["best_percent"], 80)
            self.assertEqual(item["shadowing_repetitions_total"], 3)
            self.assertIn(42, profile["processed_issue_numbers"])


if __name__ == "__main__":
    unittest.main()
