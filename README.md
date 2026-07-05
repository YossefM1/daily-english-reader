# Daily English Reader — Claude Code Routine Version

This repo is intended to run with **Claude Code Routines**, not with Claude API.

Every morning, the routine:
1. Fetches one English article.
2. Claude reads the article and creates a vocabulary file.
3. Python builds a polished HTML email.
4. Python sends the email to you.

The final email includes:
- the article in English
- intermediate/advanced words highlighted in gray
- a Hebrew vocabulary sidebar
- Hebrew translation
- pronunciation in Hebrew letters with niqqud where possible
- short Hebrew explanation
- example sentence in English

## Files

```text
src/fetch_article.py
src/build_and_send.py
CLAUDE.md
routine_prompt.md
requirements.txt
```

## Important

This version does **not** require `ANTHROPIC_API_KEY`.

Claude Code Routine itself performs the language analysis and writes:

```text
data/vocabulary.json
```

## Required routine environment variables

Set these in the Claude Code Routine environment:

```text
EMAIL_FROM
EMAIL_TO
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
```

For Gmail:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your Gmail address
SMTP_PASSWORD=your Gmail App Password
```

`SMTP_PASSWORD` must be a Gmail App Password, not your normal Gmail password.

## Optional variables

```text
RSS_FEEDS=https://news.yahoo.com/rss,https://www.yahoo.com/news/rss/finance
MAX_ARTICLE_CHARS=12000
OUTPUT_DIR=data
```

For testing one fixed article:

```text
ARTICLE_URL=https://...
```

Remove `ARTICLE_URL` when you want the routine to choose from RSS automatically.

## Local test, without sending email

You can run:

```bash
python -m pip install -r requirements.txt
python src/fetch_article.py
```

Then create `data/vocabulary.json` manually or by Claude, and run:

```bash
python src/build_and_send.py
```

## GitHub Actions

The previous GitHub Actions workflow is disabled because this project is now intended to run through Claude Code Routines.
