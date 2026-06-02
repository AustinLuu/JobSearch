"""
common.py — shared helpers for the tailor-resume skill.

Holds the pieces every stage of the skill leans on, kept deterministic and
test-covered so the LLM-driven filters (in SKILL.md) can call them without
re-deriving conventions each run:

  * paths            — the locked ~/Documents/JobSearch layout
  * sanitize / filenames — the locked {listing}__{company}_{short_id} convention
  * short_id_from_job_id — strip the li_/in_/gd_ prefix
  * load_cv / cv_number_set / cv_text — read the source of truth (cv.md)
  * extract_numbers  — the normalizer the integrity gate uses on both sides
  * TailoredResume schema validation — the contract the renderer consumes

Nothing here invents content. The honesty guarantees live in integrity_gate.py;
this module only supplies the substrate.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# --------------------------------------------------------------------------
# Paths. Default to this deployment's layout: ~/Documents/Claude/JobSearch
# (on Windows that resolves to C:\Users\<you>\Documents\Claude\JobSearch).
# Override JOBSEARCH_ROOT in tests / cloud-headless / other machines so nothing
# is hard-bound to one layout. The template lives at <root>/templates/template_0.docx.
# --------------------------------------------------------------------------

JOBSEARCH_ROOT = Path(
    os.environ.get(
        "JOBSEARCH_ROOT", Path.home() / "Documents" / "Claude" / "JobSearch"
    )
)
CV_PATH = JOBSEARCH_ROOT / "cv.md"
TEMPLATE_PATH = JOBSEARCH_ROOT / "templates" / "template_0.docx"


def dated_output_dir(date_str: str) -> Path:
    """<root>/YYYY-MM-DD/ — created lazily by the orchestrator."""
    return JOBSEARCH_ROOT / date_str


# --------------------------------------------------------------------------
# Filenames — the convention is locked in build-plan Phase 4. Keep both the
# .docx and the -critique.md derived from the same stem so they never drift.
# --------------------------------------------------------------------------

_ILLEGAL = r'/\\:*?"<>|'
_ILLEGAL_RE = re.compile(f"[{re.escape(_ILLEGAL)}]")
_WS_RE = re.compile(r"\s+")
_PREFIX_RE = re.compile(r"^(li|in|gd)_", re.IGNORECASE)


def sanitize_component(text: str) -> str:
    """Strip illegal filename chars, collapse whitespace runs to single '_'.

    Per convention: strip / \\ : * ? " < > | and collapse spaces to _.
    Also trims and removes leading/trailing underscores so stems stay clean.
    """
    if text is None:
        text = ""
    cleaned = _ILLEGAL_RE.sub("", str(text))
    cleaned = _WS_RE.sub("_", cleaned.strip())
    cleaned = re.sub(r"_{2,}", "_", cleaned)  # never collapse the "__" join here
    return cleaned.strip("_")


def short_id_from_job_id(job_id: str) -> str:
    """li_8f3a2b -> 8f3a2b. Equivalent to the record's raw_source_id."""
    return _PREFIX_RE.sub("", str(job_id))


def output_stem(listing: dict) -> str:
    """{sanitized_listing_name}__{company}_{short_id} — no extension.

    listing_name = the job title (per the Phase 4 worked example
    "Senior_Data_Engineer__Acme_8f3a"). short_id = de-prefixed job_id.
    """
    title = sanitize_component(listing.get("title", "untitled"))
    company = sanitize_component(listing.get("company", "company"))
    sid = short_id_from_job_id(listing.get("job_id", listing.get("raw_source_id", "")))
    sid = sanitize_component(sid)
    return f"{title}__{company}_{sid}"


def resume_filename(listing: dict) -> str:
    return f"{output_stem(listing)}.docx"


def critique_filename(listing: dict) -> str:
    return f"{output_stem(listing)}-critique.md"


# --------------------------------------------------------------------------
# CV access + number extraction. The integrity gate compares output numbers
# against this set; extract_numbers MUST run identically on both sides.
# --------------------------------------------------------------------------

def load_cv(cv_path: Path | str | None = None) -> str:
    path = Path(cv_path) if cv_path else CV_PATH
    return path.read_text(encoding="utf-8")


# Bare number: optional thousands separators + optional decimal. NOT preceded
# by a word char or dot (so the 3 in "S3"/"EC2"/"v1.2.3" is not mistaken for a
# metric). The magnitude suffix (k/m/b) is decided in Python by peeking at the
# char right after the match — only when it is tightly attached AND at a word
# boundary — so "1.5M" expands but "5 ms" / "5 minutes" stay 5.
_NUM_RE = re.compile(
    r"""
    (?<![\w.])                 # not preceded by a word char or dot
    (\d{1,3}(?:,\d{3})+|\d+)    # integer part, with or without thousands commas
    (?:\.(\d+))?               # optional decimal
    """,
    re.VERBOSE,
)

_SUFFIX_MULT = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def _canon_number(int_part: str, dec_part: str | None, suffix: str | None) -> str:
    """Canonicalize one match to a stable string key.

    No suffix: keep the written magnitude ("80" matches "80%", "92.84" kept).
    With a k/m/b suffix: expand it so "1.5M" and "1,500,000" collide.
    """
    digits = int_part.replace(",", "")
    raw = digits + ("." + dec_part if dec_part else "")
    if suffix:
        value = float(raw) * _SUFFIX_MULT[suffix.lower()]
        if value == int(value):
            return str(int(value))
        return ("%f" % value).rstrip("0").rstrip(".")
    if dec_part:
        norm = raw.rstrip("0").rstrip(".")
        return norm if norm else "0"
    return digits


