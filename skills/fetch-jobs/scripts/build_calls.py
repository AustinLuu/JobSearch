#!/usr/bin/env python3
"""
build_calls.py — turn `/fetch-jobs [N] [source] [entry]` + search_config.json
into a concrete, ordered list of Apify Actor calls (the "call plan").

This script does ALL the canonical->Actor translation and the per-location /
per-job_type / per-title fan-out. It does NOT call Apify (the skill driver does
that, via the Apify connector). It writes:

    <JOBSEARCH_DIR>/.fetch-runs/<run_id>/plan.json
    <JOBSEARCH_DIR>/.fetch-runs/<run_id>/raw/      (empty dir for the driver)

and prints the plan + step-by-step instructions for the driver.

Usage:
    python build_calls.py "<raw args>"            # e.g. "7 all swe_north_america"
    python build_calls.py "1 indeed"
    python build_calls.py ""                       # defaults: 7, linkedin, all entries

Optional env:
    JOBSEARCH_DIR   override the JobSearch root (default: two levels up from this
                    script, i.e. .../JobSearch/skills/fetch-jobs/scripts -> JobSearch)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import common as C

# Delete .fetch-runs/ subfolders older than this many days on each run.
RUN_RETENTION_DAYS = 14


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


def build_plan(args: str, config: dict, seen: list[str]):
    searches = config.get("searches", [])
    glob = config.get("global", {})
    entry_names = [e["name"] for e in searches]

    M, sources, entry_filter = C.parse_args(args, entry_names)
    N = C.snap_window(M)
    eff_days = C.effective_days(M)

    if entry_filter is None:
        entries = searches
    else:
        entries = [e for e in searches if e["name"] == entry_filter]
        if not entries:
            raise C.ArgError(f"unknown entry name: {entry_filter!r}")

    cap = int(glob.get("max_results_per_source_per_search", 20))
    actor_loc_fmt = glob.get("actor_location_format", {}) or {}
    enforcement = glob.get("actor_enforcement", {}) or {}

    # Deployment-tunable globals (read with safe defaults; not in the base config).
    agency_action = glob.get("agency_action", "annotate")          # annotate|drop_source|drop_post_fetch
    multi_title = glob.get("multi_title_strategy", "or_join")      # or_join|per_title

    time_range_li = C.time_range_linkedin(N)
    from_days_in = C.from_days_indeed(N)
    days_old_gd = C.days_old_glassdoor(N)

    gd_exclude_ids = C.raw_ids_for("gd", seen)

    calls = []
    call_id = 0

    for entry in entries:
        ename = entry["name"]
        titles = entry.get("titles", [])
        title_excl = C.expand_variants(entry.get("title_exclude", []))
        locations = entry.get("locations") or []
        countries = entry.get("countries", [])
        workplace = entry.get("workplace_type", [])
        job_types = entry.get("job_type", [])

        # Empty locations -> one COUNTRY_LEVEL sentinel per declared country.
        if locations:
            loc_list = list(locations)
        else:
            loc_list = [C.country_level_token(c) for c in countries]

        for actor in sources:
            for loc in loc_list:
                country = C.country_of(loc, countries)

                if actor == C.LINKEDIN:
                    inp = {
                        "titleSearch": titles,
                        "titleExclusionSearch": title_excl,
                        "locationSearch": [C.li_location_string(loc, country, actor_loc_fmt)],
                        "timeRange": time_range_li,
                        "EmploymentTypeFilter": C.translate_jobtype(job_types, actor),
                        "descriptionType": "text",
                        "includeAi": True,   # needed for ai_work_arrangement / ai_salary_* / agency-derived
                        "limit": max(10, cap),
                    }
                    wp_tokens = C.translate_workplace_linkedin(workplace)
                    if wp_tokens:
                        inp["aiWorkArrangementFilter"] = wp_tokens
                    if agency_action == "drop_source":
                        inp["removeAgency"] = True
                    # aiHasSalary intentionally UNSET (has-any-salary, not a floor).
                    calls.append(_mk_call(call_id, actor, ename, loc, country, inp))
                    call_id += 1

                elif actor == C.INDEED:
                    title_variants = titles if multi_title == "per_title" else [None]
                    for jt in job_types:
                        for tv in title_variants:
                            query = tv if tv is not None else C.or_join(titles)
                            inp = {
                                "query": query,
                                "location": C.indeed_location_string(loc, actor_loc_fmt),
                                "country": C.indeed_country_code(country),
                                "radius": (enforcement.get(actor, {})
                                           .get("call_defaults", {}) or {}).get("radius", "0"),
                                "fromDays": from_days_in,
                                "jobType": C.translate_jobtype(jt, actor),
                                "enableUniqueJobs": True,
                                "includeSimilarJobs": False,
                                "sort": "date",
                                "maxRows": cap,
                            }
                            rem = C.workplace_to_indeed(workplace)
                            if rem:
                                inp["remote"] = rem
                            calls.append(_mk_call(call_id, actor, ename, loc, country, inp))
                            call_id += 1

                elif actor == C.GLASSDOOR:
                    title_variants = titles if multi_title == "per_title" else [None]
                    for tv in title_variants:
                        keywords = tv if tv is not None else C.or_join(titles)
                        inp = {
                            "keywords": keywords,
                            "location": C.glassdoor_location_string(loc, country, actor_loc_fmt),
                            "daysOld": days_old_gd,
                            "limit": cap,
                        }
                        if gd_exclude_ids:
                            inp["excludeJobIds"] = gd_exclude_ids
                        calls.append(_mk_call(call_id, actor, ename, loc, country, inp))
                        call_id += 1

                else:
                    # Unknown / full-slug Actor: no translation surface defined.
                    raise C.ArgError(
                        f"actor {actor!r} has no translation rules; add an "
                        f"actor_enforcement entry and a build branch before use"
                    )

    meta = {
        "requested_M": M,
        "snapped_window_N": N,
        "effective_days_for_date_check": eff_days,
        "sources": sources,
        "entry_filter": entry_filter,
        "cap_per_call": cap,
        "agency_action": agency_action,
        "multi_title_strategy": multi_title,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return meta, calls


def _prune_old_runs(runs_root: Path, keep_days: int):
    """Best-effort cleanup of transient run dirs older than keep_days."""
    if not runs_root.exists():
        return
    cutoff = time.time() - keep_days * 86400
    for child in runs_root.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            pass


def _mk_call(call_id, actor, ename, loc, country, inp):
    return {
        "id": call_id,
        "actor": actor,
        "source_actor": actor,
        "source": C.ACTOR_SOURCE_NAME.get(actor, actor),
        "source_search_name": ename,
        "location": loc,
        "country": country,
        "input": inp,
    }


def main():
    args = sys.argv[1] if len(sys.argv) > 1 else ""
    root = jobsearch_dir()
    config = load_json(root / "search_config.json", {})
    seen = load_json(root / "seen_jobs.json", [])

    try:
        meta, calls = build_plan(args, config, seen)
    except C.ArgError as e:
        print(f"FETCH-JOBS ARG ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

    runs_root = root / ".fetch-runs"
    _prune_old_runs(runs_root, RUN_RETENTION_DAYS)

    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = runs_root / run_id
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)

    plan = {"meta": meta, "calls": calls}
    plan_path = run_dir / "plan.json"
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    # Human / driver-facing summary.
    print("=" * 70)
    print("FETCH-JOBS CALL PLAN")
    print("=" * 70)
    print(json.dumps(meta, indent=2))
    print(f"\nrun_dir   : {run_dir}")
    print(f"plan_path : {plan_path}")
    print(f"total Apify calls to make: {len(calls)}")
    print("-" * 70)
    for c in calls:
        print(f"[{c['id']:>3}] {c['source']:<9} {c['source_search_name']:<28} "
              f"loc={c['location']}")
    print("-" * 70)
    print("DRIVER INSTRUCTIONS:")
    print(f"  For each call i in plan.json['calls']: invoke the Apify connector")
    print(f"  `call-actor` with actor=call['actor'], input=call['input'].")
    print(f"  Save the returned dataset items (a JSON array) to:")
    print(f"      {run_dir / 'raw'}/<i>.json")
    print(f"  Then run:  python process_results.py \"{run_dir}\"")
    print("=" * 70)
    # Machine-readable last line for easy capture by the driver.
    print(f"RUN_DIR={run_dir}")


if __name__ == "__main__":
    main()
