# Phase 4 — Weekly Resume Pipeline (paste into a fresh Cowork session each week)

Run the full job-search pipeline once: discover the week's new listings, score them against
`cv.md`, tailor a resume for each strong match, and leave everything in a dated folder for my
review. **This pipeline never applies to anything** — it ends at `.docx` files plus an
apply-checklist I action myself.

Each run is **stateless**: re-read every file at the start; don't rely on memory from prior runs.

## Setup
- Connect the folder `C:\Users\Admin\Documents\Claude\JobSearch` (request access).
- Resolve today's date as `YYYY-MM-DD` from system time. Output folder is `…\JobSearch\<today>\`
  — create it if missing. If it already exists (a re-run the same day), **append** to
  `summary.md` under a new `## Run @ <UTC time>` heading rather than overwriting, and suffix
  resume filenames `_v2/_v3` on collision.
- Scoring threshold: **65**.

### Key paths
- CV (only source of strengths/numbers): `…\JobSearch\cv.md`
- Dedupe state: `…\JobSearch\seen_jobs.json` (flat JSON array of job_ids; may be `[]`)
- Discovery skill: `/fetch-jobs` (registered Cowork slash command)
- Scorer: `…\JobSearch\skills\score-job\SKILL.md` + `scripts\validate_score.py`
- Tailor: `…\JobSearch\skills\tailor-resume\SKILL.md` + `scripts\render_template.py`
  (already patched — soffice→Word page calibration, areas-of-expertise min 6 / max 9,
  compacted header spacing) + `templates\template_0.docx`
- Use `skills\tailor-resume\scripts\common.py:output_stem(listing)` for filenames.

## The run — do every step in order
Per-listing failures are non-fatal: log and continue. Fatal only if `cv.md` or `seen_jobs.json`
is missing/malformed, or `/fetch-jobs` itself crashes.

### Step 1 — Read state
Read `cv.md` in full and `seen_jobs.json` (call this set `SEEN`). If either is missing or
malformed, abort, say which file, and stop — no defaults, no commits.

### Step 2 — Fetch (sequential, not parallel)
Run `/fetch-jobs 7`. Capture the printed `<RUN_DIR>` and read `<RUN_DIR>\listings.json`.
Re-filter: drop any listing whose `job_id` is already in `SEEN` → call the rest `NEW_LISTINGS`.
If `NEW_LISTINGS` is empty, skip to Step 5, write a "nothing new" summary, commit nothing, exit.

**Apify operational notes (learned the hard way):**
- The Apify Actors are **pay-per-result** and the account has a **monthly usage hard limit**.
  Do not inflate `limit`/`maxRows` — the plan sets them. If a call errors with a usage-limit
  message, write `[]` for that call, note it, and continue; **do not re-run** it (re-running
  risks double-billing).
- **Run the Apify calls sequentially**, not via parallel subagents. Parallel calls have caused
  run-handle race conditions that cross-contaminated raw files. If you must speed it up, one
  worker, calls in order; verify each raw file's size/first item before moving on.
- If some location/search calls return nothing (limit hit or genuinely empty), treat those as
  **unfetched, not empty**, and flag the coverage gap in the summary.

