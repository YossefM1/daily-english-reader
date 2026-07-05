# Daily English Reader — Claude Code Routine Instructions

This repository is designed to be run by Claude Code Routines.

## Goal

Every morning, create one polished English-learning HTML page for a Hebrew speaker.

The generated page must contain:
- the English article text as extracted from a current article
- intermediate and advanced vocabulary highlighted in gray inside the article
- a Hebrew vocabulary sidebar
- Hebrew translation
- approximate English pronunciation written in Hebrew letters with niqqud where possible
- short Hebrew explanation
- short English example sentence

The final page must be written to:

```text
docs/index.html
```

This allows the page to be served by GitHub Pages.

## Routine run steps

Run these commands from the repository root.

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Fetch article

```bash
python src/fetch_article.py
```

This creates:

```text
data/article.json
```

### 3. Read the article

Read `data/article.json`.

### 4. Create vocabulary file

Create this file:

```text
data/vocabulary.json
```

The file must be valid JSON.

Use exactly this schema:

```json
[
  {
    "word": "exact word from the article",
    "lemma": "base form",
    "level": "B1/B2/C1/C2",
    "hebrew": "Hebrew translation",
    "explanation_hebrew": "short Hebrew explanation",
    "pronunciation_hebrew": "approximate pronunciation in Hebrew letters with niqqud",
    "example": "short English example sentence"
  }
]
```

Vocabulary selection rules:
- Select 18–35 useful words.
- Select only intermediate and advanced vocabulary, approximately B1, B2, C1, and C2.
- Do not select names of people, places, companies, products, or organizations.
- Do not select dates, numbers, abbreviations, or very basic words.
- Prefer words that are useful for general English reading.
- The `word` field must match the exact surface form appearing in the article so the highlighter can find it.
- Hebrew should be clear and natural for an Israeli Hebrew speaker.
- `pronunciation_hebrew` is an approximate guide, not IPA. Use niqqud where possible.

### 5. Build HTML page

```bash
python src/build_html.py
```

This creates:

```text
docs/index.html
data/daily_article.html
```

### 6. Commit and push the generated page

After `docs/index.html` is created, commit and push it:

```bash
git config user.name "Claude Routine"
git config user.email "claude-routine@example.com"
git add docs/index.html
git commit -m "Update daily English article" || echo "No changes to commit"
git push
```

## Required environment variables

No email variables are required in this version.

Optional environment variables:

```text
ARTICLE_URL
RSS_FEEDS
MAX_ARTICLE_CHARS
OUTPUT_DIR
DOCS_DIR
```

Useful defaults:

```text
RSS_FEEDS=https://news.yahoo.com/rss,https://www.yahoo.com/news/rss/finance
MAX_ARTICLE_CHARS=12000
OUTPUT_DIR=data
DOCS_DIR=docs
```

## Success criteria

A successful run means:
1. `data/article.json` exists.
2. `data/vocabulary.json` exists and contains valid JSON.
3. `docs/index.html` exists.
4. `docs/index.html` was committed and pushed to GitHub.
5. The final response in the routine session briefly reports the article title, source URL, number of vocabulary words, and that the HTML page was updated.
