import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Exact-count expectations for the quiz upgrade.
EXPECTED_WORD_COUNT = 25
EXPECTED_QUIZ_COUNT = 25
QUIZ_OPTION_COUNT = 4

REQUIRED_WORD_FIELDS = {
    "word", "lemma", "level", "hebrew",
    "explanation_hebrew", "pronunciation_hebrew", "example",
}

REQUIRED_QUIZ_FIELDS = {
    "id", "word", "type", "question",
    "options", "correct_answer", "explanation_hebrew",
}

# Metadata describing how this dataset was produced. Published in latest.json.
SETTINGS = {
    "source_mode": "BBC-only",
    "vocabulary_count": EXPECTED_WORD_COUNT,
    "level_mode": "B1-C1",
    "quiz_enabled": True,
}


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def normalize_vocabulary(raw):
    """Accept the current object schema {"words": [...], "quiz": [...]}.

    For backward compatibility a bare list is treated as the words array with
    an empty quiz (which then fails quiz validation with a clear message).
    """
    if isinstance(raw, list):
        return {"words": raw, "quiz": []}
    if isinstance(raw, dict):
        return {"words": raw.get("words", []), "quiz": raw.get("quiz", [])}
    raise ValueError("vocabulary.json must be a JSON object with 'words' and 'quiz'")


def validate_vocabulary(vocab: dict) -> None:
    words = vocab.get("words")
    quiz = vocab.get("quiz")

    if not isinstance(words, list):
        raise ValueError("vocabulary.json 'words' must be a JSON array")
    if not isinstance(quiz, list):
        raise ValueError("vocabulary.json 'quiz' must be a JSON array")

    if len(words) != EXPECTED_WORD_COUNT:
        raise ValueError(
            f"vocabulary.json has {len(words)} words (need exactly {EXPECTED_WORD_COUNT})"
        )
    if len(quiz) != EXPECTED_QUIZ_COUNT:
        raise ValueError(
            f"vocabulary.json has {len(quiz)} quiz questions (need exactly {EXPECTED_QUIZ_COUNT})"
        )

    word_set = set()
    for i, w in enumerate(words):
        if not isinstance(w, dict):
            raise ValueError(f"Word #{i} must be a JSON object")
        missing = REQUIRED_WORD_FIELDS - set(w.keys())
        if missing:
            raise ValueError(f"Word #{i} missing fields: {sorted(missing)}")
        word_set.add(w["word"])

    seen_ids = set()
    for i, q in enumerate(quiz):
        if not isinstance(q, dict):
            raise ValueError(f"Quiz #{i} must be a JSON object")
        missing = REQUIRED_QUIZ_FIELDS - set(q.keys())
        if missing:
            raise ValueError(f"Quiz #{i} missing fields: {sorted(missing)}")

        qid = q["id"]
        if qid in seen_ids:
            raise ValueError(f"Quiz #{i} has duplicate id: {qid!r}")
        seen_ids.add(qid)

        options = q["options"]
        if not isinstance(options, list) or len(options) != QUIZ_OPTION_COUNT:
            raise ValueError(
                f"Quiz #{i} ({qid}) must have exactly {QUIZ_OPTION_COUNT} options"
            )
        if q["correct_answer"] not in options:
            raise ValueError(
                f"Quiz #{i} ({qid}) correct_answer is not one of its options"
            )
        if q["word"] not in word_set:
            raise ValueError(
                f"Quiz #{i} ({qid}) word {q['word']!r} is not in the vocabulary words list"
            )


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))
    data_dir = docs_dir / "data"
    archive_dir = data_dir / "archive"

    article = load_json(output_dir / "article.json")
    vocab = normalize_vocabulary(load_json(output_dir / "vocabulary.json"))

    validate_vocabulary(vocab)

    url = article.get("url", "").strip()
    if not url:
        raise ValueError("article.json is missing 'url'")

    date = article.get("date", "") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Metadata only — the full article text is never included in latest.json.
    payload = {
        "date": date,
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "url": url,
        "word_count": article.get("word_count") or len(article.get("text", "").split()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": SETTINGS,
        "words": vocab["words"],
        "quiz": vocab["quiz"],
    }

    data_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    latest_path = data_dir / "latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {latest_path}")

    archive_path = archive_dir / f"{date}.json"
    archive_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {archive_path}")

    print(f"Title: {payload['title']}")
    print(f"URL:   {payload['url']}")
    print(f"Words: {len(vocab['words'])}")
    print(f"Quiz:  {len(vocab['quiz'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in build_latest_json.py: {exc}", file=sys.stderr)
        raise
