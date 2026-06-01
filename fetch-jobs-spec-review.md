# Review — `fetch-jobs-skill-spec.md`

Reviewed 2026-05-31 against the live `search_config.json`, `project-instructions.md`, `build-plan.md`, `cowork-resume-pipeline-plan.md`, `headless-resume-pipeline-plan.md`, `phase-1-prompts.md`, and `config-tuning-instructions.md`. No code written. Findings are ordered by blast radius.

The spec is in good shape on the things it set out to fix: the two-window recency model is well-reasoned, the per-Actor enforcement matrix matches the live config's `actor_enforcement` block, the per-location fetch decision is sound, and the source/entry selectors are coherent. The problems below are mostly at the seams — places where the spec's pseudocode references things that the config or the rest of the project don't actually supply.

---

## Tier 1 — will silently break the pipeline

**1. The dedupe state file does not exist under the name everything reads.**
Every document — this spec, `project-instructions.md`, `build-plan.md`, `cowork-resume-pipeline-plan.md` — reads `~/Documents/JobSearch/seen_jobs.json` (single underscore). The file actually on disk is `seen__jobs.json` (double underscore). The skill will open `seen_jobs.json`, not find it, fall back to `[]`, and treat **every job as new on every run.** Cross-run dedupe is the load-bearing mechanism for the whole "7-day window is safe because dedupe collapses repeats" argument, and it's currently a no-op. This is the single highest-impact issue and it's a one-character rename — decide which name is canonical and make the file and all four docs agree. (Glassdoor's `excludeJobIds` push and the orchestrator's append step both depend on this too.)

**2. Salary is a scalar in the output schema but an object in the filter logic.**
The Output schema shows `"salary_stated": null` (a scalar). The normalize step lists a field called `salary`. The post-fetch filter does `r.salary[salary_match_field]` with `salary_match_field ∈ {"min","max"}` — which requires salary to be a `{min, max}` object. Three different shapes for the same value. As written, `apply_salary_filter` cannot be implemented against the stated output schema. Pick one representation (recommend keeping the raw parsed range as an object internally, e.g. `salary: {min, max, currency, period}`, and only flattening to `salary_stated` for the handoff) and make the normalize step, the filter, and the output schema all reference it.

**3. The translation layer — called the skill's "central job" — has no implementation substrate.**
The pseudocode calls `li_location_string()`, `indeed_location_string()`, `glassdoor_location_string()`, `country_to_location()`, `country_of()`, `expand_variants()`, and `COUNTRY_LEVEL`, none of which are defined anywhere, and it leans on `actor_location_format` overrides from the config. But in the live config `actor_location_format` is a stub: `{ "...": "unchanged" }`. So the per-Actor location formatting the spec describes in prose has nothing behind it. Before this can be built, either the format rules need to be written into the spec explicitly (LinkedIn wants `"City, Region-full-name, Country"`, Indeed wants a separate `country` enum where UK is `"uk"`, Glassdoor needs a non-empty string with a country fallback) or `actor_location_format` needs real per-Actor entries. Right now the most important part of the skill is the least specified.

**4. Indeed's one-`job_type`-per-call limit isn't handled.**
The live config's `actor_enforcement` for Indeed says: *"one country + one location per call; one job_type per call."* Every search entry has `job_type: ["full-time", "contract"]` — two values. The pseudocode passes `jobType = translate_jobtype(entry.job_type, actor)` as if Indeed accepts the array, and the fetch loop only iterates over locations, not job types. With two job types and a one-per-call limit, the Indeed branch either sends an invalid multi-value or silently fetches only one type. You need an inner loop over `job_type` for Indeed (and the cost surface needs the matching `× job_types` term — see Tier 3).

**5. Glassdoor `excludeJobIds` is fed the wrong ID namespace.**
The pseudocode does `excludeJobIds = seen`, pushing `seen_jobs.json` straight to Glassdoor's native exclusion field. But `seen` holds the skill's *normalized, source-prefixed* `job_id`s (the output schema shows `"li_8f3a..."`). Glassdoor's `excludeJobIds[]` expects *Glassdoor's own* job IDs. Prefixed/normalized IDs won't match, so the source-side suppression silently does nothing and you pay for repeats you meant to exclude. Either store the raw per-source ID alongside the normalized one and push only the raw Glassdoor IDs, or drop this optimization and rely on post-fetch cross-run dedupe (which is correct but costs more).

---

## Tier 2 — internal contradictions and cross-doc conflicts

