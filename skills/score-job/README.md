# score-job — deployment notes

The `/score-job` skill scores **one** normalized job listing against `cv.md` and
emits strict JSON: `fit_score`, `rationale`, `matched_strengths`, `likely_gaps`.
The orchestrator (Phase 4) calls it on every new listing from `/fetch-jobs`,
shortlists those at-or-above the threshold, and hands the shortlist to
`/tailor-resume`.

This skill is **cheap by design** — a single reasoning pass with no scripts in
the critical path other than the validator. It runs first so the expensive
tailoring stage only ever sees listings that pass it. See `SKILL.md` for the
rubric and the JSON contract.

## File layout

```
score-job/
  SKILL.md                     # the operative procedure + rubric + JSON contract
  README.md                    # this file
  scripts/
    validate_score.py          # defensive parser + schema check + threshold
  tests/
    test_validate_score.py     # 24 tests (happy path, malformed JSON, schema, threshold)
```

## Deployment-tunable keys

These are the only knobs intended to be changed per deployment without editing
`SKILL.md`. All have sensible defaults; override only if needed.

| Key | Default | Where | Notes |
|---|---|---|---|
| `SCORE_THRESHOLD` | `70` | env var or `--threshold` | Shortlist cutoff. Tune per the user's calibration data. `--threshold` arg overrides env. |
| `JOBSEARCH_DIR` | `~/Documents/JobSearch` | env var | Where `cv.md` and the scratch dir live. On this machine the real root is `C:\Users\Admin\Documents\Claude\JobSearch`. Set in the orchestrator prompt or shell. |
| Scratch path | `$JOBSEARCH_DIR/.fetch-runs/<run_id>/score/<short_id>/` | per-run | Auto-pruned after 14 days per the fetch-jobs convention. The orchestrator picks the run_id; the score scratch sits next to the tailor scratch. |

## What this skill deliberately does NOT do

- Tailor a resume. That's `/tailor-resume`.
- Fetch listings or hit Apify. That's `/fetch-jobs`.
- Write `seen_jobs.json` or any persistent state. That's the orchestrator.
- Apply to jobs. Out of scope for the entire pipeline.
- Batch listings. One listing per invocation — the orchestrator loops.

## Calibration

The threshold of 70 is a placeholder. Calibrate by:
1. Running `/score-job` against a handful of cached listings.
2. Asking the candidate to judge each as good-fit / maybe / no.
3. Picking the threshold that cleanly separates "yes/maybe" from "no" in the
   data — usually somewhere in 60–80.
4. Recording the chosen value in `SCORE_THRESHOLD` (env var) or in the
   orchestrator prompt.

A miscalibrated threshold is recoverable: lower it if the shortlist is too
empty; raise it if too many marginal jobs get tailored. The tailoring stage's
integrity gate is the last line of defense — but every unnecessary tailoring
call costs tokens and time, which is why the threshold matters.

## Hard rules (carried from SKILL.md, repeated here as a deployment check)

- **JSON-only output** from the reasoning pass. The validator strips one well-
  formed code-fence wrap as a courtesy; anything else fails the parse.
- **No fabrication.** Strengths must trace to `cv.md`; gaps must trace to the
  JD. The validator can't catch this — only an honest reasoning pass can.
- **No side effects.** This skill writes one file (`score.json`) in its scratch
  dir and prints one decision line. Nothing else.
