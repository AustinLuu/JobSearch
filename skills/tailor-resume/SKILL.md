---
name: tailor-resume
description: >-
  Tailor the candidate's resume to ONE shortlisted job listing and render an
  ATS-safe .docx plus a critique. Runs three sequential filters (senior-recruiter
  audit -> XYZ rewrite -> ATS + skim test), enforces an automated integrity gate
  (every number and every inserted keyword must trace to cv.md), and writes the
  outputs under the dated folder for human review. Use when the user types
  /tailor-resume, asks to tailor/customize a resume to a specific job, or when the
  orchestrator hands a single scored listing to the tailoring step of the pipeline.
  Consumes one normalized listing object (from /fetch-jobs -> /score-job) + cv.md.
  Does NOT scrape, score for fit, or submit applications — submission is out of scope.
---

# tailor-resume

Produce, for **one** shortlisted listing, a tailored `.docx` resume and a
`-critique.md`, with integrity guarantees the skill enforces on itself because
**no human reviews mid-run.**

This skill is the quality layer of the pipeline (build-plan Phase 3). Discovery
(`/fetch-jobs`) and fit-scoring (`/score-job`) are already done by the time a
listing reaches here. This skill does **not** touch `search_config.json`, Apify,
recency windows, or CV-fit reasoning — all of that is upstream.

---

## Non-negotiable integrity constraints

These override any instinct to make the resume stronger. A weaker-but-true
resume always beats a polished-but-fabricated one.

1. **Never invent a metric.** Use only numbers that already appear in `cv.md`.
   An accomplishment whose source `Y` is `_(no metric available)_` is rewritten
   **without** a number — do not estimate, approximate, round, or insert a
   plausible-sounding figure. (`cv.md` currently carries a real `Y` on every
   accomplishment; this rule is the guardrail for when that stops being true.)
2. **Never claim a skill/keyword that does not trace to `cv.md`.** Filter 1 will
   surface "missing keywords." Filter 2 may incorporate one **only if** the
   underlying experience genuinely exists in `cv.md`. If it doesn't, omit the
   keyword and record it in `flags` — do not bend a real accomplishment to fake it.
3. **The integrity gate is mandatory and runs every time.** Its output is
   advisory: it FLAGS, it never silently drops or silently accepts. Flagged
   output is still written, but the critique and `summary.md` mark it
   `needs human check`.
4. **`.docx` only.** Never PDF or LaTeX as the working format.
5. **Submission is out of scope.** This skill ends at files on disk. Never
   apply, auto-fill a portal, or bypass anti-bot controls.

---

## Input contract

One **normalized listing object** — the exact schema `/fetch-jobs` emits and
`/score-job` passes through — plus `cv.md`. Relevant fields:

| Field | Use |
|---|---|
| `description` | The job text fed to all three filters. **Do not re-scrape** — use this body as-is (it was whitespace-normalized at discovery). |
| `title`, `company`, `job_id` | Drive the output filename (`short_id` = `job_id` with the `li_`/`in_`/`gd_` prefix stripped). |
| `url`, `salary`, `source_search_name` | Carried into the critique for context only — never inputs to the rewrite. |

`cv.md` lives at `~/Documents/JobSearch/cv.md` (the source of truth for who the
candidate is). Read it once at the start of the run.

---

## Procedure

> The three filters are reasoning passes **you** perform by following the
> instructions below and emitting the specified JSON. The integrity gate and the
> render are **scripts** you invoke. Work through a scratch dir, e.g.
> `~/Documents/JobSearch/.fetch-runs/<date>/tailor/<short_id>/`.

### Step 0 — Setup

1. Read `cv.md` in full. It is the only place numbers and skills may come from.
2. Validate the listing has `description`, `title`, `company`, `job_id`. If
   `description` is empty, stop and report — there is nothing to tailor against.
3. Compute `short_id = strip_prefix(job_id)` and the output stem
   `{sanitized_title}__{sanitized_company}_{short_id}` (use
   `scripts/common.py:output_stem`).

### Filter 1 — Senior recruiter audit

Act as a senior technical recruiter who has the CV and the job description in
front of them. Spend <10 seconds the way a real screener would. Emit JSON only:

```json
{
  "match_score": 0,
  "missing_keywords": ["", "", "", "", ""],
  "red_flags": ["", "", ""]
}
```

- `match_score` /100 — how well the CV, as written, lands for THIS job.
- `missing_keywords` — up to 5 terms the JD emphasizes that the CV underplays or
  omits. Identifying a gap here does **not** authorize claiming it later; that is
  Filter 2's judgment against `cv.md`.
