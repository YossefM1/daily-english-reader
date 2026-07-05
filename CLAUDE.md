# Daily English Reader — Claude Code Routine Instructions

This repository is designed to be run by Claude Code Routines.

## Goal

Every morning, create and send one polished English-learning article email for a Hebrew speaker.

The email must contain:
- the English article text as extracted from a current article
- intermediate and advanced vocabulary highlighted in gray inside the article
- a Hebrew vocabulary sidebar
- Hebrew translation
- approximate English pronunciation written in Hebrew letters with niqqud where possible
- short Hebrew explanation
- short English example sentence

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

It contains:

```json
{
  "title": "...",
  "url": "...",
  "text": "...",
  "source": "...",
  "date": "..."
}
```

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

### 5. Build and send the email

```bash
python src/build_and_send.py
```

This reads:
- `data/article.json`
- `data/vocabulary.json`

Then it:
- builds `data/daily_article.html`
- sends the HTML email through SMTP

## Required environment variables

The routine environment must include:

```text
EMAIL_FROM
EMAIL_TO
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
```

Recommended Gmail values:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<your gmail address>
SMTP_PASSWORD=<Gmail App Password, not the regular Gmail password>
```

Optional environment variables:

```text
ARTICLE_URL
RSS_FEEDS
MAX_ARTICLE_CHARS
OUTPUT_DIR
```

Useful defaults:

```text
RSS_FEEDS=https://news.yahoo.com/rss,https://www.yahoo.com/news/rss/finance
MAX_ARTICLE_CHARS=12000
OUTPUT_DIR=data
```

## Success criteria

A successful run means:
1. `data/article.json` exists.
2. `data/vocabulary.json` exists and contains valid JSON.
3. `data/daily_article.html` exists.
4. The email is sent to `EMAIL_TO`.
5. The final response in the routine session briefly reports the article title, source URL, and number of vocabulary words.
