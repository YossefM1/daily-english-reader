#!/usr/bin/env python3
"""Apply owner-submitted listening feedback to the public learner profile."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_PATH = ROOT / "config" / "listening_library.json"
PROFILE_PATH = ROOT / "docs" / "data" / "listening" / "profile.json"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def extract_payload(body: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", body or "", flags=re.DOTALL | re.IGNORECASE)
    raw = match.group(1) if match else (body or "").strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Listening feedback must be an object")
    return value


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def main(event_path: str) -> None:
    event = read_json(Path(event_path), {})
    issue = event.get("issue", {}) if isinstance(event, dict) else {}
    issue_number = int(issue.get("number") or event.get("number") or 0)
    payload = extract_payload(str(issue.get("body") or ""))

    if payload.get("kind") != "listening_feedback" or int(payload.get("version", 0)) != 1:
        raise ValueError("Unsupported listening feedback payload")

    session_date = str(payload.get("date") or "")
    date.fromisoformat(session_date)
    lesson_id = str(payload.get("lesson_id") or "")
    score = clamp(int(payload.get("score", 0)), 0, 100)
    completed = bool(payload.get("completed"))
    shadowing_repetitions = clamp(int(payload.get("shadowing_repetitions", 0)), 0, 10)
    first_watch_captions = bool(payload.get("first_watch_captions"))
    second_watch_captions = bool(payload.get("second_watch_captions"))
    self_rating = clamp(int(payload.get("self_rating", 0)), 0, 5)

    library = read_json(LIBRARY_PATH, {})
    valid_ids = {str(item.get("id")) for item in library.get("lessons", [])}
    if lesson_id not in valid_ids:
        raise ValueError(f"Unknown listening lesson: {lesson_id}")

    profile = read_json(
        PROFILE_PATH,
        {"version": 1, "updated_at": None, "feedback_sessions": 0, "processed_issue_numbers": [], "lessons": {}},
    )
    processed = profile.setdefault("processed_issue_numbers", [])
    if issue_number and issue_number in processed:
        print(f"Issue #{issue_number} already processed.")
        return

    lessons = profile.setdefault("lessons", {})
    previous = lessons.get(lesson_id, {}) if isinstance(lessons.get(lesson_id), dict) else {}
    attempts = int(previous.get("attempts", 0)) + 1
    best_percent = max(int(previous.get("best_percent", 0)), score)
    successful = completed and score >= 70
    lessons[lesson_id] = {
        **previous,
        "attempts": attempts,
        "completed": bool(previous.get("completed")) or successful,
        "best_percent": best_percent,
        "last_percent": score,
        "last_seen": session_date,
        "shadowing_repetitions_total": int(previous.get("shadowing_repetitions_total", 0)) + shadowing_repetitions,
        "last_shadowing_repetitions": shadowing_repetitions,
        "last_first_watch_captions": first_watch_captions,
        "last_second_watch_captions": second_watch_captions,
        "last_self_rating": self_rating,
    }

    profile["version"] = 1
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    profile["feedback_sessions"] = int(profile.get("feedback_sessions", 0)) + 1
    if issue_number:
        processed.append(issue_number)
        profile["processed_issue_numbers"] = processed[-100:]

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Applied listening feedback for {lesson_id}: {score}%.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_listening_feedback.py <github-event.json>")
    main(sys.argv[1])
