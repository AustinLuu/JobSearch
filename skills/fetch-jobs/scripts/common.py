"""
common.py — translation + grounding helpers for the /fetch-jobs skill.

This is the deterministic, side-effect-free core shared by build_calls.py and
process_results.py (and reusable by the cloud-headless variant). Everything that
turns canonical search_config.json fields into a specific Actor's parameter
format lives here, plus argument parsing, recency snapping, identifiers, and the
grounding maps.

Schema-verified against the live Apify input/output schemas on 2026-05-31:
  - fantastic-jobs/advanced-linkedin-job-search-api  (modified 2026-05-26)
  - borderline/indeed-scraper                        (modified 2026-05-27)
  - valig/glassdoor-jobs-scraper                     (modified 2026-05-25)
Re-run `fetch-actor-details` before any future build — these schemas change.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Actor identifiers
# ---------------------------------------------------------------------------

LINKEDIN = "fantastic-jobs/advanced-linkedin-job-search-api"
INDEED = "borderline/indeed-scraper"
GLASSDOOR = "valig/glassdoor-jobs-scraper"

# Map each canonical Actor to its short source prefix used in job_id.
ACTOR_PREFIX = {
    LINKEDIN: "li",
    INDEED: "in",
    GLASSDOOR: "gd",
}
ACTOR_SOURCE_NAME = {
    LINKEDIN: "linkedin",
    INDEED: "indeed",
    GLASSDOOR: "glassdoor",
}

# Source-selection aliases (matched case-insensitively).
_SOURCE_ALIASES = {
    "fantastic-jobs": LINKEDIN,
    "linkedin": LINKEDIN,
    "indeed": INDEED,
    "glassdoor": GLASSDOOR,
}
_ALL_SOURCES = [LINKEDIN, INDEED, GLASSDOOR]

DEFAULT_SOURCE = LINKEDIN


# ---------------------------------------------------------------------------
# Grounding maps — region -> (full region name, ISO-2 country, full country)
# Note the CA collision: as a *region* it is California (US); as a *country*
# code it is Canada. Locations are always "City, Region", so a trailing token
# in a location string is a REGION and is read here positionally, never as a
# bare country code. Extend this table when new locations are added to config.
# ---------------------------------------------------------------------------

REGION_MAP = {
    # Canada
    "ON": ("Ontario", "CA", "Canada"),
    "BC": ("British Columbia", "CA", "Canada"),
    "AB": ("Alberta", "CA", "Canada"),
    "QC": ("Quebec", "CA", "Canada"),
    # United States
    "NY": ("New York", "US", "United States"),
    "CA": ("California", "US", "United States"),   # region context = California
    "NJ": ("New Jersey", "US", "United States"),
    "WA": ("Washington", "US", "United States"),
    "TX": ("Texas", "US", "United States"),
    "MA": ("Massachusetts", "US", "United States"),
    "IL": ("Illinois", "US", "United States"),
}

COUNTRY_FULL = {
    "CA": "Canada",
    "US": "United States",
    "UK": "United Kingdom",
}

# Indeed's country enum uses a couple of non-ISO exceptions (UK, not GB).
_INDEED_COUNTRY_EXCEPTIONS = {"GB": "uk", "UK": "uk"}

# Sentinel emitted (one per entry.countries) when entry.locations is empty:
# "don't constrain by city, only by country". It carries its own country.
COUNTRY_LEVEL = "__COUNTRY_LEVEL__"


def country_level_token(iso2: str) -> str:
    """A COUNTRY_LEVEL location that carries its ISO-2 country."""
    return f"{COUNTRY_LEVEL}:{iso2.upper()}"


def is_country_level(loc: str) -> bool:
    return loc.startswith(COUNTRY_LEVEL)


def _country_level_iso(loc: str) -> str:
    return loc.split(":", 1)[1].upper()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

class ArgError(ValueError):
    """Raised for unrecognized / conflicting invocation arguments (fail loudly)."""


def resolve_source(token: str) -> list[str]:
    """Resolve one source token to a list of canonical Actor full-names."""
    t = token.strip()
    low = t.lower()
    if low == "all":
        return list(_ALL_SOURCES)
    if low in _SOURCE_ALIASES:
        return [_SOURCE_ALIASES[low]]
    if "/" in t:
        # full actor slug — used as-is (must be re-verified before adoption).
        return [t]
    raise ArgError(f"unrecognized source: {token!r}")


def parse_args(arg_string: str, entry_names: list[str]):
    """
    Parse `/fetch-jobs [N] [source] [entry]` arguments.

    Returns (M, sources, entry_filter):
      M            -> requested recency in days (int) or None if absent
      sources      -> list of canonical Actor full-names (default [LINKEDIN])
      entry_filter -> a single entry name (str) or None for ALL entries

    `source` and `entry` are both non-numeric and order-independent: each token
    is classified against the source aliases / slug rule first, then the entry
    names. Unknown tokens, or a second source/entry, are errors.
    """
    tokens = (arg_string or "").split()
    M: Optional[int] = None
    sources: Optional[list[str]] = None
    entry_filter: Optional[str] = None

    for tok in tokens:
        if re.fullmatch(r"\d+", tok):
            if M is not None:
                raise ArgError(f"more than one numeric (N) argument: {tok!r}")
            M = int(tok)
            continue

        low = tok.lower()
        is_source = (low == "all") or (low in _SOURCE_ALIASES) or ("/" in tok)
        if is_source:
            if sources is not None:
                raise ArgError(f"more than one source selector: {tok!r}")
            sources = resolve_source(tok)
            continue

        # Entry name match is exact and case-sensitive.
        if tok in entry_names:
            if entry_filter is not None:
                raise ArgError(f"more than one entry selector: {tok!r}")
            entry_filter = tok
            continue

        raise ArgError(
            f"unrecognized argument: {tok!r} "
            f"(not a number, source alias/slug, or known entry name)"
        )

    if sources is None:
        sources = [DEFAULT_SOURCE]
    return M, sources, entry_filter


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------

def snap_window(M: Optional[int]) -> int:
    """
    Snap the requested window to one of the two supported windows (1 or 7).
      absent      -> 7 (default; resilient to skipped Cowork runs)
      M <= 1      -> 1 (daily)
      M >= 2      -> 7 (weekly; everything from 2 upward rounds UP to 7)
    """
    if M is None:
        return 7
    if M <= 1:
        return 1
    return 7


def effective_days(M: Optional[int]) -> int:
    """
    Days used for the POST-FETCH date safety check. We fetch the snapped
    superset window but trim to exactly what the caller asked for (capped at the
    7-day ceiling, since we never fetch wider than 7). This is what makes
    `/fetch-jobs 3` actually return ~3 days rather than 7.
      absent -> 7 ; otherwise min(M, 7)
    """
    if M is None:
        return 7
    return min(M, 7)


def time_range_linkedin(N: int) -> str:
    return "24h" if N == 1 else "7d"


def from_days_indeed(N: int) -> str:
    # STRING enum, not int.
    return "1" if N == 1 else "7"


def days_old_glassdoor(N: int) -> int:
    return N


# ---------------------------------------------------------------------------
# Location translation
# ---------------------------------------------------------------------------

def _region_of(loc: str) -> str:
    """Region abbreviation = the token after the last comma in 'City, Region'."""
    if "," not in loc:
        raise ArgError(f"location is not 'City, Region': {loc!r}")
    return loc.rsplit(",", 1)[1].strip()


def country_of(loc: str, countries: list[str]) -> str:
    """
    Derive ISO-2 country for a location, read positionally (region -> country),
    and assert it is within the entry's declared countries (sanity bound).
    COUNTRY_LEVEL tokens carry their own country.
    """
    if is_country_level(loc):
        iso = _country_level_iso(loc)
    else:
        region = _region_of(loc)
        if region not in REGION_MAP:
            raise ArgError(
                f"unknown region {region!r} in location {loc!r}; "
                f"add it to REGION_MAP in common.py"
            )
        iso = REGION_MAP[region][1]
    if countries and iso not in [c.upper() for c in countries]:
        raise ArgError(
            f"location {loc!r} resolves to country {iso!r}, "
            f"which is not in entry.countries {countries!r}"
        )
    return iso


def _apply_override(actor_location_format: dict, actor: str, loc: str):
    """Return a per-Actor override string for this location if config defines one."""
    if not actor_location_format:
        return None
    actor_map = actor_location_format.get(actor) or {}
    return actor_map.get(loc)


def li_location_string(loc: str, country: str, actor_location_format=None) -> str:
    """
    LinkedIn locationSearch element: "City, <Full region>, <Full country>",
    English names, no geo IDs. COUNTRY_LEVEL -> "<Full country>".
    """
    ov = _apply_override(actor_location_format or {}, LINKEDIN, loc)
    if ov is not None:
        return ov
    if is_country_level(loc):
        return COUNTRY_FULL.get(country, country)
    city = loc.rsplit(",", 1)[0].strip()
    region = _region_of(loc)
    full_region, _iso, full_country = REGION_MAP[region]
    return f"{city}, {full_region}, {full_country}"


def indeed_location_string(loc: str, actor_location_format=None) -> str:
    """
    Indeed location: "City, <Region abbrev>" (country is a separate param).
    COUNTRY_LEVEL -> "" (the country param alone scopes it). Pair with radius "0".
    """
    ov = _apply_override(actor_location_format or {}, INDEED, loc)
    if ov is not None:
        return ov
    if is_country_level(loc):
        return ""
    return loc  # already "City, Region"


def indeed_country_code(country: str) -> str:
    """Indeed country enum: ISO-2 lowercased, with exceptions (UK not GB)."""
    iso = country.upper()
    if iso in _INDEED_COUNTRY_EXCEPTIONS:
        return _INDEED_COUNTRY_EXCEPTIONS[iso]
    return iso.lower()


def glassdoor_location_string(loc: str, country: str, actor_location_format=None) -> str:
    """
    Glassdoor location (required, non-empty): "City, <Region abbrev>".
    COUNTRY_LEVEL falls back to the country full name (location may not be empty).
    """
    ov = _apply_override(actor_location_format or {}, GLASSDOOR, loc)
    if ov is not None:
        return ov
    if is_country_level(loc):
        return country_to_location(country)
    return loc  # "City, Region"


def country_to_location(country: str) -> str:
    """Glassdoor COUNTRY_LEVEL fallback. CA->Canada, US->United States."""
    return COUNTRY_FULL.get(country.upper(), country)


# ---------------------------------------------------------------------------
# Job type translation
# ---------------------------------------------------------------------------

_JOBTYPE_LINKEDIN = {
    "full-time": "FULL_TIME",
    "part-time": "PART_TIME",
    "contract": "CONTRACTOR",
    "temporary": "TEMPORARY",
    "internship": "INTERN",
    "intern": "INTERN",
    "volunteer": "VOLUNTEER",
}
_JOBTYPE_INDEED = {
    "full-time": "fulltime",
    "part-time": "parttime",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
    "intern": "internship",
    "permanent": "permanent",
    "freelance": "freelance",
    "seasonal": "seasonal",
}


def translate_jobtype(jt, actor: str):
    """
    Map job_type(s) for an Actor.
      LinkedIn -> returns the full mapped LIST (EmploymentTypeFilter array).
      Indeed   -> pass a single string; returns the single mapped value.
    Glassdoor has no native job_type (post-fetch only) -> returns None.
    """
    if actor == LINKEDIN:
        items = jt if isinstance(jt, (list, tuple)) else [jt]
        out = []
        for v in items:
            mapped = _JOBTYPE_LINKEDIN.get(str(v).lower())
            if mapped and mapped not in out:
                out.append(mapped)
        return out
    if actor == INDEED:
        if isinstance(jt, (list, tuple)):
            raise ArgError("Indeed accepts one job_type per call; pass a single value")
        return _JOBTYPE_INDEED.get(str(jt).lower())
    return None


# ---------------------------------------------------------------------------
# Workplace translation
# ---------------------------------------------------------------------------

_WORKPLACE_CANON = {"on_site", "hybrid", "remote"}


def translate_workplace_linkedin(workplace_type: list[str]):
    """
    LinkedIn aiWorkArrangementFilter[] (BETA). Returns the token list, or None
    when the request covers ALL arrangements (no constraint -> omit the filter,
    avoid needless reliance on BETA AI enrichment).
      on_site -> On-site ; hybrid -> Hybrid ; remote -> Remote OK + Remote Solely
    """
    wp = set(workplace_type or [])
    if not wp or wp >= _WORKPLACE_CANON:
        return None  # unconstrained -> don't send the BETA filter
    tokens = []
    if "on_site" in wp:
        tokens.append("On-site")
    if "hybrid" in wp:
        tokens.append("Hybrid")
    if "remote" in wp:
        tokens.extend(["Remote OK", "Remote Solely"])
    return tokens or None


def workplace_to_indeed(workplace_type: list[str]):
    """
    Indeed `remote` enum is "remote" | "hybrid" | unset. It cannot express
    on_site, nor both remote+hybrid at once. Only set it when the request is
    EXACTLY remote-only or hybrid-only; otherwise leave unset and enforce
    post-fetch.
    """
    wp = set(workplace_type or [])
    if wp == {"remote"}:
        return "remote"
    if wp == {"hybrid"}:
        return "hybrid"
    return None  # unset -> post-fetch


def workplace_is_constraining(workplace_type: list[str]) -> bool:
    """True iff workplace_type is a proper, non-empty subset of the 3 canon values."""
    wp = set(workplace_type or [])
    return bool(wp) and wp < _WORKPLACE_CANON


# ---------------------------------------------------------------------------
# Title exclusions
# ---------------------------------------------------------------------------

def expand_variants(title_exclude: list[str]) -> list[str]:
    """
    Identity pass. The live config already lists abbreviation AND spelled-out
    forms by hand ("VP", "Vice President"), so auto-expansion is intentionally
    NOT done here (single owner = the config). This seam exists only so that, if
    that ownership ever moves, the expansion logic has one obvious home.
    """
    return list(title_exclude or [])


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

def make_job_id(prefix: str, raw_source_id) -> str:
    return f"{prefix}_{raw_source_id}"


def strip_prefix(job_id: str) -> str:
    return job_id.split("_", 1)[1] if "_" in job_id else job_id


def raw_ids_for(prefix: str, seen: list[str]) -> list[str]:
    """
    Raw (native) source IDs for one prefix, pulled out of the skill's prefixed
    job_ids in seen_jobs.json. Used for Glassdoor's excludeJobIds, which expects
    Glassdoor's OWN ID space, not the skill's "gd_..." handles.
    """
    pre = prefix + "_"
    return [strip_prefix(j) for j in (seen or []) if isinstance(j, str) and j.startswith(pre)]


# ---------------------------------------------------------------------------
# OR-join for single-string keyword Actors (Indeed query, Glassdoor keywords)
# ---------------------------------------------------------------------------

def or_join(titles: list[str]) -> str:
    return " OR ".join(titles or [])
