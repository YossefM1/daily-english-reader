# Daily English Reader — Claude Code Routine Instructions

This repository uses a **browser-overlay architecture** with **three daily
reading levels (A / B / C)**.

The Claude Routine does NOT republish the articles.
It only saves vocabulary + quiz metadata to GitHub Pages.
The actual reading happens on the original BBC website, with a Tampermonkey
userscript adding the Hebrew overlay (Words + Quiz tabs).

## Architecture

```
Claude Code Routine (cloud)
  → fetches MANY BBC article candidates from several BBC RSS feeds
  → Claude selects 3 articles by difficulty:
        A — Easier English      (prefer 300–600 words)
        B — Intermediate English (prefer 500–900 words, default level)
        C — Advanced English    (prefer 800–1400 words)
  → Claude creates 15 vocabulary words + 15 quiz questions per article
  → saves data/learning_articles.json (internal, gitignored)
  → build_today_json.py writes public metadata to docs/data/

Browser (Tampermonkey userscript)
  → runs on the original BBC article page
  → loads docs/data/today.json (the 3 selected articles)
  → checks if the current URL matches any of the 3 selected article URLs
  → if matched, loads that article's per-level data file
  → highlights vocabulary words in gray
  → injects a Hebrew sidebar with Words + Quiz tabs and the selected level
```

## Important implementation notes

- Do NOT generate a standalone article HTML page.
- Do NOT run or reintroduce `src/build_html.py` (standalone page generation is retired).
- Do NOT publish the full article text to GitHub Pages.
- Do NOT use email, SMTP, Claude API, or Anthropic API.
- Do NOT use feedparser (its `sgmllib3k` dependency fails in the Debian cloud environment).
- Yahoo RSS is excluded because it returned HTTP 403 from the cloud runner.
- Keep **BBC-only** mode for now.
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

### 2. Fetch article candidates

```bash
. .venv/bin/activate
python src/fetch_articles.py
```

This fetches candidates from several BBC feeds and creates:

```text
data/candidates.json
```

Schema (internal only, gitignored, contains full text for analysis — never published):

```json
{
  "generated_at": "ISO timestamp",
  "source_mode": "BBC-only",
  "feeds": ["..."],
  "candidate_count": 12,
  "candidates": [
    {
      "title": "...",
      "url": "https://www.bbc.co.uk/news/...",
      "source": "BBC",
      "category": "world",
      "text": "full article text (internal only)",
      "word_count": 742
    }
  ]
}
```

If some feeds fail, the script continues with the others.

### 3. Read the candidates

Read `data/candidates.json`. Use `word_count` and topic to decide which
candidate fits each level.

### 4. Select 3 articles (A / B / C) and create the learning file

Select **exactly 3 different BBC articles**, one per level:

**A — Easier English**
- Prefer **300–600 words**.
- Clear topic, simpler structure.
- Vocabulary mostly A2/B1/B2 — select useful B1/B2 words.

**B — Intermediate English** (default recommended level)
- Prefer **500–900 words**.
- Good general reading level.
- Vocabulary mostly B1/B2/C1.

**C — Advanced English**
- Prefer **800–1400 words**.
- More complex topic.
- More advanced vocabulary, including C1/C2 where useful.

If exact word-count targets are impossible, choose the closest available
candidates and explain the compromise in `difficulty_reason`.

Create the internal file:

```text
data/learning_articles.json
```

Schema:

```json
{
  "date": "YYYY-MM-DD",
  "articles": [
    {
      "id": "A",
      "level": "A",
      "level_label": "A — Easier English",
      "title": "BBC article title",
      "source": "BBC",
      "url": "https://www.bbc.co.uk/news/...",
      "word_count": 450,
      "difficulty_reason": "Shorter article, simpler vocabulary, clearer structure.",
      "words": [
        {
          "word": "exact word from the article",
          "lemma": "base form",
          "level": "B1/B2/C1/C2",
          "hebrew": "Hebrew translation",
          "explanation_hebrew": "short Hebrew explanation",
          "pronunciation_hebrew": "approximate pronunciation in Hebrew letters with niqqud",
          "example": "short English example sentence"
        }
      ],
      "quiz": [
        {
          "id": "A-q1",
          "word": "same word as one of the vocabulary items",
          "type": "english_to_hebrew",
          "question": "What does “word” mean?",
          "options": ["option 1", "option 2", "option 3", "option 4"],
          "correct_answer": "the correct option",
          "explanation_hebrew": "short Hebrew explanation of the answer"
        }
      ]
    }
  ]
}
```

Per-article vocabulary rules (apply to **each** of the 3 articles):
- Exactly **15** words.
- Levels B1/B2/C1/C2 (A-level article may lean B1/B2; C-level may include C2).
- No names of people, places, companies, products, or organizations.
- No dates, numbers, abbreviations, or very basic words.
- Prefer single-token words (easier for the highlighter).
- The `word` field must match the exact surface form appearing in that
  article's text.
