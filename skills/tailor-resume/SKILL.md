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
- "**Always-include policy (deployment, overrides relevance-pruning):** every resume,
  regardless of role, MUST include (a) the **B.Eng Mechatronics Engineering** degree in
  `education`, and (b) the **PMP** (Project Management Professional) credential in
  `certifications`, listed **first**. Both are real `cv.md` entries treated as
  universally relevant, so this is honest selection, not fabrication. Education is never
  page-trimmed and the renderer pins PMP against the page-budget cap — but they only
  appear if you put them in the JSON, so include them on every run."

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
  "certifications": ["..."],  // ALWAYS-INCLUDE POLICY (deployment): the **PMP**
                              // (Project Management Professional) credential goes on
                              // EVERY resume, listed FIRST, regardless of role — it is
                              // treated as universally relevant. Beyond that, include
                              // only role-relevant credentials and prune true-but-off-
                              // target ones (e.g. a CAD cert on an ML resume) — dropping
                              // an off-target credential is tailoring, not dishonesty.
                              // List a credential in ONE section only; the renderer drops
                              // any cert already shown under Education but does NOT judge
                              // relevance — that's your call here. (The renderer also pins
                              // PMP so the page-budget cap can never trim it; but you must
                              // still put it in this list.)

  // --- fields used when filling the DESIGNED template (template_0.docx) ---
  "role_title": "",           // NO LONGER RENDERED. The template has no headline line
                              // under the name; the renderer ignores this field. Leave
                              // it out (or empty). Kept here only for back-compat.
  "key_achievements": [       // top 2-3 highlights; each must trace to cv.md (gate checks numbers)
    { "label": "short theme", "text": "Action + result + real metric from cv.md" }
  ],
  "areas_of_expertise": ["flat list of ~9 top skills"],  // the template's 3-column block;
                              // if omitted the renderer derives it from `skills`.
  "additional_skills": "fallback single line; normally OMIT",  // ADDITIONAL SKILLS now
                              // renders MULTI-LINE: one paragraph per `skills` group, with
                              // the "Category:" label bolded (e.g. **Languages:** Python, ...).
                              // It renders from the grouped `skills` field above, so emit
                              // `skills` with real categories + items and LEAVE THIS UNSET.
                              // If you do set this string AND no `skills` groups exist, it
                              // renders as ONE unlabeled line (back-compat). Grouped `skills`
                              // take precedence. Whole-line omission only — never reword a
                              // category or item. Lean tiers drop the whole block (drop_additional).

  "_inserted_keywords": ["only keywords you actually added AND that trace to cv.md"],
  "flags": ["missing keyword X omitted — no supporting experience in cv.md", "..."]
}
```

> **Template-field integrity.** `key_achievements` are pulled from real experience:
> every number in them must trace to `cv.md`, and the integrity gate checks them like
> any other output text. (`role_title` is no longer rendered — see above.)

Save as `filter2.json`. **`_inserted_keywords` must list every Filter-1 keyword
you incorporated** — the integrity gate checks each against `cv.md`.

### Filter 3 — ATS + skim test

Read Filter 2's output as (a) an ATS parser and (b) a hiring manager skimming
200 resumes. Rewrite to survive both, and **catch and correct any
keyword-stuffing** Filter 2 introduced (robotic phrasing, keyword lists masquerading
as sentences). Keep the same TailoredResume schema. Preserve every number and
keyword's traceability — do not add new numbers or claims here.

**Two-page budget — supply a superset, let the packer fit it.** The rendered resume targets
two US-Letter pages, but **you do not pre-trim to two pages** — the renderer's two-phase packer
does the page math (see *Render*). Your job is to supply a **generous, most-relevant-first
superset** and keep every line honest. Required floors the packer always honors: **at least 3
experiences and at least 2 projects, and the top (most-relevant) experience carries at least 3
bullets.** Above those floors, **over-supply on every axis, bullets included**: up to ~7
experiences and ~6 projects, **~6–8 bullets on the top (most-relevant) role and ~4–6 bullets on
each other role and project**, 3 key achievements, a full header (up to ~9 `areas_of_expertise`, a
`context` line per role, an `additional_skills` line). Phase 1 trims the excess to fit two pages;
Phase 2 grows it back to fill the second page — so more honest material is better, not worse.
**Bullets are the main fill lever for page 2.** The grow order is experiences → projects → top
bullets → other bullets, and experiences/projects alone do not reach two pages: if you supply only
1–3 bullets per role the page stalls around 1.5 and the renderer reports leftover bottom
whitespace. Page 2 fills only as far as the material you supply: at `--fill-target 0.96` the packer
aims for a full second page but stops when it runs out of items (it never pads). The renderer's
hard caps are 8 experiences / 8 projects / 8 top bullets / 6 other bullets — **supply toward
them**, drawing the most-relevant honest bullets from `cv.md` (which has well more than enough per
role). The one thing you must do is write
**tight ~1-line bullets**: the packer caps bullet *counts*, never wording, so a 3-line bullet
wastes the room it is trying to fill. Keep **every metric verbatim**; never drop, alter, or merge
metrics, and never combine two accomplishments into one number. Keep each **key achievement to
~one line** (the renderer's gentle tightener only pulls up one- or two-word widows, condensing
≤7%). List any credential in **one section only** — a course/specialization goes under Education
*or* Certifications, never both (cv.md lists some in both; pick one).

> **Division of labor with the renderer.** You don't size the page; the two-phase packer does.
> Phase 1 sheds *presentation overhead first* (areas count, per-role `context`, the ADDITIONAL
> SKILLS line, trailing certs, one key achievement, non-top bullet counts) and only drops below
> the floors (≥3 experiences, ≥2 projects, top ≥3 bullets) as a last resort; Phase 2 then grows
> whole items back to fill the page. So **supply a generous superset** (up to ~7 experiences,
> ~6 projects, ~9 `areas_of_expertise`, a `context` per role, an `additional_skills` line, 3 key
> achievements) and let the renderer choose how much lands. Your job: **tight ~1-line bullets**
> and content that is **honest and most-relevant-first**; the packer handles the page math
> against the real (Word) layout without touching wording, metrics, or the floors.

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
  --template "<root>/templates/template_0.docx" \
  --max-pages 2 --fill-target 0.96
```

