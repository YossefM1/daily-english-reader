# Daily English Reader

This repository sends you a daily English article as an HTML email.

The email includes:
- the English article text
- intermediate/advanced vocabulary highlighted in gray
- a Hebrew vocabulary sidebar
- Hebrew translation
- approximate pronunciation in Hebrew letters with niqqud
- short explanation and example sentence

## How it works

GitHub Actions runs `src/main.py` every morning.
The script:
1. Chooses an article URL from RSS or from `ARTICLE_URL`
2. Extracts readable article text
3. Sends the article to Claude for vocabulary analysis
4. Builds an HTML email
5. Sends the email through SMTP

## Required GitHub Secrets

Go to:

Repository → Settings → Secrets and variables → Actions → Secrets

Create these secrets:

| Secret | Example |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `EMAIL_FROM` | `your.email@gmail.com` |
| `EMAIL_TO` | `your.email@gmail.com` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `your.email@gmail.com` |
| `SMTP_PASSWORD` | Gmail App Password, not your normal Gmail password |

## Optional GitHub Variables

Go to:

Repository → Settings → Secrets and variables → Actions → Variables

Optional variables:

| Variable | Example |
|---|---|
| `CLAUDE_MODEL` | `claude-sonnet-5` |
| `ARTICLE_URL` | `https://news.yahoo.com/...` |
| `RSS_FEEDS` | `https://news.yahoo.com/rss,https://www.yahoo.com/news/rss/finance` |
| `MAX_ARTICLE_CHARS` | `12000` |

If `ARTICLE_URL` is set, the workflow always uses that exact article.
If `ARTICLE_URL` is empty, the workflow chooses from RSS feeds.

## Schedule

The workflow is set to run every day at 07:00 Israel time:

```yaml
schedule:
  - cron: "0 7 * * *"
    timezone: "Asia/Jerusalem"
```

You can also run it manually from the Actions tab using `workflow_dispatch`.

## Gmail setup

Use a Gmail App Password, not your normal Gmail password.

In most cases:
- SMTP host: `smtp.gmail.com`
- Port: `587`
- Username: your Gmail address
- Password: the 16-character Gmail App Password

## Local test

Create a local `.env` or export environment variables manually, then run:

```bash
pip install -r requirements.txt
python src/main.py
```

## Notes

This is intended for private educational reading.
Keep the original article link in the email.
