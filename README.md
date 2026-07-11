# Daily English Reader

A daily English vocabulary learning tool for Hebrew speakers, with **three
reading levels every day (A / B / C)**.

> **Current test mode: BBC only.** The routine selects articles from **BBC News**
> feeds (World, Technology, Business, Science & Environment, Health,
> Entertainment & Arts). The Guardian, NPR, and Ars Technica sources are
> disabled during BBC test mode, and the userscript is optimized for BBC pages.

Every day, a Claude Code Routine fetches many BBC article candidates and selects
**three** by difficulty — A (easier), B (intermediate), C (advanced). For each,
it publishes Hebrew vocabulary **and a quiz** as metadata to GitHub Pages. A
Tampermonkey userscript loads that metadata and injects a learning overlay
directly on whichever of the three BBC articles you open, with two tabs:
**Words** and **Quiz**.

**The original article stays on the BBC website — layout, images, videos, and
embedded media are untouched. No full article text is ever published by this
project.**

## Dashboard

[https://YossefM1.github.io/daily-english-reader/](https://YossefM1.github.io/daily-english-reader/)

The dashboard shows three cards — **A — Easier English**, **B — Intermediate
English**, **C — Advanced English** — each with the article title, source, word
count, a short difficulty reason, vocabulary/quiz counts, a small vocabulary
preview, and an **Open BBC article** button.

## Architecture

```
Claude Code Routine (runs in the cloud each day)
  └─ src/fetch_articles.py    → fetches MANY BBC candidates → data/candidates.json
  └─ Claude selects A/B/C      → data/learning_articles.json (25 words + 25 quiz each)
  └─ src/build_today_json.py   → writes docs/data/today.json + per-article + latest.json + archive
  └─ git push                  → publishes metadata to GitHub Pages

Browser (your machine)
  └─ Tampermonkey userscript
       └─ loads today.json (the 3 selected articles) from GitHub Pages
       └─ checks whether the current page URL matches any of the 3 article URLs
       └─ loads that article's per-level data file
       └─ highlights vocabulary words in gray
       └─ injects a collapsible Hebrew sidebar (Words + Quiz) showing the level
```

## What gets published to GitHub Pages

Only vocabulary + quiz metadata — never the full article text.

`docs/data/today.json` — the index of today's three articles:

```json
{
  "date": "2026-07-06",
  "generated_at": "2026-07-06T06:00:00Z",
  "source_mode": "BBC-only",
  "articles": [
    {
      "id": "A",
      "level": "A",
      "level_label": "A — Easier English",
      "title": "Article title",
      "source": "BBC",
      "url": "https://www.bbc.co.uk/news/...",
      "word_count": 450,
      "difficulty_reason": "Shorter article, simpler vocabulary, clearer structure.",
      "data_url": "data/articles/2026-07-06-A.json",
      "vocabulary_count": 25,
      "quiz_count": 25
    }
  ]
}
```

`docs/data/articles/YYYY-MM-DD-A.json` (and `-B`, `-C`) — the full per-article
metadata, with `words` and `quiz` arrays (no article text):

```json
{
  "date": "2026-07-06",
  "id": "A",
  "level": "A",
  "level_label": "A — Easier English",
  "title": "Article title",
  "source": "BBC",
  "url": "https://www.bbc.co.uk/news/...",
  "word_count": 450,
  "generated_at": "2026-07-06T06:00:00Z",
  "difficulty_reason": "...",
  "settings": { "source_mode": "BBC-only", "vocabulary_count": 25, "quiz_enabled": true },
  "words": [
    {
      "word": "escalate",
      "lemma": "escalate",
      "level": "B2",
      "hebrew": "להסלים / להחמיר",
      "explanation_hebrew": "כאשר מצב הופך רציני או חמור יותר.",
      "pronunciation_hebrew": "אֶסְקֵלֵייט",
      "example": "Tensions continued to escalate throughout the week."
    }
  ],
  "quiz": [
    {
      "id": "A-q1",
      "word": "escalate",
      "type": "english_to_hebrew",
      "question": "What does “escalate” mean?",
      "options": ["לְפַרְסֵם", "להסלים / להחמיר", "לְאַחְסֵן", "לְהַרְגִּיעַ"],
      "correct_answer": "להסלים / להחמיר",
      "explanation_hebrew": "“escalate” פירושו להסלים — כשמצב הופך חמור יותר."
    }
  ]
}
```

Each article always contains **exactly 25 vocabulary words** and **exactly 25
quiz questions**. `docs/data/latest.json` is kept for backward compatibility and
mirrors the **B-level** (default) article. Archive copies are written to
`docs/data/archive/YYYY-MM-DD-{A,B,C}.json`.

### Quiz option shuffling

The build script shuffles each quiz question's four options **deterministically**
(seed = date + article id + quiz id + article URL) so the correct answer is not
always the first option. Within each article's 25 questions it enforces that the
correct answer appears in **at least 3 different positions**, **never all in the
first position**, and **no single position holds more than 7** correct answers.
If the input violates these rules, options are reshuffled deterministically —
the same input always produces the same published output.

## How to use each day

1. The routine runs automatically (or you trigger it manually).
2. Open the dashboard: [https://YossefM1.github.io/daily-english-reader/](https://YossefM1.github.io/daily-english-reader/)
3. Pick a level (A / B / C) and click **Open BBC article** to open it on BBC.
4. The Tampermonkey userscript detects which of the three articles you opened
   and shows the Hebrew vocabulary sidebar for that level.

## How to install the userscript

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser (Chrome, Firefox, Edge, Safari).
2. Open the userscript URL:
   [https://YossefM1.github.io/daily-english-reader/userscript/daily-english-reader.user.js](https://YossefM1.github.io/daily-english-reader/userscript/daily-english-reader.user.js)
3. Tampermonkey will detect it and show an **Install** / **Update** prompt — click it.
4. **Test mode:** the script runs on BBC News pages (`bbc.co.uk/news/*` and
   `bbc.com/news/*`, with or without `www`). Other sources are disabled for now.

The userscript:
- Loads `today.json` and matches the current page against the 3 selected article URLs.
- Highlights vocabulary words in gray inside the article text.
- Shows a collapsible sidebar on the right with the selected **level** near the title and two tabs:
  - **Words** — Hebrew translation, pronunciation (with niqqud), explanation, and an English example for each of the 25 words.
  - **Quiz** — 25 multiple-choice questions, one at a time, with correct/incorrect marking, the correct answer, a Hebrew explanation, and a final score with the words you missed.
- Clicking a highlighted word scrolls to its card in the Words tab.
- Your latest quiz result is saved locally (`localStorage`, keyed by date + level) — no login.
- If the current page is not one of today's 3 selected articles, the status pill shows **"not today's selected article"**.
- If `today.json` is unavailable, it falls back to `latest.json` (the B-level article) for backward compatibility.

## How to run the Claude Routine manually

Paste the contents of `routine_prompt.md` into a Claude Code Routine session
pointed at this repository. The routine will:

1. Set up the Python virtual environment.
2. Run `src/fetch_articles.py` to fetch many BBC candidates.
3. Select 3 articles (A/B/C) and create `data/learning_articles.json` with 25
   words + 25 quiz questions each.
4. Run `src/build_today_json.py` to validate, shuffle quiz options, and build
   the metadata JSON files.
5. Commit and push the public files to `main`.

## Repository structure

```
daily-english-reader/
├─ CLAUDE.md                      ← routine instructions
├─ README.md
├─ requirements.txt
├─ routine_prompt.md              ← paste this into Claude Routine
├─ src/
│  ├─ fetch_articles.py           ← fetches MANY BBC candidates (multi-level)
│  ├─ build_today_json.py         ← builds today.json + per-article + latest.json + archive
│  ├─ fetch_article.py            ← legacy single-article fetcher (kept for compatibility)
│  └─ build_latest_json.py        ← legacy single-article builder (kept for compatibility)
├─ docs/                          ← served by GitHub Pages (site root)
│  ├─ index.html                  ← dashboard with 3 level cards
│  ├─ userscript/
│  │  └─ daily-english-reader.user.js   ← installable userscript
│  └─ data/
│     ├─ today.json               ← index of today's 3 articles
│     ├─ latest.json              ← backward-compat copy of the B-level article
│     ├─ articles/
│     │  └─ YYYY-MM-DD-{A,B,C}.json   ← per-level metadata
│     └─ archive/
│        └─ YYYY-MM-DD-{A,B,C}.json   ← daily archive per level
└─ data/                          ← internal only (gitignored)
   └─ candidates.json, learning_articles.json (never published)
```

## GitHub Pages setup

```
Settings → Pages → Source: Deploy from a branch
Branch: main  |  Folder: /docs
```

## Supported sources

**Current test mode: BBC only.** Default candidate feeds:

- BBC World — `https://feeds.bbci.co.uk/news/world/rss.xml`
- BBC Technology — `https://feeds.bbci.co.uk/news/technology/rss.xml`
- BBC Business — `https://feeds.bbci.co.uk/news/business/rss.xml`
- BBC Science & Environment — `https://feeds.bbci.co.uk/news/science_and_environment/rss.xml`
- BBC Health — `https://feeds.bbci.co.uk/news/health/rss.xml`
- BBC Entertainment & Arts — `https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml`

Temporarily disabled during BBC test mode (re-enable by setting `RSS_FEEDS`):

- The Guardian World — `https://www.theguardian.com/world/rss`
- NPR — `https://feeds.npr.org/1001/rss.xml`
- Ars Technica — `https://feeds.arstechnica.com/arstechnica/index`

Yahoo RSS is excluded because it returned HTTP 403 from the Claude cloud runner.
RSS parsing uses the Python standard library — **feedparser is not used** (its
`sgmllib3k` dependency fails to build in the cloud environment).

## Environment variables (optional)

| Variable | Default | Description |
|---|---|---|
| `RSS_FEEDS` | 6 BBC section feeds | Comma-separated feed URLs |
| `LINKS_PER_FEED` | `5` | Links to consider per feed |
| `MAX_CANDIDATES` | `18` | Max extracted candidates to keep |
| `MIN_CANDIDATE_WORDS` | `150` | Minimum words for a usable candidate |
| `MAX_CANDIDATE_CHARS` | `20000` | Cap on stored candidate text |
| `ARTICLE_URL` | _(none)_ | (legacy) single-article: use a specific URL |
| `MAX_ARTICLE_CHARS` | `12000` | (legacy) trim extracted text to this length |
| `OUTPUT_DIR` | `data` | Directory for intermediate files |
| `DOCS_DIR` | `docs` | Directory for GitHub Pages output |

## Known limitations

- Single-word vocabulary items only (multi-word phrases coming later).
- Three articles per day (A/B/C).
- Highlighting may occasionally match a word in the wrong context.

## Roadmap

- ✅ Quiz system (Words + Quiz tabs, local score saving).
- ✅ Multi-level daily articles (A/B/C).
- ✅ Deterministic quiz option shuffling with distribution enforcement.
- Multi-word expression support in the highlighter.
- Hover cards instead of a fixed sidebar.
- Spaced-repetition tracking across days.
- Cross-day score history / review dashboard.
- Mobile-friendly sidebar layout.
