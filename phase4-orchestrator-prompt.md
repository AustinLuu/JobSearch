# Phase 4 — Resume Pipeline Orchestrator

Standing task. Each run is stateless: re-read every file at the start. **Do not apply to anything, ever** — this pipeline ends at `.docx` files in a dated folder for human review. No auto-submit, no auto-apply, no CAPTCHA bypass, no form fills on application portals.

---

## Setup (every run)

Set the shell environment so scripts resolve paths and policy correctly:

```
set JOBSEARCH_DIR=C:\Users\Admin\Documents\Claude\JobSearch
set JOBSEARCH_ROOT=C:\Users\Admin\Documents\Claude\JobSearch
set SCORE_THRESHOLD=65
```

Resolve today's date as `YYYY-MM-DD` from system time. The dated output folder is `%JOBSEARCH_DIR%\YYYY-MM-DD\` — create it if missing.

## Invocation — these skills are NOT all the same kind

| Skill | How to invoke |
|---|---|
| `/fetch-jobs` | **Registered Cowork slash command.** Type `/fetch-jobs 7` and execute. |
| `/score-job` | **Not registered.** Read `%JOBSEARCH_DIR%\skills\score-job\SKILL.md` and follow its procedure exactly. |
| `/tailor-resume` | **Not registered.** Read `%JOBSEARCH_DIR%\skills\tailor-resume\SKILL.md` and follow its procedure exactly. |

"Follow the procedure" means: perform the reasoning passes the SKILL.md describes, write the JSON artifacts to the paths it specifies, run the helper scripts it names. Do not improvise. If a future run shows either skill registered as a slash command, switch to typing `/score-job` / `/tailor-resume` directly.

---

## The run

Do every step in order. Per-listing failures are non-fatal — log and continue. The only fatal conditions are: `cv.md` missing/malformed, `seen_jobs.json` missing/malformed, or `/fetch-jobs` itself crashing.

### Step 1 — Read state
1. Read `%JOBSEARCH_DIR%\cv.md`. This is the only place skills and numbers in tailored output may come from.
2. Read `%JOBSEARCH_DIR%\seen_jobs.json` as a JSON array of strings (may be `[]`). Call this set `SEEN`.
3. If either file is missing or malformed, abort the run, report which file, and exit. Do not proceed with defaults.

