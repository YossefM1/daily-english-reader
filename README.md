# Daily English Reader

A daily English vocabulary learning tool for Hebrew speakers.

Every morning, a Claude Code Routine picks one current article from a major news source and publishes Hebrew vocabulary metadata to GitHub Pages. A Tampermonkey browser userscript loads that metadata and injects a vocabulary overlay directly on the original article page.

**The original article stays on the original website — layout, images, videos, and embedded media are untouched.**

## Dashboard

[https://YossefM1.github.io/daily-english-reader/](https://YossefM1.github.io/daily-english-reader/)

## Architecture

```
Claude Code Routine (runs in the cloud each morning)
  └─ src/fetch_article.py   → picks article from RSS, extracts text
  └─ Claude creates         → data/vocabulary.json  (18–35 Hebrew-annotated words)
  └─ src/build_latest_json.py → writes docs/data/latest.json + archive JSON
  └─ git push               → publishes metadata to GitHub Pages

Browser (your machine)
  └─ Tampermonkey userscript
       └─ loads latest.json from GitHub Pages
       └─ checks if current page URL = today's article URL
       └─ highlights vocabulary words in gray
       └─ injects a collapsible Hebrew vocabulary sidebar
```

## What gets published to GitHub Pages

Only vocabulary metadata — never the full article text:

```json
{
  "date": "2026-07-06",
  "title": "Article title",
  "source": "BBC",
  "url": "https://www.bbc.co.uk/news/...",
  "word_count": 420,
  "generated_at": "2026-07-06T06:00:00Z",
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
  ]
}
```

## How to use each morning

1. The routine runs automatically (or you trigger it manually).
2. Open the dashboard: [https://YossefM1.github.io/daily-english-reader/](https://YossefM1.github.io/daily-english-reader/)
3. Click **"פתח מאמר מקורי ↗"** to open today's article on the original site.
4. The Tampermonkey userscript activates automatically and shows the Hebrew vocabulary sidebar.

## How to install the userscript

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser (Chrome, Firefox, Edge, Safari).
2. Open the raw userscript URL:  
   [https://YossefM1.github.io/daily-english-reader/userscript/daily-english-reader.user.js](https://YossefM1.github.io/daily-english-reader/userscript/daily-english-reader.user.js)
3. Tampermonkey will detect it and show an **Install** prompt — click Install.
4. The script runs automatically on BBC, Guardian, NPR, and Ars Technica pages.

The userscript:
- Highlights vocabulary words in gray inside the article text.
- Shows a collapsible sidebar on the right with Hebrew translation, pronunciation, explanation, and English example sentence for each word.
- Clicking a highlighted word scrolls to its card in the sidebar.
- If the current page does not match today's article, a brief notice appears and disappears.

## How to run the Claude Routine manually

Paste the contents of `routine_prompt.md` into a Claude Code Routine session pointed at this repository. The routine will:

1. Set up the Python virtual environment.
2. Run `src/fetch_article.py` to pick and extract an article.
3. Create `data/vocabulary.json` with 18–35 annotated words.
4. Run `src/build_latest_json.py` to build the metadata JSON files.
5. Commit and push `docs/data/latest.json` and the archive file to `main`.

## Repository structure

```
daily-english-reader/
├─ CLAUDE.md                      ← routine instructions
├─ README.md
├─ requirements.txt
├─ routine_prompt.md              ← paste this into Claude Routine
├─ src/
│  ├─ fetch_article.py            ← fetches and extracts article text
│  └─ build_latest_json.py        ← builds metadata JSON for GitHub Pages
├─ docs/                          ← served by GitHub Pages (site root)
│  ├─ index.html                  ← GitHub Pages dashboard
│  ├─ userscript/
│  │  └─ daily-english-reader.user.js   ← installable userscript
│  └─ data/
│     ├─ latest.json              ← today's vocabulary metadata
│     └─ archive/
│        └─ YYYY-MM-DD.json       ← one file per day
└─ data/
   └─ .gitkeep                    ← article.json and vocabulary.json are gitignored
```

## GitHub Pages setup

In your repository settings:

```
Settings → Pages → Source: Deploy from a branch
Branch: main  |  Folder: /docs
```

## Supported sources

- BBC World News — `https://feeds.bbci.co.uk/news/world/rss.xml`
- The Guardian World — `https://www.theguardian.com/world/rss`
- NPR — `https://feeds.npr.org/1001/rss.xml`
- Ars Technica — `https://feeds.arstechnica.com/arstechnica/index`

Yahoo RSS is excluded because it returned HTTP 403 from the Claude cloud runner.

## Environment variables (optional)

| Variable | Default | Description |
|---|---|---|
| `ARTICLE_URL` | _(none)_ | Skip RSS and use a specific article URL |
| `RSS_FEEDS` | BBC, Guardian, NPR, Ars Technica | Comma-separated feed URLs |
| `MAX_ARTICLE_CHARS` | `12000` | Trim extracted text to this length |
| `OUTPUT_DIR` | `data` | Directory for intermediate files |
| `DOCS_DIR` | `docs` | Directory for GitHub Pages output |

## Known limitations

- Single-word vocabulary items only in v1 (multi-word phrases coming later).
- One article per day.
- No notification when the new article is ready.
- Highlighting may occasionally match a word in the wrong context.

## Roadmap

- Email notification when the new article is ready.
- Multi-word expression support in the highlighter.
- Hover cards instead of a fixed sidebar.
- Multiple articles per day / per topic.
- Spaced-repetition tracking across days.
- Mobile-friendly sidebar layout.