- Hebrew should be natural for an Israeli Hebrew speaker.
- `pronunciation_hebrew` is an approximate phonetic guide using Hebrew letters
  with niqqud, not IPA.

Per-article quiz rules (apply to **each** of the 3 articles):
- Exactly **15** quiz questions. Prefer one question per vocabulary word.
- Use mostly `english_to_hebrew` and `hebrew_to_english` types.
- Exactly 4 `options`; `correct_answer` must be one of them; options must be
  distinct.
- Every quiz `word` must exist in that article's `words` list.
- Give each quiz a unique `id`, prefixed by the article id (`A-q1`, `B-q1`, …).
- You do NOT need to pre-shuffle option order — the build script shuffles
  options deterministically and enforces a spread of correct-answer positions.

`data/learning_articles.json` is gitignored and must NOT be pushed. It is only
input for `build_today_json.py`.

### 5. Build the public metadata

```bash
. .venv/bin/activate
python src/build_today_json.py
```

This validates the input and writes:

```text
docs/data/today.json                    (index of the 3 articles, metadata only)
docs/data/articles/YYYY-MM-DD-A.json    (full metadata: words + quiz, no text)
docs/data/articles/YYYY-MM-DD-B.json
docs/data/articles/YYYY-MM-DD-C.json
docs/data/latest.json                   (backward-compat copy of level B)
docs/data/archive/YYYY-MM-DD-A.json     (archive copies)
docs/data/archive/YYYY-MM-DD-B.json
docs/data/archive/YYYY-MM-DD-C.json
```

The build script **fails** unless there are exactly 3 articles (ids A, B, C),
each with exactly 15 words and 15 quiz questions, each quiz has 4 distinct
options, each `correct_answer` is among its options, and each quiz `word`
exists in that article's `words` list.

It then **shuffles quiz options deterministically** (seed = date + article id +
quiz id + article url) and enforces that, within each article's 15 questions,
the correct answer appears in at least 3 different positions, never all in the
first position, and no single position holds more than 7 correct answers. If
the input violates this, it reshuffles deterministically (same input → same
output).

None of the published files contain the full article text.

### 6. Commit and push

```bash
git config user.name "Claude"
git config user.email "noreply@anthropic.com"
git add docs/data/today.json docs/data/articles/ docs/data/latest.json docs/data/archive/ \
        docs/index.html docs/userscript/daily-english-reader.user.js \
        CLAUDE.md routine_prompt.md src/ requirements.txt README.md
git commit -m "Update daily English reader metadata" || echo "No changes to commit"
git push origin HEAD:main
```

Do NOT force-push. Do NOT rewrite history.

## Legacy single-article flow (kept for compatibility)

The original single-article scripts still exist:
`src/fetch_article.py` → `data/article.json`, and `src/build_latest_json.py`
(reads `data/vocabulary.json` → writes `docs/data/latest.json`). The new
multi-level flow above supersedes them, but they remain valid and are not
required for the daily routine.

## Optional environment variables

```text
ARTICLE_URL          – (legacy single-article) override RSS with a specific URL
RSS_FEEDS            – comma-separated RSS feed URLs (default: 6 BBC section feeds)
LINKS_PER_FEED       – how many links to consider per feed (default 5)
MAX_CANDIDATES       – max successfully-extracted candidates to keep (default 18)
MIN_CANDIDATE_WORDS  – minimum words for a usable candidate (default 150)
MAX_CANDIDATE_CHARS  – cap on stored candidate text (default 20000)
MAX_ARTICLE_CHARS    – (legacy) default 12000
OUTPUT_DIR           – default data
DOCS_DIR             – default docs
```

Current test mode: **BBC only**. Default candidate feeds:

```text
https://feeds.bbci.co.uk/news/world/rss.xml
https://feeds.bbci.co.uk/news/technology/rss.xml
https://feeds.bbci.co.uk/news/business/rss.xml
https://feeds.bbci.co.uk/news/science_and_environment/rss.xml
https://feeds.bbci.co.uk/news/health/rss.xml
https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml
```

Other stable feeds (disabled during BBC test mode — set `RSS_FEEDS` to re-enable):

```text
https://www.theguardian.com/world/rss
https://feeds.npr.org/1001/rss.xml
https://feeds.arstechnica.com/arstechnica/index
```

## Success criteria

A successful run means:
1. `data/candidates.json` was created (internal use only, not pushed).
2. `data/learning_articles.json` was created with exactly 3 articles (A/B/C),
   each with exactly 15 words and 15 quiz questions (not pushed).
3. `docs/data/today.json` and the three `docs/data/articles/YYYY-MM-DD-*.json`
   files were written and pushed to `main`.
4. `docs/data/latest.json` (B-level compatibility copy) and the three
   `docs/data/archive/YYYY-MM-DD-*.json` files were written and pushed.
5. No full article text was published.
6. The final response reports: the 3 article titles + BBC URLs + levels, the
   vocabulary and quiz counts per article, and confirmation that `today.json`
   was pushed.
