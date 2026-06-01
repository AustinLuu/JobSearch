# Phase 1 Prompts — for `claude.ai` chats in the project

Three prompts, one per Phase 1 substep. Use each in a **fresh Claude.ai conversation inside the project** (so the project instructions and uploaded files are in scope). Don't combine them — each is sized to do one job well, and Phase 1 naturally splits into separate working sessions anyway.

---

## Prompt 1 — Schema discovery (substep 1)

**When to use it:** First Phase 1 session. ~30 minutes. You're capturing the *current* shape of each Actor's input schema so the skill is built against reality, not the spec from a few weeks ago. The output of this conversation becomes a reference document for the next two.

**What to expect:** Claude will call `fetch-actor-details` on each of the three Actors via the Apify connector, then produce a structured comparison table mapping your canonical config fields to each Actor's native field names and value formats. Some back-and-forth is fine if a schema is ambiguous.

### Paste this:

> I'm in Phase 1 of the build plan and starting with schema discovery. I need to capture the *current* input schema of three Apify Actors so the `/fetch-jobs` skill is built against what they actually expose today (not the version in the skill spec, which I should treat as a reference, not as authoritative).
>
> Please use the Apify connector to call `fetch-actor-details` on each of these three Actors, in order:
>
> 1. `fantastic-jobs/advanced-linkedin-job-search-api`
> 2. `borderline/indeed-scraper`
> 3. `valig/glassdoor-jobs-scraper`
>
> For each Actor, after you have the schema, tell me:
> - The exact field name and value format for **recency filtering** (e.g. `datePostedAfter`: ISO date string; `fromDays`: integer).
> - The exact field name and value format/tokens for **workplace type** (mapping to my canonical `on_site` / `hybrid` / `remote` values).
> - The exact field name and value format/tokens for **job type** (mapping to my canonical `full-time` / `contract`).
> - The exact field name and value format for **location**, and how **country** is expressed (separate field, or part of location, or LinkedIn geo IDs, etc.).
> - The exact field name and format for **experience level / seniority** if supported.
> - The exact field name and format for **salary** filters if supported.
> - The exact field name and format for **title search** (single string vs. array; substring match vs. exact).
> - The field name and format for **result cap / max results**.
> - Any source-side **dedupe** hooks (e.g. Indeed's `enableUniqueJobs`, Glassdoor's `excludeJobIds[]`).
>
> Once you have all three, produce a single **canonical-field-to-native-field translation table** with one row per canonical config field and one column per Actor. Mark cells where the Actor doesn't natively support that filter (so the skill will know to enforce it in post-fetch).
>
> Finally, flag anything in any of these schemas that differs meaningfully from what `fetch-jobs-skill-spec.md` describes — that's the list of spec updates I'll need to make.
>
> Don't write any skill code yet; this conversation is purely about pinning down the schemas.

---

## Prompt 2 — Config tuning (substep 2)

**When to use it:** Second Phase 1 session, after schema discovery is done. Probably several sessions, one per search entry. You're iterating: pick an entry, call one Actor against it, look at 20 real results, adjust titles/locations/filters, repeat. This is the step where Apify spend can balloon if you turn everything loose at once — so the prompt explicitly scopes Claude to one entry, one Actor at a time.

**What to expect:** Real back-and-forth. Claude calls the Actor, you read results together, you decide what to tune. Expect to spend an evening per major search entry. The output of each session is an updated `search_config.json` and a note about what the entry returns reliably vs. what it over-pulls.

### Paste this:

> I'm in Phase 1 of the build plan, on the config-tuning substep. The goal is to take one entry from `search_config.json` at a time, test it against one Apify Actor, look at real results, and tune the entry's titles / locations / `workplace_type` / salary filter until the first ~20 results are mostly jobs I'd actually consider. This is iterative work — don't try to do it all at once.
>
> **Rules for this conversation:**
>
> 1. We tune **one search entry at a time**. I'll tell you which entry to start with. Don't propose running multiple entries in parallel.
>
> 2. We test against **one Actor at a time** per entry. Start with whichever Actor has the cleanest filter surface for the entry (usually `borderline/indeed-scraper` for direct numeric filters, `fantastic-jobs/advanced-linkedin-job-search-api` for structured LinkedIn searches, `valig/glassdoor-jobs-scraper` for Glassdoor).
>
> 3. **Cap result count at 10–15 per call** during tuning. We're trying to see signal, not to populate a database. If a single call costs more than ~$1 in Apify credit, stop and tell me — something is mis-configured.
>
> 4. After each call, present the first ~20 results in a compact form (company, title, location, workplace type, salary if stated). I'll review with you and we'll decide what to tune.
>
> 5. **Common tuning moves:**
>    - Titles pulling in adjacent-but-wrong roles → narrow to more specific real titles (no short generic fragments like "Engineer" or "Manager").
>    - Locations returning the wrong region or no results → fix format per the Actor's schema (refer back to the schema-discovery output).
>    - `workplace_type` not filtering as expected → confirm the per-Actor translation; if Actor doesn't honor it, plan to enforce post-fetch.
>    - Too many "salary not stated" listings dropping out → confirm `salary_unknown_action: "include"` is working.
>    - Too many off-target results across the board → the entry might be conflating two role families; split it.
>
> 6. **Never tell me a result is good unless you'd defend it.** If the first 20 results contain 12 jobs that obviously don't match what I asked for, say so directly. Don't soft-pedal.
>
> 7. **Don't edit `search_config.json` yourself.** Propose edits as a JSON diff or as a complete updated entry; I'll apply them and tell you when the file is updated for the next iteration.
>
> 8. **No CV reasoning in this phase.** Don't comment on whether a returned job matches my CV — that's `/score-job`'s job, in Phase 2. Here we only care about whether the *hard filters* are doing what we think they're doing.
>
> Before I tell you which entry to start with, confirm you have access to `search_config.json` and that you understand the rules above. Then I'll pick the first entry.

