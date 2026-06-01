# Phase 1 — Config-Tuning Instructions (`search_config.json`)

I'm in Phase 1 of the build plan, on the config-tuning substep. The goal is to take one entry from `search_config.json` at a time, test it against one Apify Actor, look at real results, and tune the entry's titles / locations / `workplace_type` / salary filter until the first ~20 results are mostly jobs I'd actually consider. This is iterative work — don't try to do it all at once.

A second, equally important goal has emerged: **document where an Actor does *not* honor a filter natively**, so the fetch/pipeline layer knows what it must enforce post-fetch. A clean entry config is not enough if the Actor ignores half of it.

## Rules for this conversation

1. We tune **one search entry at a time**. I'll tell you which entry to start with. Don't propose running multiple entries in parallel.

2. We test against **one Actor at a time** per entry. Start with whichever Actor has the cleanest filter surface for the entry: `fantastic-jobs/advanced-linkedin-job-search-api` for structured LinkedIn searches, `valig/glassdoor-jobs-scraper` for Glassdoor, `borderline/indeed-scraper` for broad Indeed coverage. **Note:** despite earlier assumptions, `borderline/indeed-scraper` is *not* a direct-numeric-salary filter — its search-query mode has no salary field at all (see Per-Actor findings). Pick the Actor based on the entry's most important hard filter and confirm against the schema before relying on it.

3. **Cap result count at 10–15 per call** during tuning (`maxRows` plus a `maxItems` run cap). We're trying to see signal, not to populate a database. If a single call would cost more than ~$1 in Apify credit, stop and tell me — something is mis-configured. (For reference, `borderline/indeed-scraper` is pay-per-result at $0.005/job, so a 15-row call is ~$0.08.)

4. After each call, present the first ~20 results in a compact table (company, title, location, workplace type, salary if stated). Mark each salary against the entry's `min_salary` floor on the `salary_match_field` basis, and flag any row that leaks past a filter. I'll review with you and we'll decide what to tune.

5. **Common tuning moves:**
   - Titles pulling in adjacent-but-wrong roles → first decide *why*. If the entry's titles are genuinely too broad, narrow to more specific real titles (no short generic fragments like "Engineer" or "Manager"). But if the Actor is **fuzzy-matching** titles that don't appear in the entry at all (matching on description), the fix is a **post-fetch title allow-list**, not narrower entry titles.
   - Locations returning the wrong region, metro spillover, or no results → fix format per the Actor's schema, and pin the Actor's **radius** tightly (e.g. `radius: "0"` on Indeed) to stop neighbouring-region leakage.
   - `workplace_type` not filtering as expected → confirm the per-Actor translation; if the Actor doesn't honor it (or can't distinguish hybrid from on-site), plan to enforce post-fetch.
   - Too many "salary not stated" listings dropping out → confirm `salary_unknown_action: "include"` is working.
   - Salary present but in the wrong units (e.g. hourly comps) → normalize before comparing (hourly × 2080 → annual).
   - Too many off-target results across the board → the entry might be conflating two role families; split it.

6. **Never tell me a result is good unless you'd defend it.** If the first 20 results contain 12 jobs that obviously don't match what I asked for, say so directly. Don't soft-pedal. Quantify it (e.g. "9 of 15 on-target").

7. **Don't edit `search_config.json` yourself.** Propose edits as a JSON diff or as a complete updated entry; I'll apply them and tell you when the file is updated for the next iteration. Distinguish clearly between **entry-config changes** (titles/locations/workplace_type/min_salary in the file) and **fetch/pipeline-enforcement changes** (post-fetch filters, radius pins, unit normalization) — the latter don't belong in `search_config.json`.

8. **No CV reasoning in this phase.** Don't comment on whether a returned job matches my CV — that's `/score-job`'s job, in Phase 2. Here we only care about whether the *hard filters* are doing what we think they're doing.

Before I tell you which entry to start with, confirm you have access to `search_config.json` and that you understand the rules above. Then I'll pick the first entry.

---

## Salary semantics (current)

The salary field is **`min_salary`** — a single number, interpreted in the **role's own geographic currency, with no FX conversion**. A US role's stated salary is compared as USD against `min_salary`; a CA role's is compared as CAD against the same number. `salary_match_field` (currently `"max"`) selects which end of a stated range to test. `salary_unknown_action: "include"` (global) keeps listings with no stated salary.

