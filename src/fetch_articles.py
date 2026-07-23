"""Fetch fresh BBC article candidates for daily A/B/C selection.

Hard guarantees:
- BBC-only article URLs.
- RSS publication time must be present and no more than 12 hours old.
- Articles already published by this project are excluded by URL and title.
- Full article text stays only in the gitignored data/candidates.json file.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fetch_article import extract_article, http_get, source_from_url, split_env_list

DEFAULT_BBC_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "https://feeds.bbci.co.uk/news/health/rss.xml",
    "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
]

BBC_ARTICLE_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
BBC_FEED_HOST_SUFFIXES = ("bbci.co.uk", "bbc.co.uk", "bbc.com")

LINKS_PER_FEED = int(os.getenv("LINKS_PER_FEED", "20") or "20")
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "24") or "24")
MIN_WORDS = int(os.getenv("MIN_CANDIDATE_WORDS", "150") or "150")
MAX_STORED_CHARS = int(os.getenv("MAX_CANDIDATE_CHARS", "20000") or "20000")
MAX_ARTICLE_AGE_HOURS = float(os.getenv("MAX_ARTICLE_AGE_HOURS", "12") or "12")
MIN_REQUIRED_CANDIDATES = 3


def strip_xml_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if strip_xml_ns(child.tag).lower() in names:
            return (child.text or "").strip()
    return ""


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def is_bbc_article_url(url: str) -> bool:
    return host_of(url) in BBC_ARTICLE_HOSTS


def is_bbc_feed(feed_url: str) -> bool:
    host = host_of(feed_url)
    return any(host == suffix or host.endswith("." + suffix) for suffix in BBC_FEED_HOST_SUFFIXES)


def normalize_url(url: str) -> str:
    """Canonical host+path key, ignoring www, query, hash and trailing slash."""
    parsed = urlparse(str(url))
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return f"{host}{path}"


def normalize_title(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title)).strip().casefold()
    return re.sub(r"[^\w\s]", "", text)


def parse_published_at(raw: str) -> Optional[datetime]:
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed_entries(xml_text: str) -> List[Dict[str, object]]:
    """Parse RSS/Atom title, link and original publication timestamp."""
    root = ET.fromstring(xml_text)
    entries: List[Dict[str, object]] = []

    for elem in root.iter():
        tag = strip_xml_ns(elem.tag).lower()
        if tag not in {"item", "entry"}:
            continue

        title = child_text(elem, {"title"})
        link = child_text(elem, {"link"})
        if tag == "entry" and not link:
            for child in list(elem):
                if strip_xml_ns(child.tag).lower() == "link":
                    link = child.attrib.get("href", "").strip()
                    if link:
                        break

        # Prefer the original publication time. Use updated only when published is
        # absent; the strict age check still prevents old resurfaced stories.
        raw_published = child_text(elem, {"pubdate", "published", "date"})
        if not raw_published:
            raw_published = child_text(elem, {"updated"})
        published_at = parse_published_at(raw_published)

        if title and link:
            entries.append(
                {
                    "title": title,
                    "url": link,
                    "published_at": published_at,
                    "raw_published": raw_published,
                }
            )

    return entries


def resolve_feeds() -> List[str]:
    feeds = list(DEFAULT_BBC_FEEDS)
    for feed in split_env_list(os.getenv("RSS_FEEDS", "")):
        if is_bbc_feed(feed):
            if feed not in feeds:
                feeds.append(feed)
        else:
            print(f"WARNING: ignoring non-BBC feed: {feed}", file=sys.stderr)
    return feeds


def category_from_feed(feed_url: str) -> str:
    parts = [p for p in urlparse(feed_url).path.split("/") if p and p != "rss.xml"]
    if parts and parts[0] == "news":
        parts = parts[1:]
    return (parts[-1] if parts else "news").replace("_", " ")


def load_published_history(docs_dir: Path) -> tuple[set[str], set[str]]:
    """Load every previously published article URL/title from public metadata."""
    urls: set[str] = set()
    titles: set[str] = set()
    paths = list((docs_dir / "data" / "archive").glob("*.json"))
    today_path = docs_dir / "data" / "today.json"
    if today_path.exists():
        paths.append(today_path)

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: could not read history file {path}: {exc}", file=sys.stderr)
            continue

        records = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            records = [payload]

        for record in records:
            if not isinstance(record, dict):
                continue
            url = record.get("url") or record.get("article_url")
            title = record.get("title") or record.get("article_title")
            if url:
                urls.add(normalize_url(str(url)))
            if title:
                titles.add(normalize_title(str(title)))

    return urls, titles


def collect_feed_links(
    feeds: List[str], history_urls: set[str], history_titles: set[str]
) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    records: List[Dict[str, object]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    errors: List[str] = []

    freshness_rejections = 0
    missing_date_rejections = 0
    history_rejections = 0

    for feed_url in feeds:
        category = category_from_feed(feed_url)
        try:
            response = http_get(feed_url)
            entries = parse_feed_entries(response.text)
            print(f"Feed OK: {feed_url} ({len(entries)} entries, category={category!r})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{feed_url}: {exc}")
            print(f"Feed failed: {feed_url}: {exc}", file=sys.stderr)
            continue

        for entry in entries[:LINKS_PER_FEED]:
            url = str(entry["url"])
            title = str(entry["title"])
            published_at = entry.get("published_at")

            if not is_bbc_article_url(url):
                continue
            if not isinstance(published_at, datetime):
                missing_date_rejections += 1
                continue

            age_hours = (now - published_at).total_seconds() / 3600
            if age_hours < -1 or age_hours > MAX_ARTICLE_AGE_HOURS:
                freshness_rejections += 1
                continue

            url_key = normalize_url(url)
            title_key = normalize_title(title)
            if url_key in history_urls or title_key in history_titles:
                history_rejections += 1
                continue
            if url_key in seen_urls or title_key in seen_titles:
                continue

            seen_urls.add(url_key)
            seen_titles.add(title_key)
            records.append(
                {
                    "title": title,
                    "url": url,
                    "category": category,
                    "published_at": published_at.isoformat(),
                    "age_hours": round(max(age_hours, 0), 2),
                }
            )

    records.sort(key=lambda item: str(item["published_at"]), reverse=True)
    print(
        "Candidate-link filters: "
        f"freshness={freshness_rejections}, missing_date={missing_date_rejections}, "
        f"already_published={history_rejections}, accepted={len(records)}"
    )

    if not records and errors:
        raise RuntimeError("No fresh article links found. Feed errors:\n" + "\n".join(errors))
    return records


def build_candidates(
    records: List[Dict[str, object]], history_urls: set[str], history_titles: set[str]
) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    candidate_urls: set[str] = set()
    candidate_titles: set[str] = set()

    for record in records:
        if len(candidates) >= MAX_CANDIDATES:
            break

        url = str(record["url"])
        try:
            article = extract_article(url)
        except Exception as exc:  # noqa: BLE001
            print(f"Skip (extract failed): {url}: {exc}", file=sys.stderr)
            continue

        text = article.text or ""
        word_count = len(text.split())
        if word_count < MIN_WORDS:
            print(f"Skip (too short, {word_count} words): {url}", file=sys.stderr)
            continue

        url_key = normalize_url(url)
        title_key = normalize_title(article.title or str(record["title"]))
        if url_key in history_urls or title_key in history_titles:
            print(f"Skip (already published after extraction): {article.title}", file=sys.stderr)
            continue
        if url_key in candidate_urls or title_key in candidate_titles:
            continue

        candidate_urls.add(url_key)
        candidate_titles.add(title_key)
        candidates.append(
            {
                "title": article.title,
                "url": url,
                "source": article.source or source_from_url(url),
                "category": record["category"],
                "published_at": record["published_at"],
                "age_hours": record["age_hours"],
                "text": text[:MAX_STORED_CHARS],
                "word_count": word_count,
            }
        )
        print(
            f"Candidate #{len(candidates)}: {record['age_hours']}h old · "
            f"[{record['category']}] {word_count} words — {article.title}"
        )

    return candidates


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    history_urls, history_titles = load_published_history(docs_dir)
    print(f"Loaded publication history: {len(history_urls)} URLs, {len(history_titles)} titles")

    feeds = resolve_feeds()
    records = collect_feed_links(feeds, history_urls, history_titles)
    candidates = build_candidates(records, history_urls, history_titles)

    if len(candidates) < MIN_REQUIRED_CANDIDATES:
        raise RuntimeError(
            f"Only {len(candidates)} usable BBC candidates were found that are both "
            f"new to this project and no more than {MAX_ARTICLE_AGE_HOURS:g} hours old. "
            "Refusing to reuse an old article. Increase LINKS_PER_FEED/add BBC feeds "
            "or run again later."
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": "BBC-only",
        "freshness_limit_hours": MAX_ARTICLE_AGE_HOURS,
        "history_exclusion": True,
        "feeds": feeds,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    out_path = output_dir / "candidates.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(candidates)} fresh, never-used candidates to {out_path}")
    for candidate in sorted(candidates, key=lambda item: item["word_count"]):
        print(
            f"  {candidate['word_count']:>5} words · {candidate['age_hours']:>5}h · "
            f"[{candidate['category']}] {candidate['title']}"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR in fetch_articles.py: {exc}", file=sys.stderr)
        raise
