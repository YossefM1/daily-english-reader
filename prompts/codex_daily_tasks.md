# Codex daily reading-task generation flow

Run this only after Claude has published the daily article metadata.

1. Read `docs/data/today.json` and the three Claude-generated per-article files.
2. Confirm all selected article URLs are BBC-only.
3. Read the private learner profile from the private personalization location, if available.
4. Process any new downloaded assessment JSON files from previous sessions.
5. Update the learner profile conservatively; never change a skill score without assessment evidence.
6. Fetch and read the three original BBC articles from their public BBC URLs.
7. Generate exactly 10 article-specific reading-comprehension tasks per article.
8. Adapt tasks using priority: recent manual override, private learner profile, then default A/balanced with low confidence.
9. Validate task quality: real article-specific prompts, concrete article-related MCQ options, correct answer in options, plausible wrong distractors, mixed answer positions, expected_points for open tasks, no placeholder strings, no full article text.
10. Publish only `docs/data/tasks/task-index.json` and `docs/data/tasks/YYYY-MM-DD-{A,B,C}.json` to the public repository.

Do not regenerate Claude vocabulary or quiz data. Do not modify the userscript, workflows, source code, `docs/index.html`, or `docs/tasks.html` during a normal daily task run unless explicitly requested.
