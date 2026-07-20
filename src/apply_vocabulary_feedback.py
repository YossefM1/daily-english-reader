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


def main(event_path: str) -> None:
    event = read_json(Path(event_path), {})
    issue = event.get("issue", {}) if isinstance(event, dict) else {}
    issue_number = int(issue.get("number") or event.get("number") or 0)
    payload = extract_payload(str(issue.get("body") or ""))

    session_date = str(payload.get("date") or "")
    date.fromisoformat(session_date)
    known = unique_strings(payload.get("known"), "known")
    review = unique_strings(payload.get("review"), "review")
    if set(known) & set(review):
        raise ValueError("A word cannot be both known and review")

    bank_words: list[dict[str, Any]] = []
    for bank_path in sorted(BANK_DIR.glob("vocabulary_core_words*.json")):
        bank = read_json(bank_path, {})
        part = bank.get("words", []) if isinstance(bank, dict) else []
        if not isinstance(part, list):
            raise ValueError(f"Invalid words array in {bank_path}")
        bank_words.extend(part)
    valid_ids = {str(w.get("id")) for w in bank_words}
    invalid = sorted((set(known) | set(review)) - valid_ids)
    if invalid:
        raise ValueError("Unknown word IDs: " + ", ".join(invalid))

    profile = read_json(
        PROFILE_PATH,
        {"version": 1, "updated_at": None, "feedback_sessions": 0, "processed_issue_numbers": [], "words": {}},
    )
    words = profile.setdefault("words", {})
    processed = profile.setdefault("processed_issue_numbers", [])
    if issue_number and issue_number in processed:
        print(f"Issue #{issue_number} was already processed; nothing to do.")
        return

    for word_id in known:
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        words[word_id] = {
            **previous,
            "status": "known",
            "mastery": 3,
            "last_seen": session_date,
            "next_review": None,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
        }

    tomorrow = (date.fromisoformat(session_date) + timedelta(days=1)).isoformat()
    for word_id in review:
        previous = words.get(word_id, {}) if isinstance(words.get(word_id), dict) else {}
        words[word_id] = {
            **previous,
            "status": "learning",
            "mastery": max(0, min(2, int(previous.get("mastery", 1)) - 1)),
            "last_seen": session_date,
            "next_review": tomorrow,
            "times_seen": int(previous.get("times_seen", 0)) + 1,
        }

    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    profile["feedback_sessions"] = int(profile.get("feedback_sessions", 0)) + 1
    if issue_number:
        processed.append(issue_number)
        profile["processed_issue_numbers"] = processed[-100:]

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Applied feedback: {len(known)} known, {len(review)} review.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_vocabulary_feedback.py <github-event.json>")
    main(sys.argv[1])