This populates the template's sections (Name, Contact, Summary, Areas of
Expertise, Key Achievements, Professional Experience, Projects, Education &
Certifications, Additional Skills), cloning its repeatable blocks to fit your content
and reusing its own runs so the **embedded font carries over**. It returns JSON with an
`ats_flags` list — copy those into the critique. Per the locked decision, the skills
block stays **3-column**, which `ats_flags` flags as a parse risk every run.

It also runs a **one-line tightener** by default: any target line (bullet, key-achievement,
education detail, additional-skills, summary) that wraps to two lines and *can* be recovered
gets a near-invisible horizontal condense (`w:w`) so the trailing widow word pulls up to one
line. The condense is a **gentle cap — `WIDOW_MIN_SCALE = 0.93`** (≤7% narrower, imperceptible);
harder cases are left to wrap and the packer reclaims the line instead. It accounts for the
bullet's non-scaling hanging indent, leaves genuine two-line content wrapped, changes no text
(the integrity gate is unaffected), and reports what it condensed under `tighten.applied`. Tune
with `--min-scale` or disable with `--no-tighten`. It is measured with **LibreOffice** and
**no-ops where LibreOffice/pdfplumber aren't present** (e.g. a Windows/Word-only box) — harmless,
since the tightener is only polish; the two-phase packer does the real fitting.

**Fit is content-only, automatic, and two-phase.** The template's fonts/margins are fixed
(do NOT shrink them — that fights the design), so length is governed by **how many whole items**
are shown. `render_template.py` fills, measures the real page count and fill via the active
backend (see *Measurement backend* below), and adjusts in two phases. **Phase 1 (shrink to fit):**
walk the budget ladder from richest (`rich-max`) to leanest, re-rendering and re-measuring after
each, and stop at the **first tier that fits `--max-pages` (default 1)** — shedding presentation
overhead before content:

| tier | key ach. | experiences | top / other bullets | projects | areas | context | add'l skills | certs | tightener |
|---|---|---|---|---|---|---|---|---|---|
| rich-max | 3 | 5 | 6 / 3 | 4 | 9 | keep | keep | all | 0.94 |
| rich | 3 | 5 | 5 / 3 | 3 | 9 | keep | keep | all | 0.93 |
| rich-lean | 3 | 4 | 5 / 3 | 3 | 9 | keep | keep | all | 0.93 |
| full-plus | 3 | 4 | 5 / 2 | 2 | 9 | keep | keep | all | 0.92 |
| full | 3 | 3 | 4 / 2 | 2 | 9 | keep | keep | all | 0.92 |
| lean-context | 3 | 3 | 4 / 2 | 2 | 8 | drop | keep | all | 0.90 |
| lean-ka | 2 | 3 | 4 / 2 | 2 | 6 | drop | keep | 2 | 0.90 |
| lean-areas | 2 | 3 | 3 / 2 | 2 | 5 | drop | drop | 1 | 0.88 |
| lean-bullets | 2 | 3 | 3 / 1 | 2 | 4 | drop | drop | 1 | 0.86 |
| lean-max | 2 | 3 | 3 / 1 | 2 | 3 | drop | drop | 1 | 0.84 |
| one-project | 2 | 3 | 3 / 1 | **1** | 3 | drop | drop | 1 | 0.84 |
| hard-bullets | 2 | 3 | **2** / 1 | 1 | 3 | drop | drop | 1 | 0.82 |
| last-resort | 2 | **2** | 2 / 1 | 1 | 3 | drop | drop | 1 | 0.80 |

