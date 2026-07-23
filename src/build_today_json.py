#!/usr/bin/env python3
"""Build public A/B/C metadata with strict freshness and history checks.

The selected articles must come from the current data/candidates.json, have an
original RSS publication timestamp no more than 12 hours old, and must not have
appeared in an earlier archive date. Full article text is never published.
"""

import hashlib
import json
import os
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

EXPECTED_IDS = ["A", "B", "C"]
EXPECTED_WORD_COUNT = 25
EXPECTED_QUIZ_COUNT = 25
QUIZ_OPTION_COUNT = 4
MAX_ARTICLE_AGE_HOURS = float(os.getenv("MAX_ARTICLE_AGE_HOURS", "12") or "12")
BBC_ARTICLE_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
LEVEL_LABELS = {
    "A": "A — Easier English",
    "B": "B — Intermediate English",
    "C": "C — Advanced English",
}
DEFAULT_LEVEL = "B"
REQUIRED_WORD_FIELDS = {
    "word", "lemma", "level", "hebrew", "explanation_hebrew",
    "pronunciation_hebrew", "example",
}
REQUIRED_QUIZ_FIELDS = {
    "id", "word", "type", "question", "options", "correct_answer",
    "explanation_hebrew",
}
MIN_DISTINCT_POSITIONS = 4
MAX_PER_POSITION = 10


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def normalize_url(url: str) -> str:
    parsed = urlparse(str(url))
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return f"{host}{path}"


def normalize_title(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title)).strip().casefold()
    return re.sub(r"[^\w\s]", "", text)


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def assert_bbc_url(url: str, context: str) -> None:
    host = urlparse(str(url)).netloc.lower()
    if host not in BBC_ARTICLE_HOSTS:
        raise ValueError(f"Non-BBC URL in {context}: {url!r}")


def stable_seed(*parts) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def distribution_ok(positions: List[int], count: int) -> bool:
    counts = Counter(positions)
    return (
        len(counts) >= MIN_DISTINCT_POSITIONS
        and counts.get(0, 0) != count
        and (not counts or max(counts.values()) <= MAX_PER_POSITION)
    )


def shuffle_quiz_options(quiz: List[dict], date: str, article_id: str, url: str) -> List[dict]:
    positions: List[int] = []
    for question in quiz:
        options = list(question["options"])
        random.Random(stable_seed(date, article_id, question["id"], url)).shuffle(options)
        question["options"] = options
        positions.append(options.index(question["correct_answer"]))

    if distribution_ok(positions, len(quiz)):
        return quiz

    order = sorted(
        range(len(quiz)),
        key=lambda i: stable_seed(date, article_id, quiz[i]["id"], url, "repair"),
    )
    for rank, index in enumerate(order):
        question = quiz[index]
        correct = question["correct_answer"]
        distractors = [option for option in question["options"] if option != correct]
        random.Random(
            stable_seed(date, article_id, question["id"], url, "distractors")
        ).shuffle(distractors)
        target = rank % QUIZ_OPTION_COUNT
        options = distractors[:]
        options.insert(target, correct)
        question["options"] = options
    return quiz


def load_candidate_map(candidates_path: Path) -> Dict[str, dict]:
    payload = load_json(candidates_path)
    if payload.get("freshness_limit_hours") not in (None, MAX_ARTICLE_AGE_HOURS):
        print("WARNING: candidate freshness limit differs from build limit")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("data/candidates.json must contain a candidates array")

    result: Dict[str, dict] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        url = candidate.get("url")
        published_at = candidate.get("published_at")
        if not url or not published_at:
            continue
        result[normalize_url(url)] = candidate
    return result


