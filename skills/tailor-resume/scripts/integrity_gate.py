"""
integrity_gate.py — the automated honesty check the skill runs on itself,
because no human reviews mid-run (build-plan Phase 3, step 4).

Two checks, both against cv.md as the sole source of truth:

  1. NUMBERS  — every numeric figure in the tailored output must trace to a
     figure already present in cv.md. A novel number is the signature of a
     fabricated metric, so it is flagged.

  2. KEYWORDS — every keyword Filter 2 reports having *inserted* (the
     "missing keywords" it chose to incorporate) must trace to real
     experience in cv.md. A keyword with no support is a claimed skill the
     candidate may not have, so it is flagged.

Design rule, non-negotiable: this gate FLAGS, it does not reject. Flagged
output is still rendered and written; summary.md / the critique mark it
"needs human check" so nothing is silently accepted OR silently dropped.

Usage:
    python integrity_gate.py --tailored tailored.json --cv cv.md \\
        [--inserted-keywords kw.json] [--out report.json]

`tailored.json`   = the TailoredResume content (Filter 3 output / what renders).
`kw.json`         = optional JSON list of strings: the keywords Filter 2 added.
                    May also be embedded as tailored.json -> "_inserted_keywords".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow running both as a module and as a loose script.
try:
    from . import common
except ImportError:  # pragma: no cover - direct-script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import common  # type: ignore


# A handful of numbers are structural rather than claims (years used as plain
# dates, single-digit list counts that are everywhere in any CV). We do NOT
# whitelist these by default — being noisy-but-safe beats silently passing a
# fabricated figure — but the threshold for "distinctive" is exposed so a
# deployment can tune it if review noise is genuinely a problem.
_TOKEN_RE = re.compile(r"[A-Za-z0-9+#./-]+")
_STOPWORDS = {
    "and", "or", "the", "a", "an", "of", "to", "in", "on", "for", "with",
    "using", "via", "by", "at", "as", "is", "are", "be", "across", "per",
}


@dataclass
class Flag:
    kind: str          # "number" | "keyword"
    value: str         # the offending value (canonical number, or keyword)
    detail: str        # human-readable explanation
    context: str = ""  # where it appeared in the output


@dataclass
class GateReport:
    passed: bool
    number_flags: list[Flag] = field(default_factory=list)
    keyword_flags: list[Flag] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "needs_human_check": not self.passed,
            "number_flags": [vars(f) for f in self.number_flags],
            "keyword_flags": [vars(f) for f in self.keyword_flags],
            "summary": self.summary(),
        }

    def summary(self) -> str:
        if self.passed:
            return "Integrity gate PASSED: all numbers and inserted keywords trace to cv.md."
        parts = []
        if self.number_flags:
            parts.append(f"{len(self.number_flags)} number(s) not traceable to cv.md")
        if self.keyword_flags:
            parts.append(f"{len(self.keyword_flags)} inserted keyword(s) not traceable to cv.md")
        return "Integrity gate FLAGGED: " + "; ".join(parts) + ". Output written, marked 'needs human check'."


# --------------------------------------------------------------------------
# Number check
# --------------------------------------------------------------------------

def check_numbers(tailored: dict, cv_text: str) -> list[Flag]:
    allowed = common.cv_number_set(cv_text)
    flags: list[Flag] = []
    seen: set[tuple[str, str]] = set()
    for chunk in common.iter_all_text(tailored):
        if not chunk:
            continue
        for canon, raw in common.extract_numbers(chunk):
            if canon in allowed:
                continue
            key = (canon, chunk[:80])
            if key in seen:
                continue
            seen.add(key)
            flags.append(
                Flag(
                    kind="number",
                    value=canon,
                    detail=(
                        f"figure '{raw}' has no matching number anywhere in cv.md "
                        f"(possible fabricated/altered metric)"
                    ),
                    context=chunk.strip()[:160],
                )
            )
    return flags


# --------------------------------------------------------------------------
# Keyword check
# --------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _content_tokens(text: str) -> list[str]:
    return [t for t in _tokens(text) if t not in _STOPWORDS and len(t) > 1]


def keyword_traces(keyword: str, cv_text: str) -> tuple[bool, str]:
    """Return (traces, reason). Substring match is strongest; else require all
    content tokens of the keyword to appear somewhere in cv.md."""
    kw = keyword.strip()
    if not kw:
        return True, "empty"
    cv_lower = cv_text.lower()
    if kw.lower() in cv_lower:
        return True, "exact substring in cv.md"

    cv_tok = set(_tokens(cv_text))
    ctoks = _content_tokens(kw)
    if not ctoks:
        return True, "no content tokens"
    present = [t for t in ctoks if t in cv_tok]
    if len(present) == len(ctoks):
        return True, "all content tokens present in cv.md"
    if not present:
        return False, "no content tokens found in cv.md"
    missing = [t for t in ctoks if t not in cv_tok]
    return False, f"only partial support; missing token(s): {', '.join(missing)}"


def check_keywords(inserted_keywords: list[str], cv_text: str) -> list[Flag]:
    flags: list[Flag] = []
    for kw in inserted_keywords or []:
        traces, reason = keyword_traces(kw, cv_text)
        if not traces:
            flags.append(
                Flag(
                    kind="keyword",
                    value=kw,
                    detail=f"inserted keyword does not trace to cv.md ({reason})",
                )
            )
    return flags


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run_gate(
    tailored: dict,
    cv_text: str,
    inserted_keywords: list[str] | None = None,
) -> GateReport:
    if inserted_keywords is None:
        inserted_keywords = tailored.get("_inserted_keywords", [])
    num_flags = check_numbers(tailored, cv_text)
    kw_flags = check_keywords(inserted_keywords, cv_text)
    return GateReport(
        passed=not (num_flags or kw_flags),
        number_flags=num_flags,
        keyword_flags=kw_flags,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resume integrity gate.")
    ap.add_argument("--tailored", required=True, help="TailoredResume JSON file")
    ap.add_argument("--cv", default=None, help="path to cv.md (default: locked path)")
    ap.add_argument("--inserted-keywords", default=None, help="JSON list of inserted keywords")
    ap.add_argument("--out", default=None, help="write report JSON here")
    args = ap.parse_args(argv)

    tailored = common.load_json(args.tailored)
    cv_text = common.load_cv(args.cv)
    inserted = None
    if args.inserted_keywords:
        inserted = json.loads(Path(args.inserted_keywords).read_text(encoding="utf-8"))

    report = run_gate(tailored, cv_text, inserted)
    payload = report.to_dict()

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    # Exit 0 always: a flag is a review signal, NOT a build failure. The
    # orchestrator decides what to do; the gate never blocks the write.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