**Header is cut before content.** The ladder is ordered so the **content floors —
≥3 experiences, ≥2 projects, top role ≥3 bullets — are protected for as long as possible.**
The first ten tiers (`rich-max`…`lean-max`) shed only *presentation overhead* — areas-of-expertise
count, experience `context` lines, the ADDITIONAL SKILLS line, trailing low-relevance
certifications, one key achievement, and non-top bullet counts down to their allowed minimum —
while keeping all three floors intact.
Only the final three tiers (`one-project`, `hard-bullets`, `last-resort`) drop **below** a
floor, and only because even a fully-lean header still overflows. Every tier trims by
**whole-item omission only** (drop an area, a context blurb, the additional-skills line, a key
achievement, a trailing bullet, a project, a trailing role) — it NEVER edits a bullet's words
or a metric, so the integrity gate result is unchanged (omission, never fabrication). Items are
most-relevant-first, so trimming drops the least-relevant material.

**Phase 2 (grow to fill).** If the chosen tier honors the floors **and** the page is under
`--fill-target` (default **0.96**) full, the renderer greedily adds whole items back —
**experiences and projects first, then bullets** (`+1 experience → +1 project → +1 top-role
bullet → +1 other-role bullet`), staying on each op while it keeps fitting — up to caps
`(experiences 8, top bullets 8, other bullets 6, projects 8)`, bounded to 16 trial renders. The
committed result is tagged `<tier>+fill`. Growth is whole-item too, so integrity is again
untouched. Disable Phase 2 with `--no-grow`; raise/lower the goal with `--fill-target`. The
returned JSON reports `fit_ok`, the `tier` used (`+fill` if Phase 2 grew it), what was `trimmed`,
the `fill` ratio (from the active backend), and the full Phase-1 `ladder`.

**Measurement backend — this is what makes the fill honest.** Page count and fill come from
`scripts/measure_fit.py`, with two backends chosen by the `RESUME_FIT_BACKEND` env var (default
`auto`):

- **`word`** — drives **real MS Word via COM (`pywin32`)**. AUTHORITATIVE: it measures the page
  exactly as the candidate sees it. Picked automatically on Windows when Word + pywin32 are
  present. **This is the Cowork/desktop path; it requires `pip install pywin32` and a desktop MS
  Word install.**
- **`soffice`** — LibreOffice → PDF (pypdf/pdfplumber). Cross-platform fallback for the
  cloud-headless path. **It lays this template out ~1in taller than Word**, so on its own it
  stops the packer ~5 lines short of a full Word page — which is exactly why the Word backend
  exists. Treat its fill numbers as approximate.

`auto` picks Word on Windows (falling back to LibreOffice if Word can't start), LibreOffice
elsewhere. Force with `RESUME_FIT_BACKEND=word|soffice`. Sanity-check the backend on any machine
with `python scripts/measure_fit.py --file <resume>.docx --diagnose`.

**So Filter 3 should supply a GENEROUS SUPERSET, most-relevant-first — and let the packer choose
how much fits.** Provide **more than will fit**: up to ~7 experiences and ~6 projects, **~6–8
bullets on the top role and ~4–6 on each other role/project**, 3 key
achievements, up to ~9 `areas_of_expertise`, a `context` line per role, and an `additional_skills`
line. Phase 1 trims it to two pages; Phase 2 grows it back to fill — both against the *real* (Word)
layout. Bullets are the main page-2 fill lever: thin per-role bullets (1–3) leave the page short
even with all experiences/projects present. Still write **tight ~1-line bullets**: the packer caps
bullet *counts*, not wording, so 2–3 line bullets waste the room it is trying to fill and can force
a tier below a floor. Generous
superset + tight bullets = a full resume at whatever tier fits, all floors honored
(verified: a dense senior CV landed at `lean-areas`, 98.7% full in Word, one page).

If even `last-resort` is over target, the tightest render is left on disk with
`fit_ok: false` and a note — accept the overflow and mark `needs human check`, or cut more
in Filter 3. If **neither** backend can measure (no Word/pywin32 **and** no LibreOffice/pypdf),
page count is unmeasurable: it renders the full budget and reports `fit_ok: null` (flag it).
Disable the whole cascade with `--no-cascade` (single fill at the richest budget + tighten), or
change the target with `--max-pages N`.

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
| `scripts/render_template.py` | TailoredResume JSON → fills the **designed** `template_0.docx` in place (preserves embedded fonts/styles/3-col skills). The normal renderer here; two-phase shrink-then-grow packer, returns `ats_flags`/`tier`/`fill`/`ladder`. |
| `scripts/measure_fit.py` | Page-count + fill measurement behind the packer. Pluggable backend (`RESUME_FIT_BACKEND`): **`word`** via pywin32/COM (authoritative, Windows/Cowork) or **`soffice`** via LibreOffice (headless fallback). Has a `--diagnose` CLI to verify the backend on a given machine. |
| `scripts/make_template.py` | One-time: generate the canonical `templates/template_0.docx`. |

Run `python scripts/make_template.py` once after install so a base template exists.

See `README.md` for deployment-tunable keys and the template-handling rationale.
