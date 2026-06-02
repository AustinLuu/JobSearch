# Phase 3 (`tailor-resume`) — Handoff to Finish in a New Conversation

**Purpose:** everything a fresh conversation needs to *complete* Phase 3 of the resume
pipeline. The tailoring skill is **built, deployed to disk, and unit-tested**; what
remains is the real-listing validation that the build plan's "done-when" actually
requires, plus a short list of polish items. Read this top to bottom before touching
anything.

> **Scope:** this is about finishing **Phase 3 only** (the `tailor-resume` skill). Phase 2
> (`/score-job`) and Phase 4 (orchestrator) are adjacent and noted at the end for context,
> but they are not this document's job.

---

## TL;DR — what's done vs. what's left

**Done and verified:**
- The `tailor-resume` skill is written, deployed to the user's disk, byte-verified, and its
  test suite passes (**25/25**).
- Both renderers work: the **designed-template filler** (`render_template.py`, now filling a
  **Calibri** `template_0.docx`) and the **from-scratch ATS fallback** (`render_docx.py`, Arial).
- The **integrity gate** works — proven live by catching an over-claimed keyword.
- The **dynamic content-budget cascade** (designed template) and the **undergrad-achievement
  strip** (both renderers) are implemented and tested.
- **One** end-to-end run was completed on a *synthetic* listing.

**The catch (most important thing in this doc):** in every test so far, *Claude hand-authored
the filter JSON* (`filter1/filter2/filter3`). The three filters are supposed to be **model
reasoning passes that follow `SKILL.md` from a raw listing**, and that path has **never been
exercised on real postings**. Closing Phase 3 = doing exactly that.

**Left to do:** Task A (real-listing validation — the core done-when), Task B (polish), Task C
(make it actually invocable). See *Remaining work*.

---

## 1. What Phase 3 is

Per `build-plan.md` Phase 3: a skill that takes **one shortlisted listing + `cv.md`** and
produces a **tailored `.docx` + a `-critique.md`** in a dated folder, via three sequential
filters, with an automated integrity gate, because **no human reviews mid-run**. Submission is
out of scope.

The three filters:
1. **Filter 1 — senior recruiter audit:** match score /100, top-5 missing keywords, 3 red flags.
2. **Filter 2 — XYZ rewrite:** rewrite experience as *accomplished X, measured by Y, by doing Z*,
   incorporate missing keywords **only if they trace to `cv.md`**, select for role-relevance.
3. **Filter 3 — ATS + skim test:** survive an ATS parser and a 10-second skim; tighten to a
   one-page budget; catch keyword-stuffing.

**Build-plan "done-when" (the bar to clear):** five real test runs all pass manual integrity
review, the `.docx` opens cleanly with the template's layout intact, and the user would be
comfortable submitting any of them.

---

## 2. Current state (what exists, where, and that it works)

**Installed on disk** at `C:\Users\Admin\Documents\Claude\JobSearch\skills\tailor-resume\`:

```
tailor-resume\
  SKILL.md            # orchestration: filters -> gate -> render -> critique (the entry point)
  README.md           # deployment notes (NOTE: slightly stale — see Task B)
  scripts\
    common.py         # paths, filename convention, number extraction, schema validation,
                      #   strip_undergrad_achievements()
    integrity_gate.py # numbers + inserted-keywords must trace to cv.md; FLAGS, never rejects
    render_docx.py    # from-scratch ATS renderer (fallback); density ladder; count_pages()
    render_template.py# fills the DESIGNED template; cascade (BUDGET_LADDER); one-line tightener
    make_template.py  # generates a blank canonical template (fallback only)
  tests\
    test_common.py    test_integrity_gate.py    test_render.py
    fixtures\sample_listing.json
