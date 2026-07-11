# Private personalization setup

The real learner profile must not be committed to this public repository. Store it in a private repository or private local storage that Codex can read during the future task-generation run.

Priority for task adaptation:

1. A recent explicit manual override from `config/learning_focus.json`.
2. The private learner profile.
3. The safe default: recommended level `A`, confidence `low`, focus `balanced`.

Assessment JSON exported from the Reading Tasks page may be downloaded by the learner and later copied into the private personalization workflow. Do not upload answers, assessment results, grammar notes, or learner profile data to public GitHub issues.

Codex must update skill scores only when assessment evidence is present. With no evidence, keep score values `null`, evidence counts at `0`, and trends `unknown`.
