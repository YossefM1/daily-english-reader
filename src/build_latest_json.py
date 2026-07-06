import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_WORD_FIELDS = {
    "word", "lemma", "level", "hebrew",
    "explanation_hebrew", "pronunciation_hebrew", "example",
}


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_vocabulary(words: list) -> None:
    if not isinstance(words, list):
        raise ValueError("vocabulary.json must be a JSON array")
    if len(words) < 10:
        raise ValueError(f"vocabulary.json has only {len(words)} words (need at least 10)")
    for i, w in enumerate(words):
        missing = REQUIRED_WORD_FIELDS - set(w.keys())
        if missing:
            raise ValueError(f"Word #{i} missing fields: {missing}")


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))
    data_dir = docs_dir / "data"
    archive_dir = data_dir / "archive"

    article = load_json(output_dir / "article.json")
    words = load_json(output_dir / "vocabulary.json")

    validate_vocabulary(words)

    url = article.get("url", "").strip()
    if not url:
        raise ValueError("article.json is missing 'url'")

    date = article.get("date", "") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    payload = {
        "date": date,
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "url": url,
        "word_count": article.get("word_count") or len(article.get("text", "").split()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "words": words,
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
    print(f"Words: {len(words)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in build_latest_json.py: {exc}", file=sys.stderr)
        raise
