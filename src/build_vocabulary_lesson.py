#!/usr/bin/env python3
"""Build the adaptive daily core-vocabulary lesson for GitHub Pages."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "config"
PROFILE_PATH = ROOT / "docs" / "data" / "vocabulary" / "learner-profile.json"
TODAY_PATH = ROOT / "docs" / "data" / "vocabulary" / "today.json"
ARCHIVE_DIR = ROOT / "docs" / "data" / "vocabulary" / "archive"
ARTICLE_TODAY_PATH = ROOT / "docs" / "data" / "today.json"
LESSON_SIZE = int(os.environ.get("VOCABULARY_LESSON_SIZE", "10"))
MAX_REVIEW = int(os.environ.get("VOCABULARY_MAX_REVIEW", "4"))


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def lesson_date() -> str:
    explicit = os.environ.get("VOCABULARY_DATE", "").strip()
    if explicit:
        date.fromisoformat(explicit)
        return explicit
    article_today = read_json(ARTICLE_TODAY_PATH, {})
    candidate = article_today.get("date") if isinstance(article_today, dict) else None
    if candidate:
        date.fromisoformat(candidate)
        return candidate
    return datetime.now(timezone.utc).date().isoformat()


def stable_rank(day: str, word_id: str) -> str:
    return hashlib.sha256(f"{day}:{word_id}".encode("utf-8")).hexdigest()


def profile_entry(profile_words: dict[str, Any], word_id: str) -> dict[str, Any]:
    value = profile_words.get(word_id, {})
    return value if isinstance(value, dict) else {}


def main() -> None:
    bank_files = sorted(BANK_DIR.glob("vocabulary_core_words*.json"))
    words: list[dict[str, Any]] = []
    for bank_path in bank_files:
        bank = read_json(bank_path, {})
        part = bank.get("words", []) if isinstance(bank, dict) else []
        if not isinstance(part, list):
            raise SystemExit(f"Invalid words array in {bank_path}")
        words.extend(part)
    if not words:
        raise SystemExit(f"No vocabulary words found in {BANK_DIR}")
    if len({w.get('id') for w in words}) != len(words):
        raise SystemExit("Vocabulary word IDs must be unique")

    profile = read_json(
        PROFILE_PATH,
        {"version": 2, "updated_at": None, "feedback_sessions": 0, "processed_issue_numbers": [], "words": {}},
    )
    if not isinstance(profile, dict):
        raise SystemExit("Learner profile must be a JSON object")
    profile_words = profile.setdefault("words", {})
    if not isinstance(profile_words, dict):
        raise SystemExit("Learner profile words must be an object")

    day = lesson_date()
    due: list[dict[str, Any]] = []
    unseen: list[dict[str, Any]] = []
    learning_not_due: list[dict[str, Any]] = []

    for word in words:
        word_id = str(word.get("id", ""))
        entry = profile_entry(profile_words, word_id)
        verified_known = (
            entry.get("status") == "known"
            and int(entry.get("mastery", 0)) >= 5
            and int(entry.get("successful_sessions", 0)) >= 2
        )
        if verified_known:
            continue
        if not entry:
            unseen.append(word)
            continue
        legacy_self_marked = entry.get("status") == "known" and not verified_known
        effective_entry = {**entry}
        if legacy_self_marked:
            effective_entry["status"] = "learning"
            effective_entry["next_review"] = day
            effective_entry["verification_required"] = True
        next_review = str(effective_entry.get("next_review") or "9999-12-31")
        wrapped = {**word, "_profile": effective_entry}
        if next_review <= day:
            due.append(wrapped)
        else:
            learning_not_due.append(wrapped)

    due.sort(
        key=lambda w: (
            str(w.get("_profile", {}).get("next_review") or ""),
            int(w.get("_profile", {}).get("mastery", 0)),
            str(w.get("word")),
        )
    )
    unseen.sort(key=lambda w: stable_rank(day, str(w.get("id"))))
    learning_not_due.sort(
        key=lambda w: (
            str(w.get("_profile", {}).get("next_review") or "9999-12-31"),
            stable_rank(day, str(w.get("id"))),
        )
    )

    selected: list[tuple[dict[str, Any], str]] = []
    for word in due[: min(MAX_REVIEW, LESSON_SIZE)]:
        selected.append((word, "review"))
    for word in unseen:
        if len(selected) >= LESSON_SIZE:
            break
        selected.append((word, "new"))
    for word in due[min(MAX_REVIEW, LESSON_SIZE) :]:
        if len(selected) >= LESSON_SIZE:
            break
        selected.append((word, "review"))
    for word in learning_not_due:
        if len(selected) >= LESSON_SIZE:
            break
        selected.append((word, "review"))

    published_words = []
    for position, (word, reason) in enumerate(selected, start=1):
        clean = {k: v for k, v in word.items() if not k.startswith("_")}
        entry = word.get("_profile", {}) if isinstance(word.get("_profile"), dict) else {}
        clean["reason"] = reason
        clean["position"] = position
        clean["learning_state"] = {
            "mastery": int(entry.get("mastery", 0)),
            "times_seen": int(entry.get("times_seen", 0)),
            "last_score": entry.get("last_score"),
            "verification_required": bool(entry.get("verification_required")),
        }
        published_words.append(clean)

    all_ids = {str(w.get("id")) for w in words}
    known_count = sum(1 for wid in all_ids if profile_entry(profile_words, wid).get("status") == "known")
    learning_count = sum(
        1
        for wid in all_ids
        if profile_entry(profile_words, wid) and profile_entry(profile_words, wid).get("status") != "known"
    )
    now = datetime.now(timezone.utc).isoformat()
    output = {
        "version": 2,
        "date": day,
        "generated_at": now,
        "track": "Essential English 3000",
        "lesson_size": len(published_words),
        "method": {
            "name": "Active retrieval + contextual production + spaced review",
            "steps": ["study", "productive_recall", "context_cloze", "sentence_production"],
            "mastery_threshold": 5,
        },
        "selection": {
            "new_count": sum(1 for w in published_words if w["reason"] == "new"),
            "review_count": sum(1 for w in published_words if w["reason"] == "review"),
            "rule": "Due review words are prioritized; remaining places use unseen core words; mastered words are excluded.",
        },
        "profile_summary": {
            "bank_size": len(words),
            "known_count": known_count,
            "learning_count": learning_count,
            "remaining_count": max(0, len(words) - known_count),
            "profile_updated_at": profile.get("updated_at"),
        },
        "words": published_words,
    }

    TODAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    TODAY_PATH.write_text(rendered, encoding="utf-8")
    (ARCHIVE_DIR / f"{day}.json").write_text(rendered, encoding="utf-8")
    print(
        f"Built vocabulary lesson {day}: {len(published_words)} words "
        f"({output['selection']['new_count']} new, {output['selection']['review_count']} review)."
    )


if __name__ == "__main__":
    main()
