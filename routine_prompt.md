You are running the daily English reader routine from the GitHub repository `YossefM1/daily-english-reader`.

Goal:
Create and publish one polished English-learning HTML page based on one current English article.

Follow the repository instructions in `CLAUDE.md` exactly.

Important:
- Do not use email or SMTP.
- Do not use Claude API.
- Use a Python virtual environment.
- Do not use feedparser.
- Push the generated `docs/index.html` to `main`, not only to a temporary Claude branch.

Execution steps:

1. From the repository root, run:
   python -m venv .venv
   . .venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -r requirements.txt

2. Run:
   . .venv/bin/activate
   python src/fetch_article.py

3. Open and read:
   data/article.json

4. Based on the article text, create:
   data/vocabulary.json

Use exactly this JSON schema:
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

Vocabulary rules:
- Select 18–35 words.
- Choose intermediate and advanced words only.
- Avoid names, places, companies, dates, numbers, and very basic words.
- The `word` must appear exactly in the article so the Python highlighter can mark it.
- Hebrew should be natural and useful for an Israeli Hebrew speaker.
- Add niqqud in the Hebrew pronunciation where possible.

5. Validate `data/vocabulary.json`:
   - It must be valid JSON.
   - It must contain 18–35 words.
   - Every `word` should appear in the article text.

6. Run:
   . .venv/bin/activate
   python src/build_html.py

7. Commit and push the generated page to `main`:
   git config user.name "Claude Routine"
   git config user.email "claude-routine@example.com"
   git add docs/index.html
   git commit -m "Update daily English article" || echo "No changes to commit"
   git push origin HEAD:main

Success means `docs/index.html` was updated in GitHub on the `main` branch.

At the end, report only:
- article title
- original URL
- number of vocabulary words
- whether docs/index.html was updated successfully on main