def load_prior_history(archive_dir: Path, current_date: str) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    titles: set[str] = set()
    for path in archive_dir.glob("*.json"):
        # Today's files may be replaced during a repair run. Earlier dates remain
        # immutable history and may never be selected again.
        if path.name.startswith(current_date + "-"):
            continue
        try:
            record = load_json(path)
        except Exception as exc:
            raise ValueError(f"Could not read archive history {path}: {exc}") from exc
        url = record.get("url") or record.get("article_url")
        title = record.get("title") or record.get("article_title")
        if url:
            urls.add(normalize_url(url))
        if title:
            titles.add(normalize_title(title))
    return urls, titles


def validate_article_content(article: dict, expected_id: str) -> None:
    if article.get("id") != expected_id:
        raise ValueError(f"Article id must be {expected_id!r}")
    if article.get("level") != expected_id:
        raise ValueError(f"Article {expected_id} level must equal its id")
    for field in ("title", "url"):
        if not str(article.get(field, "")).strip():
            raise ValueError(f"Article {expected_id} missing {field}")
    assert_bbc_url(article["url"], f"article {expected_id}")

    words = article.get("words")
    quiz = article.get("quiz")
    if not isinstance(words, list) or len(words) != EXPECTED_WORD_COUNT:
        raise ValueError(f"Article {expected_id} needs exactly {EXPECTED_WORD_COUNT} words")
    if not isinstance(quiz, list) or len(quiz) != EXPECTED_QUIZ_COUNT:
        raise ValueError(f"Article {expected_id} needs exactly {EXPECTED_QUIZ_COUNT} quiz questions")

    word_set = set()
    for index, word in enumerate(words):
        if not isinstance(word, dict):
            raise ValueError(f"Article {expected_id} word #{index} must be an object")
        missing = REQUIRED_WORD_FIELDS - set(word)
        if missing:
            raise ValueError(f"Article {expected_id} word #{index} missing {sorted(missing)}")
        word_set.add(word["word"])

    seen_ids = set()
    for index, question in enumerate(quiz):
        if not isinstance(question, dict):
            raise ValueError(f"Article {expected_id} quiz #{index} must be an object")
        missing = REQUIRED_QUIZ_FIELDS - set(question)
        if missing:
            raise ValueError(f"Article {expected_id} quiz #{index} missing {sorted(missing)}")
        if question["id"] in seen_ids:
            raise ValueError(f"Duplicate quiz id {question['id']}")
        seen_ids.add(question["id"])
        options = question["options"]
        if not isinstance(options, list) or len(options) != QUIZ_OPTION_COUNT:
            raise ValueError(f"Quiz {question['id']} needs four options")
        if len(set(options)) != QUIZ_OPTION_COUNT:
            raise ValueError(f"Quiz {question['id']} has duplicate options")
        if question["correct_answer"] not in options:
            raise ValueError(f"Quiz {question['id']} correct answer is not in options")
        if question["word"] not in word_set:
            raise ValueError(f"Quiz {question['id']} word is absent from vocabulary")


def validate_selection(raw: dict, candidates: Dict[str, dict], archive_dir: Path):
    date = str(raw.get("date", "")).strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    articles = raw.get("articles")
    if not isinstance(articles, list) or len(articles) != 3:
        raise ValueError("learning_articles.json must contain exactly three articles")

    by_id = {article.get("id"): article for article in articles if isinstance(article, dict)}
    if sorted(by_id) != EXPECTED_IDS:
        raise ValueError(f"Article ids must be exactly {EXPECTED_IDS}")

    prior_urls, prior_titles = load_prior_history(archive_dir, date)
    now = datetime.now(timezone.utc)
    selected_urls: set[str] = set()
    selected_titles: set[str] = set()
    ordered = []

    for article_id in EXPECTED_IDS:
        article = by_id[article_id]
        validate_article_content(article, article_id)
        url_key = normalize_url(article["url"])
        title_key = normalize_title(article["title"])

        if url_key in prior_urls or title_key in prior_titles:
            raise ValueError(f"Article {article_id} was already published on an earlier date")
        if url_key in selected_urls or title_key in selected_titles:
            raise ValueError("A/B/C articles must be different")

        candidate = candidates.get(url_key)
        if not candidate:
            raise ValueError(
                f"Article {article_id} is absent from the current fresh candidates.json: {article['url']}"
            )
        published_at = parse_iso_datetime(candidate["published_at"])
        age_hours = (now - published_at).total_seconds() / 3600
        if age_hours < -1 or age_hours > MAX_ARTICLE_AGE_HOURS:
            raise ValueError(
                f"Article {article_id} is {age_hours:.2f} hours old; limit is "
                f"{MAX_ARTICLE_AGE_HOURS:g} hours"
            )

        # Preserve verified freshness metadata in the public metadata. The text
        # itself remains internal and is deliberately omitted.
        article["published_at"] = published_at.isoformat()
        article["age_hours_at_selection"] = round(max(age_hours, 0), 2)
        selected_urls.add(url_key)
        selected_titles.add(title_key)
        ordered.append(article)

    return date, ordered


