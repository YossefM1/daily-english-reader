# Daily English Reader agent rules

- Keep the project BBC-only. Published article URLs and task article URLs must use `bbc.com`, `www.bbc.com`, `bbc.co.uk`, or `www.bbc.co.uk`.
- Preserve the separation of responsibilities: Claude publishes article, vocabulary, and quiz metadata; Codex publishes reading-comprehension task metadata after Claude's daily files exist.
- Do not publish full BBC article text. Public task files may include article-specific questions, options, expected points, and Hebrew rubrics/explanations only.
- Never commit the real learner profile, answers, assessment results, grammar notes, or private personalization data. Only schemas and examples belong in this public repository.
- Manual focus in `config/learning_focus.json` is an override, not a learner profile. It must never contain assessment details.
- Reading tasks must be article-specific. Do not use vague placeholder options such as “The article’s central event or claim”, “A minor background detail only”, “A topic not discussed in the article”, or “A conclusion supported by details in the article”.
- Validate exactly 10 tasks per article, allowed categories/types, MCQ answer/options, mixed correct-answer positions, no placeholder strings, BBC URLs, and no full article text before publishing task files.
