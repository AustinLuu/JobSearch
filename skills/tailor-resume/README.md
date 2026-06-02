# tailor-resume — deployment notes

The quality layer of the resume pipeline (build-plan Phase 3). Consumes one
normalized listing object (`/fetch-jobs` → `/score-job` passthrough) plus
`cv.md`; emits a tailored `.docx` + a `-critique.md` into the dated folder.
**Discovery, scoring, dedupe, and submission are all out of scope here.**

## What it does, in one line

`Filter 1 (recruiter audit) → Filter 2 (XYZ rewrite) → Filter 3 (ATS + skim) →
integrity gate → render .docx → critique`, with the gate enforcing that every
number and every inserted keyword traces to `cv.md`.

## Install / first-run

```bash
# from the skill dir
python scripts/make_template.py        # writes templates/template_0.docx
python -m pytest tests/ -q             # or: python tests/test_common.py && python tests/test_integrity_gate.py
```

The skill assumes the locked layout. Override the root for tests / cloud-headless
with the `JOBSEARCH_ROOT` env var (default `~/Documents/JobSearch`).

| Path | Meaning |
|---|---|
| `~/Documents/JobSearch/cv.md` | source of truth; the only place numbers/skills may come from |
| `~/Documents/JobSearch/templates/template_0.docx` | base template the renderer loads |
| `~/Documents/JobSearch/YYYY-MM-DD/` | dated output folder |

## Deployment-tunable keys

These are intentionally few — the heavy tuning lives in `search_config.json`
(discovery) and the scoring threshold (Phase 2), not here.

