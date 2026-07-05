\
import os
import re
import json
import html
import random
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from typing import List, Dict, Any, Optional

import requests
import feedparser
import trafilatura
from bs4 import BeautifulSoup
from anthropic import Anthropic


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


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def split_env_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def choose_article_url() -> str:
    explicit = os.getenv("ARTICLE_URL", "").strip()
    if explicit:
        return explicit

    feeds = split_env_list(os.getenv("RSS_FEEDS", "")) or DEFAULT_RSS_FEEDS

    entries = []
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:12]:
            link = getattr(entry, "link", "")
            title = getattr(entry, "title", "")
            if link and title:
                entries.append((title, link))

    if not entries:
        raise RuntimeError("No article links found. Set ARTICLE_URL or RSS_FEEDS.")

    # Random among recent items keeps the morning article varied.
    return random.choice(entries[:10])[1]


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
            text = data.get("text") or ""
            source = data.get("sitename") or "Yahoo"
            date = data.get("date") or ""
            if len(text.split()) >= 250:
                return Article(title=title.strip(), url=url, text=text.strip(), source=source, date=date)

    # Fallback extraction if trafilatura fails.
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DailyEnglishReader/1.0; personal educational use)"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Daily English Article"
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n\n".join(p for p in paragraphs if len(p.split()) > 8)

    if len(text.split()) < 150:
        raise RuntimeError(
            "Could not extract enough article text. Try another ARTICLE_URL or RSS_FEEDS source."
        )

    return Article(title=title.strip(), url=url, text=text.strip(), source="Yahoo")


def trim_article(text: str) -> str:
    max_chars = int(os.getenv("MAX_ARTICLE_CHARS", "12000") or "12000")
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars]
    last_period = trimmed.rfind(".")
    if last_period > 1000:
        trimmed = trimmed[: last_period + 1]
    return trimmed + "\n\n[Article shortened for email/API size.]"


def extract_json_array(raw: str) -> List[Dict[str, Any]]:
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", raw)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if isinstance(parsed, dict) and "words" in parsed:
        parsed = parsed["words"]

    if not isinstance(parsed, list):
        raise ValueError("Claude output was not a JSON list.")

    return parsed


