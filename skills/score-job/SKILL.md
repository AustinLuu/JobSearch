---
name: score-job
description: >-
  Score ONE normalized job listing against cv.md for CV-fit, returning strict JSON
  with a 0-100 fit score, a brief rationale, matched strengths, and likely gaps.
  Cheap reasoning pass that gates the expensive tailoring step — runs on every
  listing /fetch-jobs returns, keeps only those above the threshold for tailoring.
  Use when the user types /score-job, asks to score a job against the CV, or when
  the orchestrator hands a single normalized listing to the scoring step. Consumes
  one normalized listing object (from /fetch-jobs) + cv.md. Returns JSON only —
  never prose, never side effects, never an application action.
---

# score-job

Decide, for **one** normalized listing, how well the candidate's CV (as written)
lands for this job. Returns a numeric fit score plus a short rationale and two
short lists, as STRICT JSON. The orchestrator uses this to **shortlist** listings
for `/tailor-resume`: high enough → tailor; below threshold → skip.

This skill is the cheap reasoning gate between discovery (`/fetch-jobs`) and the
expensive quality layer (`/tailor-resume`). It is deliberately one pass — no
filters, no rewriting, no fabrication. **Do not tailor a job to score it.**

---

## Non-negotiable rules

1. **JSON-only output.** No prose preamble, no trailing commentary, no markdown
   code fences. The orchestrator parses your output mechanically.
2. **Score reflects the CV as written.** Don't speculate about hidden skills or
   "transferable" experience the CV doesn't show. If the CV doesn't list it, it
   doesn't count for the score.
3. **No fabrication.** `matched_strengths` must cite real CV content. `likely_gaps`
   may name skills the JD requires that the CV doesn't show — but don't invent
   gaps either; only flag what the JD actually asks for.
4. **One listing per call.** Don't batch. The orchestrator loops.
5. **No side effects.** Don't write files, don't update `seen_jobs.json`, don't
   apply. The orchestrator owns state.

---

## Input contract

One **normalized listing object** as emitted by `/fetch-jobs` (single element from
`listings.json`), plus `cv.md`. Relevant fields:

| Field | Use |
|---|---|
| `title` | Role match signal — seniority, function. |
| `company` | Context only; do not let prestige bias the score. |
| `description` | The primary text scored against the CV. Use as-is. |
| `location`, `workplace_type` | Surface a hard mismatch as a gap, not a score multiplier. |
| `salary` | Context only; salary mismatch is `/fetch-jobs`'s filter, not yours. |
| `job_id`, `url`, `source_search_name` | Passed through unchanged in the output for the orchestrator's bookkeeping. |

`cv.md` lives at `$JOBSEARCH_DIR/cv.md` (default `~/Documents/JobSearch/cv.md`).
Read it once at the start of the run.

---

## Procedure

> The scoring itself is a **single reasoning pass** you perform by following the
> rubric below. The validator is a **script** you invoke to defensively parse and
> apply the threshold. Work through a scratch dir, e.g.
> `$JOBSEARCH_DIR/.fetch-runs/<run_id>/score/<short_id>/`.

### Step 0 — Setup

1. Read `cv.md` in full. It is the only source of strengths.
2. Validate the listing has `job_id`, `title`, `company`, `description`. If
   `description` is empty, emit `fit_score: 0`, `rationale: "no description"`,
   and an empty strengths/gaps — do not invent.

### Step 1 — Score

Apply this rubric. Score each component, then combine; don't free-form the number.

| Component | Weight | What earns it |
|---|---|---|
| **Role function match** | 35 | Title + responsibilities map to a role the CV has actually held. Engineering/IC roles score this against the CV's engineering experience; PM/lead roles against any leadership the CV shows. Title prestige alone earns nothing. |
| **Domain / stack overlap** | 30 | Languages, frameworks, tools, and domain (e.g. ML platform, medical imaging, cloud infra) the JD names that the CV demonstrates with real accomplishments. Listed-but-unused tools in the Skills section count less than tools that appear in an actual X/Y/Z bullet. |
| **Seniority fit** | 15 | JD's stated level (junior / mid / senior / staff / lead) vs. the CV's tenure and scope. Both directions of mismatch reduce — over-qualified is a real risk for screeners too. |
| **Location / workplace fit** | 10 | Hard mismatch (e.g. JD is "onsite NYC", CV is "Toronto, Canada") drops this to ~0. Remote-friendly or candidate's-location-listed pulls this near full. |
| **Differentiators** | 10 | The CV has something the JD specifically prizes that most candidates wouldn't — a niche stack, a regulatory background, a published project, a recognized credential. Pure plus, not a deduction. |

