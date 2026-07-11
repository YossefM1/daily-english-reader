#!/usr/bin/env python3
"""Safely apply a reader-focus issue body to private and public config files."""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_LEVELS = {"A", "B", "C"}

ALLOWED_FOCUS = {
    "balanced",
    "main_idea",
    "factual_details",
    "inference",
    "vocabulary_context",
    "summary",
    "written_expression",
}

ALLOWED_FIELDS = {
    "preferred_level",
    "question_focus",
}


def read_body(path: str | None) -> str:
    """Read the GitHub issue body from a file or environment variable."""
    if path:
        return Path(path).read_text(encoding="utf-8")

    body = os.getenv("ISSUE_BODY")

    if body is None:
        raise ValueError(
            "Missing issue body: set ISSUE_BODY or pass --body-file"
        )

    return body


def extract_json(body: str) -> dict:
    """Extract and validate one fenced JSON object from the issue body."""
    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        body,
        re.DOTALL | re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            "Issue body must contain one fenced JSON object"
        )

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("Focus payload must be a JSON object")

    unknown_fields = set(data) - ALLOWED_FIELDS
    missing_fields = ALLOWED_FIELDS - set(data)

    if unknown_fields:
        raise ValueError(
            f"Unknown field(s): {', '.join(sorted(unknown_fields))}"
        )

    if missing_fields:
        raise ValueError(
            f"Missing field(s): {', '.join(sorted(missing_fields))}"
        )

    if data["preferred_level"] not in ALLOWED_LEVELS:
        raise ValueError(
            "preferred_level must be one of A, B, C"
        )

    if data["question_focus"] not in ALLOWED_FOCUS:
        raise ValueError(
            "question_focus has an invalid value"
        )

    return data


def write_json(path: Path, payload: dict) -> None:
    """Write formatted UTF-8 JSON, creating parent folders when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply a validated Daily English Reader focus issue."
    )

    parser.add_argument(
        "--body-file",
        help="Path to the file containing the GitHub issue body.",
    )

    parser.add_argument(
        "--output",
        default="config/learning_focus.json",
        help="Internal focus configuration output path.",
    )

    parser.add_argument(
        "--public-output",
        default="docs/data/learning_focus.json",
        help="Public safe focus configuration output path.",
    )

    args = parser.parse_args()

    data = extract_json(read_body(args.body_file))

    public_data = {
        "preferred_level": data["preferred_level"],
        "question_focus": data["question_focus"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "YossefM1",
    }

    internal_output = Path(args.output)
    public_output = Path(args.public_output)

    write_json(internal_output, public_data)
    write_json(public_output, public_data)

    print(
        "Applied reader focus: "
        f"{public_data['preferred_level']} / "
        f"{public_data['question_focus']} "
        f"to {internal_output} and {public_output}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)