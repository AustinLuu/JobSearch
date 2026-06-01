# `/fetch-jobs` Skill Specification

A skill that fetches recent job listings from LinkedIn, Indeed, and Glassdoor via the Apify connector, filtered by the searches defined in `search_config.json` and constrained to the last **N days**, where N is supplied at invocation.

**Invocation:** `/fetch-jobs [N] [source] [entry]`
- `N` — recency window in days; parse the leading integer, then **snap to the supported window** (see below). Absent → default 7.
- `source` — optional board/actor selector (see *Source selection*). Absent → default **`fantastic-jobs`** (LinkedIn only).
- `entry` — optional search-entry selector by `name` (see *Entry selection*). Absent → **all entries** in `config.searches`.

`source` and `entry` are both non-numeric tokens; order between them does not matter — each is classified by matching against the known source aliases first, then the entry names (see *Argument parsing*).

Examples: `/fetch-jobs 7` (last 7 days, default LinkedIn, **all 5 entries**) · `/fetch-jobs 7 linkedin` (same) · `/fetch-jobs 1 indeed` (last day, Indeed, all entries) · `/fetch-jobs 7 all` (all boards, all entries) · `/fetch-jobs 7 swe_north_america` (default LinkedIn, **just that entry**) · `/fetch-jobs 7 all product_manager_north_america` (all boards, one entry) · `/fetch-jobs` (defaults: 7 days, fantastic-jobs, all entries).

This is the discovery front-end shared by both the Cowork-scheduled and cloud-headless pipelines. Its output (a normalized, deduped, recency-and-hard-filtered listing array) feeds the scoring step (`/score-job`).

> **Schema verification log.** The per-Actor fields below were verified against the live Apify schemas on **2026-05-31**. Actor last-modified dates at verification: LinkedIn `2026-05-26`, Indeed `2026-05-27`, Glassdoor `2026-05-25`. Re-run `fetch-actor-details` before any future build — these schemas change, and several fields here already diverge from the original draft of this spec.

