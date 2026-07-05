\
import html
import json
import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def load_article(path: Path) -> Article:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Article(
        title=str(data.get("title", "Daily English Article")),
        url=str(data.get("url", "")),
        text=str(data.get("text", "")),
        source=str(data.get("source", "Yahoo")),
        date=str(data.get("date", "")),
    )


def load_vocabulary(path: Path) -> List[Dict[str, Any]]:
    vocab = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(vocab, dict) and "words" in vocab:
        vocab = vocab["words"]

    if not isinstance(vocab, list):
        raise RuntimeError("vocabulary.json must contain a JSON list or an object with a 'words' list.")

    cleaned: List[Dict[str, Any]] = []
    seen = set()

    for item in vocab:
        if not isinstance(item, dict):
            continue

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

    if len(cleaned) < 5:
        raise RuntimeError("vocabulary.json contains too few vocabulary items.")

    return cleaned[:45]


def make_highlight_pattern(vocab: List[Dict[str, Any]]) -> Optional[re.Pattern]:
    words = []
    for item in vocab:
        w = item["word"].strip()
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
      Generated for private English-learning use. Original source link is included above.
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
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls(context=context)
            server.login(smtp_username, smtp_password)
            server.send_message(msg)


def main() -> None:
    data_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    article_path = data_dir / "article.json"
    vocab_path = data_dir / "vocabulary.json"

    if not article_path.exists():
        raise RuntimeError(f"Missing {article_path}. Run fetch_article.py first.")

    if not vocab_path.exists():
        raise RuntimeError(f"Missing {vocab_path}. Claude Routine must create it before sending.")

    article = load_article(article_path)
    vocab = load_vocabulary(vocab_path)

    html_email = build_html_email(article, vocab)

    # Also save a local copy as an artifact in the routine run.
    out_html = data_dir / "daily_article.html"
    out_html.write_text(html_email, encoding="utf-8")

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
    print(f"Saved HTML copy to: {out_html}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in build_and_send.py: {exc}", file=sys.stderr)
        raise
