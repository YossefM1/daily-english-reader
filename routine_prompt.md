You are running the daily English reader routine from the GitHub repository `YossefM1/daily-english-reader`.

## Goal

Publish today's English vocabulary and quiz metadata to GitHub Pages so the browser userscript can display a Hebrew learning overlay (Words + Quiz tabs) on the original article.

**Do NOT generate a standalone article page.**  
**Do NOT publish the full article text.**  
**Only generate `docs/data/latest.json` and `docs/data/archive/YYYY-MM-DD.json`.**

The actual reading experience happens on the original news website. The Tampermonkey userscript handles the overlay. Your job is only to publish the vocabulary metadata.

## Steps

### 1. Set up the Python environment

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

### 2. Fetch the article

```bash
. .venv/bin/activate
python src/fetch_article.py
```

### 3. Read the article

Open and read `data/article.json`.

### 4. Create vocabulary

Create `data/vocabulary.json` with this exact schema (both a vocabulary list
and a quiz):

```json
{
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
      "id": "q1",
      "word": "same word as one of the vocabulary items",
      "type": "english_to_hebrew",
      "question": "What does “word” mean?",
      "options": ["correct", "wrong1", "wrong2", "wrong3"],
      "correct_answer": "correct",
      "explanation_hebrew": "short Hebrew explanation of the answer"
    }
  ]
}
```

Vocabulary rules:
- Exactly 15 words.
- B1/B2/C1/C2 only — no basic words. Prefer B1/B2/C1; C2 should not dominate.
- Avoid names, companies, places, organizations, dates, numbers, abbreviations.
- Prefer single-token words (not multi-word phrases).
- `word` must match an exact visible surface form from the article text.
- Hebrew must be natural and useful for an Israeli Hebrew speaker.
- `pronunciation_hebrew` should use Hebrew letters with niqqud where possible.

Quiz rules:
- Exactly 15 quiz questions. Prefer one question per vocabulary word.
- Use mostly `english_to_hebrew` and `hebrew_to_english` question types.
- Exactly 4 `options` per question; `correct_answer` must be one of them.
- Every quiz `word` must exist in the `words` list. Give each a unique `id`.
- Keep options plausible but not confusingly identical.

Validate: exactly 15 words and exactly 15 quiz questions, all required fields
present, all words appear in the article. `build_latest_json.py` enforces this.

### 5. Build metadata JSON

```bash
. .venv/bin/activate
python src/build_latest_json.py
```

This writes:
- `docs/data/latest.json`
- `docs/data/archive/YYYY-MM-DD.json`

These files do NOT contain the full article text.

### 6. Commit and push to main

```bash
git config user.name "Claude"
git config user.email "noreply@anthropic.com"
git add docs/data/latest.json docs/data/archive/ docs/index.html docs/userscript/daily-english-reader.user.js CLAUDE.md routine_prompt.md src/ requirements.txt README.md
git commit -m "Update daily English reader metadata" || echo "No changes to commit"
git push origin HEAD:main
```

**Do not force-push. Do not rewrite history. Push to `main` only.**

## Constraints

- Do not use Claude API or Anthropic API key.
- Do not use Gmail, SMTP, or any email service.
- Do not use feedparser.
- Do not publish `data/article.json` or `data/vocabulary.json` directly.
- Do not overwrite `docs/index.html` unless there is a dashboard improvement to make.
- Do not overwrite `docs/userscript/daily-english-reader.user.js` unless there is a bug fix.

## Final report

After a successful run, report only:
- Article title
- Original article URL
- Number of vocabulary words
- Number of quiz questions
- Confirmation that `docs/data/latest.json` was pushed to `main`
