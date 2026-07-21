#!/usr/bin/env python3
"""Publish the listening library and choose an adaptive daily viewing lesson."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_SOURCE = ROOT / "config" / "listening_library.json"
LIBRARY_PUBLIC = ROOT / "docs" / "data" / "listening" / "library.json"
PROFILE_PATH = ROOT / "docs" / "data" / "listening" / "profile.json"
TODAY_PATH = ROOT / "docs" / "data" / "listening" / "today.json"
ARTICLE_TODAY_PATH = ROOT / "docs" / "data" / "today.json"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def lesson_date() -> str:
    explicit = os.environ.get("LISTENING_DATE", "").strip()
    if explicit:
        date.fromisoformat(explicit)
        return explicit
    article_today = read_json(ARTICLE_TODAY_PATH, {})
    candidate = article_today.get("date") if isinstance(article_today, dict) else None
    if candidate:
        date.fromisoformat(str(candidate))
        return str(candidate)
    return datetime.now(timezone.utc).date().isoformat()


def stable_rank(day: str, lesson_id: str) -> str:
    return hashlib.sha256(f"{day}:{lesson_id}".encode("utf-8")).hexdigest()


def main() -> None:
    library = read_json(LIBRARY_SOURCE, {})
    lessons = library.get("lessons", []) if isinstance(library, dict) else []
    if not isinstance(lessons, list) or not lessons:
        raise SystemExit("Listening library is empty")
    ids = [str(item.get("id") or "") for item in lessons]
    if not all(ids) or len(set(ids)) != len(ids):
        raise SystemExit("Listening lesson IDs must be present and unique")

    profile = read_json(
        PROFILE_PATH,
        {"version": 1, "updated_at": None, "feedback_sessions": 0, "processed_issue_numbers": [], "lessons": {}},
    )
    lesson_profile = profile.setdefault("lessons", {})
    if not isinstance(lesson_profile, dict):
        raise SystemExit("Listening profile lessons must be an object")

    day = lesson_date()
    unseen: list[dict[str, Any]] = []
    needs_review: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []

    for lesson in lessons:
        entry = lesson_profile.get(str(lesson["id"]), {})
        if not isinstance(entry, dict) or not entry:
            unseen.append(lesson)
            continue
        wrapped = {**lesson, "_profile": entry}
        if bool(entry.get("completed")) and int(entry.get("best_percent", 0)) >= 70:
            completed.append(wrapped)
        else:
            needs_review.append(wrapped)

    unseen.sort(key=lambda item: stable_rank(day, str(item["id"])))
    needs_review.sort(
        key=lambda item: (
            int(item.get("_profile", {}).get("best_percent", 0)),
            str(item.get("_profile", {}).get("last_seen") or ""),
        )
    )
    completed.sort(
        key=lambda item: (
            str(item.get("_profile", {}).get("last_seen") or ""),
            int(item.get("_profile", {}).get("best_percent", 0)),
        )
    )
    selected = (unseen or needs_review or completed)[0]

    public_library = {**library, "published_at": datetime.now(timezone.utc).isoformat()}
    public_library["lessons"] = [{k: v for k, v in lesson.items() if not k.startswith("_")} for lesson in lessons]

    completed_count = sum(
        1
        for lesson_id in ids
        if bool(lesson_profile.get(lesson_id, {}).get("completed"))
        and int(lesson_profile.get(lesson_id, {}).get("best_percent", 0)) >= 70
    )
    output = {
        "version": 1,
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lesson_id": selected["id"],
        "selection_reason": "new" if not selected.get("_profile") else "review",
        "profile_summary": {
            "library_size": len(lessons),
            "completed_count": completed_count,
            "remaining_count": max(0, len(lessons) - completed_count),
            "profile_updated_at": profile.get("updated_at"),
        },
    }

    TODAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_PUBLIC.write_text(json.dumps(public_library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TODAY_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Selected listening lesson {selected['id']} for {day}.")


if __name__ == "__main__":
    main()
