# Daily English Reader — Claude Code Routine Instructions

This repository uses a **browser-overlay architecture** with **three daily
reading levels (A / B / C)**.

The Claude Routine does NOT republish the articles.
It only saves vocabulary + quiz metadata to GitHub Pages.
The actual reading happens on the original BBC website, with a Tampermonkey
userscript adding the Hebrew overlay (Words + Quiz tabs).

## Publishing authorization

Claude Code is explicitly authorized to publish the Daily English Reader daily
content to `main` after all generation and verification checks pass.

This authorization applies every day and does not require asking the user again.

Claude Code may:

- commit the generated daily metadata files;
- push the working branch;
- fast-forward merge the working branch into `main`;
- push `main` to `origin`.

Claude Code must use only a fast-forward merge. Never force-push, never rewrite
history, and never merge if verification failed, if conflicts exist, or if
`main` has diverged.

If the merge is not fast-forward, if there are conflicts, if `main` has changed
unexpectedly, or if GitHub rejects the push, stop and report the problem.

## Architecture

```text
Claude Code Routine (cloud)
  → fetches MANY BBC article candidates from several BBC RSS feeds
  → Claude selects 3 articles by difficulty:
        A — Easier English       (prefer 300–600 words)
        B — Intermediate English (prefer 500–900 words, default level)
        C — Advanced English     (prefer 800–1400 words)
  → Claude creates 25 vocabulary words + 25 quiz questions per article
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

## BBC-only source rule (hard requirement)

This project is **BBC-only**. The Tampermonkey overlay only runs on BBC article
pages, so any non-BBC article silently shows no vocabulary/quiz overlay.

- **Guardian, NPR, Ars Technica, Yahoo, and every other non-BBC source are
  forbidden.** They must never appear in `data/candidates.json`,
  `data/learning_articles.json`, or any public `docs/data/*.json` file.
- Every published article URL (A, B, and C) must have exactly one of these
  hostnames: `bbc.com`, `www.bbc.com`, `bbc.co.uk`, `www.bbc.co.uk`.
- Any ambient `RSS_FEEDS` environment variable listing non-BBC feeds is ignored
  and overridden in BBC-only mode. `src/fetch_articles.py` drops non-BBC feeds
  and non-BBC candidate URLs (with a printed warning); `src/build_today_json.py`
  fails the build if any public URL is not BBC. Do not work around these guards.
- If fewer than 3 BBC candidates are available, **fetch more BBC candidates**
  (add BBC feeds, raise `LINKS_PER_FEED`) or **fail the run clearly**. It is
  never acceptable to fill A/B/C with a non-BBC article to reach three.

## Important implementation notes

- Do NOT generate a standalone article HTML page.
- Do NOT run or reintroduce `src/build_html.py` (standalone page generation is retired).
- Do NOT publish the full article text to GitHub Pages.
- Do NOT use email, SMTP, Claude API, or Anthropic API.
- Do NOT use feedparser (its `sgmllib3k` dependency fails in the Debian cloud environment).
- Yahoo RSS is excluded because it returned HTTP 403 from the cloud runner.
- Keep **BBC-only** mode for now.
- Use a Python virtual environment for all dependency installation.
- `data/candidates.json` and `data/learning_articles.json` are internal only and must not be committed or published.

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

- Exactly **25** words.
- Levels B1/B2/C1/C2 (A-level article may lean B1/B2; C-level may include C2).
- No names of people, places, companies, products, or organizations.
- No dates, numbers, abbreviations, or very basic words.
- Prefer single-token words (easier for the highlighter).
- The `word` field must match the exact surface form appearing in that article's text.
- Hebrew should be natural for an Israeli Hebrew speaker.
- `pronunciation_hebrew` is an approximate phonetic guide using Hebrew letters with niqqud, not IPA.

Per-article quiz rules (apply to **each** of the 3 articles):

- Exactly **25** quiz questions. Prefer one question per vocabulary word.
- Use mostly `english_to_hebrew` and `hebrew_to_english` types.
- Exactly 4 `options`; `correct_answer` must be one of them; options must be distinct.
- Every quiz `word` must exist in that article's `words` list.
- Give each quiz a unique `id`, prefixed by the article id (`A-q1`, `B-q1`, …).
- You do NOT need to pre-shuffle option order — the build script shuffles options deterministically and enforces a spread of correct-answer positions.

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
each with exactly 25 words and 25 quiz questions, each quiz has 4 distinct
options, each `correct_answer` is among its options, and each quiz `word`
exists in that article's `words` list.

It then **shuffles quiz options deterministically** (seed = date + article id +
quiz id + article url) and enforces that, within each article's 25 questions,
the correct answer appears in all 4 option positions, never all in the first
position, and no single position holds more than 10 correct answers. If the
input violates this, it reshuffles deterministically (same input → same
output).

None of the published files contain the full article text.

### 6. Verify generated output before publishing

Before committing, verify all of the following:

- `docs/data/today.json` exists and contains exactly 3 articles: A, B, and C.
- Each public per-article JSON contains exactly 25 vocabulary words and 25 quiz questions.
- No public JSON file contains a `text` field or full article body.
- All vocabulary surface forms appear in the corresponding article text from `data/candidates.json`.
- `data/candidates.json` and `data/learning_articles.json` remain untracked/gitignored.

Suggested checks:

```bash
git status --short
python src/build_today_json.py
```

### 7. Commit, merge to `main`, and push

Use this publishing flow every day after verification passes.

```bash
git config user.name "Claude"
git config user.email "noreply@anthropic.com"

WORKING_BRANCH="$(git branch --show-current)"

# Commit only the public generated metadata files.
git add docs/data/today.json docs/data/articles/ docs/data/latest.json docs/data/archive/
git commit -m "Update daily English reader metadata" || echo "No changes to commit"

# Push the working branch first, if it is not main.
if [ "$WORKING_BRANCH" != "main" ]; then
  git push origin "$WORKING_BRANCH"
fi

# Publish to main using fast-forward only.
git fetch origin
git switch main
git pull --ff-only origin main

if [ "$WORKING_BRANCH" != "main" ]; then
  git merge --ff-only "$WORKING_BRANCH"
fi

git push origin main
```

Do NOT use `git push --force`.
Do NOT use `git push --force-with-lease`.
Do NOT rewrite history.
Do NOT merge with a merge commit.
Do NOT manually resolve conflicts during the routine.

If any command fails, stop and report the exact failure.
