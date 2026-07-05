You are running the daily English reader routine from the GitHub repository `YossefM1/daily-english-reader`.

Goal:
Send me one polished English-learning email based on one current English article.

Follow the repository instructions in `CLAUDE.md` exactly.

Execution steps:
1. From the repository root, run:
   python -m pip install -r requirements.txt

2. Run:
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

5. Run:
   python src/build_and_send.py

Success means the HTML email was sent.
At the end, report only:
- article title
- original URL
- number of vocabulary words
- whether the email was sent successfully
