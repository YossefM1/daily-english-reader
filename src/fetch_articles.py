"""Fetch several BBC article candidates for multi-level (A/B/C) selection.

This script fetches candidate articles from several BBC RSS feeds using only the
Python standard library for XML parsing (NO feedparser — its sgmllib3k
dependency fails to build in the Claude Routine Debian environment) plus the
existing allowed dependencies (requests, trafilatura, beautifulsoup4).

It saves data/candidates.json, an internal file (gitignored, never published)
containing enough candidates for Claude to choose one easier (A), one
intermediate (B) and one advanced (C) article.

Each candidate includes: title, url, source, category (feed), text, word_count.

Full article text is stored ONLY in data/candidates.json for internal analysis
and must never be copied into the public docs/data/*.json files.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

# Reuse the battle-tested helpers from the single-article fetcher. Both files
# live in src/, which is sys.path[0] when this script is run directly.
from fetch_article import (
    extract_article,
    http_get,
    parse_rss_links,
    source_from_url,
    split_env_list,
)

# BBC-only mode: candidate feeds span several BBC sections so Claude has enough
# variety (topic and length) to pick A/B/C reading levels.
DEFAULT_BBC_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "https://feeds.bbci.co.uk/news/health/rss.xml",
    "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
]

# How many links to consider per feed, and how many successful candidates to
# collect before stopping. Tunable via environment variables.
LINKS_PER_FEED = int(os.getenv("LINKS_PER_FEED", "5") or "5")
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "18") or "18")
MIN_WORDS = int(os.getenv("MIN_CANDIDATE_WORDS", "150") or "150")
# Keep the stored text bounded so the internal file stays a sane size. This is
# generous enough to preserve full word counts for level selection.
MAX_STORED_CHARS = int(os.getenv("MAX_CANDIDATE_CHARS", "20000") or "20000")


def category_from_feed(feed_url: str) -> str:
    """Derive a human-readable category from a BBC RSS feed URL.

    e.g. .../news/science_and_environment/rss.xml -> "science and environment"
    """
    path = urlparse(feed_url).path  # /news/technology/rss.xml
    parts = [p for p in path.split("/") if p and p != "rss.xml"]
    # Drop the leading "news" segment when present.
    if parts and parts[0] == "news":
        parts = parts[1:]
    if not parts:
        return "news"
    return parts[-1].replace("_", " ")


def collect_feed_links(feeds: List[str]) -> List[Dict[str, str]]:
    """Return de-duplicated (url, title, category) records from all feeds.

    A feed that fails is logged and skipped; other feeds continue.
    """
    seen_urls = set()
    records: List[Dict[str, str]] = []
    errors: List[str] = []

    for feed_url in feeds:
        category = category_from_feed(feed_url)
        try:
            response = http_get(feed_url)
            entries = parse_rss_links(response.text)
            print(f"Feed OK: {feed_url} ({len(entries)} entries, category='{category}')")
        except Exception as exc:  # noqa: BLE001 — continue with other feeds
            errors.append(f"{feed_url}: {exc}")
            print(f"Feed failed: {feed_url}: {exc}", file=sys.stderr)
            continue

        for title, link in entries[:LINKS_PER_FEED]:
            if link in seen_urls:
                continue
            seen_urls.add(link)
            records.append({"title": title, "url": link, "category": category})

    if not records and errors:
        raise RuntimeError("No article links found. Feed errors:\n" + "\n".join(errors))

    return records


def build_candidates(records: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """Extract article text for each link, keeping only successful, long-enough ones."""
    candidates: List[Dict[str, object]] = []

    for rec in records:
        if len(candidates) >= MAX_CANDIDATES:
            break

        url = rec["url"]
        try:
            article = extract_article(url)
        except Exception as exc:  # noqa: BLE001 — skip unextractable articles
            print(f"Skip (extract failed): {url}: {exc}", file=sys.stderr)
            continue

        text = article.text or ""
        word_count = len(text.split())
        if word_count < MIN_WORDS:
            print(f"Skip (too short, {word_count} words): {url}", file=sys.stderr)
            continue

        stored_text = text[:MAX_STORED_CHARS]

        candidates.append(
            {
                "title": article.title,
                "url": url,
                "source": article.source or source_from_url(url),
                "category": rec["category"],
                "text": stored_text,
                "word_count": word_count,
            }
        )
        print(f"Candidate #{len(candidates)}: [{rec['category']}] {word_count} words — {article.title}")

    return candidates


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    output_dir.mkdir(parents=True, exist_ok=True)

    feeds = split_env_list(os.getenv("RSS_FEEDS", "")) or DEFAULT_BBC_FEEDS

    records = collect_feed_links(feeds)
    candidates = build_candidates(records)

    if not candidates:
        raise RuntimeError("No usable candidates extracted from any feed.")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": "BBC-only",
        "feeds": feeds,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    out_path = output_dir / "candidates.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSaved {len(candidates)} candidates to {out_path}")
    # A compact summary sorted by length helps Claude pick A/B/C quickly.
    for c in sorted(candidates, key=lambda c: c["word_count"]):
        print(f"  {c['word_count']:>5} words · [{c['category']}] {c['title']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR in fetch_articles.py: {exc}", file=sys.stderr)
        raise