## Config state (as of this revision)

`search_config.json` holds five entries, all using the single `min_salary` field:

| Entry | `min_salary` | Notes |
|-------|--------------|-------|
| `swe_north_america` | 130000 | titles already specific; CA+US, all workplace types |
| `ml_remote_north_america` | 130000 | |
| `product_manager_north_america` | 105000 | |
| `project_manager_north_america` | 100000 | |
| `consultant_north_america` | 110000 | |

There is **no** `swe_onsite_hybrid_us` entry — if that scope is wanted it would be a new fork of `swe_north_america` (US locations only, `workplace_type: ["on_site", "hybrid"]`).

All entries currently share the same six locations (`Toronto, ON` / `Vancouver, BC` / `Calgary, AB` / `New York, NY` / `San Francisco, CA` / `New Jersey, NJ`), `countries: ["CA", "US"]`, `workplace_type: ["on_site", "hybrid", "remote"]`, and `job_type: ["full-time", "contract"]`.

---

## Per-Actor findings

### `borderline/indeed-scraper` (tested against `swe_north_america`)

Tested on Toronto/CA and New York/US. Titles and locations in the entry are correct as written — the issues below are all Actor behavior, not entry-config defects.

**Schema / call mechanics**
- Pay-per-result, $0.005/job. A 15-row call ≈ $0.08.
- Search-query mode fields: `country` (single enum), `query` (single string; supports boolean `OR` and `-exclude` but matches fuzzily), `location` (single string), `radius`, `remote` (`remote` | `hybrid` only), `level` (US domain only), `sort`, `jobType` (single enum), `fromDays`, `maxRows`. A URLs mode exists as an alternative.
- **One country and one location per call.** An entry spanning CA+US and six cities can only be exercised one city/country at a time.

**What the Actor does *not* honor — enforce these post-fetch**
1. **No salary field in query mode.** `min_salary` cannot be filtered at the Actor; apply it post-fetch (or build a URLs-mode URL with the salary param baked in).
2. **No `title_exclude` field.** Modeled as `-term` in the query, but Indeed's `-` operator is unreliable (VP-titled roles still leaked until `-VP -"Vice President"` was added). Enforce `title_exclude` post-fetch.
3. **Fuzzy title matching.** Roles whose titles contain none of the entry's title tokens still came back (e.g. "Delivery Specialist", "Senior Applied Scientist") by matching on description. Requires a **post-fetch title allow-list**: keep a listing only if its title contains one of the entry's canonical title tokens.
4. **`workplace_type` not selectable as the entry wants.** Only `remote` or `hybrid` can be requested; there is no `on_site` option, and "not remote" conflates on-site with hybrid. For an entry wanting all three, leave `remote` unset (returns everything); the output exposes only an `isRemote` boolean, so hybrid-vs-on-site can't be separated from this source — enforce/annotate post-fetch if needed.
5. **Radius defaults wide → metro spillover.** New York pulled in Plainsboro, NJ results until `radius: "0"` was set. Pin radius tightly on the fetch call. (Radius lives in the call, not the entry — unless we choose to add a per-entry radius field.)
6. **Hourly comps need normalization.** Hourly roles return `salary.salaryMax` as the hourly number (e.g. `50`). Normalize hourly × 2080 → annual before comparing against `min_salary`.

**Net result for `swe_north_america`:** with `radius: "0"` and the VP exclusions, NY went from ~9/15 to ~12–13/15 on-target. Remaining noise (Applied Scientist, Delivery Specialist) is exactly what the post-fetch title allow-list resolves. Toronto/CA came back 15/15 on-target with no fixes needed.

**Required post-fetch enforcement layer (Indeed):** title allow-list • `title_exclude` • `min_salary` floor (in-currency, hourly-normalized, unknown→include) • `workplace_type`.

**Re-confirmed (NY/US, `radius: "0"`, 15-row run, 2026-05-31):** `radius: "0"` held — zero location spillover, all 15 rows New York, NY. VP/Manager excludes worked. Raw on-target ~6/15 → ~9/15 after the "Forward Deployed" title fix; the remaining junk (Patent Attorney ×2, "Delivery Specialist", "Principal Engineer", "Full Stack Lead") is exactly what the post-fetch title allow-list resolves. Hourly normalization confirmed live: `.Net Core Software Engineer` $50/hr → $104k **fails** the $130k floor; `Full Stack Lead – Java` $81/hr → $168.5k **passes**. `isRemote` is still the only workplace signal (no hybrid-vs-on-site separation).

