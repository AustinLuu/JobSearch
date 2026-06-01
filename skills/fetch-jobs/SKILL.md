---
name: fetch-jobs
description: "Discovery front-end for the resume pipeline. Fetches recent job listings from LinkedIn, Indeed, and Glassdoor via the Apify connector, filtered by search_config.json and constrained to the last N days, then normalizes, hard-filters, and dedupes them into a single listing array for scoring. Use when the user types /fetch-jobs, or asks to pull, fetch, or discover recent job postings for the pipeline. Optional args: N (recency days, default 7), source (linkedin/indeed/glassdoor/all), entry (a search_config.json entry name)."
---

# /fetch-jobs

Turn `/fetch-jobs [N] [source] [entry]` into a normalized, deduped,
recency-and-hard-filtered array of job listings. This skill applies **only the
deterministic filters** in `search_config.json` (titles, title exclusions,
locations, workplace type, country, job type, salary floor, excluded companies).
**CV-fit reasoning is NOT done here — that is `/score-job`'s job.**

All of the translation, normalization, filtering, and dedupe logic lives in two
Python scripts so it is deterministic and testable. Your job as the driver is to
run those scripts and make the Apify calls in between. **Do not re-implement the
filtering in prose or invent listings — only return what the scripts produce.**

## Invocation

```
/fetch-jobs [N] [source] [entry]
```

- **N** — recency in days. Snapped to the only two windows every board supports
  natively: `N<=1` → **1 day**, `N>=2` → **7 days**, absent → **7**. (You still
  trim to exactly what was asked via the post-fetch date check.)
- **source** — `linkedin`/`fantastic-jobs` (default), `indeed`, `glassdoor`,
  `all`, or a full `username/actor` slug.
- **entry** — a single `search_config.json` entry name (e.g.
  `swe_north_america`); absent → all entries.

`source` and `entry` are order-independent. Unknown tokens are errors (fail
loudly — never silently default).

## Procedure

The two Python scripts are bundled in this skill's own `scripts/` directory — run
them from this skill's base directory (shown to you when the skill loads), e.g.
`scripts/build_calls.py`. They read/write the job-search data (`search_config.json`,
`seen_jobs.json`, `.fetch-runs/`) from the JobSearch data folder, resolved as the
`JOBSEARCH_DIR` environment variable if set, otherwise `~/Documents/JobSearch/`.
If the data lives elsewhere, export `JOBSEARCH_DIR` before running the scripts.

### Step 1 — Build the call plan

Run (passing the raw argument string, even if empty):

```
python scripts/build_calls.py "<the args>"
```

This reads `search_config.json` and `seen_jobs.json`, does all per-Actor
translation (recency tokens, location strings, job-type/workplace mapping, title
exclusions, per-location + per-job_type fan-out, Glassdoor `excludeJobIds` from
seen IDs), and writes a **plan** to `~/Documents/JobSearch/.fetch-runs/<run_id>/plan.json`.
Capture the `RUN_DIR=...` line it prints — you need it for Steps 2 and 3.

Read `plan.json`. It contains `meta` and a `calls` array; each call has:
`id`, `actor`, `input`, `source_search_name`, `location`, `country`.

### Step 2 — Execute each Apify call

For **every** call in `plan.json["calls"]`, in order, use the **Apify connector**
to run the Actor:

- Call the Apify `call-actor` tool with `actor = call["actor"]` and
  `input = call["input"]` (pass the input object through unchanged — it is
  already correctly shaped for that Actor).
- Take the returned dataset items (a JSON array of listing objects) and **save
  them verbatim** to:

  ```
  <RUN_DIR>/raw/<call.id>.json
  ```

  (e.g. `<RUN_DIR>/raw/0.json`, `<RUN_DIR>/raw/1.json`, …). If a call returns no
  items, still write `[]` so the processor knows the call ran.

Notes:
- These Actors are **pay-per-result** — do not inflate `maxRows`/`limit`; the
  plan already set them from `max_results_per_source_per_search`.
- If a call errors, write `[]` for that id, note it, and continue — one bad call
  must not abort the run.
- Do not add, drop, or edit any input fields. The plan is authoritative.

### Step 3 — Normalize, filter, dedupe

Run:

```
python scripts/process_results.py "<RUN_DIR>"
```

This reads the plan + every `raw/<id>.json` + `search_config.json` +
`seen_jobs.json`, then:

- normalizes each Actor's output into the shared schema (salary becomes the
  object `{min, max, currency, period}`, hourly comps annualized ×2080,
  Glassdoor dates derived from `ageInDays`);
- applies the **post-fetch** filters each board requires per
  `global.actor_enforcement` (salary floor on all boards; title allow-list +
  title_exclude on Indeed/Glassdoor; workplace/job-type where the Actor can't
  filter natively; excluded companies; the date safety check);
- dedupes in three scopes — within-Actor reposts, cross-board/cross-search
  `(company+title+location)`, and cross-run against `seen_jobs.json`;
- caps listings per employer (`max_per_employer`), **after** dedupe.

It writes the final array to `<RUN_DIR>/listings.json` and a debug breakdown to
`<RUN_DIR>/run-summary.json`, and prints counts + drop reasons.

### Step 4 — Return

Return the contents of `<RUN_DIR>/listings.json` as the result handed to
`/score-job`. Briefly report: how many listings survived, and the headline drop/
dedupe numbers from the printed summary. **Do not** modify the listings or update
`seen_jobs.json` — that is the orchestrator's job after the whole pipeline
succeeds (a mid-run failure must not poison dedupe state).

## Hard rules

- Only the scripts decide what is included. Don't fabricate, estimate, or
  "helpfully" add listings or fields.
- Never push CV-relevance scoring into this step.
- The output ends at a normalized array. No applying, no submitting.

## Output schema (one element)

```json
{
  "job_id": "li_8f3a2b",
  "raw_source_id": "8f3a2b",
  "source": "linkedin",
  "source_actor": "fantastic-jobs/advanced-linkedin-job-search-api",
  "company": "Acme",
  "title": "Senior Data Engineer",
  "location": "Toronto, ON",
  "workplace_type": "hybrid",
  "salary": { "min": 140000, "max": 180000, "currency": "CAD", "period": "annual" },
  "is_agency": false,
  "url": "https://...",
  "description": "...",
  "date_posted": "2026-05-24",
  "source_search_name": ["swe_north_america"]
}
```

`salary` is always an object (any field `null` if not stated); `period` is always
`"annual"` by this point. If a pay figure was stated without a period it is
assumed annual and the object carries an extra `"period_assumed": true`.
`source_search_name` is an array because dedupe merges listings that matched
multiple entries.