### Step 2 — Fetch
Run `/fetch-jobs 7`. (Only `1` and `7` are supported windows; `7` is the resilient default — Cowork skips runs while the machine is asleep/closed and recovers on next wake, so the 7-day window covers gaps.) Capture the printed `<RUN_DIR>` path (a `.fetch-runs\<timestamp>\` directory the skill creates).

The skill writes `<RUN_DIR>\listings.json`. Read it. Defensively re-filter: drop any listing whose `job_id` is in `SEEN`. Let `NEW_LISTINGS` be the result.

If `NEW_LISTINGS` is empty, skip to Step 5, write a "nothing new" summary, do not commit anything to `seen_jobs.json`, and exit cleanly.

### Step 3 — Score
For each listing in `NEW_LISTINGS`:

1. Compute `short_id` = `job_id` with the `li_` / `in_` / `gd_` prefix stripped.
2. Make `<RUN_DIR>\score\<short_id>\`.
3. Follow `%JOBSEARCH_DIR%\skills\score-job\SKILL.md` (rubric + JSON contract). Emit the score JSON to `<RUN_DIR>\score\<short_id>\score.json`.
4. Run the validator:
   ```
   python %JOBSEARCH_DIR%\skills\score-job\scripts\validate_score.py --score <RUN_DIR>\score\<short_id>\score.json
   ```
5. Parse the validator's stdout line. Three outcomes:
   - `SHORTLIST` → keep for Step 4.
   - `SKIP` → record disposition for the summary; do not tailor.
   - `INVALID` → record `{job_id, reason}` for the summary. Do **not** tailor. Do **not** commit to `seen_jobs.json` (let it be retried next run with a clean reasoning pass).

Let `SHORTLIST` be the listings the validator marked `SHORTLIST`. Never tailor a listing whose score hasn't passed the validator.

### Step 4 — Tailor each shortlisted listing
For each `listing` in `SHORTLIST`, follow `%JOBSEARCH_DIR%\skills\tailor-resume\SKILL.md`:

1. Make `<RUN_DIR>\tailor\<short_id>\`.
2. Reasoning pass — Filter 1 (recruiter audit) → `<RUN_DIR>\tailor\<short_id>\filter1.json`.
3. Reasoning pass — Filter 2 (XYZ rewrite) → `filter2.json`. **Hard rules from SKILL.md apply:** never invent a metric; only insert a missing keyword if it traces to `cv.md`; otherwise omit it and append to `flags`.
4. Reasoning pass — Filter 3 (ATS + skim test) → `filter3.json`. This is what the gate reads and the renderer renders.
5. Run the integrity gate:
   ```
   python %JOBSEARCH_DIR%\skills\tailor-resume\scripts\integrity_gate.py ^
     --tailored <RUN_DIR>\tailor\<short_id>\filter3.json ^
     --cv %JOBSEARCH_DIR%\cv.md ^
     --out <RUN_DIR>\tailor\<short_id>\gate_report.json
   ```
6. Compute the output stem with `common.output_stem(listing)` from `%JOBSEARCH_DIR%\skills\tailor-resume\scripts\common.py`. The stem is `{sanitized_title}__{sanitized_company}_{short_id}` — strip `/ \ : * ? " < > |` and collapse spaces to `_`.
7. **Filename collision check.** If `%JOBSEARCH_DIR%\YYYY-MM-DD\<stem>.docx` already exists (e.g. prior Phase-3 hand run, prior intra-day re-trigger), append `_v2`, `_v3`, ... to the stem until unique. Record the suffix in the summary so the source is auditable.
8. Render:
   ```
   python %JOBSEARCH_DIR%\skills\tailor-resume\scripts\render_template.py ^
     --tailored <RUN_DIR>\tailor\<short_id>\filter3.json ^
     --out %JOBSEARCH_DIR%\YYYY-MM-DD\<stem>.docx ^
     --template %JOBSEARCH_DIR%\templates\template_0.docx
   ```
   Capture the renderer's returned JSON: `fit_ok`, `tier`, `trimmed`, `fill`, `ats_flags`, `tighten`.
9. Write `%JOBSEARCH_DIR%\YYYY-MM-DD\<stem>-critique.md`:
   - **Filter 1:** match_score, missing_keywords, red_flags.
   - **Filter 2:** honesty flags (keywords/metrics omitted and why).
   - **Filter 3:** ats_notes, skim_notes.
   - **Integrity gate:** PASS or FLAGGED + every flag verbatim.
   - **Renderer report:** fit_ok, tier, fill, ats_flags.
   - **Job context:** company, title, URL, salary, source_search_name, fit_score, status.

**Per-listing status to record for the summary:**

| Status | Conditions |
|---|---|
| `ready for review` | render `fit_ok: true`, gate `passed: true`. |
| `needs human check — integrity flagged` | gate `passed: false`. Output is still written. |
| `needs human check — overflow` | `fit_ok: false`. Last-resort tier output is on disk. |
| `needs human check — unmeasurable` | `fit_ok: null`. **Means Word + pywin32 missing on host — flag this loudly in Step 7; the Cowork production path requires the Word backend.** |
| `tailoring failed` | any exception in Filter 1/2/3 or renderer. Record the error. The `job_id` IS still committed in Step 6 — don't loop forever — but the summary flags it loudly. |

### Step 5 — Write the summary
Write `%JOBSEARCH_DIR%\YYYY-MM-DD\summary.md`. **If the file already exists** (Phase-3 hand work, earlier intra-day run, scheduled run that already fired today), **append** a new `## Run @ <UTC timestamp>` section underneath the existing content. Do not overwrite.

Each section contains:
- **Run metadata:** `<RUN_DIR>` path, recency window, source(s), entry filter, scoring threshold, totals (fetched / new-after-SEEN / shortlist / skip / invalid / failed).
- **One row per listing in SHORTLIST** (regardless of tailoring outcome):
  ```markdown
  ### <Company> — <Title>
  - **Status:** <status>
  - **Fit score:** <0-100>
  - **Files:** [resume](./<stem>.docx) · [critique](./<stem>-critique.md)
  - **Source:** <source_search_name>  ·  <url>
  - **Integrity:** <PASS / FLAGGED + flag count>
  - **Fit:** <tier> · fill <fill>% · fit_ok <true/false/null>
  ```
- **Tail list:** `SKIP` and `INVALID` dispositions — `job_id`, company, title, decision. No per-file links.

### Step 6 — Commit dedupe state (LAST step, only after Steps 1–5 succeed)
This is the only step that touches `seen_jobs.json`. If anything earlier crashed the run before reaching here, do **not** commit — the next run re-processes the same listings (good: state isn't poisoned).

1. Build the commit list: `job_id` for every listing with a definitive disposition — `SHORTLIST` (regardless of tailoring outcome) or `SKIP`. **Exclude** `INVALID` (bad score JSON — let it be retried next run).
2. Read `seen_jobs.json` (still a flat JSON array), union with the commit list, dedupe, sort lexically for stable diffs, write back atomically.
3. Single writer: only this orchestrator, only at this step. Neither `/fetch-jobs` nor `/tailor-resume` writes this file.

### Step 7 — Final report
Print exactly one line:
```
Run complete: <new> new listings, <shortlist> tailored, <flags> needing human review. Outputs in %JOBSEARCH_DIR%\YYYY-MM-DD\.
```

If any listing produced `fit_ok: null`, print a second line flagging the deployment misconfiguration: `WARNING: Word + pywin32 backend missing — rendered .docx files are unmeasured and may overflow. Install pywin32 and verify Word is installed and reachable.`

---

## Hard rules — never override

1. **Submission is out of scope.** No applying, no auto-submit, no form fills, no CAPTCHA bypass. The pipeline ends at files on disk.
2. **Never invent or alter a metric.** All numbers in tailored output come from `cv.md`. The integrity gate enforces this; never patch around a flag by removing or weakening the gate.
3. **Never claim a skill or keyword that doesn't trace to `cv.md`.** Filter 1 identifies missing keywords; Filter 2 may incorporate one ONLY if the underlying experience is real. Otherwise omit it and add to `flags`.
4. **`.docx` only** — never PDF/LaTeX as the working format.
5. **Single writer to `seen_jobs.json`** — only this orchestrator, only at Step 6, only after Steps 1–5 succeed.
6. **Stateless per run.** Re-read every file at the top. Do not rely on memory from previous runs.
7. **One listing at a time.** Score, tailor, write per listing — not batched. The pipeline tolerates per-listing failures; it does not tolerate cross-listing state leaks.

---

## Failure modes — quick reference

| Condition | Behavior |
|---|---|
| `cv.md` or `seen_jobs.json` missing/malformed | Abort. Report which file. No commits. |
| `/fetch-jobs` crashes or returns 0 listings | Write "nothing new" summary. Commit nothing. Exit clean. |
| `/score-job` reasoning emits non-JSON | Validator returns `INVALID`. Record. **Do not commit** — retry next run. |
| Tailor stage exception | Record `tailoring failed`. **Commit** `job_id` (no infinite loop). |
| Integrity gate flags | Render anyway. Mark `needs human check — integrity flagged`. Copy flags into critique verbatim. |
| Renderer `fit_ok: false` | Last-resort `.docx` is on disk. Mark `needs human check — overflow`. |
| Renderer `fit_ok: null` | Deployment misconfigured (no Word backend). Mark `needs human check — unmeasurable`. Flag in Step 7. |
| `seen_jobs.json` write fails | Surface loudly. Do not retry mid-run. Next run re-does the work (acceptable cost). |

---

## What this prompt deliberately does not do

- It does not score-then-tailor in one pass. Scoring is cheap, tailoring is expensive; they're separated so the threshold gates the cost.
- It does not retry failed listings within the run. Per-listing failures are surfaced; the next run handles them (or the user removes the `job_id` from `seen_jobs.json` to force a retry).
- It does not change the dated folder. Today's date governs; collisions are suffixed; summary appends. The audit trail is preserved.
- It does not modify `cv.md`. CV maintenance is a separate manual workflow.
- It does not apply to anything. Ever.