```

- Files were verified **byte-identical** to the working copies, and `pytest tests/` passes
  **25/25** on the copied-back bytes.
- The designed template lives at `…\JobSearch\templates\template_0.docx` and is now **Calibri**
  (user-edited). The renderer clones the template's own run formatting, so Calibri carries
  through automatically; all section anchors survive the edit.

**What was proven, and how (be honest about the limits):**
- Live run on the bundled `sample_listing.json` (a synthetic "Senior ML Platform Engineer @
  Helix Imaging" posting). Claude played the filters by hand. The gate **flagged** an
  over-claimed keyword ("deployment cycle time" — `cycle` not in `cv.md`); it was dropped and
  re-gated clean. All numbers traced.
- `render_template.py` filled the real Calibri template: anchors found, fonts preserved, 3-col
  skills intact, right-tab alignment working, tightener condensed near-overflow lines, OOXML
  validation passed.
- The cascade auto-fit to **one page** at the `one-project` tier on Calibri (vs. `hard-bullets`
  on the old serif — Calibri is more compact). Undergrad GPA/Dean's-list correctly stripped.

---

## 3. Remaining work to close Phase 3

### Task A — Real-listing validation (this is the actual done-when)
1. Obtain **3–5 real job postings** relevant to the CV. Either the user pastes them, or pull via
   `/fetch-jobs` once Phase 1's Apify connector is ready (note: that costs Apify credits — don't
   trigger it unprompted).
2. For **each** listing, run the **real `SKILL.md` procedure as model reasoning** — Filter 1 →
   Filter 2 → Filter 3, emitting the JSON the skill specifies. **Do not hand-author the filter
   JSON.** The whole point is to test the skill the way it runs in production; hand-authoring
   re-creates the gap that's still open.
3. Run `integrity_gate.py` on the final `filter3.json` against `cv.md`. **Read every flag.**
   Manually confirm: every number traces to `cv.md`; every kept keyword reflects real experience;
   nothing was invented or merged.
4. Render via `render_template.py` (Calibri template, cascade on, target 1 page). Open the
   `.docx`. Confirm: layout intact, honest content, one page (or a deliberate 2), critique
   accurate.
5. **Acceptance:** five clean runs the user would actually submit. Iterate `SKILL.md` wording if
   the model's filter output reveals weak spots (e.g., under-tightened bullets, weak red-flag
   detection, keyword over-reach).

> Watch especially for: (a) the model inventing or rounding a metric — the gate should catch novel
> numbers, but eyeball anyway; (b) bullets longer than ~1 line, which force the cascade to drop
> whole roles (see *Gotchas*); (c) the model claiming a "missing keyword" whose support is thin.

### Task B — Polish / open decisions
- **Update `README.md`** — it predates the undergrad-strip and the cascade; bring it in sync with
  `SKILL.md` (the operative doc, which *is* current).
- **Confirm the page target.** Cascade defaults to **1 page** (`--max-pages`, configurable). If a
  2-page ceiling is wanted, it's a one-word change. (User said "over 2 pages" once but all prior
  work targeted one page — confirm intent.)
- **Verify `LibreOffice` + `pdfplumber` (+ `pypdf`) are installed on the Cowork machine.** Without
  them the page-count + tightener silently no-op (the `.docx` still renders, but `fit_ok: null`).
- Font: **Calibri chosen** for the designed template; the fallback renderer stays Arial. Done.

### Task C — Make the skill invocable (cross-cutting; needed to actually use or orchestrate it)
- `/tailor-resume` does **not** appear in the Cowork `/` menu because the skill lives in
  `JobSearch\skills\` — a *granted working folder*, **not** a registered skills location. Cowork
  loads skills from **Customize → Skills** (the documented UI) or the scanned `~/.claude/skills/`
  directory.
- Fix: install via **Customize → Skills** (upload the whole folder, not just `SKILL.md` — it needs
  `scripts/`), or copy the folder into `C:\Users\Admin\.claude\skills\tailor-resume\` and reopen
  Cowork. The skill's scripts still resolve their paths from `~/Documents/Claude/JobSearch` either
  way.
- **Open question to resolve early:** does `/fetch-jobs` currently appear in the `/` menu? If yes,
  install `tailor-resume` the same way it was. If no, neither skill was ever a real slash command
  and the orchestrator (Phase 4) must invoke them differently — settle this before Phase 4.

---

## 4. Environment facts the new conversation MUST know (gotchas)

- **Two filesystems.** Claude's sandbox (`/home/claude`, `/mnt/...`) is separate from the user's
  Windows disk, reached via the **Filesystem MCP** tools. Don't confuse them.
- **Granted directories only:** `Documents\GitHub`, `Downloads`, `Desktop`, and
  `Documents\Claude\JobSearch`. **`C:\Users\Admin\.claude` is NOT accessible** — so Claude cannot
  install the skill into the scanned skills dir itself; the user must (Task C).
- **Filesystem tools are deferred + `tool_search` is flaky.** `write_file`, `edit_file`,
  `create_directory`, `copy_file_user_to_claude`, `list_directory` must be loaded via
  `tool_search`, which frequently returns the wrong connectors (Gmail/Vercel/FMP). Retry with
  varied queries until they load.
- **Deploy/verify method that works:** edit on the sandbox → apply the *same* edits to the on-disk
  file via `Filesystem:edit_file` (exact `oldText`/`newText`) → `copy_file_user_to_claude` the file
  back → `diff` against the sandbox copy → run `pytest` on the copied-back bytes. This is how the
  current deploy was verified byte-exact.
- **LibreOffice rendering ≈ but ≠ Word.** Page measurement uses `soffice → PDF → page count`. The
  sandbox lacks true Calibri and substitutes **Carlito** (metric-compatible), so sandbox previews
  are representative but the authoritative render is on the user's machine.
- **`JOBSEARCH_ROOT`** defaults to `~/Documents/Claude/JobSearch` (env-overridable). All script
  paths derive from it.

**Locked paths:**
```
cv.md                 ~/Documents/Claude/JobSearch/cv.md            (source of truth)
template               …/JobSearch/templates/template_0.docx        (Calibri)
search definitions     …/JobSearch/search_config.json
cross-run dedupe       …/JobSearch/seen_jobs.json                   (single underscore)
dated outputs          …/JobSearch/YYYY-MM-DD/
per-run scratch        …/JobSearch/.fetch-runs/                     (auto-pruned)
output resume          {sanitized_title}__{company}_{short_id}.docx
output critique        {sanitized_title}__{company}_{short_id}-critique.md
```

---

## 5. Non-negotiable integrity constraints (carry forward verbatim)

1. **Never invent or alter a metric.** Numbers come only from `cv.md`. No estimating, rounding,
   or merging two accomplishments into one combined figure. Missing metric → write it without a
   number.
2. **Never claim a skill/keyword that doesn't trace to `cv.md`.** Filter 1 may *identify* a missing
   keyword; Filter 2 may *use* it only if the underlying experience genuinely exists; else omit and
   flag.
3. **The integrity gate is mandatory every run. It FLAGS, never rejects** — flagged output is still
   written but marked "needs human check."
4. **`.docx` only** (never PDF/LaTeX as the working format).
5. **Submission is out of scope** — the skill ends at files on disk. No auto-apply, no CAPTCHA
   bypass.
6. **Trimming is honest omission, never fabrication.** The cascade and the undergrad-strip only
   *remove whole items / lines* — they never edit a bullet's words or a metric, so the gate result
   is unchanged.

---

## 6. Data contracts (handoffs between stages)

- **Input listing** (from `/fetch-jobs` → `/score-job`, passed through): normalized object with
  `job_id`, `company`, `title`, `location`, `salary`, `url`, `description`, `source_search_name`,
  etc. The tailoring skill reads `description` (don't re-scrape) and uses `title`/`company`/`job_id`
  for the filename.
- `filter1.json` → `{ match_score, missing_keywords[], red_flags[] }`
- `filter2.json` → TailoredResume + `_inserted_keywords[]` + `flags[]`
- `filter3.json` → final TailoredResume + `_inserted_keywords[]` + `ats_notes[]` + `skim_notes[]`
  — **this is what renders and what the gate checks.**
- `gate_report.json` → `{ passed, needs_human_check, number_flags[], keyword_flags[], summary }`

**TailoredResume schema** (validated by `common.validate_tailored_resume`): `contact{name,line}`,
`summary`, `skills[{category,items}]`, `experience[{title,company,location,dates,context,bullets}]`,
`projects[…]`, `education[{degree,institution,location,dates,details}]`, `certifications[]`. Plus
designed-template fields: `role_title` (the **target** job's title — an honest headline, not a held
title), `key_achievements[{label,text}]`, `areas_of_expertise[]` (flat, ~9, for the 3-col block),
`additional_skills` (string).

**Note on education `details`:** GPA / Dean's-list / honours / awards / coursework are stripped at
render by default in *both* renderers (`strip_undergrad_achievements`). Degree/institution/dates are
always kept. Filters needn't emit those lines.

---

## 7. The dynamic budget cascade (designed template) — how it behaves

`render_template.py` runs by default: fill → measure pages → if over `--max-pages` (default **1**),
walk `BUDGET_LADDER` and stop at the loosest tier that fits.

| tier | key achievements | experiences | top / other bullets | projects | tightener floor |
|---|---|---|---|---|---|
| full | 3 | 3 | 4 / 2 | 2 | 0.90 |
| tight-ka | 2 | 3 | 3 / 2 | 2 | 0.90 |
| one-project | 2 | 3 | 3 / 2 | 1 | 0.88 |
| hard-bullets | 2 | 3 | 2 / 1 | 1 | 0.85 |
| last-resort | 2 | 2 | 2 / 1 | 1 | 0.82 |

- Trims by **whole-item omission only** (drop a key achievement, a trailing bullet, a project, a
  trailing role); items are most-relevant-first, so it sheds the least-relevant material. Never
  edits text/metrics → gate result unchanged.
- Reports `fit_ok`, `tier`, `trimmed` (e.g. `key_achievements: 3->2`), and the full `ladder`.
- **Filter 3 still owns bullet length.** The cascade caps *counts*, not wording — long (2–3 line)
  bullets force it to drop whole roles (down to `last-resort` = 2 experiences). Tight ~1-line
  bullets keep it gentle (3 experiences). So Task A must produce tight bullets.
- If `last-resort` is still over target → tightest render left on disk, `fit_ok: false`, note to
  accept overflow ("needs human check") or cut upstream. If page count is unmeasurable (no
  LibreOffice) → renders full budget, `fit_ok: null`.
- Disable with `--no-cascade`; change target with `--max-pages N`.

---

## 8. Adjacent phases (context only — not Phase 3 scope)

- **Phase 2 `/score-job` is NOT built.** It scores a listing against `cv.md` and returns strict
  JSON `{ fit_score, rationale, matched_strengths, likely_gaps }` + a threshold. It is a
  prerequisite for the Phase 4 orchestrator and feeds Phase 3 its input. This is the next real gap
  after Phase 3 closes.
- **Phase 4 orchestrator** chains fetch → score → tailor → write into the dated folder + `summary.md`,
  updates `seen_jobs.json`, and explicitly does **not** apply. It depends on Task C (skills being
  invocable) being resolved.

---

## 9. Suggested first moves in the new conversation

1. Read this doc, then `SKILL.md` and `cv.md`.
2. Re-confirm the on-disk skill tree and run `pytest tests/` (expect 25 passed). Re-pull the
   Calibri `template_0.docx` and confirm anchors if anything seems off.
3. Do **Task A with one real listing as a dry run** — run the filters as genuine model reasoning,
   gate it, render it, review it. Fix `SKILL.md` if the output reveals gaps.
4. Repeat for 4 more real listings. When five are clean and submit-worthy, Phase 3's done-when is
   met.
5. Handle **Task B** (README sync, page-target confirm, LibreOffice check) and **Task C** (install
   the skill so `/tailor-resume` is invocable) — Task C is also a prerequisite for Phase 4.

---

*Prepared as a self-contained handoff. The skill code is current on disk and unit-tested; the
remaining work is real-listing validation + polish + registration, not rebuilding.*