- `red_flags` — up to 3 things a hiring manager spots fast (title mismatch,
  buried relevant experience, unexplained gap, wrong seniority signal, etc.).

Save as `filter1.json`.

### Filter 2 — XYZ rewrite

Rewrite the experience (and, where useful, summary/skills) using the
**X-Y-Z** form — *accomplished **X**, measured by **Y**, by doing **Z*** —
reordering and re-emphasizing to address Filter 1's findings, **subject to the
integrity constraints above.** Concretely, as explicit rules:

- "Include a missing keyword ONLY if the underlying experience exists in
  `cv.md`. If it doesn't, omit it and add it to `flags`."
- "Never invent a metric. Use only `Y`-values (or other figures) present in
  `cv.md`. An accomplishment whose `Y` is `_(no metric available)_` is rewritten
  **without** a number."
- "If you cannot honestly include a keyword or a metric, say so in `flags`."
- "Select for **relevance to the target role**: surface the skills, projects, and
  certifications that fit the job and drop true-but-off-target ones (e.g. a CAD
  certification on an ML role). This is selection among real facts — legitimate
  tailoring, not fabrication. When in doubt, keep it; when clearly unrelated, cut it."

Emit a **TailoredResume** object (schema below), plus the bookkeeping fields:

```jsonc
{
  "contact":  { "name": "...", "line": "City · email · linkedin-url · github-url · site-url" },
  // The renderer splits `line` on " · " and renders a compact one-line row:
  //   • phone numbers are DROPPED (kept off the resume),
  //   • email shows as the address (mailto-linked),
  //   • a LinkedIn/GitHub URL shows as the word "LinkedIn"/"GitHub" (linked),
  //   • any other URL shows as "Portfolio" (linked),
  //   • use "Label|URL" for a custom link label, plain text for location.
  // You can still include a phone in `line`; it simply won't render. Order follows
  // the line. Result here: "City • email • LinkedIn • GitHub • Portfolio".
  "summary":  "2-4 sentences, factual, tuned to the role.",
  "skills":   [ { "category": "Languages", "items": ["..."] }, ... ],
  "experience": [
    { "title": "...", "company": "...", "location": "...", "dates": "...",
      "context": "one-sentence scope (optional)",
      "bullets": ["X..., measured by Y..., by doing Z..."] }
  ],
  "projects":   [ /* same shape as an experience entry; optional */ ],
  "education":  [ { "degree": "...", "institution": "...", "location": "...",
                    "dates": "...", "details": ["..."] } ],
  // NOTE: undergrad-style achievements in education `details` — GPA, Dean's/honour
  // list, academic awards/medals/scholarships, "relevant coursework" — are stripped
  // by the renderer BY DEFAULT (experienced-candidate resumes lead with work, not
  // school). Degree/institution/location/dates are always kept. So you needn't emit
  // those lines; if one slips through it's dropped at render. (Opt back in only via
  // the renderer's keep flag — not the normal path.)
  "certifications": ["..."],  // Include ONLY role-relevant credentials. Prune ones
                              // unrelated to the target role (e.g. a CAD cert on an ML
                              // resume) — dropping a true-but-off-target credential is
                              // tailoring, not dishonesty. List a credential in ONE
                              // section only; the renderer drops any cert already shown
                              // under Education but does NOT judge relevance — that's
                              // your call here.

  // --- fields used when filling the DESIGNED template (template_0.docx) ---
  "role_title": "the TARGET job's title",   // headline under the name. Honest as a
                              // headline for the role applied to — NOT a claim you hold it.
                              // Use listing.title.
  "key_achievements": [       // top 2-3 highlights; each must trace to cv.md (gate checks numbers)
    { "label": "short theme", "text": "Action + result + real metric from cv.md" }
  ],
  "areas_of_expertise": ["flat list of ~9 top skills"],  // the template's 3-column block;
                              // if omitted the renderer derives it from `skills`.
  "additional_skills": "tools + supporting skills, one line",  // else derived from `skills`

  "_inserted_keywords": ["only keywords you actually added AND that trace to cv.md"],
  "flags": ["missing keyword X omitted — no supporting experience in cv.md", "..."]
}
```