> **Config schema (migrated 2026-05-31).** This spec now matches the **live** `search_config.json`: each entry uses a single `min_salary` (compared in the role's own currency, no FX) plus `salary_match_field` (`"min"`/`"max"`, selecting which end of a stated range to test); the `global` block carries `max_results_per_source_per_search`, `salary_unknown_action`, `salary_normalization` (hourly × 2080), `max_per_employer`, `exclude_companies`, and a per-Actor `actor_enforcement` map. The earlier per-currency floors (`min_salary_cad` / `min_salary_usd`) are gone.

---

## Two design facts worth internalizing

**1. Hard filters live here; CV-relevance does not.** This skill applies only the deterministic filters from `search_config.json` (titles, locations, workplace type, country, job type, salary floor, excluded companies). CV-fit reasoning is `/score-job`'s job, in Phase 2. Pushing CV-relevance into discovery doesn't speed anything up — it just moves the same Claude API call earlier in the pipeline while making `/fetch-jobs` slower, more expensive, and less reusable.

**2. The three Actors support different filter surfaces, and each names its fields differently.** So the skill's central job is **translating canonical config fields into each Actor's native parameter format — and enforcing the rest post-fetch.** Filtering at the source matters because these Actors are pay-per-result: a filter the Actor honors natively means you don't pay for listings you'd discard. But the native surfaces are *uneven* — Glassdoor in particular exposes almost nothing beyond title/location/recency, so a large share of filtering for that board is post-fetch. Know which is which (see the table) so you neither pay for junk nor silently skip a filter the Actor never applied.

---

## Recency: only two supported windows (1 day or 7 days)

This is the single most important correction from schema verification. The original draft treated recency as a free integer N translated per board. **It is not.** Across the three Actors, the only day/week windows that *every* board can express natively and precisely are **1 day** and **7 days**:

- **LinkedIn** (`timeRange`) offers enum buckets `1h` / `24h` / `7d` / `6m`. At day-or-coarser granularity the only options are `24h` and `7d` — there is **no 3-day bucket**. (A separate `datePostedAfter` ISO field exists but the Actor explicitly discourages it for regular-interval runs and warns it is duplicate-prone, so we don't use it.)
- **Indeed** (`fromDays`) is a **string enum** `"1"` / `"3"` / `"7"` / `"14"` — not a free integer. `"1"` and `"7"` are available.
- **Glassdoor** (`daysOld`) is a direct integer, so it can take 1 or 7 exactly.

Therefore the skill supports exactly two recency windows. The invocation argument is **snapped** to one of them:

```
M = parse_leading_integer(args)   # may be absent
if M is absent:        N = 7      # default — see rationale
elif M <= 1:           N = 1      # daily window
else:                  N = 7      # weekly window (everything >= 2 rounds UP to 7)
```

**Why round up (2–6 → 7) instead of to-nearest.** Snapping `3` down to `1` would silently drop every listing posted 2–3 days ago — a discovery pipeline must never under-collect. Rounding up returns a superset; the post-fetch date check (below) then trims to exactly N if a tighter bound is wanted. For windows `> 7`, also clamp to 7 (7 is the agreed ceiling; LinkedIn's only larger bucket is `6m`, which is far too wide).

**Why default to 7 (weekly), not 1.** The pipeline runs on a daily-ish cadence, and Cowork **skips** scheduled runs when the machine is asleep/closed (per the Cowork plan), recovering on the next wake. A 1-day window plus a skipped run means jobs posted on the skipped day are never seen. A **7-day window plus cross-run dedupe** is resilient: even after a few skipped days, the next run's 7-day window still covers the gap, and `seen_jobs.json` prevents re-tailoring anything already processed. Use `N=1` only for deliberately tight, low-cost runs where you know the schedule fired.

> **Conflict to confirm:** `project-instructions.md`, `build-plan.md`, and the two pipeline plans all reference a default of `N = 3`. Three is no longer directly representable (LinkedIn has no 3-day bucket) and now resolves to the 7-day window under the round-up rule. Recommend updating those docs to say the default is **7 (weekly)**, with **1 (daily)** as the only alternative. Flagging rather than editing those files unprompted.

Per-window translation:

| N | LinkedIn `timeRange` | Indeed `fromDays` | Glassdoor `daysOld` |
|---|---|---|---|
| **1** | `"24h"` | `"1"` (string) | `1` (int) |
| **7** | `"7d"` | `"7"` (string) | `7` (int) |

Always still apply the **post-fetch date safety check** (`r.date_posted >= today − N`) for all three boards — bucket boundaries and posting-time delays make source-side recency approximate.

---

## Source selection

The skill takes an optional second positional argument selecting which board(s)/Actor(s) to run. This keeps tuning and cost-control cheap: you can exercise a single board without paying for the others.

| `source` value | Resolves to | Board |
|---|---|---|
| *(omitted)* / `fantastic-jobs` / `linkedin` | `fantastic-jobs/advanced-linkedin-job-search-api` | LinkedIn |
| `indeed` | `borderline/indeed-scraper` | Indeed |
| `glassdoor` | `valig/glassdoor-jobs-scraper` | Glassdoor |
| `all` | all three of the above | LinkedIn + Indeed + Glassdoor |
| *(full actor slug, e.g. `cheap_scraper/linkedin-job-scraper`)* | that exact Actor | — (must be re-verified before use; see Decisions) |

**Default is `fantastic-jobs`** — the LinkedIn Actor with the cleanest validated filter surface (14/15 on-target, native title/title_exclude/location/job_type/workplace, separates hybrid from on-site). Running the default means **LinkedIn only**, not all three boards. Use `all` to fan out across every board.

When a single board is selected, only that board's row of the per-Actor translation table and enforcement matrix applies.

---

## Entry selection

The skill takes an optional argument selecting **which search entry** to run, by its `name` in `config.searches`. Omitted → **all entries** run (the default; this is what a scheduled production run does).

| `entry` value | Effect |
|---|---|
| *(omitted)* | Run every entry in `config.searches` (default). |
| an entry `name` (e.g. `swe_north_america`) | Run only that one entry. |

Valid names are whatever's in the live config — currently `swe_north_america`, `ml_remote_north_america`, `product_manager_north_america`, `project_manager_north_america`, `consultant_north_america`. Match is **exact, case-sensitive** against `entry.name`. An unrecognized entry name is an error (fail loudly — don't silently run all entries, which would be a surprising and expensive misfire).

**Why it exists:** during Phase-1 tuning you iterate one entry at a time. Without this selector every test run fetches all five entries × every location, which is wasteful and slow. With it, `/fetch-jobs 7 swe_north_america` (or `/fetch-jobs 1 indeed swe_north_america`) exercises exactly the entry under test. Production runs simply omit it.

> **Scope note:** single-entry selection narrows only the `config.searches` loop. Recency, source, per-location fetch, post-fetch enforcement, and all three dedup scopes behave identically — including cross-run dedup against `seen_jobs.json`. Running a single entry still records its results in `seen_jobs.json` when the orchestrator commits (so a later all-entries run won't re-surface them); during tuning where you want repeatable output, run against a scratch `seen_jobs.json` or skip the commit.

---

## Argument parsing

Three positional-ish arguments, but only `N` is positional. `source` and `entry` are both non-numeric and are disambiguated by content, so they can appear in either order:

```
tokens = split(args)
N_token   = first token matching /^\d+$/         # optional; else default 7
remaining = all other tokens
source = default "fantastic-jobs/advanced-linkedin-job-search-api"
entry  = default ALL

for tok in remaining:
    if tok is a known source alias OR contains "/":   source = resolve_source(tok)
    elif tok exactly matches a config.searches[].name: entry  = tok
    else: ERROR(f"unrecognized argument: {tok}")      # typo guard — never silently ignore
```

Rules:
- The source token is matched case-insensitively against the alias table; an unrecognized token containing `/` is treated as a full actor slug; any other unrecognized non-numeric token that also isn't a valid entry name is an error.
- Entry-name match is exact and case-sensitive (config names are lowercase_snake).
- At most one source selector and one entry selector; a second of either is an error.

---

## Inputs

### 1. Invocation arguments

- `N` — recency window in days, snapped to **1 or 7** (see Recency). Default **7**.
- `source` — board/actor selector (see Source selection). Default **`fantastic-jobs`**.
- `entry` — search-entry selector by `name` (see Entry selection). Default **all entries**.

### 2. `search_config.json`

Stored at `~/Documents/JobSearch/search_config.json`. Live schema:

```json
{
  "searches": [
    {
      "name": "string — used for tagging matches and for logging",
      "titles": ["string", "..."],
      "title_exclude": ["string", "..."],
      "locations": ["City, Region", "..."],
      "countries": ["ISO-2", "..."],
      "workplace_type": ["on_site" | "hybrid" | "remote", "..."],
      "job_type": ["full-time" | "contract" | "...", "..."],
      "min_salary": 105000,
      "salary_match_field": "max" | "min"
    }
  ],
  "global": {
    "max_results_per_source_per_search": 20,
    "salary_unknown_action": "include" | "exclude",
    "salary_normalization": { "hourly_to_annual_multiplier": 2080 },
    "max_per_employer": 3,
    "exclude_companies": ["string", "..."],
    "actor_location_format": { "...": "per-Actor location string overrides" },
    "actor_enforcement": {
      "<actor full name>": {
        "native": ["field", "..."],
        "post_fetch": ["field", "..."],
        "call_defaults": { "...": "..." },
        "limits": "string",
        "notes": "string"
      }
    }
  }
}
```

Field notes:
- **`countries`** is an array of ISO-2 codes (`["CA", "US"]`). The skill iterates locations directly (see per-location fetch below); `countries` is used to derive each Actor's `country` parameter from the location being fetched, and as a sanity bound on post-fetch location checks.
- **`locations`** holds `"City, Region"` strings (e.g. `"Toronto, ON"`, `"New York, NY"`). These are canonical; each Actor needs its own format (LinkedIn wants `"City, Region-full-name, Country"`, etc.), so they're translated per-Actor at call time via `actor_location_format` overrides + the documented format rules. `locations: []` (empty) means "don't constrain by city, only by country." **Glassdoor requires a non-empty `location`**, so an empty `locations` must fall back to a country-derived location string (`country_to_location`).
- **`title_exclude`** is the canonical exclusion list, enforced per the matrix (LinkedIn native — *list every variant incl. abbreviation + spelled-out form*; Indeed/Glassdoor post-fetch).
- **`workplace_type`** is always explicit. Native-mapping is uneven (LinkedIn partial/BETA + separates hybrid/on-site; Indeed partial; Glassdoor none) — see the table.
- **`min_salary`** is a single number, interpreted in the **role's own geographic currency, with no FX** (a US role's salary compared as USD; a CA role's as CAD — both against the same number). **`salary_match_field`** selects which end of a stated range to test (`"max"` = compare the range's upper bound against the floor). **No board filters salary natively** → always post-fetch, combined with `salary_unknown_action` and `salary_normalization`.
- **`salary_normalization.hourly_to_annual_multiplier`** (2080) converts hourly comps to annual before comparison.
- **`max_per_employer`** caps distinct listings per company; applied **after** dedup (see pseudocode).
- **`exclude_companies`** is global (cross-search); enforced post-fetch on all boards.
- **`actor_enforcement`** is the machine-readable mirror of the per-Actor matrix below: per-Actor `native` vs `post_fetch` field lists, plus `call_defaults` (e.g. Indeed `radius:"0"`), `limits`, and `notes`. The skill reads this to decide, per selected Actor, which filters to push to the call and which to enforce after fetch.

### 3. `seen_jobs.json`

Stored at `~/Documents/JobSearch/seen_jobs.json`. An array of `job_id` strings from prior runs, used for cross-run dedupe. Empty array `[]` if missing.

---

## Per-Actor translation table

The three recommended Actors and how canonical config fields map to each, **as verified 2026-05-31**. `PF` = the Actor does **not** support this filter natively → the skill must enforce it **post-fetch**. **Always re-verify with `fetch-actor-details` before building** — schemas change.

| Canonical field | LinkedIn (`fantastic-jobs/advanced-linkedin-job-search-api`) | Indeed (`borderline/indeed-scraper`) | Glassdoor (`valig/glassdoor-jobs-scraper`) |
|---|---|---|---|
| **Recency (1 or 7 days)** | `timeRange` enum — `1`→`"24h"`, `7`→`"7d"` | `fromDays` **string** enum — `1`→`"1"`, `7`→`"7"` | `daysOld` integer — `1`→`1`, `7`→`7` |
| **Titles** | `titleSearch[]` (array; **prefix match** via `:*`, e.g. `"Soft:*"`) | `query` (single string; OR-join the array — *verify OR is honored*) | `keywords` (single string, **required**; OR-join — *verify*) |
| **Title exclusions** | `titleExclusionSearch[]` — **native, but EXACT-PHRASE match.** An abbreviation in the array does NOT catch the spelled-out form. List every variant (`"VP"` **and** `"Vice President"`). Verified 2026-05-31 (PM run): a "Senior Product Manager CoBrand - Vice President" row leaked past a config excluding only `"VP"`. | modeled as `-term` in `query`, but Indeed's `-` operator is **unreliable** → **PF** (post-fetch title_exclude) | **PF** (no field) |
| **Locations** | `locationSearch[]` (array; **phrase match**, exact `"City, State/Region, Country"`, English names, **no geo IDs**) | `location` (single string: city/state/zip/`"remote"`) | `location` (single string, **required**) |
| **Country** | embedded in `locationSearch` strings | separate `country` enum (**uses `"uk"`**, `"us"`, `"ca"`, …) | embedded in `location` string |
| **Workplace type** (`on_site`/`hybrid`/`remote`) | `remote` (bool) + **BETA** `aiWorkArrangementFilter[]` tokens `On-site`/`Hybrid`/`Remote OK`/`Remote Solely` (remote = include both `Remote OK`+`Remote Solely`). **Separates hybrid from on-site** — the only board that does. | `remote` **enum** `["remote","hybrid"]` (string). `on_site` → **PF**; can't separate hybrid/on-site (only `isRemote` bool in output) | **PF** (no field at all) |
| **Job type** | `EmploymentTypeFilter[]` tokens `FULL_TIME`/`PART_TIME`/`CONTRACTOR`/`TEMPORARY`/`INTERN`/… (`full-time`→`FULL_TIME`, `contract`→`CONTRACTOR`) | `jobType` enum `fulltime`/`parttime`/`contract`/… (`full-time`→`fulltime`, `contract`→`contract`) | **PF** (no field) |
| **Experience level** | `seniorityFilter[]` tokens `Associate`/`Director`/`Executive`/`Mid-Senior level`/`Entry level`/`Not Applicable`/`Internship` (**case-sensitive, English-speaking countries only**); BETA `aiExperienceLevelFilter[]` year-bands `0-2`/`2-5`/`5-10`/`10+` | `level` enum `entry_level`/`mid_level`/`senior_level` — **US domain only** (`country:"us"`); else **PF** | **PF** (no field) |
| **Salary floor** | **PF** (only `aiHasSalary` boolean = *has any salary*, not a floor — **leave unset** so unknown-salary rows survive) | **PF** (no salary field) | **PF** (`minRating` is a 0–5 *company rating*, not salary) |
| **Result cap** | `limit` (integer; **min 10**, max 5000, default 10) | `maxRows` (integer, default 100) — **not** `maxItems` | `limit` (integer, default 100) |
| **Source-side dedupe** | none usable (`excludeATSDuplicate` only applies alongside the Career Site Job Listing API Actor) | `enableUniqueJobs: true` (boolean) | `excludeJobIds[]` — push `seen_jobs.json` IDs here |
| **Agency / job-board filtering** | native `removeAgency: true` (drops agencies/job boards at source) + per-record `linkedin_org_recruitment_agency_derived` bool for post-fetch handling. See Open questions for policy. | (no native field) | (no native field) |

**Post-fetch enforcement is therefore mandatory for:** salary floor (all three boards), excluded companies (all three), title_exclude (Indeed; Glassdoor — LinkedIn native if all variants listed), title allow-list (Indeed + Glassdoor, to catch fuzzy/keyword leaks), workplace type (Glassdoor always; Indeed `on_site` and hybrid/on-site separation; LinkedIn if the BETA filter proves unreliable), job type (Glassdoor always), experience level (Glassdoor always; Indeed for any non-US country), and the date safety check (all three).

**Other useful native fields seen in the schemas (optional, not part of the canonical mapping):**
- LinkedIn: `locationExclusionSearch[]`, `organizationExclusionSearch[]`, `descriptionType` (`text`/`html`/empty), `noDirectApply`/`directApply` (Easy-Apply filters).
- Indeed: `radius` (enum km/mi — pin to `"0"` to stop metro spillover), `sort` (`relevance`/`date`), `includeSimilarJobs` (default true — set false to reduce noise).
- Glassdoor: `easyApply` (bool), `minRating` (company-rating floor).

---

## Skill logic (pseudocode)

```
M = parse_leading_integer(args)            # may be absent
N = 7 if M is absent else (1 if M <= 1 else 7)   # snap to supported window
config = load(~/Documents/JobSearch/search_config.json)
sources       = resolve_sources(args)      # see Argument parsing; default ["fantastic-jobs/advanced-linkedin-job-search-api"]
entry_filter  = resolve_entry(args, config.searches)  # see Argument parsing; default ALL (None)
seen   = load(~/Documents/JobSearch/seen_jobs.json)
today  = current date
date_after = today - N days                # for the post-fetch date safety check
CAP = config.global.max_results_per_source_per_search   # N results per location per source

# Entry selection: run all entries, or just the one named (exact, case-sensitive; unknown name = error)
entries = config.searches if entry_filter is None else [e for e in config.searches if e.name == entry_filter]

# Native recency tokens per window
time_range_li = "24h" if N == 1 else "7d"
from_days_in  = "1"   if N == 1 else "7"   # STRING, not int
days_old_gd   = N                          # 1 or 7

results = []

for each entry in entries:
    # locations to fetch; empty list means "country-level only"
    loc_list = entry.locations if entry.locations else [COUNTRY_LEVEL for c in entry.countries]

    for each actor in sources:
        enforce = config.global.actor_enforcement[actor]    # native vs post_fetch field lists + call_defaults

        # === PER-LOCATION FETCH ===
        # Always one call per location, capped at CAP results each. This is the fix for
        # multi-location crowding: a combined OR'd call lets large metros fill the top-N
        # and starve smaller ones (NJ + Calgary returned 0 in 15-row combined runs for
        # swe + pm). One call per location guarantees each gets up to CAP of its own.
        # Applies to ALL actors, including fantastic-jobs whose locationSearch accepts
        # arrays - we still go per-location.
        for each loc in loc_list:
            country = country_of(loc, entry.countries)

            if actor == "fantastic-jobs/advanced-linkedin-job-search-api":
                call actor with:
                    titleSearch          = entry.titles,                 # prefix match; consider ":*"
                    titleExclusionSearch = expand_variants(entry.title_exclude),  # BOTH abbrev + spelled-out
                    locationSearch       = [li_location_string(loc, country)],    # single-element array, this loc only
                    timeRange            = time_range_li,
                    EmploymentTypeFilter = translate_jobtype(entry.job_type, actor),
                    aiWorkArrangementFilter = translate_workplace(entry.workplace_type, actor),  # BETA; see note
                    removeAgency         = <policy>,                     # see Decisions; or leave unset + annotate
                    # aiHasSalary       : LEAVE UNSET - has-any-salary, not a floor; true drops unknown-salary rows
                    limit                = max(10, CAP)                  # LinkedIn floor is 10

            else if actor == "borderline/indeed-scraper":
                call actor with:
                    query            = OR_join(entry.titles),            # verify OR is honored
                    location         = indeed_location_string(loc),
                    country          = indeed_country_code(country),     # note: "uk" not "gb"
                    radius           = enforce.call_defaults.radius or "0",  # pin metro; stops spillover
                    fromDays         = from_days_in,                     # STRING enum
                    remote           = workplace_to_indeed(entry.workplace_type),  # "remote"|"hybrid"|unset
                    jobType          = translate_jobtype(entry.job_type, actor),
                    enableUniqueJobs = true,
                    maxRows          = CAP                               # NOT maxItems

            else if actor == "valig/glassdoor-jobs-scraper":
                call actor with:
                    keywords     = OR_join(entry.titles),                # required
                    location     = glassdoor_location_string(loc) or country_to_location(country),  # required, non-empty
                    daysOld      = days_old_gd,
                    excludeJobIds = seen,
                    limit        = CAP
                    # no jobType / workplace / experience / salary / radius - all PF for Glassdoor

            for each listing returned:
                listing.source_search_name = entry.name
                listing.source_actor       = actor
                results.append(listing)

# --- Normalize ---
for each listing in results:
    normalize to: {
        job_id, source, source_actor, company, title, location,
        workplace_type, salary, is_agency, url,
        description, date_posted, source_search_name
    }
    normalize salary to annual (hourly x config.global.salary_normalization.hourly_to_annual_multiplier)

# --- Post-fetch filtering: per listing, apply only what its source_actor lists under post_fetch ---
# (actor_enforcement[r.source_actor].post_fetch decides which of these run for each listing)
results = [r for r in results if r.company not in config.global.exclude_companies]   # all actors
results = apply_title_allowlist(results, entry.titles)                 # Indeed + Glassdoor (fuzzy/keyword leak guard)
results = apply_title_exclude(results, entry.title_exclude)            # Indeed + Glassdoor (LI native if variants listed)
results = apply_salary_filter(results, entry.min_salary, entry.salary_match_field, config.global.salary_unknown_action)
                                                                      # ALL boards; compare r.salary[salary_match_field]
                                                                      # in the role's OWN currency (no FX); unknown->include
results = apply_workplace_type_filter(results, entry.workplace_type)   # Glassdoor always; Indeed on_site + hybrid/on-site; LI if BETA unreliable
results = apply_jobtype_filter(results, entry.job_type)                # Glassdoor always
results = [r for r in results if r.date_posted >= date_after]          # date safety check, ALL boards

# --- Dedupe (three scopes, all required) ---
results = collapse_within_actor(results)              # SAME actor returns identical reposts (verified 3x, fantastic-jobs)
results = collapse_by_hash(company + title + location)  # cross-board / cross-search
results = drop_where(job_id in seen)                  # cross-run
# Tag the surviving listing with all source_search_names that matched it

# --- Cap per employer (AFTER dedup, so the cap counts distinct listings, not reposts) ---
results = cap_per_employer(results, config.global.max_per_employer)

return results  # array of normalized listing objects
```

**Per-location fetch - why it's unconditional.** Every Actor is now called once per location with its own `CAP` budget, *including* fantastic-jobs even though its `locationSearch` accepts an array. The combined-array approach is cheaper per run but lets high-volume metros (NY, SF) consume the entire top-`CAP` before smaller ones (NJ, Calgary) surface - verified 0 results for NJ + Calgary in 15-row combined runs across both the `swe_north_america` and `product_manager_north_america` entries. Per-location calls trade some cost for guaranteed coverage; the cost implication is in Cost discipline below.

**Note on experience_level:** it is not a field in the live `search_config.json`, so it's absent from the call bodies above. The native `seniorityFilter` (LinkedIn) and `level` (Indeed) inputs remain in the translation table for if an `experience_level` field is added later.

**Note:** the skill does **not** update `seen_jobs.json`. That's the orchestrator's job after the full pipeline succeeds — a mid-run failure shouldn't poison dedupe state for the next run.

**Note on within-Actor reposts.** A single Actor can return the identical listing multiple times in one run. Verified 2026-05-31: an agency repost ("Growth Product Manager / OpenArt AI, $300–400k") surfaced **3×** from fantastic-jobs in one 15-row PM run. This is distinct from cross-board and cross-run dedupe and must be handled first. Critically, **`max_per_employer` does NOT absorb it** — three identical reposts sit exactly at a cap of 3 and pass through. Collapse on a fuzzy key (title + company + salary, or a stable source id where available) before the employer cap is applied.

**Note on LinkedIn workplace/experience BETA filters:** `aiWorkArrangementFilter` and `aiExperienceLevelFilter` are flagged BETA in the schema and depend on AI enrichment of the listing. Treat their output as best-effort and re-run the workplace check post-fetch if precision matters. The non-AI `remote` boolean is an alternative for remote-only searches but is documented as "very sensitive" (matches "remote" anywhere in title/description/location), so it over-includes.

---

## Output schema

A single normalized array, handed to `/score-job`:

```json
[
  {
    "job_id": "li_8f3a...",
    "source": "linkedin",
    "company": "Acme",
    "title": "Senior Data Engineer",
    "location": "Toronto, ON",
    "workplace_type": "hybrid",
    "salary_stated": null,
    "is_agency": false,
    "url": "https://...",
    "description": "...",
    "date_posted": "2026-05-24",
    "source_search_name": ["swe_onsite_hybrid_canada"]
  }
]
```

`source_search_name` is an array because cross-search dedupe collapses listings that matched multiple entries — useful downstream when you want to know which intent surfaced a job.
`is_agency` is populated from `linkedin_org_recruitment_agency_derived` where the source provides it (LinkedIn); `null`/`false` elsewhere.

---

## How this plugs into the pipelines

- **Cowork-scheduled plan:** the scheduled task prompt's Step 1 becomes `/fetch-jobs 7` (or `1`). The config file is read each run (a fresh session re-reads everything), so tuning the config doesn't require redeploying the skill.
- **Cloud-headless plan:** same translation logic, written as a Python/Node script calling Apify's API instead of the connector. The config file lives in object storage or version control instead of `~/Documents/JobSearch/`.

---

## Cost discipline

Every Actor call specifies a result cap (`limit` for LinkedIn/Glassdoor, `maxRows` for Indeed). With per-location fetching the cost surface is:

`(search entries) × (locations per entry) × (selected Actors) × (max_results_per_source_per_search)`

Two levers changed this from the earlier model:
- **Per-location fetch multiplies by `locations per entry`** (no longer collapsed). For a 6-location entry this is a 6× increase over a single combined call per Actor — the deliberate cost of guaranteed small-metro coverage. Keep `max_results_per_source_per_search` modest (it's the per-location budget now, not per-entry).
- **Source selection divides by the boards you skip.** The default (`fantastic-jobs`, LinkedIn only) is `× 1` Actor; `all` is `× 3`. During tuning, run one board at a time.
- **Entry selection divides by the entries you skip.** Omitting the entry arg runs all `(search entries)`; naming one collapses that term to 1. During tuning, always name the single entry under test — a default all-entries × all-locations run is the most expensive thing the skill can do (5 entries × 6 locations × CAP, per selected board).

For tuning, set `max_results_per_source_per_search` to 10–15 (LinkedIn's `limit` floor is **10** — can't go lower). For production, raise to 20–25 only on entries you've confirmed produce signal. Track Apify run cost in the console for the first week of scheduled runs to confirm spend is what you expect.

Worked example: a 6-location entry, default source (fantastic-jobs only), cap 15 → 6 calls × 15 rows ≈ 90 billable results ≈ **$0.45** (+ 6 actor-starts). The same entry with `all` ≈ 18 calls; LinkedIn + Indeed dominate cost, Glassdoor is ~10× cheaper per result.

Reference per-call costs at 15 rows (verified 2026-05-31): fantastic-jobs ≈ $0.085, Indeed ≈ $0.075, Glassdoor ≈ $0.007.

Because the workweek window (`N=7`) returns a superset that dedupe then collapses, expect the **first** weekly-window run to be the most expensive; subsequent runs should be cheap as `seen_jobs.json` and `excludeJobIds[]` (Glassdoor) suppress repeats. Indeed's `enableUniqueJobs` and Glassdoor's `excludeJobIds[]` reduce billable duplicates at the source; LinkedIn has no equivalent, so its dedupe cost is paid in-results (and includes within-Actor reposts — see dedupe note).

---

## Decisions to lock per deployment

- Recency window: **1 (daily)** or **7 (weekly)**; default **7** for resilience to skipped Cowork runs.
- Per-entry result caps (in `search_config.json`).
- Whether `salary_unknown_action` is `"include"` (recommended default — preserves jobs that don't state salary; relevant because salary is post-fetch on every board) or `"exclude"` (aggressive — drops anything without a stated salary, often a third of postings).
- **Agency-repost policy** (fantastic-jobs): drop at source (`removeAgency: true`), drop post-fetch (`linkedin_org_recruitment_agency_derived`), or annotate-and-keep (`is_agency`). PM run had 5 of 15 rows agency/job-board. Open.
- Which Actors to use. Selected at invocation via the `source` arg (default `fantastic-jobs`); see Source selection. The three mapped Actors are the cleanest validated filter surface; alternates exist (`cheap_scraper/linkedin-job-scraper`, `valig/indeed-jobs-scraper`, `cheap_scraper/glassdoor-jobs-scraper-remove-duplicate-jobs`) and can be passed as full slugs, but must be re-verified with `fetch-actor-details` (schema + native-vs-PF surface) and given an `actor_enforcement` entry before adoption.
- **Empirical check still open:** confirm that Indeed `query` and Glassdoor `keywords` honor `" OR "` as a boolean operator. Neither schema documents it. Test during Phase 1 manual runs before relying on multi-title searches; if OR isn't honored, run one Actor call per title instead.

---

## Open questions

- **Agency reposts.** See Decisions. (fantastic-jobs offers source-drop via `removeAgency`, post-fetch-drop via `linkedin_org_recruitment_agency_derived`, or annotate-and-keep via `is_agency`.)
- **Salary currency.** Compared in-currency with no FX. Revisit if searches span beyond CA/US.
- **Indeed/Glassdoor multi-title OR.** Confirm `query`/`keywords` honor `" OR "`; if not, one call per title (further multiplies cost — see Cost discipline).

**Resolved 2026-05-31:** config-schema migration (now matches live `search_config.json`); multi-location crowding (per-location fetch, `CAP` results per location, all Actors); Actor selection (source arg, default `fantastic-jobs`); entry selection (optional entry-name arg, default all entries).

---

## Recency snapping (reference)

The skill supports only two windows. The snapping rule is:

- `N ≤ 1` → **1 day** (LinkedIn `24h`, Indeed `"1"`, Glassdoor `1`)
- `N ≥ 2` → **7 days** (LinkedIn `7d`, Indeed `"7"`, Glassdoor `7`) — i.e. everything from 2 upward rounds **up** to weekly
- absent → **7 days** (default)

Always apply the post-fetch date check (`r.date_posted >= today − N`) regardless of source, since bucket boundaries and posting-time delays make source-side recency approximate.

*(If you ever swap in an alternate Actor exposing only coarse 24h/week/month buckets, the same two-window model still applies: map `N=1`→24h bucket and `N=7`→week bucket, and keep the post-fetch date check.)*

---

## Changelog

- **2026-05-31 (entry selector):** Added an optional **entry selector** — an argument naming a single `config.searches[].name` to run, defaulting to all entries. Added the *Entry selection* and *Argument parsing* sections (source + entry are order-independent, classified by content; unknown source or entry tokens error rather than silently defaulting). Pseudocode resolves `entry_filter` and loops over the filtered `entries`. Cost surface notes that naming an entry collapses the `(search entries)` term to 1, and that the all-entries × all-locations default is the skill's most expensive run.
- **2026-05-31 (schema migration + per-location + source arg):** Migrated Inputs + pseudocode to the live `search_config.json` shape (single in-currency `min_salary` + `salary_match_field`; `global` with `salary_normalization`, `max_per_employer`, `exclude_companies`, `actor_location_format`, `actor_enforcement`); removed the old per-currency floors and the divergence note. Replaced the multi-location crowding workaround with **unconditional per-location fetching** (`CAP` = `max_results_per_source_per_search` results per location, every Actor incl. fantastic-jobs); updated the cost surface accordingly. Added **Source selection**: optional second positional arg (`/fetch-jobs N [source]`) with `linkedin`/`indeed`/`glassdoor`/`all` aliases + full-slug support, defaulting to `fantastic-jobs` (LinkedIn only); unrecognized non-slug tokens error rather than fall back. Post-fetch filtering now keyed off each listing's `source_actor` against `actor_enforcement`.
- **2026-05-31 (PM tuning findings):** Folded in findings from the `product_manager_north_america` × fantastic-jobs tuning pass. Added: `titleExclusionSearch` exact-phrase gotcha (abbrev vs spelled-out — VP/Vice President) as a dedicated table row; `removeAgency` + `linkedin_org_recruitment_agency_derived` agency-handling row and policy decision; within-Actor repost dedupe as a third explicit scope (verified 3× repost) with the `max_per_employer`-doesn't-absorb-it caveat and post-dedup ordering; multi-location crowding promoted to confirmed-across-two-entries; LinkedIn single-call-per-entry (location array) noted in field notes, pseudocode, and cost surface; Indeed `radius:"0"` metro pin and hybrid/on-site non-separation; `aiHasSalary` leave-unset guidance; `is_agency` added to output schema; salary normalization (hourly×2080) in normalize step; reference per-call costs. Added top-of-file **Config-schema divergence** note: this spec still documents the older `min_salary_cad`/`min_salary_usd` + slim `global` shape; live config uses single `min_salary` + `salary_match_field` + `salary_normalization` + `max_per_employer` + `actor_enforcement` — Inputs/pseudocode not yet migrated, flagged not silently rewritten.
- **(prior)** Schema verification against live Apify schemas; two-window recency model; per-Actor translation table.
