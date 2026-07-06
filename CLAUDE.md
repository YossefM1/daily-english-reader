# Daily English Reader — Claude Code Routine Instructions

This repository uses a **browser-overlay architecture**.

The Claude Routine does NOT republish the article.  
It only saves vocabulary metadata to GitHub Pages.  
The actual reading happens on the original news website, with a Tampermonkey userscript adding the Hebrew overlay.

## Architecture

```
Claude Code Routine (cloud)
  → fetches one article from RSS
  → extracts text for analysis only
  → creates Hebrew vocabulary metadata
  → saves docs/data/latest.json and archive JSON to GitHub

Browser (Tampermonkey userscript)
  → runs on the original article page
  → loads latest.json from GitHub Pages
  → checks if the current URL matches today's article URL
  → highlights vocabulary words in gray
  → injects a Hebrew vocabulary sidebar
```

## Important implementation notes

- Do NOT generate a standalone article HTML page.
- Do NOT publish the full article text to GitHub Pages.
- Do NOT use email, SMTP, Claude API, or Anthropic API.
- Do NOT use feedparser (its `sgmllib3k` dependency fails in the Debian cloud environment).
- Yahoo RSS is excluded from defaults because it returned HTTP 403 from the cloud runner.
- Use a Python virtual environment for all dependency installation.

## Routine run steps

Run all commands from the repository root.

### 1. Prepare Python environment

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

### 2. Fetch article

```bash
. .venv/bin/activate
python src/fetch_article.py
```

This creates:

```text
data/article.json
```

Schema:

```json
{
  "date": "YYYY-MM-DD",
  "title": "...",
  "source": "...",
  "url": "...",
  "text": "...",
  "word_count": 123
}
```

`data/article.json` is for internal analysis only. It is gitignored and must NOT be pushed.

### 3. Read the article

Read `data/article.json` to understand the article text.

### 4. Create vocabulary file

Create:

```text
data/vocabulary.json
```

The file must be valid JSON. Use exactly this schema:

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
- Select only intermediate and advanced vocabulary: B1, B2, C1, C2.
- Do not select names of people, places, companies, products, or organizations.
- Do not select dates, numbers, abbreviations, or very basic words.
- Prefer single-token words (single word, not phrases) — they are easier for the highlighter.
- The `word` field must match the exact surface form appearing in the article text.
- Hebrew should be clear and natural for an Israeli Hebrew speaker.
- `pronunciation_hebrew` is an approximate phonetic guide using Hebrew letters with niqqud, not IPA.

`data/vocabulary.json` is gitignored and must NOT be pushed directly.  
It is only used as input for `build_latest_json.py`.

### 5. Build latest.json

```bash
. .venv/bin/activate
python src/build_latest_json.py
```

This creates:

```text
docs/data/latest.json
docs/data/archive/YYYY-MM-DD.json
```

`latest.json` contains metadata and vocabulary only. It does NOT include the full article text.

### 6. Commit and push

```bash
git config user.name "Claude"
git config user.email "noreply@anthropic.com"
git add docs/data/latest.json docs/data/archive/ docs/index.html docs/userscript/daily-english-reader.user.js CLAUDE.md routine_prompt.md src/ requirements.txt README.md
git commit -m "Update daily English reader metadata" || echo "No changes to commit"
git push origin HEAD:main
```

Do NOT force-push. Do NOT rewrite history.

## Optional environment variables

```text
ARTICLE_URL       – override RSS and use a specific article URL
RSS_FEEDS         – comma-separated RSS feed URLs
MAX_ARTICLE_CHARS – default 12000
OUTPUT_DIR        – default data
DOCS_DIR          – default docs
```

Current test mode: **BBC only**. The routine selects articles from BBC World
News exclusively:

```text
RSS_FEEDS=https://feeds.bbci.co.uk/news/world/rss.xml
```

Other stable feeds (temporarily disabled during BBC test mode — re-add to
`RSS_FEEDS` to re-enable):

```text
https://www.theguardian.com/world/rss
https://feeds.npr.org/1001/rss.xml
https://feeds.arstechnica.com/arstechnica/index
```

## Success criteria

A successful run means:
1. `data/article.json` was created (internal use only, not pushed).
2. `data/vocabulary.json` was created and contains 18–35 valid words (not pushed directly).
3. `docs/data/latest.json` was written and pushed to `main`.
4. `docs/data/archive/YYYY-MM-DD.json` was written and pushed to `main`.
5. The final response reports: article title, source URL, number of vocabulary words, and confirmation that latest.json was pushed.