---

## Prompt 3 — Skill authoring (substep 3)

**When to use it:** Third Phase 1 session, after config tuning has produced a working `search_config.json` you trust. You're now writing the `/fetch-jobs` skill itself — the thing that reads the config, calls all three Actors per search entry, normalizes, dedupes, and returns the array. This is a focused build session with a concrete deliverable.

**What to expect:** Claude proposes a skill structure and writes the skill content. You review, refine, and then test by running `/fetch-jobs 3` end-to-end in a separate Cowork session. The output of this conversation is the skill file ready to install.

### Paste this:

> I'm in Phase 1 of the build plan, on the skill-authoring substep. Schema discovery is done (the translation table from that session should be in scope), and `search_config.json` is tuned and trusted. Now I need to build the `/fetch-jobs` skill itself.
>
> **Inputs you have in scope:**
> - `fetch-jobs-skill-spec.md` (the spec — but treat as a reference, not as binding; the schema-discovery output supersedes it where they disagree).
> - The schema-translation table from the schema-discovery conversation.
> - `search_config.json` (the tuned config).
> - `cv.md` (not needed by this skill — confirming it's not in scope here).
> - Project standing instructions (read these).
>
> **What the skill needs to do, in order:**
>
> 1. Parse `N` from invocation args (default **3** per project instructions).
> 2. Read `~/Documents/JobSearch/search_config.json`. Validate JSON; fail loudly if malformed.
> 3. Read `~/Documents/JobSearch/seen_jobs.json` for cross-run dedupe state. Empty array if missing.
> 4. For each entry in `searches[]`:
>    - Translate canonical config fields (`titles`, `locations`, `workplace_type`, `job_type`, `country`/`countries`, `min_salary_*`) into each Actor's native parameter format, per the translation table.
>    - Translate `N` per Actor (direct pass-through for numeric, computed ISO date for absolute-date Actors, bucket-snap for coarse-bucket alternates if any are used).
>    - Push already-seen IDs into Glassdoor's `excludeJobIds[]` (source-side dedupe).
>    - Enable Indeed's `enableUniqueJobs`.
>    - Call all three Actors.
> 5. Normalize all outputs into the shared schema: `{ job_id, source, company, title, location, workplace_type, salary_stated, url, description, date_posted, source_search_name }`.
> 6. Post-fetch filtering:
>    - Drop any listing whose company is in `global.exclude_companies`.
>    - Apply salary filter honoring `salary_unknown_action: "include"` (default; keep listings with no stated salary) or `"exclude"` (drop them).
>    - Date safety check: drop anything whose `date_posted` is older than `today − N days`, in case a coarse-bucket Actor returned something stale.
> 7. Dedupe:
>    - By `job_id` against `seen_jobs.json` (cross-run).
>    - Cross-board and cross-search by `(company + title + location)` normalized hash, so the same role appearing on multiple boards or matched by multiple search entries comes back once. Keep the first occurrence; tag it with all source searches that matched it.
> 8. Return the deduped array. **Do not** update `seen_jobs.json` here — that's the orchestrator's job after the full pipeline succeeds, so a mid-run failure doesn't poison the dedupe state.
>
> **Constraints:**
>
> - **No silent failures.** Every Actor call is wrapped to catch errors; a single Actor failing doesn't kill the whole run — log it, return results from the others, and surface the failure in the output. (Adjust this if the skill spec says otherwise; the spec wins if it's explicit.)
> - **Cost discipline.** Honor `global.max_results_per_source_per_search`. Never call an Actor without a result cap.
> - **No CV reasoning in this skill.** That's `/score-job`'s job. This skill returns listings; it does not rank them.
> - **Output shape is the JSON array.** Whatever this skill returns is the input to `/score-job`, so the schema must be stable.
>
> **Process:**
>
> 1. First, propose the skill's structure: file layout, what's in the main prompt, what (if anything) is in supporting files. Don't write the skill content yet.
> 2. Once I've okayed the structure, write the skill in full.
> 3. After writing, walk through how to install it locally and how I'd run `/fetch-jobs 3` to test it end-to-end. The test will happen in a separate Cowork session, not in this chat — but tell me what to look for so I know whether it worked.
> 4. Don't propose Phase 2 work. We finish Phase 1 first.

---

## Order to run these in

1. **Prompt 1 (Schema discovery)** — fresh chat, ~30 minutes. Save the translation table output as a reference (paste it into the project as `actor-schema-translation.md`, or just keep it open in a tab).
2. **Prompt 2 (Config tuning)** — fresh chat per major search entry, expect several sessions across a few evenings. Each session ends with a `search_config.json` update applied.
3. **Prompt 3 (Skill authoring)** — fresh chat, one focused session once tuning is done. Output is the skill ready to install.

Don't run them out of order. Schema discovery feeds tuning (you need to know what each Actor's filters actually do); tuning feeds skill authoring (no point building a skill against an untuned config that produces noise).

## A note on "fresh chat"

Each prompt starts a new conversation in the project so the standing instructions and project files are in scope but no prior conversation's reasoning leaks in. Phase 1's three substeps are different enough in shape that letting them share context tends to muddy each one — the schema-discovery instinct ("be exhaustive about all fields") works against the tuning instinct ("look at real results, narrow"), which works against the authoring instinct ("commit to a concrete design").