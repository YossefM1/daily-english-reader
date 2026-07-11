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

# ── Strict BBC-only guard ─────────────────────────────────────────────────────
# The project is BBC-only. The Tampermonkey overlay supports BBC pages only, so
# non-BBC articles (Guardian, NPR, Ars Technica, Yahoo, …) MUST NEVER become
# candidates. Enforce this by URL hostname, not by feed name or trust.
#
# Published article URLs must have exactly one of these hostnames:
BBC_ARTICLE_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
# BBC feeds are served from feeds.bbci.co.uk (a BBC-owned domain); article links
# they contain resolve to the bbc.com / bbc.co.uk hosts above.
BBC_FEED_HOST_SUFFIXES = ("bbci.co.uk", "bbc.co.uk", "bbc.com")


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_bbc_article_url(url: str) -> bool:
    """True only for the strict BBC article hostname allow-list."""
    return host_of(url) in BBC_ARTICLE_HOSTS


def is_bbc_feed(feed_url: str) -> bool:
    """True if a feed lives on a BBC-owned domain (feeds.bbci.co.uk etc.)."""
    host = host_of(feed_url)
    return any(host == s or host.endswith("." + s) for s in BBC_FEED_HOST_SUFFIXES)


def resolve_feeds() -> List[str]:
    """Return the BBC-only feed list, ignoring any non-BBC ambient RSS_FEEDS.

    In BBC-only mode we NEVER honour a non-BBC feed, even if it is set in the
    RSS_FEEDS environment variable. To guarantee enough topic/length variety for
    A/B/C selection, we ALWAYS use the full DEFAULT_BBC_FEEDS set and merge in
    any *extra* BBC feeds found in RSS_FEEDS. Non-BBC feeds are dropped with a
    warning and can never narrow or replace the default BBC set.
    """
    feeds: List[str] = list(DEFAULT_BBC_FEEDS)
    for f in split_env_list(os.getenv("RSS_FEEDS", "")):
        if is_bbc_feed(f):
            if f not in feeds:
                feeds.append(f)
        else:
            print(
                f"WARNING: ignoring non-BBC feed from RSS_FEEDS (BBC-only mode): {f}",
                file=sys.stderr,
            )
    return feeds

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
        # Strict BBC-only gate: reject any candidate whose article URL is not a
        # BBC hostname, regardless of which feed it came from.
        if not is_bbc_article_url(url):
            print(
                f"WARNING: rejecting non-BBC candidate URL (BBC-only mode): "
                f"{url} (host {host_of(url)!r})",
                file=sys.stderr,
            )
            continue
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

    feeds = resolve_feeds()

    records = collect_feed_links(feeds)
    candidates = build_candidates(records)

    if not candidates:
        raise RuntimeError("No usable candidates extracted from any feed.")

    # Final defensive sweep: absolutely no non-BBC URL may survive into
    # candidates.json (the build step and the userscript both assume BBC-only).
    non_bbc = [c for c in candidates if not is_bbc_article_url(c["url"])]
    if non_bbc:
        for c in non_bbc:
            print(
                f"WARNING: dropping non-BBC candidate before save: {c['url']}",
                file=sys.stderr,
            )
        candidates = [c for c in candidates if is_bbc_article_url(c["url"])]
    if not candidates:
        raise RuntimeError("No BBC candidates available after strict BBC-only filtering.")

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
