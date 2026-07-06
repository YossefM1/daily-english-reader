"""Build the public multi-level metadata files from data/learning_articles.json.

Reads the internal file data/learning_articles.json (created by Claude during the
routine, gitignored, contains no separate article text) and writes the public
GitHub Pages metadata:

  docs/data/today.json                      (index of the 3 daily articles)
  docs/data/articles/YYYY-MM-DD-A.json      (full metadata for level A)
  docs/data/articles/YYYY-MM-DD-B.json      (full metadata for level B)
  docs/data/articles/YYYY-MM-DD-C.json      (full metadata for level C)
  docs/data/latest.json                     (backward-compat copy of level B)
  docs/data/archive/YYYY-MM-DD-A.json        (archive copies)
  docs/data/archive/YYYY-MM-DD-B.json
  docs/data/archive/YYYY-MM-DD-C.json

None of these public files contain the full article text.

Validation is strict: exactly 3 articles with ids A/B/C, exactly 15 words and
15 quiz questions per article, 4 options per quiz, correct_answer among the
options, and every quiz word present in that article's words list.

Quiz options are shuffled DETERMINISTICALLY (seeded by date + article id +
quiz id + article url) so the correct answer is not always the first option,
and the distribution of correct-answer positions across each article's 15
questions is enforced. This is idempotent: the same input always yields the
same output.
"""

import hashlib
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

EXPECTED_ARTICLE_COUNT = 3
EXPECTED_IDS = ["A", "B", "C"]
EXPECTED_WORD_COUNT = 15
EXPECTED_QUIZ_COUNT = 15
QUIZ_OPTION_COUNT = 4

LEVEL_LABELS = {
    "A": "A — Easier English",
    "B": "B — Intermediate English",
    "C": "C — Advanced English",
}

REQUIRED_WORD_FIELDS = {
    "word", "lemma", "level", "hebrew",
    "explanation_hebrew", "pronunciation_hebrew", "example",
}

REQUIRED_QUIZ_FIELDS = {
    "id", "word", "type", "question",
    "options", "correct_answer", "explanation_hebrew",
}

# Distribution rules for correct-answer positions within one article's quiz.
MIN_DISTINCT_POSITIONS = 3
MAX_PER_POSITION = 7

# The default recommended level; latest.json mirrors this one for compatibility.
DEFAULT_LEVEL = "B"


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ── Deterministic shuffling ──────────────────────────────────────────────────

def stable_seed(*parts) -> int:
    """A stable integer seed derived from the given parts (no wall-clock/random)."""
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def distribution_ok(positions: List[int], count: int) -> bool:
    """True if correct-answer positions meet the distribution rules."""
    counts = Counter(positions)
    if len(counts) < MIN_DISTINCT_POSITIONS:
        return False
    if counts.get(0, 0) == count:  # all correct answers in the first slot
        return False
    if counts and max(counts.values()) > MAX_PER_POSITION:
        return False
    return True


def shuffle_quiz_options(quiz: List[dict], date: str, article_id: str, url: str) -> List[dict]:
    """Deterministically shuffle each quiz question's options.

    First pass: shuffle every question independently with a per-question seed.
    If the resulting correct-answer positions violate the distribution rules,
    a deterministic repair pass assigns balanced target positions.
    """
    # ── First pass: independent per-question deterministic shuffle. ──
    positions: List[int] = []
    for q in quiz:
        seed = stable_seed(date, article_id, q["id"], url)
        opts = list(q["options"])
        random.Random(seed).shuffle(opts)
        q["options"] = opts
        positions.append(opts.index(q["correct_answer"]))

    if distribution_ok(positions, len(quiz)):
        return quiz

    # ── Repair pass: balanced round-robin target positions. ──
    # Order the questions by a deterministic repair seed so the balanced
    # assignment is not a trivially predictable A,B,C,D,A,... pattern, then
    # place each correct answer at its assigned slot with distractors ordered
    # deterministically around it.
    order = sorted(
        range(len(quiz)),
        key=lambda i: stable_seed(date, article_id, quiz[i]["id"], url, "repair"),
    )
    for rank, i in enumerate(order):
        q = quiz[i]
        target = rank % QUIZ_OPTION_COUNT
        correct = q["correct_answer"]
        distractors = [o for o in q["options"] if o != correct]
        random.Random(
            stable_seed(date, article_id, q["id"], url, "distractors")
        ).shuffle(distractors)
        new_opts = distractors[:]
        new_opts.insert(min(target, len(new_opts)), correct)
        q["options"] = new_opts

    return quiz