def analyze_vocabulary(article_text: str) -> List[Dict[str, Any]]:
    api_key = env_required("ANTHROPIC_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "").strip() or "claude-sonnet-5"

    client = Anthropic(api_key=api_key)

    prompt = f"""
You are helping a Hebrew speaker improve English reading.

Given the English article below, identify useful vocabulary words for learning.
Select only intermediate and advanced words, approximately B1, B2, C1, and C2.
Do not select:
- very basic words
- names of people, places, companies, products, or organizations
- dates, numbers, abbreviations
- words that appear only once but are not useful for general English

Prefer 18-35 useful words.

For each selected word, return:
- word: the exact word as it appears in the article
- lemma: the base form
- level: one of B1, B2, C1, C2
- hebrew: Hebrew translation
- explanation_hebrew: short Hebrew explanation
- pronunciation_hebrew: approximate pronunciation in Hebrew letters with niqqud where possible
- example: one short English example sentence

Return only a valid JSON array. No markdown. No comments.

Article:
<<<
{article_text}
>>>
""".strip()

    response = client.messages.create(
        model=model,
        max_tokens=5000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    vocab = extract_json_array(raw)

    cleaned = []
    seen = set()
    for item in vocab:
        word = str(item.get("word", "")).strip()
        if not word:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({
            "word": word,
            "lemma": str(item.get("lemma", "")).strip(),
            "level": str(item.get("level", "")).strip(),
            "hebrew": str(item.get("hebrew", "")).strip(),
            "explanation_hebrew": str(item.get("explanation_hebrew", "")).strip(),
            "pronunciation_hebrew": str(item.get("pronunciation_hebrew", "")).strip(),
            "example": str(item.get("example", "")).strip(),
        })

    return cleaned[:40]


def make_highlight_pattern(vocab: List[Dict[str, Any]]) -> Optional[re.Pattern]:
    words = []
    for item in vocab:
        w = item["word"].strip()
        # Keep only normal word-ish terms for stable highlighting.
        if re.match(r"^[A-Za-z][A-Za-z'’-]{2,}$", w):
            words.append(re.escape(w))
    words = sorted(set(words), key=len, reverse=True)
    if not words:
        return None
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE)


def highlight_text(text: str, vocab: List[Dict[str, Any]]) -> str:
    pattern = make_highlight_pattern(vocab)
    if not pattern:
        return html.escape(text)

    vocab_map = {item["word"].lower(): item for item in vocab}

    def highlight_paragraph(paragraph: str) -> str:
        result = []
        pos = 0
        for match in pattern.finditer(paragraph):
            result.append(html.escape(paragraph[pos:match.start()]))
            word = match.group(0)
            item = vocab_map.get(word.lower())
            level = html.escape(item.get("level", "")) if item else ""
            result.append(
                f'<span class="vocab-highlight" title="{level}">{html.escape(word)}</span>'
            )
            pos = match.end()
        result.append(html.escape(paragraph[pos:]))
        return "".join(result)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n".join(f"<p>{highlight_paragraph(p)}</p>" for p in paragraphs)


def build_vocab_sidebar(vocab: List[Dict[str, Any]]) -> str:
    cards = []
    for item in vocab:
        cards.append(f"""
        <div class="word-card">
          <div class="word-row">
            <span class="word">{html.escape(item.get("word", ""))}</span>
            <span class="level">{html.escape(item.get("level", ""))}</span>
          </div>
          <div class="hebrew">{html.escape(item.get("hebrew", ""))}</div>
          <div class="pronunciation">{html.escape(item.get("pronunciation_hebrew", ""))}</div>
          <div class="explanation">{html.escape(item.get("explanation_hebrew", ""))}</div>
          <div class="example">{html.escape(item.get("example", ""))}</div>
        </div>
        """)
    return "\n".join(cards)


def build_html_email(article: Article, vocab: List[Dict[str, Any]]) -> str:
    article_html = highlight_text(article.text, vocab)
    vocab_html = build_vocab_sidebar(vocab)

    return f"""\
<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(article.title)}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background: #f5f5f2;
      color: #222;
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.7;
    }}
    .container {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px;
    }}
    .header {{
      background: #ffffff;
      border-radius: 18px;
      padding: 26px 30px;
      margin-bottom: 18px;
      border: 1px solid #e6e2d9;
    }}
    h1 {{
      margin: 0 0 12px 0;
      font-size: 30px;
      line-height: 1.25;
    }}
    .meta {{
      color: #666;
      font-size: 14px;
      font-family: Arial, sans-serif;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 2.2fr) minmax(280px, 0.9fr);
      gap: 18px;
      align-items: start;
    }}
    .article {{
      background: #ffffff;
      border-radius: 18px;
      padding: 30px;
      border: 1px solid #e6e2d9;
      font-size: 19px;
    }}
    .article p {{
      margin: 0 0 1.1em 0;
    }}
    .vocab-highlight {{
      background: #e1e1dd;
      border-radius: 5px;
      padding: 0 4px;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .sidebar {{
      background: #ffffff;
      border-radius: 18px;
      padding: 22px;
      border: 1px solid #e6e2d9;
      font-family: Arial, sans-serif;
      direction: rtl;
    }}
    .sidebar h2 {{
      margin: 0 0 16px 0;
      font-size: 20px;
    }}
    .word-card {{
      border-top: 1px solid #eee;
      padding: 14px 0;
    }}
    .word-card:first-of-type {{
      border-top: 0;
    }}
    .word-row {{
      direction: ltr;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }}
    .word {{
      font-weight: 700;
      font-size: 18px;
      color: #222;
    }}
    .level {{
      font-size: 12px;
      background: #eee;
      border-radius: 999px;
      padding: 2px 8px;
      color: #444;
    }}
    .hebrew {{
      font-weight: 700;
      margin-top: 6px;
    }}
    .pronunciation {{
      color: #555;
      font-size: 15px;
      margin-top: 4px;
    }}
    .explanation {{
      color: #333;
      font-size: 14px;
      margin-top: 6px;
    }}
    .example {{
      direction: ltr;
      color: #666;
      font-size: 13px;
      margin-top: 8px;
      font-style: italic;
    }}
    .footer {{
      color: #777;
      font-size: 12px;
      font-family: Arial, sans-serif;
      margin-top: 16px;
      text-align: center;
    }}
    a {{
      color: #444;
    }}
    @media (max-width: 850px) {{
      .layout {{
        display: block;
      }}
      .sidebar {{
        margin-top: 18px;
      }}
      .article {{
        font-size: 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>{html.escape(article.title)}</h1>
      <div class="meta">
        Source: {html.escape(article.source)}
        {" | Date: " + html.escape(article.date) if article.date else ""}
        | <a href="{html.escape(article.url)}">Original article</a>
      </div>
    </div>

    <div class="layout">
      <main class="article">
        {article_html}
      </main>

      <aside class="sidebar">
        <h2>מילון לכתבה</h2>
        {vocab_html}
      </aside>
    </div>

    <div class="footer">
      Generated for private English-learning use. Please keep the original source link.
    </div>
  </div>
</body>
</html>
"""


def send_email(subject: str, html_body: str, text_body: str) -> None:
    email_from = env_required("EMAIL_FROM")
    email_to = env_required("EMAIL_TO")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_username = os.getenv("SMTP_USERNAME", email_from).strip()
    smtp_password = env_required("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_username, smtp_password)
            server.send_message(msg)


def main() -> None:
    url = choose_article_url()
    article = extract_article(url)
    article.text = trim_article(article.text)

    vocab = analyze_vocabulary(article.text)

    html_email = build_html_email(article, vocab)
    text_email = (
        f"{article.title}\n\n"
        f"Original article: {article.url}\n\n"
        f"Vocabulary words:\n"
        + "\n".join([f"- {x['word']} = {x['hebrew']} ({x['pronunciation_hebrew']})" for x in vocab])
    )

    subject = f"Daily English Article: {article.title[:70]}"
    send_email(subject, html_email, text_email)

    print(f"Sent article: {article.title}")
    print(f"URL: {article.url}")
    print(f"Vocabulary words: {len(vocab)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