---

### `fantastic-jobs/advanced-linkedin-job-search-api` (tested against `swe_north_america`)

Tested NY/SF/Toronto/Vancouver in one combined call, plus isolated Calgary and New Jersey runs. **Cleanest filter surface of the three Actors — 14/15 on-target.** The issues are minor and mostly post-fetch.

**Schema / call mechanics**
- Pay-per-event: $0.005/job + ~$0.01 Actor start. A 15-row call ≈ $0.085.
- Search fields are **arrays**: `titleSearch`, `titleExclusionSearch`, `locationSearch`, `EmploymentTypeFilter` (`FULL_TIME` / `CONTRACTOR` / …), `aiWorkArrangementFilter` (`On-site` / `Hybrid` / `Remote OK` / `Remote Solely`). Plus `timeRange` (`1h`/`24h`/`7d`/`6m`), `limit`, `includeAi`, `removeAgency`, `seniorityFilter`, `aiHasSalary` (bool), and more.
- **All six locations can be searched in ONE call** (`locationSearch` is an array) — unlike Indeed/Glassdoor's one-location-per-call.

**What the Actor honors NATIVELY (no post-fetch needed)**
1. **Titles** — `titleSearch` array, phrase matching. The entry's title tokens map 1:1.
2. **`title_exclude`** — `titleExclusionSearch` array. Worked cleanly (no Manager/Director/VP leaked), unlike Indeed's unreliable `-term`.
3. **Locations** — `locationSearch` array, exact `City, Region, Country` full names. No spillover.
4. **`job_type`** — `EmploymentTypeFilter` (`FULL_TIME`, `CONTRACTOR`).
5. **`workplace_type`** — `ai_work_arrangement` / `aiWorkArrangementFilter` **distinguishes Hybrid from On-site** (the thing Indeed structurally cannot). Relevant for any future `swe_onsite_hybrid_us` fork.

**What the Actor does NOT honor — enforce post-fetch**
1. **No numeric salary-floor input.** Only `aiHasSalary` (boolean: has-any-salary). `min_salary` must be enforced post-fetch using `ai_salary_maxvalue` (fall back to `salary_raw.value.maxValue`), in-currency, unknown→include, hourly × 2080. **Leave `aiHasSalary` unset** — setting it `true` drops "salary not stated" rows and violates `salary_unknown_action: "include"`.
2. **Internships leak through title tokens.** "Full Stack Engineer Intern" (tagged `employment_type: FULL_TIME`) matched the `Full Stack Engineer` token. Drop via seniority `Internship` / title contains "intern" post-fetch, or add `"Intern"`/`"Internship"` to entry `title_exclude` (honored natively here, but `"Intern"` risks colliding with "Internal…/International…" under phrase matching — prefer the post-fetch route).

**Net result for `swe_north_america`:** 14/15 on-target. The one leak was the internship above.

**Required post-fetch enforcement layer (fantastic-jobs):** `min_salary` floor (in-currency, hourly-normalized, unknown→include) • intern/internship exclusion (if not in entry) • workplace annotation from `ai_work_arrangement` (reliable, no enforcement needed for all-three entries).

---

### `valig/glassdoor-jobs-scraper` (tested against `swe_north_america`)

Tested NY (keyword `Software Engineer`, 15 rows). **Thinnest filter surface and noisiest output — ~4-6/15 on-target.** Cheapest per result but the most enforcement-hungry.

**Schema / call mechanics**
- Pay-per-event: $0.0004/result + ~$0.001 start. A 15-row call ≈ $0.007.
- Input is minimal: `keywords` (**single string**), `location` (**single string**), `daysOld`, `easyApply`, `minRating`, `limit`, `excludeJobIds`. That's it.

**What the Actor honors NATIVELY** — effectively **nothing** of the entry's hard filters. No title array, no `title_exclude`, no `job_type`, no `workplace_type`, no salary filter.