**6. The `N=3` default conflict (spec already flags this — adding nuance).**
The spec correctly notes that `project-instructions.md`, `build-plan.md`, and the pipeline plans all say default `N=3`, and recommends flagging rather than editing. Confirmed — and it's actually five places: `project-instructions.md` ("N defaults to 3"), `build-plan.md` line 50, `phase-1-prompts.md` line 98 ("default 3 per project instructions"), and `cowork-resume-pipeline-plan.md` line 74 literally invokes `/fetch-jobs 3`. Two things worth adding to the spec's flag: (a) at runtime the conflict is **cosmetic, not functional** — the snapping rule rounds `3 → 7`, so the existing `/fetch-jobs 3` in the scheduled-task prompt still works, it just resolves to the weekly window; (b) because of that, the *only* doc that strictly needs editing is `project-instructions.md` (the stated default), and the cleanest fix is to change "N defaults to 3" to "N defaults to 7 (weekly); 1 (daily) is the only alternative." The rest can stay as-is or be updated opportunistically.

**7. "Trims to exactly N" is impossible after the snap.**
The round-up rationale says snapping returns a superset and "the post-fetch date check then trims to exactly N if a tighter bound is wanted." But by that point `N` has already been reassigned to the snapped window (`N = 7`), and the date check uses `today − N` with the snapped value. So `/fetch-jobs 3` cannot return 3 days of results — it returns 7, trimmed to 7. To actually support the claim you'd need to keep the original requested `M` and run the date check against `today − M`. Either implement that (preserve `M` for the post-fetch trim) or delete the "trims to exactly N" sentence so the spec stops promising a precision it doesn't deliver.

**8. `expand_variants()` duplicates work the config already does by hand.**
The spec's `titleExclusionSearch = expand_variants(entry.title_exclude)` implies the skill auto-expands abbreviations (VP → also "Vice President"). But the live config already lists both forms manually in every entry (`"VP", "Vice President"`). So either the config does it (and `expand_variants` should be dropped to avoid a second, possibly inconsistent expansion table) or the skill does it (and the config shouldn't carry both forms). Pick one owner. Given the tuning workflow edits the config by hand, leaving it in the config is the more visible choice — then `expand_variants` becomes an identity pass and should be cut.

**9. `enforce.call_defaults.radius` will fault for Actors that have no `call_defaults`.**
The pseudocode reads `enforce.call_defaults.radius or "0"`. In the live config only Indeed has a `call_defaults` key; `fantastic-jobs` and `valig/glassdoor` don't. The expression only runs inside the Indeed branch today, so it's safe *now*, but it's a latent trap the moment someone copies the pattern. Guard it (`enforce.get("call_defaults", {}).get("radius", "0")`) or document that `call_defaults` is optional and must be defaulted.

---

## Tier 3 — minor, cost, and under-specified

**10. Cost surface understates Indeed.** The formula is `entries × locations × actors × cap`. It omits the `× job_types` term Indeed forces (Tier 1 #4), and — if the still-open OR-operator question resolves "not honored" — a `× titles` term for Indeed/Glassdoor. Worst case Indeed is `locations × job_types × titles × cap` calls per entry, materially more than the worked example suggests.

**11. `exclude_companies` is `[]` in the live config**, so that filter is currently a no-op. Fine, but the spec presents Glassdoor employer-flooding (Deloitte 8/15) as handled by `exclude_companies` *and* `max_per_employer`; today only `max_per_employer` is doing anything. Worth a one-line note so it's not mistaken for active.

**12. `date_posted` parsing is undefined.** The date safety check assumes a normalized comparable `date_posted`, but each Actor names and formats this field differently and the normalize step doesn't say how it's parsed. Low risk, but it's the kind of thing that silently passes stale rows if one Actor returns e.g. a relative "3 days ago" string.

**13. `job_id` format is never specified.** The output shows `"li_8f3a..."` but there's no rule for how it's derived per source. This matters because it's the key for both cross-run dedupe and (if fixed) Glassdoor's `excludeJobIds`. Define it: `{source_prefix}_{raw_source_id}` and keep `raw_source_id` accessible.

---

## Open decisions still genuinely open (carry-forward, not new)

- **Agency-repost policy** (fantastic-jobs `removeAgency` vs `linkedin_org_recruitment_agency_derived` vs annotate-and-keep). PM run was 5/15 agency rows. Unresolved.
- **Indeed/Glassdoor multi-title OR.** Whether `query`/`keywords` honor `" OR "` is untested and gates whether titles fan out into separate calls (a real cost multiplier — see #10).
- **`salary_unknown_action`.** Live config is `"include"`, which the spec recommends; just confirm that's the intended production posture, since salary is post-fetch on all three boards and "include" lets unpriced rows through to `/score-job`.

---

## Bottom line

Nothing here is architectural — the recency model, the source/entry selectors, and the enforcement matrix are sound and match the live config. The risk is concentrated in five concrete seams (Tier 1): a misnamed dedupe file that silently disables cross-run dedupe, a salary value that's three shapes at once, an undefined translation layer sitting on a stubbed `actor_location_format`, Indeed's per-call job_type limit, and a mismatched ID namespace for Glassdoor exclusion. Close those five before any build session; the Tier 2/3 items can be folded into the same pass.