def _attached_suffix(text: str, end: int) -> str | None:
    """A magnitude suffix counts only if it sits immediately after the number
    and is itself followed by a non-letter (end, space, punctuation)."""
    if end >= len(text):
        return None
    ch = text[end]
    if ch.lower() not in _SUFFIX_MULT:
        return None
    nxt = text[end + 1] if end + 1 < len(text) else ""
    if not nxt or not nxt.isalpha():
        return ch
    return None


def extract_numbers(text: str) -> list[tuple[str, str]]:
    """Return [(canonical_value, raw_match), ...] for every number in text."""
    out: list[tuple[str, str]] = []
    for m in _NUM_RE.finditer(text):
        int_part, dec_part = m.group(1), m.group(2)
        suffix = _attached_suffix(text, m.end())
        raw = m.group(0) + (suffix or "")
        out.append((_canon_number(int_part, dec_part, suffix), raw))
    return out


def cv_number_set(cv_text: str) -> set[str]:
    """The set of canonical numeric values appearing anywhere in cv.md.

    'Anywhere' is deliberate: build-plan says an output figure is acceptable if
    traceable to a Y *or any other figure* in the CV, so we don't restrict to
    Y-lines. This makes the gate conservative about *novel* numbers only.
    """
    return {canon for canon, _ in extract_numbers(cv_text)}


# --------------------------------------------------------------------------
# TailoredResume content contract — what Filter 3 emits and the renderer reads.
# Kept intentionally flat and ATS-friendly: no nested layout, no columns.
# --------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


_REQUIRED_TOP = ["contact", "summary", "skills", "experience"]
_REQUIRED_CONTACT = ["name", "line"]  # 'line' = the single contact row, kept in body


def validate_tailored_resume(doc: dict) -> ValidationResult:
    """Structural validation only. Honesty checks live in integrity_gate.py."""
    errors: list[str] = []
    for key in _REQUIRED_TOP:
        if key not in doc:
            errors.append(f"missing required top-level key: {key!r}")

    contact = doc.get("contact", {})
    if isinstance(contact, dict):
        for k in _REQUIRED_CONTACT:
            if not contact.get(k):
                errors.append(f"contact.{k} is required and must be non-empty")
    else:
        errors.append("contact must be an object with 'name' and 'line'")

    exp = doc.get("experience", [])
    if not isinstance(exp, list) or not exp:
        errors.append("experience must be a non-empty list")
    else:
        for i, role in enumerate(exp):
            if not role.get("title") or not role.get("company"):
                errors.append(f"experience[{i}] needs both 'title' and 'company'")
            bullets = role.get("bullets", [])
            if not isinstance(bullets, list):
                errors.append(f"experience[{i}].bullets must be a list")

    skills = doc.get("skills", [])
    if not isinstance(skills, list):
        errors.append("skills must be a list of {category, items} objects")

    return ValidationResult(ok=not errors, errors=errors)


def load_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Default education policy: experienced-candidate resumes lead with work, not
# school. Strip GPA / honours / Dean's-list / awards / coursework detail lines
# from education by DEFAULT across every render (render_docx + render_template).
# Degree, institution, location, and dates are always kept. Keyword-based and
# intentionally transparent so a deployment can tune the pattern; pass
# keep_undergrad_achievements=True at the call site to opt back in.
# --------------------------------------------------------------------------

_UNDERGRAD_ACHIEVEMENT_RE = re.compile(
    r"\b("
    r"gpa|grade point average|"
    r"dean'?s\s+(?:honou?r|list)|honou?r\s+roll|honou?r\s+list|"
    r"cum\s+laude|magna\s+cum\s+laude|summa\s+cum\s+laude|"
    r"with\s+(?:distinction|honou?rs)|first[-\s]class|"
    r"scholarship|bursary|award|medal|prize|"
    r"relevant\s+coursework|coursework"
    r")\b",
    re.IGNORECASE,
)


def strip_undergrad_achievements(education, keep: bool = False):
    """Return a COPY of `education` with GPA / honours / Dean's-list / awards /
    coursework detail lines removed (default policy). Degree, institution,
    location, and dates are never touched. Set keep=True to pass through
    unchanged. Never mutates the input."""
    if keep:
        return list(education or [])
    out = []
    for e in education or []:
        e2 = dict(e)
        e2["details"] = [
            d for d in e2.get("details", [])
            if d and not _UNDERGRAD_ACHIEVEMENT_RE.search(str(d))
        ]
        out.append(e2)
    return out


def iter_all_text(doc: dict) -> Iterable[str]:
    """Yield every human-readable string in a TailoredResume, for the gate."""
    contact = doc.get("contact", {})
    if isinstance(contact, dict):
        yield contact.get("name", "")
        yield contact.get("line", "")
    yield doc.get("summary", "")
    for grp in doc.get("skills", []):
        if isinstance(grp, dict):
            yield grp.get("category", "")
            for it in grp.get("items", []):
                yield it
    for section in ("experience", "projects"):
        for role in doc.get(section, []):
            if not isinstance(role, dict):
                continue
            for k in ("title", "company", "location", "dates", "context"):
                yield role.get(k, "") or ""
            for b in role.get("bullets", []):
                yield b
    for edu in doc.get("education", []):
        if isinstance(edu, dict):
            for k in ("degree", "institution", "location", "dates"):
                yield edu.get(k, "") or ""
            for d in edu.get("details", []):
                yield d
    for cert in doc.get("certifications", []):
        yield cert if isinstance(cert, str) else ""
