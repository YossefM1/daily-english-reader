\
import json
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup


# BBC-only test mode: the routine currently selects articles from BBC World
# News exclusively. Guardian, NPR and Ars Technica feeds are intentionally
# disabled for now (they can be re-added via RSS_FEEDS when test mode ends).
DEFAULT_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]


@dataclass
class Article:
    title: str
    url: str
    text: str
    source: str = "Unknown"
    date: str = ""
    word_count: int = 0


def split_env_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def http_get(url: str) -> requests.Response:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DailyEnglishReader/2.0; "
            "+https://github.com/YossefM1/daily-english-reader)"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response


def strip_xml_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def child_text(element: ET.Element, names: List[str]) -> str:
    for child in list(element):
        if strip_xml_ns(child.tag).lower() in names:
            return (child.text or "").strip()
    return ""


def parse_rss_links(xml_text: str) -> List[Tuple[str, str]]:
    """
    Minimal RSS/Atom parser using only Python stdlib.
    This avoids feedparser and its sgmllib3k dependency, which failed to build
    in the Claude Routine Debian environment.
    """
    root = ET.fromstring(xml_text)
    entries: List[Tuple[str, str]] = []

    for elem in root.iter():
        tag = strip_xml_ns(elem.tag).lower()

        if tag == "item":  # RSS
            title = child_text(elem, ["title"])
            link = child_text(elem, ["link"])
            if title and link:
                entries.append((title, link))

        elif tag == "entry":  # Atom
            title = child_text(elem, ["title"])
            link = ""
            for child in list(elem):
                if strip_xml_ns(child.tag).lower() == "link":
                    link = child.attrib.get("href", "").strip()
                    if link:
                        break
            if title and link:
                entries.append((title, link))

    return entries


def choose_article_url() -> str:
    explicit = os.getenv("ARTICLE_URL", "").strip()
    if explicit:
        return explicit

    feeds = split_env_list(os.getenv("RSS_FEEDS", "")) or DEFAULT_RSS_FEEDS
    entries: List[Tuple[str, str]] = []

    errors = []
    for feed_url in feeds:
        try:
            response = http_get(feed_url)
            feed_entries = parse_rss_links(response.text)
            entries.extend(feed_entries[:12])
            print(f"Feed OK: {feed_url} ({len(feed_entries)} entries)")
        except Exception as exc:
            errors.append(f"{feed_url}: {exc}")
            print(f"Feed failed: {feed_url}: {exc}", file=sys.stderr)

    if not entries:
        raise RuntimeError("No article links found. Feed errors:\n" + "\n".join(errors))

    return random.choice(entries[:20])[1]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "bbc" in host:
        return "BBC"
    if "guardian" in host:
        return "The Guardian"
    if "npr" in host:
        return "NPR"
    if "arstechnica" in host:
        return "Ars Technica"
    if "yahoo" in host:
        return "Yahoo"
    return host or "Unknown"


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
            source = data.get("sitename") or source_from_url(url)
            date = data.get("date") or ""

            if len(text.split()) >= 180:
                return Article(
                    title=title.strip(),
                    url=url,
                    text=text,
                    source=source,
                    date=date,
                )

    # Fallback extraction if trafilatura fails.
    response = http_get(url)

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

    return Article(title=title.strip(), url=url, text=text, source=source_from_url(url))


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
    article.word_count = len(article.text.split())

    out_path = output_dir / "article.json"
    out_path.write_text(
        json.dumps(asdict(article), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved article to {out_path}")
    print(f"Title: {article.title}")
    print(f"URL: {article.url}")
    print(f"Source: {article.source}")
    print(f"Words: {len(article.text.split())}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in fetch_article.py: {exc}", file=sys.stderr)
        raise