### Step 3 — Score (parallelize across subagents)
Split `NEW_LISTINGS` across ~6–8 subagents. Each reads `cv.md` once, then for each listing:
`short_id` = `job_id` minus the `li_`/`in_`/`gd_` prefix; follow `score-job\SKILL.md` exactly
(rubric + strict JSON); write `score.json` to `<RUN_DIR>\score\<short_id>\`; run
`python skills\score-job\scripts\validate_score.py --score <…>\score.json --threshold 65`.
Record each as SHORTLIST / SKIP / INVALID (INVALID = bad score JSON; do not tailor and do not
commit it — let it retry next week). Merge into `dispositions_all.json` + `shortlist.json`.

### Step 4 — Tailor each shortlisted listing (parallelize, but mind the sandbox)
Split `SHORTLIST` across a few subagents (≈3–4 listings each). For each, follow
`tailor-resume\SKILL.md`: Filter 1 → Filter 2 → Filter 3 → integrity gate → render → critique.
Rules that matter in this sandbox:
- **Renders run in the foreground** (~30 s each). Background `nohup &` processes do **not**
  survive between bash calls here — that silently corrupted renders before. **One render per
  bash call.**
- The renderer's page calibration is already in place; expect winning tiers around
  `hard-bullets` / `last-resort+fill` at ~100 % fill, `fit_ok: true`, 1 page. (If the host has
  MS Word + pywin32 the renderer uses that authoritative backend automatically; `fit_ok: null`
  means even LibreOffice is missing — flag it.)
- **Integrity gate is mandatory.** Every number in the output must trace to `cv.md`; never
  invent or alter a metric; only insert a missing keyword if real experience backs it (else
  omit and add to `flags`). If the gate flags, still render but mark `needs human check`.
- Output `<stem>.docx` + `<stem>-critique.md` into `…\<today>\`. Record per-listing status:
  `ready for review` (fit_ok true + gate passed) / `needs human check — integrity flagged` /
  `needs human check — overflow` (fit_ok false) / `needs human check — unmeasurable`
  (fit_ok null) / `tailoring failed` (exception).

### Step 5 — Summary
Write/append `…\<today>\summary.md`: run metadata (`<RUN_DIR>`, recency window, source(s),
threshold, coverage caveats from Step 2, totals: fetched / new-after-SEEN / shortlist / skip /
invalid / failed); one row per shortlisted listing (company, title, status, fit score, file
links, integrity result, fit tier/fill); and a tail list of SKIP/INVALID dispositions.

### Step 6 — Apply-checklist (this replaces "applying")
Write `…\<today>\apply-checklist.md`: one row per `ready for review` resume —
`company · title · fit score · application URL (from the listing's url) · resume file link ·
[ ] applied` — sorted by fit score, so I can open each posting and submit it myself.

### Step 7 — Commit dedupe state (LAST, single writer)
Only now touch `seen_jobs.json`. Build the commit list = `job_id` of every listing with a
definitive disposition (SHORTLIST regardless of tailoring outcome, or SKIP). **Exclude
INVALID.** Union with the existing array, dedupe, sort, write back atomically. If any earlier
step crashed before here, **do not commit** — next week reprocesses cleanly.

### Step 8 — Final report + verify
Print one line: `Run complete: <new> new, <shortlist> tailored, <flags> needing review.
Outputs in …\JobSearch\<today>\.` Then verify on disk: each shortlisted listing has both a
`.docx` and a `-critique.md`; `seen_jobs.json` is valid, sorted, and grew by the expected
count; flag any `fit_ok: null` loudly (Word/LibreOffice backend missing).

## Hard rules — never override
1. **No applying. Ever.** No auto-submit, no portal form fills, no logins, no CAPTCHA solving.
   The pipeline ends at `.docx` + the apply-checklist.
2. **Never invent or alter a metric.** All numbers trace to `cv.md`; the integrity gate enforces
   it — never weaken or skip the gate.
3. **Never claim a skill/keyword not in `cv.md`.**
4. **`.docx` only** (never PDF/LaTeX as the working format).
5. **Single writer to `seen_jobs.json`** — only this orchestrator, only at Step 7, only after
   Steps 1–6 succeed.
6. **Stateless per run; one listing at a time** through score/tailor — no cross-listing state.

## Failure-mode quick reference
| Condition | Behavior |
|---|---|
| `cv.md` / `seen_jobs.json` missing or malformed | Abort, name the file, no commits. |
| `/fetch-jobs` crashes or returns 0 new | "Nothing new" summary, commit nothing, exit clean. |
| Apify usage-limit / call error | Write `[]`, flag coverage gap, continue, don't re-run. |
| Score JSON invalid | Validator → INVALID; record, **don't commit**, retry next week. |
| Integrity gate flags | Render anyway, mark `needs human check`, copy flags into critique. |
| Renderer `fit_ok: false` / `null` | Keep file, mark overflow / unmeasurable, flag in Step 8. |
