\
import json
import os
import random
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Tuple

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup


DEFAULT_RSS_FEEDS = [
    "https://news.yahoo.com/rss",
    "https://www.yahoo.com/news/rss/finance",
]


@dataclass
class Article:
    title: str
    url: str
    text: str
    source: str = "Yahoo"
    date: str = ""


def split_env_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def choose_article_url() -> str:
    explicit = os.getenv("ARTICLE_URL", "").strip()
    if explicit:
        return explicit

    feeds = split_env_list(os.getenv("RSS_FEEDS", "")) or DEFAULT_RSS_FEEDS
    entries: List[Tuple[str, str]] = []

    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:15]:
            link = getattr(entry, "link", "")
            title = getattr(entry, "title", "")
            if link and title:
                entries.append((title, link))

    if not entries:
        raise RuntimeError("No article links found. Set ARTICLE_URL or RSS_FEEDS.")

    return random.choice(entries[:10])[1]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_article(url: str) -> Article:
    downloaded = trafilatura.fetch_url(url)

    if downloaded:
        extracted_json = trafilatura.extract(
            downloaded,
            output_format="json",
            include_comments=False,
            include_tables=False,
            with_metadata=True,
        )
        if extracted_json:
            data = json.loads(extracted_json)
            title = data.get("title") or "Daily English Article"
            text = normalize_text(data.get("text") or "")
            source = data.get("sitename") or "Yahoo"
            date = data.get("date") or ""

            if len(text.split()) >= 250:
                return Article(
                    title=title.strip(),
                    url=url,
                    text=text,
                    source=source,
                    date=date,
                )

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DailyEnglishReader/1.0; personal educational use)"
    }
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Daily English Article"
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = normalize_text("\n\n".join(p for p in paragraphs if len(p.split()) > 8))

    if len(text.split()) < 150:
        raise RuntimeError(
            "Could not extract enough article text. Try another ARTICLE_URL or RSS_FEEDS source."
        )

    return Article(title=title.strip(), url=url, text=text, source="Yahoo")


def trim_article(text: str) -> str:
    max_chars = int(os.getenv("MAX_ARTICLE_CHARS", "12000") or "12000")
    if len(text) <= max_chars:
        return text

    trimmed = text[:max_chars]
    last_period = trimmed.rfind(".")
    if last_period > 1000:
        trimmed = trimmed[: last_period + 1]
    return trimmed + "\n\n[Article shortened for routine size.]"


def main() -> None:
    output_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    output_dir.mkdir(parents=True, exist_ok=True)

    url = choose_article_url()
    article = extract_article(url)
    article.text = trim_article(article.text)

    out_path = output_dir / "article.json"
    out_path.write_text(
        json.dumps(asdict(article), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved article to {out_path}")
    print(f"Title: {article.title}")
    print(f"URL: {article.url}")
    print(f"Words: {len(article.text.split())}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in fetch_article.py: {exc}", file=sys.stderr)
        raise
