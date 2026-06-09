#!/usr/bin/env python3
"""
validate_score.py — defensive validator for /score-job output.

Reads a score.json emitted by the /score-job reasoning pass, checks the schema,
applies the shortlist threshold, and prints exactly one decision line on stdout.

Exit codes:
  0  parsed and validated; printed SHORTLIST or SKIP line.
  2  malformed JSON or schema violation; printed INVALID line.

Design notes:
  - This script never crashes the orchestrator. Bad input -> exit 2 + a line on
    stderr; the orchestrator skips-and-logs the listing.
  - The threshold is the *only* policy lever: --threshold or $SCORE_THRESHOLD
    (default 70). The score itself is never modified here.
  - Strips ```json fences and surrounding whitespace before parsing, because
    LLM output occasionally adds them despite the prompt forbidding it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


REQUIRED_KEYS = {
    "job_id": str,
    "fit_score": int,
    "rationale": str,
    "matched_strengths": list,
    "likely_gaps": list,
}

DEFAULT_THRESHOLD = 70

# A permissive ```...``` / ```json...``` stripper. We only strip if the text
# *starts* with a fence — otherwise we leave it alone (an embedded backtick run
# inside a real JSON string is none of our business).
_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _fail_invalid(reason: str) -> "NoReturn":
    # Decision line on stdout (orchestrator reads stdout); reason on stderr.
    print(f'INVALID    reason="{reason}"')
    print(reason, file=sys.stderr)
    sys.exit(2)


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.match(text)
    return m.group(1) if m else text


def _parse_json(text: str) -> dict:
    cleaned = _strip_fences(text).strip()
    if not cleaned:
        _fail_invalid("empty input")
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        _fail_invalid(f"json decode error: {e.msg} at line {e.lineno} col {e.colno}")
    if not isinstance(obj, dict):
        _fail_invalid(f"top-level must be object, got {type(obj).__name__}")
    return obj


def _check_schema(obj: dict) -> None:
    for key, expected in REQUIRED_KEYS.items():
        if key not in obj:
            _fail_invalid(f"missing key: {key}")
        val = obj[key]
        # bool is a subclass of int in Python — reject it explicitly.
        if expected is int and isinstance(val, bool):
            _fail_invalid(f"key {key!r}: expected int, got bool")
        if not isinstance(val, expected):
            _fail_invalid(
                f"key {key!r}: expected {expected.__name__}, got {type(val).__name__}"
            )
    score = obj["fit_score"]
    if not (0 <= score <= 100):
        _fail_invalid(f"fit_score out of range [0,100]: {score}")
    for i, s in enumerate(obj["matched_strengths"]):
        if not isinstance(s, str):
            _fail_invalid(f"matched_strengths[{i}] not a string")
    for i, g in enumerate(obj["likely_gaps"]):
        if not isinstance(g, str):
            _fail_invalid(f"likely_gaps[{i}] not a string")
    if not obj["job_id"].strip():
        _fail_invalid("job_id is empty")
    if not obj["rationale"].strip():
        _fail_invalid("rationale is empty")


def _resolve_threshold(arg: int | None) -> int:
    if arg is not None:
        return arg
    env = os.environ.get("SCORE_THRESHOLD", "").strip()
    if env:
        try:
            return int(env)
        except ValueError:
            _fail_invalid(f"SCORE_THRESHOLD env var not an integer: {env!r}")
    return DEFAULT_THRESHOLD


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate /score-job output and apply shortlist threshold.")
    p.add_argument("--score", required=True, help="Path to score.json")
    p.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=f"Shortlist threshold (default: $SCORE_THRESHOLD or {DEFAULT_THRESHOLD})",
    )
    args = p.parse_args(argv)

    path = Path(args.score)
    if not path.exists():
        _fail_invalid(f"score file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        _fail_invalid(f"could not read {path}: {e}")

    obj = _parse_json(raw)
    _check_schema(obj)

    threshold = _resolve_threshold(args.threshold)
    job_id = obj["job_id"]
    score = obj["fit_score"]
    decision = "SHORTLIST" if score >= threshold else "SKIP     "
    print(f"{decision}  job_id={job_id}  fit_score={score}  threshold={threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