Sum to a **0-100** integer. Round to integer. Do not nudge the number to hit the
threshold — the threshold is the orchestrator's policy lever, not yours.

### Step 2 — Strengths and gaps

- **`matched_strengths`**: 3-6 specific items the CV demonstrates that the JD
  asks for. Phrase concretely (e.g. "AWS S3 + EC2 HPC for ML training pipelines"
  — not "cloud experience"). Each item must trace to a real bullet or skill in
  `cv.md`.
- **`likely_gaps`**: 0-5 items the JD requires that the CV doesn't show.
  Phrase concretely (e.g. "no Kubernetes experience shown" — not "infrastructure
  gap"). Don't invent gaps for things the JD didn't ask for.

### Step 3 — Rationale

One sentence. Two short clauses at most. Lead with the score driver, end with the
biggest risk. Example: *"Strong ML-platform + AWS overlap and senior tenure match
the role; gap is no Kubernetes experience, which the JD calls out as required."*

### Step 4 — Emit JSON

Output STRICTLY this shape, nothing else:

```json
{
  "job_id": "li_8f3a2b",
  "fit_score": 78,
  "rationale": "...",
  "matched_strengths": ["...", "...", "..."],
  "likely_gaps": ["...", "..."]
}
```

- `job_id` echoes the listing's `job_id` unchanged.
- `fit_score` is an integer 0-100.
- `matched_strengths` is a list of strings; non-empty unless `fit_score` is very low.
- `likely_gaps` is a list of strings; may be empty.

Save as `score.json` in the scratch dir.

### Step 5 — Validate + threshold

Run:

```bash
python scripts/validate_score.py \
  --score score.json \
  --threshold "$SCORE_THRESHOLD"        # optional; defaults to 70
```

The validator:
- defensively parses the JSON (strips stray code fences, tries `json.loads`,
  fails with exit code 2 and a one-line reason on malformed input);
- enforces the schema (required keys, types, score range, list types);
- compares `fit_score` against `--threshold` (default 70, env-overridable via
  `SCORE_THRESHOLD`) and prints one of:
  - `SHORTLIST  job_id=<id>  fit_score=<n>  threshold=<t>` (exit 0)
  - `SKIP       job_id=<id>  fit_score=<n>  threshold=<t>` (exit 0)
  - `INVALID    reason="<…>"` (exit 2)

The validator is the **only** thing that decides shortlist vs. skip — your job is
to emit honest JSON. The orchestrator reads the validator's exit code + stdout.

### Step 6 — Return

Return the contents of `score.json` plus the validator's decision line. Nothing
else. The orchestrator collects shortlisted listings and hands each to
`/tailor-resume`.

---

## Hard rules (carried from above)

- JSON only — no prose, no commentary, no markdown fencing.
- No fabrication — strengths must trace to `cv.md`; gaps must trace to the JD.
- No side effects — never write to `seen_jobs.json`, never call other skills,
  never auto-apply.
- One listing per invocation.
- Threshold is policy: tune via `--threshold`/`$SCORE_THRESHOLD`, don't bend the
  score to land on it.

---

## Output schema (strict)

```json
{
  "job_id": "<echoed>",
  "fit_score": 0,
  "rationale": "one sentence",
  "matched_strengths": ["…"],
  "likely_gaps": ["…"]
}
```

The validator rejects anything else (missing keys, wrong types, score outside
0-100, prose around the JSON, code fences). On rejection the orchestrator must
mark the listing `INVALID` and skip it — never re-roll, never patch the JSON.

---

## Scripts

| Script | Role |
|---|---|
| `scripts/validate_score.py` | Defensive JSON parser + schema validator + threshold comparator. Single entry point for the validator step. |

See `README.md` for deployment-tunable keys (`SCORE_THRESHOLD`, scratch path).
