# Daily English Reader — HTML-only Claude Code Routine

This repo is intended to run with **Claude Code Routines**.

Every morning, the routine:
1. Fetches one English article.
2. Claude reads the article and creates a vocabulary file.
3. Python builds a polished HTML page.
4. The routine commits and pushes the generated page to GitHub.

The final page is:

```text
docs/index.html
```

If GitHub Pages is enabled for this repo, the reading page is available at:

```text
https://YossefM1.github.io/daily-english-reader/
```

## Files

```text
src/fetch_article.py
src/build_html.py
CLAUDE.md
routine_prompt.md
requirements.txt
docs/index.html
```

## Important

This version does **not** use:
- Claude API
- Anthropic API key
- Gmail
- SMTP
- App Password

Email sending can be added later.

## Routine environment variables

No secret variables are required.

Recommended variables:

```text
RSS_FEEDS=https://news.yahoo.com/rss,https://www.yahoo.com/news/rss/finance
MAX_ARTICLE_CHARS=12000
OUTPUT_DIR=data
DOCS_DIR=docs
```

For testing one fixed article:

```text
ARTICLE_URL=https://...
```

Remove `ARTICLE_URL` when you want the routine to choose from RSS automatically.

## GitHub Pages setup

In GitHub:

```text
Repository → Settings → Pages
```

Set:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

Then the page should be available at:

```text
https://YossefM1.github.io/daily-english-reader/
```

## Local test

```bash
python -m pip install -r requirements.txt
python src/fetch_article.py
```

Then create `data/vocabulary.json` manually or by Claude, and run:

```bash
python src/build_html.py
```