# ── Validation ───────────────────────────────────────────────────────────────

def validate_article(article: dict, expected_id: str) -> None:
    aid = article.get("id")
    if aid != expected_id:
        raise ValueError(f"Article #{expected_id} has id {aid!r} (expected {expected_id!r})")

    for field in ("title", "url", "level"):
        if not str(article.get(field, "")).strip():
            raise ValueError(f"Article {expected_id} missing required field: {field!r}")

    words = article.get("words")
    quiz = article.get("quiz")
    if not isinstance(words, list):
        raise ValueError(f"Article {expected_id} 'words' must be a JSON array")
    if not isinstance(quiz, list):
        raise ValueError(f"Article {expected_id} 'quiz' must be a JSON array")

    if len(words) != EXPECTED_WORD_COUNT:
        raise ValueError(
            f"Article {expected_id} has {len(words)} words (need exactly {EXPECTED_WORD_COUNT})"
        )
    if len(quiz) != EXPECTED_QUIZ_COUNT:
        raise ValueError(
            f"Article {expected_id} has {len(quiz)} quiz questions "
            f"(need exactly {EXPECTED_QUIZ_COUNT})"
        )

    word_set = set()
    for i, w in enumerate(words):
        if not isinstance(w, dict):
            raise ValueError(f"Article {expected_id} word #{i} must be a JSON object")
        missing = REQUIRED_WORD_FIELDS - set(w.keys())
        if missing:
            raise ValueError(f"Article {expected_id} word #{i} missing fields: {sorted(missing)}")
        word_set.add(w["word"])

    seen_ids = set()
    for i, q in enumerate(quiz):
        if not isinstance(q, dict):
            raise ValueError(f"Article {expected_id} quiz #{i} must be a JSON object")
        missing = REQUIRED_QUIZ_FIELDS - set(q.keys())
        if missing:
            raise ValueError(f"Article {expected_id} quiz #{i} missing fields: {sorted(missing)}")

        qid = q["id"]
        if qid in seen_ids:
            raise ValueError(f"Article {expected_id} quiz #{i} has duplicate id: {qid!r}")
        seen_ids.add(qid)

        options = q["options"]
        if not isinstance(options, list) or len(options) != QUIZ_OPTION_COUNT:
            raise ValueError(
                f"Article {expected_id} quiz {qid} must have exactly {QUIZ_OPTION_COUNT} options"
            )
        if len(set(options)) != QUIZ_OPTION_COUNT:
            raise ValueError(f"Article {expected_id} quiz {qid} has duplicate options")
        if q["correct_answer"] not in options:
            raise ValueError(
                f"Article {expected_id} quiz {qid} correct_answer is not one of its options"
            )
        if q["word"] not in word_set:
            raise ValueError(
                f"Article {expected_id} quiz {qid} word {q['word']!r} is not in that "
                f"article's words list"
            )


def validate_and_index(raw: dict) -> List[dict]:
    articles = raw.get("articles")
    if not isinstance(articles, list):
        raise ValueError("learning_articles.json must have an 'articles' array")
    if len(articles) != EXPECTED_ARTICLE_COUNT:
        raise ValueError(
            f"learning_articles.json has {len(articles)} articles "
            f"(need exactly {EXPECTED_ARTICLE_COUNT}: A, B, C)"
        )

    by_id: Dict[str, dict] = {}
    for a in articles:
        if not isinstance(a, dict):
            raise ValueError("Each article must be a JSON object")
        by_id[a.get("id")] = a

    if sorted(by_id.keys()) != EXPECTED_IDS:
        raise ValueError(f"Article ids must be exactly {EXPECTED_IDS}, got {sorted(by_id.keys())}")

    ordered = []
    for expected_id in EXPECTED_IDS:
        article = by_id[expected_id]
        validate_article(article, expected_id)
        ordered.append(article)
    return ordered


