You are running the daily English reader routine from the GitHub repository `YossefM1/daily-english-reader`.

## Goal

Publish **three** daily English articles (levels A / B / C) as vocabulary + quiz
metadata to GitHub Pages so the browser userscript can display a Hebrew learning
overlay (Words + Quiz tabs) on the original BBC article the user chooses.

**Do NOT generate a standalone article page. Do NOT run `build_html.py`.**
**Do NOT publish the full article text.**
**Only generate `docs/data/today.json`, `docs/data/articles/YYYY-MM-DD-{A,B,C}.json`, `docs/data/latest.json` (B-level copy), and the archive files.**

The reading experience happens on the original BBC website. The Tampermonkey
userscript handles the overlay. Your job is only to publish the metadata.

If this prompt conflicts with `CLAUDE.md`, follow `CLAUDE.md`.

## Steps

### 1. Set up the Python environment

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

This creates `data/candidates.json` (internal, gitignored) with many BBC
candidates, each including title, url, source, category, text, and word_count.

### 3. Read the candidates

Open and read `data/candidates.json`.

### 4. Select 3 articles and create `data/learning_articles.json`

Pick **3 different BBC articles**, one per level:

- **A — Easier English**: prefer 300–600 words, clear topic, simpler structure; vocabulary mostly A2/B1/B2 (choose useful B1/B2 words).
- **B — Intermediate English** (default): prefer 500–900 words; vocabulary mostly B1/B2/C1.
- **C — Advanced English**: prefer 800–1400 words, more complex topic; vocabulary including C1/C2 where useful.

If exact word-count targets are impossible, pick the closest candidates and say
so in `difficulty_reason`.

Create `data/learning_articles.json` with this exact schema:

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
          "options": ["opt1", "opt2", "opt3", "opt4"],
          "correct_answer": "the correct option",
          "explanation_hebrew": "short Hebrew explanation of the answer"
        }
      ]
    }
  ]
}
```

Rules for **each** of the 3 articles:
- Exactly 15 words and exactly 15 quiz questions.
- Vocabulary: B1/B2/C1/C2 only, no basic words; no names, places,
  organizations, dates, numbers, abbreviations; prefer single-token words; the
  `word` must be an exact surface form from that article's text.
- Hebrew must be natural for an Israeli Hebrew speaker; `pronunciation_hebrew`
  uses Hebrew letters with niqqud where possible.
- Quiz: mostly `english_to_hebrew` / `hebrew_to_english`; exactly 4 distinct
  options; `correct_answer` among them; every quiz `word` in that article's
  words list; unique quiz ids prefixed by the article id (`A-q1`, `B-q1`, …).
- You do NOT need to shuffle options — the build script shuffles them
  deterministically and enforces the correct-answer position distribution.

### 5. Build metadata JSON

```bash
. .venv/bin/activate
python src/build_today_json.py
```

This validates the 3 articles (15 words + 15 quiz each, 4 options, correct
answer present, quiz words valid), deterministically shuffles quiz options,
enforces the correct-answer position spread, and writes:

- `docs/data/today.json`
- `docs/data/articles/YYYY-MM-DD-A.json`, `-B.json`, `-C.json`
- `docs/data/latest.json` (backward-compat copy of level B)
- `docs/data/archive/YYYY-MM-DD-A.json`, `-B.json`, `-C.json`

None of these contain the full article text.

### 6. Commit and push to main

```bash
git config user.name "Claude"
git config user.email "noreply@anthropic.com"
git add docs/data/today.json docs/data/articles/ docs/data/latest.json docs/data/archive/ \
        docs/index.html docs/userscript/daily-english-reader.user.js \
        CLAUDE.md routine_prompt.md src/ requirements.txt README.md
git commit -m "Update daily English reader metadata" || echo "No changes to commit"
git push origin HEAD:main
```

**Do not force-push. Do not rewrite history. Push to `main` only.**

## Constraints

- Do not use Claude API or Anthropic API key.
- Do not use Gmail, SMTP, or any email service.
- Do not use feedparser.
- Do not run or reintroduce `build_html.py` / standalone article pages.
- Do not publish `data/candidates.json` or `data/learning_articles.json`.
- Do not overwrite `docs/index.html` or the userscript unless there is an
  improvement or bug fix to make.

## Final report

After a successful run, report only:
- For each level A/B/C: article title, BBC URL, vocabulary count, quiz count.
- Confirmation that `docs/data/today.json` (and per-article + latest.json) was
  pushed to `main`.
