# fetch-jobs skill

Discovery front-end for the resume-tailoring pipeline (Phase 1 of `build-plan.md`).
Implements `fetch-jobs-skill-spec.md`. Given `/fetch-jobs [N] [source] [entry]`,
it pulls recent listings from LinkedIn / Indeed / Glassdoor via the Apify
connector, applies the deterministic hard filters from `search_config.json`, and
returns a normalized, deduped array for `/score-job`.

## Layout

```
skills/fetch-jobs/
  SKILL.md                 # the procedure the model follows when /fetch-jobs runs
  README.md                # this file
  scripts/
    common.py              # translation + grounding helpers (pure, testable)
    build_calls.py         # args + config -> the Apify call plan
    process_results.py     # raw items -> normalized, filtered, deduped array
  tests/
    test_fetch_jobs.py     # unit tests for the deterministic core
    test_integration.py    # end-to-end on the live config + synthetic results
```

## How it runs (three stages)

1. `build_calls.py "<args>"` → writes `~/Documents/JobSearch/.fetch-runs/<run_id>/plan.json`.
2. The model executes each call in the plan via the **Apify connector** and saves
   each result set to `<run_dir>/raw/<id>.json`.
3. `process_results.py <run_dir>` → writes `<run_dir>/listings.json` (the output).

The Apify calls happen through the connector (Cowork-scheduled path). The two
Python modules are the deterministic core and are reused verbatim by the
cloud-headless variant — only the call execution in stage 2 swaps to direct
Apify API calls.

## Install (Cowork)

This skill currently lives in the project folder. To make `/fetch-jobs`
invokable, copy the `fetch-jobs/` directory into your Cowork/Claude skills
directory (e.g. `~/.claude/skills/`), or keep it here and reference the scripts
by path from the orchestrator prompt. Either way it reads `search_config.json`,
`seen_jobs.json`, and writes `.fetch-runs/` under `~/Documents/JobSearch/`
(override with the `JOBSEARCH_DIR` env var).

## Tests

```
cd skills/fetch-jobs
python tests/test_fetch_jobs.py
JOBSEARCH_DIR=$(cd ../.. && pwd) python tests/test_integration.py
```

Both suites pass against the live `search_config.json`. The integration test
exercises: plan call-count math, per-Actor input shaping, salary
normalization/annualization, the salary floor, title allow-list vs title_exclude
ordering, all three dedupe scopes (including within-Actor reposts), the
per-employer cap, and the date safety check.

## Schema verification

Input + output schemas were re-verified against the live Apify Actors on
**2026-05-31** (LinkedIn modified 2026-05-26, Indeed 2026-05-27, Glassdoor
2026-05-25) — no drift from the spec's translation table. **Re-run
`fetch-actor-details` before any future build**; if field names change, update
the call shaping in `build_calls.py` and the normalizers in `process_results.py`.

## Deployment-tunable config (read with safe defaults)

These live in `search_config.json["global"]` and were given sensible defaults so
the base config didn't need editing. Add the key to override:

| key | default | options | effect |
|---|---|---|---|
| `agency_action` | `"annotate"` | `annotate` / `drop_source` / `drop_post_fetch` | How to handle LinkedIn agency/job-board reposts. `annotate` keeps them and sets `is_agency`; `drop_source` sets `removeAgency:true` on the LinkedIn call; `drop_post_fetch` drops rows where `is_agency` is true. |
| `multi_title_strategy` | `"or_join"` | `or_join` / `per_title` | Indeed/Glassdoor take a single keyword string. `or_join` sends `"A OR B"` in one call; `per_title` fans out one call per title (more coverage, **multiplies cost**). LinkedIn always uses its native `titleSearch[]` array regardless. |

## Two open items to confirm in Phase-1 manual runs (from the spec)

1. **Indeed/Glassdoor `OR` operator.** Neither schema documents whether `query`
   / `keywords` honor `" OR "`. The default `multi_title_strategy: "or_join"`
   assumes it does. Test it on a real run; if OR is *not* honored (you get
   results for only one title, or junk), set `multi_title_strategy: "per_title"`.
   Irrelevant when `source` is the default LinkedIn (native title array).
2. **Agency policy.** Default is `annotate` (keep + flag). Switch via
   `agency_action` once you've seen how many agency rows your runs surface.

## Notes / decisions baked in

- **Recency** is snapped to 1 or 7 days (the only windows all three boards
  express natively). The post-fetch date check uses the **originally requested**
  `M` (capped at 7), so `/fetch-jobs 3` fetches the 7-day superset but trims the
  output to ~3 days.
- **Per-location fetch is unconditional** (one call per location per Actor,
  including LinkedIn) to stop large metros from starving small ones.
- **Salary** is post-fetch on every board, compared in the role's own currency
  with **no FX**, against the end selected by `salary_match_field`. Unknown
  salary follows `salary_unknown_action` (live config = `include`). When a
  listing states pay but not a pay-period, it is **assumed annual** (these
  boards overwhelmingly post annual) and the salary object carries
  `"period_assumed": true` so the assumption is visible downstream.
- **Cross-board dedupe** normalizes for string drift before hashing: company
  names are compared with common suffixes stripped (`Google` == `Google LLC`)
  and locations by city token (`Toronto, Ontario, Canada` == `Toronto, ON`), so
  the same job on two boards collapses in `all` mode.
- **Run-dir cleanup:** `build_calls.py` prunes `.fetch-runs/` folders older than
  `RUN_RETENTION_DAYS` (14) on each run.
- This skill **does not** update `seen_jobs.json`.