> **Template-field integrity.** `role_title` is a headline for the role being applied
> to (the listing's title) — it signals fit, it does **not** assert you currently hold
> that title, and nothing elsewhere may claim you do. `key_achievements` are pulled from
> real experience: every number in them must trace to `cv.md`, and the integrity gate
> checks them like any other output text.

Save as `filter2.json`. **`_inserted_keywords` must list every Filter-1 keyword
you incorporated** — the integrity gate checks each against `cv.md`.

### Filter 3 — ATS + skim test

Read Filter 2's output as (a) an ATS parser and (b) a hiring manager skimming
200 resumes. Rewrite to survive both, and **catch and correct any
keyword-stuffing** Filter 2 introduced (robotic phrasing, keyword lists masquerading
as sentences). Keep the same TailoredResume schema. Preserve every number and
keyword's traceability — do not add new numbers or claims here.

**One-page budget.** The rendered resume targets a single US-Letter page, so select
*and* tighten content to fit it. Required minimums: **at least 3 experiences and at
least 2 projects**, and the **top (most-relevant) experience carries at least 3 bullets**
(omitting whole low-relevance roles is fine *above* that floor, not below it). Beyond the
floor, fit one page by **shortening bullet prose to ~1 line each**, not by dropping below
the minimums — a 3-line bullet costs as much room as three 1-line bullets, so tighten
wording (and you may drop a role's `context` line) while keeping **every metric
verbatim**. Never drop or alter a metric, and never merge two accomplishments into one
combined number. Rough budget for this seniority: the top experience **≥3 bullets**,
other experiences 1–2 each; 2 projects with 1 bullet each; 3–4 skill groups; a 1–2 line
summary; and keep each **key achievement to ~one line** (they should fit without help —
the renderer's tightener only mops up lines that overflow by ≤10%). List any credential
in **one section only** — a course/specialization goes under Education *or*
Certifications, never both (cv.md lists some in both; pick one). The renderer measures
the real page count and flags over-budget output — see *Render* — so when in doubt,
tighten bullets before cutting, and cut a whole low-value item only after that.

Emit the **final TailoredResume** (same schema, carrying `_inserted_keywords`
forward, possibly trimmed if you removed a stuffed keyword) plus:

```jsonc
{ "...": "all TailoredResume fields ...",
  "_inserted_keywords": ["..."],
  "ats_notes": ["what would have failed parsing and how it was fixed"],
  "skim_notes": ["what a skimming manager would miss and how it was surfaced"] }
```

Save as `filter3.json`. **This file is what renders and what the gate checks.**

### Integrity gate (after Filter 3)

Run it on the final content — never skip it:

```bash
python scripts/integrity_gate.py \
  --tailored filter3.json \
  --cv ~/Documents/JobSearch/cv.md \
  --out gate_report.json
```

- Numbers: every figure in the output must trace to a number in `cv.md`.
- Keywords: every `_inserted_keywords` entry must trace to `cv.md`.
- `passed: true` → proceed clean. `passed: false` → still render, but mark the
  job `needs human check` in the critique and `summary.md`, and copy the flags in.

If the gate flags a **number**, that is almost always a fabricated/altered
metric introduced by a filter — fix Filter 2/3 to use the real `cv.md` figure
(or no figure) and re-run the gate, rather than shipping a flagged number.

### Render to `.docx`

**Two renderers — pick by whether a designed template exists:**

**A. Designed template present** (`templates/template_0.docx` is a real, formatted
resume — the normal case here). Fill it in place so its embedded fonts, section rules,
and layout are preserved:

```bash
python scripts/render_template.py \
  --tailored filter3.json \
  --out "<root>/<date>/{stem}.docx" \
  --template "<root>/templates/template_0.docx"
```

This populates the template's sections (Name, Role Title, Contact, Summary, Areas of
Expertise, Key Achievements, Professional Experience, Projects, Education &
Certifications, Additional Skills), cloning its repeatable blocks to fit your content
and reusing its own runs so the **embedded font carries over**. It returns JSON with an
`ats_flags` list — copy those into the critique. Per the locked decision, the skills
block stays **3-column**, which `ats_flags` flags as a parse risk every run.

It also runs a **one-line tightener** by default: any target line (bullet, key-achievement,
education detail, additional-skills, summary) that wraps to two lines *by only a hair*
gets a near-invisible horizontal condense (`w:w`, ≥90% / ≤10%) so the orphan word pulls
up to one line. Lines needing more than that are left to wrap — that's a content-trim
call, not a squish. It changes no text (the integrity gate is unaffected), is measured
against LibreOffice layout, and reports what it condensed under `tighten.applied`. Tune
with `--min-scale` or disable with `--no-tighten`; it no-ops if LibreOffice/pdfplumber
aren't present.

**Fit here is content-only, and now automatic.** The template's fonts/margins are fixed
(do NOT shrink them — that fights the design), so length is governed by trimming content.
By default `render_template.py` runs a **dynamic content budget**: it fills, measures the
real page count, and if over the target (`--max-pages`, default **1**) it walks a ladder of
progressively tighter budgets — re-rendering and re-measuring after each — stopping at the
loosest tier that fits:

| tier | key achievements | experiences | top / other bullets | projects | tightener floor |
|---|---|---|---|---|---|
| full | 3 | 3 | 4 / 2 | 2 | 0.90 |
| tight-ka | 2 | 3 | 3 / 2 | 2 | 0.90 |
| one-project | 2 | 3 | 3 / 2 | 1 | 0.88 |
| hard-bullets | 2 | 3 | 2 / 1 | 1 | 0.85 |
| last-resort | 2 | 2 | 2 / 1 | 1 | 0.82 |

Every tier trims by **whole-item omission only** (drop a key achievement, a trailing
bullet, a project, a trailing role) and pushes the tightener harder — it NEVER edits a
bullet's words or a metric, so the integrity gate result is unchanged (omission, never
fabrication). Items are most-relevant-first, so trimming drops the least-relevant material.
The returned JSON reports `fit_ok`, the `tier` used, what was `trimmed` (e.g.
`key_achievements: 3->2`), and the full `ladder`.

**Filter 3 still owns bullet length.** The cascade caps *counts*, not wording — so if your
bullets are long (2–3 lines), the cascade compensates by dropping whole roles and can fall
all the way to `last-resort` (2 experiences). If Filter 3 tightens bullets to ~1 line first,
the cascade stays gentle and keeps 3 experiences. So: write tight bullets; let the cascade
be the safety net, not the primary trimmer.

If even `last-resort` is over target, the tightest render is left on disk with
`fit_ok: false` and a note — accept the overflow and mark `needs human check`, or cut more
in Filter 3. If LibreOffice/pdfplumber aren't installed, page count is unmeasurable: it
renders the full budget and reports `fit_ok: null` (flag it). Disable the cascade with
`--no-cascade` (single fill at full budget + tighten), or change the target with
`--max-pages N`.

**B. No designed template** (blank/absent). Use the from-scratch ATS renderer with
one-page fit:

```bash
python scripts/render_docx.py --tailored filter3.json \
  --out "<root>/<date>/{stem}.docx" --max-pages 1
```
`--max-pages 1` renders at the loosest density that fits (relaxed→default→snug→compact),
never below the readability floor; `fit_ok:false` means cut content, `fit_ok:null` means
page count was unmeasurable (install LibreOffice).

**Either way, validate before handoff:**

```bash
python /mnt/skills/public/docx/scripts/office/validate.py "<date>/{stem}.docx"
```

### Write the critique

Write `{stem}-critique.md` next to the `.docx` containing:

- Filter 1: `match_score`, `missing_keywords`, `red_flags`.
- Filter 3: `ats_notes`, `skim_notes`.
- Integrity gate: PASS/FLAGGED + every flag verbatim.
- Filter 2 `flags`: keywords/metrics deliberately omitted for honesty.
- Context line: company, title, `url`, `salary`, `source_search_name`, status
  (`ready for review` or `needs human check`).

---

## Outputs (locked filename convention)

Written into the dated folder `~/Documents/JobSearch/YYYY-MM-DD/`:

- `{sanitized_title}__{company}_{short_id}.docx`
- `{sanitized_title}__{company}_{short_id}-critique.md`

`short_id` = de-prefixed `job_id`. Sanitize: strip `/ \ : * ? " < > |`, collapse
spaces to `_`. Use `scripts/common.py` (`resume_filename`, `critique_filename`)
so the two stay in sync — do not hand-format filenames.

The orchestrator (Phase 4), not this skill, appends the `job_id` to
`seen_jobs.json` and writes the per-run `summary.md`. This skill never writes
`seen_jobs.json`.

---

## Scripts

| Script | Role |
|---|---|
| `scripts/common.py` | Paths, filename convention, cv number extraction, TailoredResume validation. Imported by the others. |
| `scripts/integrity_gate.py` | The honesty check (numbers + inserted keywords vs `cv.md`). Flags, never rejects. |
| `scripts/render_docx.py` | TailoredResume JSON → ATS-safe `.docx` built from scratch (used when there is NO designed template). One-page fit via density ladder. |
| `scripts/render_template.py` | TailoredResume JSON → fills the **designed** `template_0.docx` in place (preserves embedded fonts/styles/3-col skills). The normal renderer here; returns `ats_flags`. |
| `scripts/make_template.py` | One-time: generate the canonical `templates/template_0.docx`. |

Run `python scripts/make_template.py` once after install so a base template exists.

See `README.md` for deployment-tunable keys and the template-handling rationale.
