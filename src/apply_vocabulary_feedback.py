#!/usr/bin/env python3
"""Apply a repository-owner vocabulary feedback issue to the public learner profile."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "config"
PROFILE_PATH = ROOT / "docs" / "data" / "vocabulary" / "learner-profile.json"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def extract_payload(body: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", body or "", flags=re.DOTALL | re.IGNORECASE)
    raw = match.group(1) if match else (body or "").strip()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Feedback payload must be an object")
    return payload


def unique_strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be an array of word IDs")
    return list(dict.fromkeys(value))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def apply_v1(words: dict[str, Any], payload: dict[str, Any], session_date: str) -> tuple[int, int]:
    known = unique_strings(payload.get("known"), "known")
    review = unique_strings(payload.get("review"), "review")
    if set(known) & set(review):
        raise ValueError("A word cannot be both known and review")
    if len(known) + len(review) > 100:
        raise ValueError("Feedback contains too many words")

    for word_id in known:
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        words[word_id] = {
            **previous,
            "status": "known",
            "mastery": 5,
            "last_seen": session_date,
            "next_review": None,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
            "successful_sessions": max(2, int(previous.get("successful_sessions", 0))),
            "known_source": "manual_like",
        }

    tomorrow = (date.fromisoformat(session_date) + timedelta(days=1)).isoformat()
    for word_id in review:
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        words[word_id] = {
            **previous,
            "status": "learning",
            "mastery": max(0, int(previous.get("mastery", 1)) - 1),
            "last_seen": session_date,
            "next_review": tomorrow,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
        }
    return len(known), len(review)


def validate_results(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("results must be an array")
    if len(value) > 100:
        raise ValueError("Feedback contains too many results")
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each result must be an object")
        word_id = str(item.get("id") or "")
        if not word_id or word_id in seen:
            raise ValueError("Result word IDs must be present and unique")
        seen.add(word_id)
        score = int(item.get("score", -1))
        if score < 0 or score > 4:
            raise ValueError(f"Invalid score for {word_id}")
        confidence = str(item.get("confidence") or "again")
        if confidence not in {"easy", "hard", "again"}:
            raise ValueError(f"Invalid confidence for {word_id}")
        cleaned.append(
            {
                "id": word_id,
                "score": score,
                "confidence": confidence,
                "recall_attempts": clamp(int(item.get("recall_attempts", 0)), 0, 10),
                "recall_correct": bool(item.get("recall_correct")),
                "recall_hint": bool(item.get("recall_hint")),
                "context_attempts": clamp(int(item.get("context_attempts", 0)), 0, 10),
                "context_correct": bool(item.get("context_correct")),
                "production_complete": bool(item.get("production_complete")),
            }
        )
    return cleaned


def review_days(score: int, confidence: str, mastery: int) -> int:
    if confidence == "again" or score <= 1:
        return 1
    if score == 2:
        return 2
    if score == 3:
        return 3 if mastery < 3 else 7
    days_by_mastery = {0: 1, 1: 3, 2: 7, 3: 14, 4: 30, 5: 60}
    days = days_by_mastery.get(mastery, 30)
    if confidence == "hard":
        return min(days, 3)
    return days


def apply_manual_known(words: dict[str, Any], known_ids: list[str], session_date: str) -> int:
    for word_id in known_ids:
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        words[word_id] = {
            **previous,
            "status": "known",
            "mastery": 5,
            "last_seen": session_date,
            "next_review": None,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
            "successful_sessions": max(2, int(previous.get("successful_sessions", 0))),
            "last_score": 4,
            "best_score": max(4, int(previous.get("best_score", 0))),
            "last_confidence": "easy",
            "known_source": "manual_like",
        }
    return len(known_ids)


def apply_v2(words: dict[str, Any], results: list[dict[str, Any]], session_date: str) -> tuple[int, int]:
    mastered = 0
    learning = 0
    session_day = date.fromisoformat(session_date)
    for result in results:
        word_id = result["id"]
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        old_mastery = clamp(int(previous.get("mastery", 0)), 0, 5)
        score = result["score"]
        confidence = result["confidence"]

        if score == 4 and confidence == "easy":
            mastery = clamp(old_mastery + 2, 0, 5)
        elif score >= 3:
            mastery = clamp(old_mastery + 1, 0, 5)
        elif score == 2:
            mastery = clamp(old_mastery - 1, 0, 5)
        else:
            mastery = clamp(old_mastery - 2, 0, 5)

        successful_sessions = int(previous.get("successful_sessions", 0)) + (1 if score >= 3 else 0)
        is_known = mastery >= 5 and successful_sessions >= 2 and score >= 3 and confidence != "again"
        next_review = None
        status = "known" if is_known else "learning"
        if is_known:
            mastered += 1
        else:
            learning += 1
            next_review = (session_day + timedelta(days=review_days(score, confidence, mastery))).isoformat()

        words[word_id] = {
            **previous,
            "status": status,
            "mastery": mastery,
            "last_seen": session_date,
            "next_review": next_review,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
            "successful_sessions": successful_sessions,
            "last_score": score,
            "best_score": max(int(previous.get("best_score", 0)), score),
            "last_confidence": confidence,
            "known_source": "adaptive_mastery" if is_known else previous.get("known_source"),
            "last_result": {
                "recall_attempts": result["recall_attempts"],
                "recall_correct": result["recall_correct"],
                "recall_hint": result["recall_hint"],
                "context_attempts": result["context_attempts"],
                "context_correct": result["context_correct"],
                "production_complete": result["production_complete"],
            },
        }
    return mastered, learning


def main(event_path: str) -> None:
    event = read_json(Path(event_path), {})
    issue = event.get("issue", {}) if isinstance(event, dict) else {}
    issue_number = int(issue.get("number") or event.get("number") or 0)
    payload = extract_payload(str(issue.get("body") or ""))
    if payload.get("kind") != "vocabulary_feedback":
        raise ValueError("Unsupported vocabulary feedback payload")
    version = int(payload.get("version", 1))
    if version not in {1, 2}:
        raise ValueError("Unsupported vocabulary feedback version")

    session_date = str(payload.get("date") or "")
    date.fromisoformat(session_date)

    bank_words: list[dict[str, Any]] = []
    for bank_path in sorted(BANK_DIR.glob("vocabulary_core_words*.json")):
        bank = read_json(bank_path, {})
        part = bank.get("words", []) if isinstance(bank, dict) else []
        if not isinstance(part, list):
            raise ValueError(f"Invalid words array in {bank_path}")
        bank_words.extend(part)
    valid_ids = {str(w.get("id")) for w in bank_words}

    profile = read_json(
        PROFILE_PATH,
        {"version": 2, "updated_at": None, "feedback_sessions": 0, "processed_issue_numbers": [], "words": {}},
    )
    words = profile.setdefault("words", {})
    processed = profile.setdefault("processed_issue_numbers", [])
    if issue_number and issue_number in processed:
        print(f"Issue #{issue_number} was already processed; nothing to do.")
        return

    if version == 1:
        ids = set(unique_strings(payload.get("known"), "known")) | set(unique_strings(payload.get("review"), "review"))
        invalid = sorted(ids - valid_ids)
        if invalid:
            raise ValueError("Unknown word IDs: " + ", ".join(invalid))
        manually_known, learning = apply_v1(words, payload, session_date)
        adaptively_mastered = 0
    else:
        manual_known = unique_strings(payload.get("manual_known"), "manual_known")
        results = validate_results(payload.get("results"))
        result_ids = {item["id"] for item in results}
        if set(manual_known) & result_ids:
            raise ValueError("A word cannot be both manually known and actively scored")
        if not manual_known and not results:
            raise ValueError("Feedback must contain manual_known or results")
        invalid = sorted((set(manual_known) | result_ids) - valid_ids)
        if invalid:
            raise ValueError("Unknown word IDs: " + ", ".join(invalid))
        manually_known = apply_manual_known(words, manual_known, session_date)
        adaptively_mastered, learning = apply_v2(words, results, session_date)

    profile["version"] = 2
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    profile["feedback_sessions"] = int(profile.get("feedback_sessions", 0)) + 1
    if issue_number:
        processed.append(issue_number)
        profile["processed_issue_numbers"] = processed[-100:]

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Applied feedback: {manually_known} manually known, "
        f"{adaptively_mastered} adaptively mastered, {learning} scheduled for review."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_vocabulary_feedback.py <github-event.json>")
    main(sys.argv[1])