**What the Actor does NOT honor — enforce post-fetch**
1. **Single keyword, no title array → heavy fuzzy leaks.** One keyword (`Software Engineer`) pulled "Python Engineer with AI", "Fullstack Java Developer", "Software QA Engineer", "AI DevOps Engineer", "AI Systems Engineer", "Consultant – Guidewire Developer". Requires the post-fetch **title allow-list**. To exercise the entry's full title set, loop one title per call or accept a representative keyword + allow-list.
2. **No `radius` parameter at all → metro spillover that CANNOT be pinned at the Actor.** `New York City, US` returned Albany (~150 mi), Melville and Jericho (Long Island). **Location precision is post-fetch-ONLY here** — drop by checking `location.name`. This is unique to Glassdoor.
3. **No workplace-type / remote field in the output.** on_site/hybrid/remote is **unknowable** from this source.
4. **No `job_type` filter.** Enforce post-fetch.
5. **Salary floor post-fetch**, hourly × 2080 (confirmed: "Python Engineer" $65/hr → $135.2k passes). `pay.period` exposes `HOURLY`/`ANNUAL`.
6. **Single-employer flooding.** Deloitte was 8/15. Consider a `max_per_employer` cap.

**Net result for `swe_north_america`:** 4/15 clean as the entry was written (6/15 after the "Forward Deployed" title fix); the rest were title leaks, metro spillover, or sub-$130k.

**Required post-fetch enforcement layer (Glassdoor):** title allow-list • **location pin (no radius)** • `min_salary` floor (in-currency, hourly-normalized, unknown→include) • `job_type` • `workplace_type` (unobtainable from source — annotate as unknown) • optional `max_per_employer`.

---

### Cross-Actor summary — `swe_north_america`

| | fantastic-jobs | Indeed (borderline) | Glassdoor (valig) |
|---|---|---|---|
| Clean on-target (15-row) | **14/15** | ~9/15 (allow-list lifts higher) | ~4–6/15 |
| Titles | array + exclude, **native** | fuzzy; `-exclude` unreliable → post-fetch | single keyword, **heavy** fuzzy leaks |
| Locations | all 6 in one call, no spillover | 1/call; clean with `radius:"0"` | 1/call; **spillover, no radius fix** |
| Workplace | **separates hybrid/on-site** | `isRemote` bool only | **no field at all** |
| `job_type` | `FULL_TIME`+`CONTRACTOR` native | one per call | none |
| Salary | post-fetch | post-fetch | post-fetch |
| Cost / 15 rows | ~$0.085 | ~$0.075 | ~$0.007 |

**Verdict:** fantastic-jobs is the primary Actor for this entry. Indeed is a usable secondary once the post-fetch layer is on. Glassdoor is the weakest fit and the most enforcement-hungry (location precision is post-fetch-only).

---

### Location-format verification — fantastic-jobs (2026-05-31)

Isolated single-location runs confirmed the two formats missing from the `actor_location_format` override table:

- **Calgary** → `"Calgary, Alberta, Canada"`: 15/15 rows in Calgary, Alberta, Canada. No spillover. ✅
- **New Jersey** → `"New Jersey, United States"`: 15/15 rows in region New Jersey, US (Jersey City, Iselin, Morristown, Princeton, Whippany, Moorestown, Englewood Cliffs, + one state-level posting). Resolves **statewide**, matching the entry's `"New Jersey, NJ"` state-level intent. No leak into NY/PA. ✅

The earlier zeros for NJ/Calgary in the combined six-location run were **not** a format failure — the `limit: 15` filled with NY/SF/Toronto/Vancouver before the smaller metros surfaced. **Fetch-layer note:** in a combined OR'd multi-location run, smaller metros get crowded out of the top-N; to guarantee coverage of all six, raise `limit` substantially or fetch per-location. (Glassdoor/Indeed Calgary+NJ formats remain unverified — confirm when testing those Actors outside NY.)

---

### Entry-config defect found — `swe_north_america`

One real defect (not Actor noise): the title **`"Forward Deployment Engineer"` matched zero listings** across Glassdoor + Indeed, while the real industry title **`"Forward Deployed Engineer"`** appeared 6× (Deloitte/Palantir FDE roles). Proposed fix — replace `"Forward Deployment Engineer"` → `"Forward Deployed Engineer"` in the entry's `titles`. *(Applies to `search_config.json`; to be applied by Austin — not edited here.)* All other entry fields (titles, locations, `workplace_type`, `min_salary`, `salary_match_field`) verified sound — no other entry-config change warranted.
