\
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Article:
    title: str
    url: str
    text: str
    source: str = "Unknown"
    date: str = ""


def load_article(path: Path) -> Article:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Article(
        title=str(data.get("title", "Daily English Article")),
        url=str(data.get("url", "")),
        text=str(data.get("text", "")),
        source=str(data.get("source", "Unknown")),
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


def build_html_page(article: Article, vocab: List[Dict[str, Any]]) -> str:
    article_html = highlight_text(article.text, vocab)
    vocab_html = build_vocab_sidebar(vocab)

    return f"""\
<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(article.title)}</title>
  <style>
    :root {{
      --bg: #f5f5f2;
      --paper: #ffffff;
      --line: #e6e2d9;
      --text: #222;
      --muted: #666;
      --highlight: #e1e1dd;
    }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.7;
    }}
    .container {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .header {{
      background: var(--paper);
      border-radius: 18px;
      padding: 26px 30px;
      margin-bottom: 18px;
      border: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 12px 0;
      font-size: 31px;
      line-height: 1.25;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      font-family: Arial, sans-serif;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 2.2fr) minmax(300px, 0.9fr);
      gap: 18px;
      align-items: start;
    }}
    .article {{
      background: var(--paper);
      border-radius: 18px;
      padding: 34px;
      border: 1px solid var(--line);
      font-size: 20px;
    }}
    .article p {{
      margin: 0 0 1.15em 0;
    }}
    .vocab-highlight {{
      background: var(--highlight);
      border-radius: 5px;
      padding: 0 4px;
      box-decoration-break: clone;
      -webkit-box-decoration-break: clone;
    }}
    .sidebar {{
      background: var(--paper);
      border-radius: 18px;
      padding: 22px;
      border: 1px solid var(--line);
      font-family: Arial, sans-serif;
      direction: rtl;
      position: sticky;
      top: 18px;
      max-height: calc(100vh - 36px);
      overflow: auto;
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
    @media (max-width: 900px) {{
      .layout {{
        display: block;
      }}
      .sidebar {{
        position: static;
        max-height: none;
        margin-top: 18px;
      }}
      .article {{
        font-size: 18px;
        padding: 24px;
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


def main() -> None:
    data_dir = Path(os.getenv("OUTPUT_DIR", "data"))
    docs_dir = Path(os.getenv("DOCS_DIR", "docs"))

    article_path = data_dir / "article.json"
    vocab_path = data_dir / "vocabulary.json"

    if not article_path.exists():
        raise RuntimeError(f"Missing {article_path}. Run fetch_article.py first.")

    if not vocab_path.exists():
        raise RuntimeError(f"Missing {vocab_path}. Claude Routine must create it before building HTML.")

    article = load_article(article_path)
    vocab = load_vocabulary(vocab_path)

    html_page = build_html_page(article, vocab)

    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    docs_index = docs_dir / "index.html"
    local_copy = data_dir / "daily_article.html"

    docs_index.write_text(html_page, encoding="utf-8")
    local_copy.write_text(html_page, encoding="utf-8")

    print(f"Built HTML page: {docs_index}")
    print(f"Saved local copy: {local_copy}")
    print(f"Title: {article.title}")
    print(f"URL: {article.url}")
    print(f"Vocabulary words: {len(vocab)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR in build_html.py: {exc}", file=sys.stderr)
        raise