| Where | Key | Default | Effect |
|---|---|---|---|
| `scripts/render_docx.py` | `BODY_FONT` | `Arial` | resume font (ATS-safe sans-serif) |
| `scripts/render_docx.py` | `BODY_SIZE` | `10.5` | body point size |
| `scripts/render_docx.py` | `NAME_SIZE` / `SECTION_SIZE` | `18` / `12` | name + section heading sizes |
| `scripts/render_docx.py` | `MARGIN` | `1440` DXA (1") | page margins |
| `scripts/render_docx.py` | `RULE_COLOR` | `2E75B6` | section-heading underline color |
| `scripts/render_docx.py` | `COMPACT_DENSITY` | `margin 900 / body 10 / spacing 0.5` | the one-page compression floor; renderer never tightens past this |
| CLI | `--max-pages` | unset (`1` when passed) | fit the resume to at most N pages; omit to render once with no length check |
| env | `JOBSEARCH_ROOT` | `~/Documents/JobSearch` | relocate the whole working tree |

To re-brand, either edit the style spec above **or** drop your own
`template_0.docx` at the template path (see below) — don't theme per job.

## Template handling (and the one decision made here)

Build-plan Phase 3 step 5 specifies loading a fixed `template_0.docx` and
populating its sections so styles stay consistent and ATS-friendly. No
`template_0.docx` was supplied when this skill was built, so:

- The renderer carries a **canonical ATS-safe style spec** (the constants in
  `render_docx.py`) and `make_template.py` bakes that exact spec into a
  `template_0.docx`. The template and the renderer therefore share one style
  source — "preserve the template's styles / don't re-theme per job" holds
  because the styles are fixed and centralized; only content varies.
- At render time, **if** a `template_0.docx` exists at the template path (yours
  or the generated one), the renderer opens it, clears the body, and fills
  content into the template's own styles. If none exists, it builds from the
  canonical spec directly, so the pipeline still works out of the box.

**Swap point:** to use your own designed base, save it as
`~/Documents/JobSearch/templates/template_0.docx`. Keep it ATS-clean: contact
line in the body (not a header/footer), no columns/text-boxes/layout-tables,
standard headings. The renderer preserves whatever paragraph/character styles it
defines.

> If you would rather the renderer do a strict unpack→edit-XML→repack against a
> richly-formatted existing template (the docx skill's "edit existing document"
> path) instead of regenerating from the style spec, that's a different renderer
> implementation — say so and provide the real `template_0.docx`.

## Two renderers: designed-template fill vs. from-scratch

- **`render_template.py` (normal here).** Opens the designed `template_0.docx` and fills
  it in place — swapping content into Name / Role Title / Contact / Summary / Areas of
  Expertise (3-col) / Key Achievements / Professional Experience / Projects / Education &
  Certifications / Additional Skills, cloning the template's repeatable blocks and reusing
  its own runs so the **embedded fonts and section rules carry over**. Right-aligned
  company/dates are rebuilt with a real RIGHT tab stop. Returns `ats_flags` (the 3-column
  skills parse-risk note) for the critique. Fit is **content-only** — it never resizes the
  template; length is governed by Filter 3's one-page budget (≥3 experiences, ≥2 projects).
  Template-specific input fields: `role_title` (the target job title — a headline, not a
  claim), `key_achievements` (`[{label,text}]`, gate-checked), `areas_of_expertise`
  (flat list; else derived), `additional_skills` (string; else derived).
- **`render_docx.py` (fallback).** Builds an ATS resume from scratch in a fixed Arial
  style with the one-page density ladder. Used only when no designed template exists.

### One-line tightener (template renderer)

`render_template.py` runs a bounded cosmetic pass after filling: a target line (bullet,
key-achievement, education detail, additional-skills, summary) that wraps to two lines by
a *small* amount is condensed horizontally (`w:w`, floor `--min-scale` = 0.90, i.e. ≤10%)
so the orphan word collapses onto one line. It is deliberately conservative:

- Only paragraphs that overflow by an amount recoverable within the scale floor are touched;
  half-line overflows are left to wrap (trim the content instead — that's Filter 3's job).
- It **skips** name/role/contact, headings, the 3-column skills, and tab-aligned split
  lines (company/title/project/university).
- It changes **no text**, so the integrity gate result is unchanged.
- It measures real wrap behaviour with LibreOffice + pdfplumber; if either is missing it
  no-ops. Like page-counting, LibreOffice is a close proxy for Word, not identical — so it
  targets clear orphans, not brim-full lines. `--no-tighten` disables it.

The `JOBSEARCH_ROOT` default is `~/Documents/Claude/JobSearch`; the designed template
lives at `<root>/templates/template_0.docx`.

## One-page fit

`render_docx.py --max-pages 1` (used by SKILL.md's render step) keeps the resume to a
single page in the only honest way: **content first, type second.**

1. The filters budget content to ~one page (Filter 3's *one-page budget*): keep the
   most relevant roles/bullets, omit whole low-relevance items. Omission is tailoring;
   it never strips a metric from a kept bullet.
2. The renderer measures the real page count with LibreOffice (`soffice` → PDF → page
   count via `pypdf` or `pdfinfo`), then renders at the **loosest density that still
   fits** — walking `relaxed → default → snug → compact`. Picking the loosest fit
   *fills* the page, so a trimmed resume doesn't leave a big blank lower half. It never
   goes below `COMPACT` (the readability/ATS floor).
3. If it *still* overflows at compact, it does **not** shrink further or drop content on
   its own. It writes the compact best-effort and returns `fit_ok: false` with a note to
   tighten/cut content upstream (or accept two pages and mark `needs human check`).

**One page is mostly a content discipline.** For a senior candidate, 3 experiences +
2 projects fits one page only with short (~1-line) bullets — tightening bullet *prose*
(metrics kept verbatim) matters more than typography. The filters' one-page budget owns
this; the renderer just measures and flags.

## Header, links, and de-duplication

- **Contact line is auto-hyperlinked.** The renderer splits `contact.line` on `" · "`,
  classifies each token (email → `mailto:`, bare domain/URL → `https://` with scheme/www
  stripped for display, everything else → plain text), and renders a centered name +
  centered contact row with a divider rule — contact text stays in the **body**, never a
  header/footer.
- **Education/Certifications de-dup.** `_dedupe_certs` drops any certification whose
  distinctive words are already covered by an Education entry (e.g. a DL Specialization
  that `cv.md` lists in both), so nothing prints twice. List a credential in one section.

**Dependency:** the page-count check needs LibreOffice (`soffice`) plus `pypdf` or
`pdfinfo`. Without them the renderer returns `fit_ok: null` and writes the `.docx` at
default density unverified — flag this in the critique. The docx skill bundles a
LibreOffice launcher (`/mnt/skills/public/docx/scripts/office/soffice.py`) for
sandboxed runs; a desktop Cowork run needs LibreOffice installed locally.

> Page geometry is measured with LibreOffice, a close proxy for Word's pagination, not
> an exact match — so the fit aims at a comfortable page, not a brim-full one.

## Integrity gate semantics (important)

- The gate **flags, never rejects.** Exit code is always 0; a flag is a review
  signal, not a build failure. Flagged jobs are still written but marked
  `needs human check`.
- **Numbers:** an output figure is acceptable if it traces to *any* figure in
  `cv.md` (not just a `Y`-line) — matching build-plan wording. Small integers
  recur throughout `cv.md`, so the gate is deliberately lenient on those and
  sharp on distinctive metrics (e.g. a fabricated `47%`). This is by design: the
  failure mode it must never have is silently passing an invented headline metric.
- **Keywords:** the skill passes Filter 2's `_inserted_keywords`; each must
  appear in `cv.md` as a substring or have all its content tokens present.

## Data contracts (handoffs between stages)

- `filter1.json` → `{ match_score, missing_keywords[], red_flags[] }`
- `filter2.json` → TailoredResume + `_inserted_keywords[]` + `flags[]`
- `filter3.json` → final TailoredResume + `_inserted_keywords[]` + `ats_notes[]`
  + `skim_notes[]` — **this is what renders and what the gate checks**
- `gate_report.json` → `{ passed, needs_human_check, number_flags[], keyword_flags[], summary }`

TailoredResume schema is validated by `common.validate_tailored_resume` and
documented in `SKILL.md`.

## Cloud-headless note

The filters become Claude API calls and the scripts run unchanged (set
`JOBSEARCH_ROOT`, point `--cv`/`--out` at object storage paths). The integrity
gate and renderer are pure Python with no connector dependency, so they port
directly.