def build_article_payload(article: dict, date: str, generated_at: str) -> dict:
    article_id = article["id"]
    return {
        "date": date,
        "id": article_id,
        "level": article_id,
        "level_label": article.get("level_label") or LEVEL_LABELS[article_id],
        "title": article["title"],
        "source": article.get("source", "BBC"),
        "url": article["url"],
        "published_at": article["published_at"],
        "age_hours_at_selection": article["age_hours_at_selection"],
        "word_count": article.get("word_count") or 0,
        "generated_at": generated_at,
        "difficulty_reason": article.get("difficulty_reason", ""),
        "settings": {
            "source_mode": "BBC-only",
            "freshness_limit_hours": MAX_ARTICLE_AGE_HOURS,
            "history_exclusion": True,
            "vocabulary_count": EXPECTED_WORD_COUNT,
            "quiz_enabled": True,
        },
        "words": article["words"],
        "quiz": shuffle_quiz_options(
            article["quiz"], date, article_id, article["url"]
        ),
    }


def build_today_index(payloads: List[dict], date: str, generated_at: str) -> dict:
    return {
        "date": date,
        "generated_at": generated_at,
        "source_mode": "BBC-only",
        "freshness_limit_hours": MAX_ARTICLE_AGE_HOURS,
        "history_exclusion": True,
        "articles": [
            {
                "id": item["id"],
                "level": item["level"],
                "level_label": item["level_label"],
                "title": item["title"],
                "source": item["source"],
                "url": item["url"],
                "published_at": item["published_at"],
                "age_hours_at_selection": item["age_hours_at_selection"],
                "word_count": item["word_count"],
                "difficulty_reason": item["difficulty_reason"],
                "data_url": f"data/articles/{date}-{item['id']}.json",
                "vocabulary_count": len(item["words"]),
                "quiz_count": len(item["quiz"]),
            }
            for item in payloads
        ],
    }


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))
    data_dir = docs_dir / "data"
    articles_dir = data_dir / "articles"
    archive_dir = data_dir / "archive"

    raw = load_json(output_dir / "learning_articles.json")
    candidates = load_candidate_map(output_dir / "candidates.json")
    date, articles = validate_selection(raw, candidates, archive_dir)
    generated_at = datetime.now(timezone.utc).isoformat()

    payloads = [build_article_payload(article, date, generated_at) for article in articles]
    today = build_today_index(payloads, date, generated_at)

    # Validation is complete before any public file is replaced.
    write_json(data_dir / "today.json", today)
    for payload in payloads:
        suffix = payload["id"]
        write_json(articles_dir / f"{date}-{suffix}.json", payload)
        write_json(archive_dir / f"{date}-{suffix}.json", payload)

    level_b = next(payload for payload in payloads if payload["id"] == DEFAULT_LEVEL)
    write_json(data_dir / "latest.json", level_b)
    print("Published three fresh, never-repeated BBC article metadata files.")


if __name__ == "__main__":
    main()
