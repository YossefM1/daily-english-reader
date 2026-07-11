#!/usr/bin/env python3
"""Safely apply a reader-focus issue body to config/learning_focus.json."""
import argparse, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_LEVELS = {"A", "B", "C"}
ALLOWED_FOCUS = {"balanced", "main_idea", "factual_details", "inference", "vocabulary_context", "summary", "written_expression"}
ALLOWED_FIELDS = {"preferred_level", "question_focus"}


def read_body(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    body = os.getenv("ISSUE_BODY")
    if body is None:
        raise ValueError("Missing issue body: set ISSUE_BODY or pass --body-file")
    return body


def extract_json(body: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.DOTALL | re.IGNORECASE)
    if not m:
        raise ValueError("Issue body must contain one fenced JSON object")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Focus payload must be a JSON object")
    unknown = set(data) - ALLOWED_FIELDS
    missing = ALLOWED_FIELDS - set(data)
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"Missing field(s): {', '.join(sorted(missing))}")
    if data["preferred_level"] not in ALLOWED_LEVELS:
        raise ValueError("preferred_level must be one of A, B, C")
    if data["question_focus"] not in ALLOWED_FOCUS:
        raise ValueError("question_focus has an invalid value")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file")
    parser.add_argument("--output", default="config/learning_focus.json")
    parser.add_argument("--public-output", default="docs/data/learning_focus.json")
    args = parser.parse_args()
    data = extract_json(read_body(args.body_file))
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = "YossefM1"
    public_data = {
        "preferred_level": data["preferred_level"],
        "question_focus": data["question_focus"],
        "updated_at": data["updated_at"],
        "updated_by": data["updated_by"],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(public_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    public_out = Path(args.public_output)
    public_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.write_text(json.dumps(public_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Applied reader focus: {data['preferred_level']} / {data['question_focus']} "
        f"to {out} and {public_out}"
    )
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
