#!/usr/bin/env python3
"""
process_results.py — normalize, post-fetch filter, dedupe, and cap the raw
Apify results produced by a build_calls.py run.

Reads:
    <run_dir>/plan.json
    <run_dir>/raw/<call_id>.json      (one JSON array of dataset items per call)
    <JOBSEARCH_DIR>/search_config.json
    <JOBSEARCH_DIR>/seen_jobs.json

Writes:
    <run_dir>/listings.json           (the normalized output array for /score-job)
    <run_dir>/run-summary.json        (counts + drop reasons, for debugging)

This script does NOT update seen_jobs.json — that is the orchestrator's job
after the full pipeline succeeds (a mid-run failure must not poison dedupe
state).

Field mappings verified against live Apify output schemas on 2026-05-31.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import common as C


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def jobsearch_dir() -> Path:
    # The job-search data folder, independent of where this skill is installed.
    # 1) JOBSEARCH_DIR env if set; 2) the standard ~/Documents/JobSearch; 3) the
    # repo layout (scripts/ -> fetch-jobs/ -> skills/ -> JobSearch/) as a fallback.
    env = os.environ.get("JOBSEARCH_DIR")
    if env:
        return Path(env).expanduser()
    default = Path.home() / "Documents" / "JobSearch"
    if (default / "search_config.json").exists():
        return default
    return Path(__file__).resolve().parents[3]


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Salary normalization
# ---------------------------------------------------------------------------

_PERIOD_TO_ANNUAL = {
    "annual": 1, "annually": 1, "year": 1, "yearly": 1, "yr": 1,
    "month": 12, "monthly": 12, "mo": 12,
    "week": 52, "weekly": 52, "wk": 52,
    "day": 260, "daily": 260,
    # hour handled separately via config multiplier
}


def _infer_currency(country: str):
    return {"CA": "CAD", "US": "USD", "UK": "GBP"}.get((country or "").upper())


def _norm_period(raw):
    if not raw:
        return None
    r = str(raw).strip().lower()
    if r in ("hour", "hourly", "hr", "per hour"):
        return "hourly"
    for key in _PERIOD_TO_ANNUAL:
        if r.startswith(key):
            return "annual_like:" + key
    if "hour" in r:
        return "hourly"
    if "year" in r or "annual" in r:
        return "annual_like:annual"
    if "month" in r:
        return "annual_like:month"
    return None


def normalize_salary(smin, smax, currency, period_raw, country, hourly_mult):
    """
    Return {min, max, currency, period} with min/max annualized and
    period == "annual" (or all-null if nothing stated). currency falls back to
    the role's country currency. No FX conversion is ever applied.
    """
    out = {"min": None, "max": None,
           "currency": currency or _infer_currency(country),
           "period": None}

    def _num(x):
        try:
            if x is None:
                return None
            v = float(x)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    mn, mx = _num(smin), _num(smax)
    if mn is None and mx is None:
        return {"min": None, "max": None, "currency": None, "period": None}

    p = _norm_period(period_raw)
    assumed = False
    if p == "hourly":
        mult = float(hourly_mult)
    elif p and p.startswith("annual_like:"):
        mult = _PERIOD_TO_ANNUAL[p.split(":", 1)[1]]
    else:
        # Unintelligible / missing period. These boards overwhelmingly post
        # ANNUAL figures, so assume annual (mult = 1) rather than guessing from
        # magnitude (a <2000 heuristic misreads monthly/weekly pay by 2080x).
        # Flag it so the assumption is visible downstream.
        mult = 1
        assumed = True

    if mn is not None:
        out["min"] = round(mn * mult)
    if mx is not None:
        out["max"] = round(mx * mult)
    out["period"] = "annual"
    if assumed:
        out["period_assumed"] = True
    return out


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_REL_RE = re.compile(r"(\d+)\s*\+?\s*day", re.I)


def parse_iso_date(s):
    if not s:
        return None
    s = str(s)
    # Trim time / timezone, keep the date part.
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def parse_relative_age(s, today):
    if not s:
        return None
    s = str(s).strip().lower()
    if s in ("today", "just posted", "just now"):
        return today
    m = _REL_RE.search(s)
    if m:
        return today - timedelta(days=int(m.group(1)))
    return None


# ---------------------------------------------------------------------------
# Per-Actor normalizers
# ---------------------------------------------------------------------------

def _first(seq):
    if isinstance(seq, (list, tuple)) and seq:
        return seq[0]
    return None


def _map_li_workplace(item):
    wa = item.get("ai_work_arrangement")
    if wa:
        w = str(wa).strip().lower()
        if w == "on-site":
            return "on_site"
        if w == "hybrid":
            return "hybrid"
        if w.startswith("remote"):
            return "remote"
    if item.get("remote_derived") is True:
        return "remote"
    return None


def normalize_linkedin(item, tag, today, hourly_mult):
    raw_id = item.get("id") or item.get("linkedin_id")
    country = (_first(item.get("countries_derived")) or tag["country"])
    sal = normalize_salary(
        item.get("ai_salary_minvalue"), item.get("ai_salary_maxvalue"),
        item.get("ai_salary_currency"), item.get("ai_salary_unittext"),
        tag["country"], hourly_mult,
    )
    return {
        "job_id": C.make_job_id("li", raw_id),
        "raw_source_id": str(raw_id) if raw_id is not None else None,
        "source": "linkedin",
        "source_actor": C.LINKEDIN,
        "company": item.get("organization"),
        "title": item.get("title"),
        "location": _first(item.get("locations_derived")) or item.get("location_type"),
        "workplace_type": _map_li_workplace(item),
        "salary": sal,
        "is_agency": item.get("linkedin_org_recruitment_agency_derived"),
        "url": item.get("url") or item.get("external_apply_url"),
        "description": item.get("description_text"),
        "date_posted": _iso_or_none(item.get("date_posted") or item.get("date_created")),
        "source_search_name": [tag["source_search_name"]],
    }


def normalize_indeed(item, tag, today, hourly_mult):
    raw_id = item.get("jobKey")
    loc = item.get("location") or {}
    sal_obj = item.get("salary") or {}
    sal = normalize_salary(
        sal_obj.get("salaryMin"), sal_obj.get("salaryMax"),
        sal_obj.get("salaryCurrency"), sal_obj.get("salaryType"),
        tag["country"], hourly_mult,
    )
    # date: prefer datePublished (ISO), else postedToday/age relative.
    dp = parse_iso_date(item.get("datePublished"))
    if dp is None and item.get("postedToday"):
        dp = today
    if dp is None:
        dp = parse_relative_age(item.get("age"), today)
    return {
        "job_id": C.make_job_id("in", raw_id),
        "raw_source_id": str(raw_id) if raw_id is not None else None,
        "source": "indeed",
        "source_actor": C.INDEED,
        "company": item.get("companyName"),
        "title": item.get("title"),
        "location": (loc.get("formattedAddressShort") or loc.get("city")
                     or loc.get("fullAddress")),
        "workplace_type": "remote" if item.get("isRemote") else None,
        "salary": sal,
        "is_agency": None,
        "url": item.get("jobUrl") or item.get("applyUrl"),
        "description": item.get("descriptionText"),
        "date_posted": dp.isoformat() if dp else None,
        "source_search_name": [tag["source_search_name"]],
    }


def normalize_glassdoor(item, tag, today, hourly_mult):
    raw_id = item.get("id")
    emp = item.get("employer") or {}
    loc = item.get("location") or {}
    pay = item.get("pay") or {}
    sal = normalize_salary(
        pay.get("min"), pay.get("max"), pay.get("currency"), pay.get("period"),
        tag["country"], hourly_mult,
    )
    # Glassdoor has no absolute date field -> derive from ageInDays.
    age = item.get("ageInDays")
    dp = None
    if isinstance(age, (int, float)):
        dp = today - timedelta(days=int(age))
    return {
        "job_id": C.make_job_id("gd", raw_id),
        "raw_source_id": str(raw_id) if raw_id is not None else None,
        "source": "glassdoor",
        "source_actor": C.GLASSDOOR,
        "company": emp.get("name"),
        "title": item.get("title"),
        "location": loc.get("name"),
        "workplace_type": None,  # Glassdoor exposes nothing -> always post-fetch/unknown
        "salary": sal,
        "is_agency": None,
        "url": item.get("url") or item.get("seoUrl"),
        "description": item.get("description"),
        "date_posted": dp.isoformat() if dp else None,
        "source_search_name": [tag["source_search_name"]],
    }


def _iso_or_none(s):
    d = parse_iso_date(s)
    return d.isoformat() if d else None


_NORMALIZERS = {
    C.LINKEDIN: normalize_linkedin,
    C.INDEED: normalize_indeed,
    C.GLASSDOOR: normalize_glassdoor,
}


# ---------------------------------------------------------------------------
# Post-fetch filters (each keyed on the listing's source_actor via enforcement)
# ---------------------------------------------------------------------------

def _norm_text(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


# Company-name suffixes stripped for cross-board dedupe (so "Google" == "Google LLC").
_COMPANY_SUFFIXES = ("incorporated", "inc", "llc", "l.l.c", "ltd", "limited",
                     "corporation", "corp", "company", "co", "gmbh", "plc", "sa", "ag")


def _company_key(name):
    t = re.sub(r"[^a-z0-9 ]", " ", _norm_text(name))
    t = re.sub(r"\s+", " ", t).strip()
    parts = t.split()
    while parts and parts[-1] in _COMPANY_SUFFIXES:
        parts.pop()
    return " ".join(parts) or t


def _city_token(location):
    # First comma-separated token, normalized: tolerates "Toronto, Ontario,
    # Canada" (LinkedIn) vs "Toronto, ON" (Indeed/Glassdoor) for cross-board dedupe.
    return _norm_text(str(location or "").split(",")[0])


def title_matches_allowlist(title, titles):
    t = _norm_text(title)
    return any(_norm_text(x) in t for x in titles if x)


def title_hits_exclude(title, excludes):
    t = _norm_text(title)
    return any(_norm_text(x) and _norm_text(x) in t for x in excludes)


def salary_passes(rec, min_salary, match_field, unknown_action):
    val = (rec.get("salary") or {}).get(match_field)
    if val is None:
        return unknown_action != "exclude"   # include unless explicitly excluded
    try:
        return float(val) >= float(min_salary)
    except (TypeError, ValueError):
        return unknown_action != "exclude"


def workplace_passes(rec, workplace_type):
    if not C.workplace_is_constraining(workplace_type):
        return True  # unconstrained (all 3) -> no-op
    wt = rec.get("workplace_type")
    if wt is None:
        return True  # unknown -> keep (superset / don't under-collect)
    return wt in set(workplace_type)


# ---------------------------------------------------------------------------
# Dedupe + cap
# ---------------------------------------------------------------------------

def _hash_key(rec):
    # Cross-board / cross-search key. Uses a normalized company key and city
    # token so the SAME job collapses even when boards format the strings
    # differently (e.g. "Google" vs "Google LLC", "Toronto, Ontario, Canada"
    # vs "Toronto, ON").
    return (_company_key(rec.get("company")), _norm_text(rec.get("title")),
            _city_token(rec.get("location")))


def _within_actor_key(rec):
    # A true within-Actor repost is identical across title+company+location+salary.
    # Location is included so distinct same-company roles in different cities are
    # NOT collapsed here (the per-employer cap handles volume separately).
    sal = rec.get("salary") or {}
    return (rec.get("source_actor"), _norm_text(rec.get("title")),
            _norm_text(rec.get("company")), _norm_text(rec.get("location")),
            sal.get("min"), sal.get("max"))


def _merge_search_names(dst, src):
    names = dst.get("source_search_name") or []
    for n in src.get("source_search_name") or []:
        if n not in names:
            names.append(n)
    dst["source_search_name"] = names


def collapse(records, key_fn):
    """Keep first occurrence per key; merge source_search_name tags into it."""
    out = []
    index = {}
    for r in records:
        k = key_fn(r)
        if k in index:
            _merge_search_names(index[k], r)
        else:
            index[k] = r
            out.append(r)
    return out


def cap_per_employer(records, cap):
    if not cap or cap <= 0:
        return records
    counts = {}
    out = []
    for r in records:
        emp = _norm_text(r.get("company"))
        counts[emp] = counts.get(emp, 0) + 1
        if counts[emp] <= cap:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process(run_dir: Path, config: dict, seen: list[str], today: date):
    plan = load_json(run_dir / "plan.json", None)
    if plan is None:
        raise SystemExit(f"no plan.json in {run_dir}")
    meta = plan["meta"]
    calls = plan["calls"]

    glob = config.get("global", {})
    hourly_mult = (glob.get("salary_normalization", {})
                   .get("hourly_to_annual_multiplier", 2080))
    salary_unknown = glob.get("salary_unknown_action", "include")
    exclude_companies = {_norm_text(c) for c in glob.get("exclude_companies", [])}
    max_per_emp = glob.get("max_per_employer", 0)
    enforcement = glob.get("actor_enforcement", {}) or {}
    agency_action = meta.get("agency_action", "annotate")
    eff_days = meta.get("effective_days_for_date_check", 7)
    date_after = today - timedelta(days=eff_days)

    # Index entries by name to recover their per-entry filter params.
    entries_by_name = {e["name"]: e for e in config.get("searches", [])}

    stats = {"raw_items": 0, "normalized": 0, "missing_raw_files": [], "drops": {}}

    def drop(reason, n=1):
        stats["drops"][reason] = stats["drops"].get(reason, 0) + n

    normalized = []
    for call in calls:
        raw_path = run_dir / "raw" / f"{call['id']}.json"
        items = load_json(raw_path, None)
        if items is None:
            stats["missing_raw_files"].append(call["id"])
            continue
        if isinstance(items, dict):  # tolerate {items:[...]} or {data:[...]}
            items = items.get("items") or items.get("data") or []
        stats["raw_items"] += len(items)
        actor = call["source_actor"]
        normalizer = _NORMALIZERS.get(actor)
        if normalizer is None:
            continue
        tag = {"source_search_name": call["source_search_name"],
               "country": call["country"], "location": call["location"]}
        for it in items:
            try:
                rec = normalizer(it, tag, today, hourly_mult)
            except Exception as e:  # never let one bad row kill the batch
                drop(f"normalize_error:{type(e).__name__}")
                continue
            if not rec.get("raw_source_id"):
                drop("missing_id")
                continue
            rec["_entry"] = call["source_search_name"]
            normalized.append(rec)

    stats["normalized"] = len(normalized)

    # ---- Post-fetch filtering -------------------------------------------
    kept = []
    for r in normalized:
        entry = entries_by_name.get(r["_entry"], {})
        pf = set(enforcement.get(r["source_actor"], {}).get("post_fetch", []))

        # exclude_companies: global, all actors.
        if _norm_text(r.get("company")) in exclude_companies:
            drop("exclude_company")
            continue

        # agency drop (post-fetch policy) — LinkedIn only carries the flag.
        if agency_action == "drop_post_fetch" and r.get("is_agency") is True:
            drop("agency_post_fetch")
            continue

        # title allow-list (Indeed + Glassdoor: catch keyword/fuzzy leaks).
        if "title_allowlist" in pf and entry.get("titles"):
            if not title_matches_allowlist(r.get("title"), entry["titles"]):
                drop("title_allowlist")
                continue

        # title_exclude (Indeed + Glassdoor post-fetch; LinkedIn native).
        if "title_exclude" in pf and entry.get("title_exclude"):
            if title_hits_exclude(r.get("title"), entry["title_exclude"]):
                drop("title_exclude")
                continue

        # salary floor (post-fetch on EVERY board, so always applied).
        if not salary_passes(r, entry.get("min_salary", 0),
                             entry.get("salary_match_field", "max"),
                             salary_unknown):
            drop("salary_floor")
            continue

        # workplace type.
        if "workplace_type" in pf and not workplace_passes(r, entry.get("workplace_type")):
            drop("workplace_type")
            continue

        # date safety check (all boards). Keep rows with unknown dates rather
        # than silently dropping (superset) but flag them in stats.
        dp = parse_iso_date(r.get("date_posted"))
        if dp is None:
            drop("date_unknown_kept")
        elif dp < date_after:
            drop("date_too_old")
            continue

        kept.append(r)

    # ---- Dedupe (three scopes, order matters) ---------------------------
    before = len(kept)
    kept = collapse(kept, _within_actor_key)      # within-Actor reposts first
    drop("dedupe_within_actor", before - len(kept))

    before = len(kept)
    kept = collapse(kept, _hash_key)               # cross-board / cross-search
    drop("dedupe_cross_board", before - len(kept))

    seen_set = set(seen or [])
    before = len(kept)
    kept = [r for r in kept if r["job_id"] not in seen_set]   # cross-run
    drop("dedupe_cross_run", before - len(kept))

    # ---- Per-employer cap (AFTER dedup) ---------------------------------
    before = len(kept)
    kept = cap_per_employer(kept, max_per_emp)
    drop("employer_cap", before - len(kept))

    # Drop internal helper field.
    for r in kept:
        r.pop("_entry", None)

    return meta, kept, stats


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python process_results.py <run_dir>")
    run_dir = Path(sys.argv[1]).expanduser()
    root = jobsearch_dir()
    config = load_json(root / "search_config.json", {})
    seen = load_json(root / "seen_jobs.json", [])
    today = date.today()

    meta, listings, stats = process(run_dir, config, seen, today)

    out_path = run_dir / "listings.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)

    summary = {"meta": meta, "stats": stats, "final_count": len(listings),
               "listings_path": str(out_path)}
    with (run_dir / "run-summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 70)
    print("FETCH-JOBS RESULTS")
    print("=" * 70)
    print(f"raw items fetched : {stats['raw_items']}")
    print(f"normalized        : {stats['normalized']}")
    if stats["missing_raw_files"]:
        print(f"!! missing raw files for call ids: {stats['missing_raw_files']}")
    print("drop / dedupe breakdown:")
    for k, v in sorted(stats["drops"].items()):
        if v:
            print(f"    {k:<24} {v}")
    print("-" * 70)
    print(f"FINAL LISTINGS    : {len(listings)}")
    print(f"written to        : {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
# end of process_results.py