# ── Payload construction ──────────────────────────────────────────────────────

def build_article_payload(article: dict, date: str, generated_at: str) -> dict:
    """Full per-article public metadata (no article text)."""
    aid = article["id"]
    return {
        "date": date,
        "id": aid,
        "level": article.get("level", aid),
        "level_label": article.get("level_label") or LEVEL_LABELS.get(aid, aid),
        "title": article.get("title", ""),
        "source": article.get("source", "BBC"),
        "url": article["url"],
        "word_count": article.get("word_count") or 0,
        "generated_at": generated_at,
        "difficulty_reason": article.get("difficulty_reason", ""),
        "settings": {
            "source_mode": "BBC-only",
            "vocabulary_count": EXPECTED_WORD_COUNT,
            "quiz_enabled": True,
        },
        "words": article["words"],
        "quiz": article["quiz"],
    }


def build_today_index(articles: List[dict], date: str, generated_at: str) -> dict:
    entries = []
    for a in articles:
        aid = a["id"]
        entries.append(
            {
                "id": aid,
                "level": a.get("level", aid),
                "level_label": a.get("level_label") or LEVEL_LABELS.get(aid, aid),
                "title": a.get("title", ""),
                "source": a.get("source", "BBC"),
                "url": a["url"],
                "word_count": a.get("word_count") or 0,
                "difficulty_reason": a.get("difficulty_reason", ""),
                "data_url": f"data/articles/{date}-{aid}.json",
                "vocabulary_count": len(a["words"]),
                "quiz_count": len(a["quiz"]),
            }
        )
    return {
        "date": date,
        "generated_at": generated_at,
        "source_mode": "BBC-only",
        "articles": entries,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))
    data_dir = docs_dir / "data"
    articles_dir = data_dir / "articles"
    archive_dir = data_dir / "archive"

    raw = load_json(output_dir / "learning_articles.json")
    articles = validate_and_index(raw)

    date = str(raw.get("date", "")).strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_at = datetime.now(timezone.utc).isoformat()

    # Deterministically shuffle each article's quiz options and enforce the
    # correct-answer position distribution BEFORE writing anything.
    for a in articles:
        a["quiz"] = shuffle_quiz_options(a["quiz"], date, a["id"], a["url"])
        positions = [q["options"].index(q["correct_answer"]) for q in a["quiz"]]
        counts = Counter(positions)
        print(
            f"Article {a['id']} correct-answer positions "
            f"{{A:{counts.get(0,0)}, B:{counts.get(1,0)}, C:{counts.get(2,0)}, D:{counts.get(3,0)}}}"
        )
        if not distribution_ok(positions, len(a["quiz"])):
            raise RuntimeError(
                f"Article {a['id']} quiz distribution still invalid after shuffle: {counts}"
            )

    # Build and write per-article public + archive files.
    article_payloads = {}
    for a in articles:
        payload = build_article_payload(a, date, generated_at)
        article_payloads[a["id"]] = payload
        write_json(articles_dir / f"{date}-{a['id']}.json", payload)
        write_json(archive_dir / f"{date}-{a['id']}.json", payload)

    # today.json index.
    today = build_today_index(articles, date, generated_at)
    write_json(data_dir / "today.json", today)

    # latest.json backward-compatibility copy of the default (B) level.
    default_payload = article_payloads.get(DEFAULT_LEVEL) or next(iter(article_payloads.values()))
    latest = dict(default_payload)
    # Match the historical latest.json settings shape (keeps old clients happy).
    latest["settings"] = {
        "source_mode": "BBC-only",
        "vocabulary_count": EXPECTED_WORD_COUNT,
        "level_mode": "B1-C1",
        "quiz_enabled": True,
    }
    write_json(data_dir / "latest.json", latest)

    print("\nSummary:")
    for a in articles:
        print(
            f"  {a['id']} [{a.get('level_label', '')}] — {a.get('word_count', 0)} words — "
            f"{a.get('title', '')}"
        )
    print(f"  latest.json mirrors level {DEFAULT_LEVEL}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR in build_today_json.py: {exc}", file=sys.stderr)
        raise
