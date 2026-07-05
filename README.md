# Daily English Reader — HTML-only Claude Code Routine v2

This repo is intended to run with **Claude Code Routines**.

Every morning, the routine:
1. Fetches one English article.
2. Claude reads the article and creates a vocabulary file.
3. Python builds a polished HTML page.
4. The routine commits and pushes the generated page to `main`.

The final page is:

```text
docs/index.html
```

If GitHub Pages is enabled for this repo, the reading page is available at:

```text
https://YossefM1.github.io/daily-english-reader/
```

## v2 fixes

This version fixes two problems found in the first successful routine run:

1. Removed `feedparser`, because its `sgmllib3k` dependency failed in the Claude Routine Debian environment.
2. Removed Yahoo RSS from defaults, because Yahoo returned HTTP 403 from the Claude cloud runner.
3. Updated the routine instructions to use a Python virtual environment.
4. Updated the push command to push generated `docs/index.html` to `main`.

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
- feedparser

Email sending can be added later.

## Routine environment variables

No secret variables are required.

Recommended variables:

```text
RSS_FEEDS=https://feeds.bbci.co.uk/news/world/rss.xml,https://www.theguardian.com/world/rss,https://feeds.npr.org/1001/rss.xml,https://feeds.arstechnica.com/arstechnica/index
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
