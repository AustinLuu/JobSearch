"""
Integration test: build a plan from the LIVE search_config.json, then feed
synthetic Actor results (shaped like the real Apify output schemas) through
process_results to exercise normalize + post-fetch filters + 3-scope dedupe +
employer cap + date trim.

Run:  JOBSEARCH_DIR=<JobSearch> python tests/test_integration.py
"""
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import common as C            # noqa: E402
import build_calls as B       # noqa: E402
import process_results as P   # noqa: E402


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name


def main():
    root = B.jobsearch_dir()
    config = B.load_json(root / "search_config.json", {})
    assert config, "could not load live search_config.json"

    # ---- 1. Plan from the live config -------------------------------------
    meta, calls = B.build_plan("7 all swe_north_america", config, seen=[])
    swe = next(e for e in config["searches"] if e["name"] == "swe_north_america")
    nloc = len(swe["locations"])           # 5
    njt = len(swe["job_type"])             # 2
    # LinkedIn: 1 call/location ; Indeed: loc * job_type ; Glassdoor: 1/location
    expected = nloc + (nloc * njt) + nloc
    check(f"plan call count == {expected}", len(calls) == expected)
    check("snapped N=7", meta["snapped_window_N"] == 7)

    li_calls = [c for c in calls if c["source_actor"] == C.LINKEDIN]
    check("LI gets EmploymentTypeFilter array",
          li_calls[0]["input"]["EmploymentTypeFilter"] == ["FULL_TIME", "CONTRACTOR"])
    check("LI timeRange 7d", li_calls[0]["input"]["timeRange"] == "7d")
    check("LI no aiWorkArrangementFilter (all 3 wp = unconstrained)",
          "aiWorkArrangementFilter" not in li_calls[0]["input"])
    check("LI no removeAgency (annotate default)", "removeAgency" not in li_calls[0]["input"])
    check("LI aiHasSalary unset", "aiHasSalary" not in li_calls[0]["input"])
    check("LI location translated",
          "Ontario, Canada" in " ".join(li_calls[0]["input"]["locationSearch"])
          or any("United States" in s for s in
                 [li_calls[i]["input"]["locationSearch"][0] for i in range(len(li_calls))]))

    in_calls = [c for c in calls if c["source_actor"] == C.INDEED]
    check("Indeed one jobType per call (string)",
          all(isinstance(c["input"]["jobType"], str) for c in in_calls))
    check("Indeed fromDays '7' string", in_calls[0]["input"]["fromDays"] == "7")
    check("Indeed radius 0", in_calls[0]["input"]["radius"] == "0")
    check("Indeed country lowercased iso", in_calls[0]["input"]["country"] in ("ca", "us"))

    gd_calls = [c for c in calls if c["source_actor"] == C.GLASSDOOR]
    check("Glassdoor daysOld 7 int", gd_calls[0]["input"]["daysOld"] == 7)
    check("Glassdoor keywords OR-joined", " OR " in gd_calls[0]["input"]["keywords"])

    # ---- 2. Synthetic raw results + process -------------------------------
    today = date(2026, 5, 31)
    recent = (today - timedelta(days=2)).isoformat()
    stale = (today - timedelta(days=20)).isoformat()

    # Find one call id per actor to attach synthetic items to.
    li_id = li_calls[0]["id"]
    in_id = in_calls[0]["id"]
    gd_id = gd_calls[0]["id"]

    li_items = [
        # good: high salary, recent, on-site
        {"id": "LI1", "organization": "Acme", "title": "Senior Software Engineer",
         "locations_derived": ["Toronto, ON"], "ai_work_arrangement": "On-site",
         "ai_salary_minvalue": 150000, "ai_salary_maxvalue": 190000,
         "ai_salary_currency": "CAD", "ai_salary_unittext": "YEAR",
         "linkedin_org_recruitment_agency_derived": False,
         "url": "https://x/li1", "description_text": "...", "date_posted": recent},
        # within-actor repost x3 (same title+company+salary) -> collapse to 1
        *[{"id": f"LI_R{i}", "organization": "OpenArt AI",
           "title": "Growth Product Engineer", "locations_derived": ["New York, NY"],
           "ai_work_arrangement": "Hybrid", "ai_salary_minvalue": 300000,
           "ai_salary_maxvalue": 400000, "ai_salary_currency": "USD",
           "ai_salary_unittext": "YEAR",
           "linkedin_org_recruitment_agency_derived": True,
           "url": f"https://x/r{i}", "description_text": "...", "date_posted": recent}
          for i in range(3)],
        # unknown salary -> included (salary_unknown_action=include)
        {"id": "LI2", "organization": "Globex", "title": "Backend Engineer",
         "locations_derived": ["Vancouver, BC"], "ai_work_arrangement": "Remote OK",
         "ai_salary_minvalue": None, "ai_salary_maxvalue": None,
         "url": "https://x/li2", "description_text": "...", "date_posted": recent},
        # stale -> dropped by date check
        {"id": "LI3", "organization": "OldCo", "title": "Software Engineer",
         "locations_derived": ["Toronto, ON"], "ai_salary_maxvalue": 200000,
         "ai_salary_currency": "CAD", "ai_salary_unittext": "YEAR",
         "url": "https://x/li3", "description_text": "...", "date_posted": stale},
    ]
    in_items = [
        # cross-board duplicate of LI1 (same company+title+location) -> collapsed
        {"jobKey": "IN1", "companyName": "Acme", "title": "Senior Software Engineer",
         "location": {"formattedAddressShort": "Toronto, ON", "countryCode": "CA"},
         "isRemote": False, "salary": {"salaryMin": 150000, "salaryMax": 190000,
         "salaryCurrency": "CAD", "salaryType": "yearly"},
         "jobUrl": "https://i/in1", "descriptionText": "...", "datePublished": recent},
        # passes allow-list (contains "Senior Software Engineer") but hits the
        # "Manager" title_exclude -> dropped post-fetch on Indeed
        {"jobKey": "IN2", "companyName": "BizCo",
         "title": "Senior Software Engineer - Engineering Manager",
         "location": {"formattedAddressShort": "New York, NY"},
         "salary": {"salaryMax": 250000, "salaryCurrency": "USD", "salaryType": "yearly"},
         "jobUrl": "https://i/in2", "descriptionText": "...", "datePublished": recent},
        # title allow-list miss ("Recruiter") -> dropped
        {"jobKey": "IN3", "companyName": "TalentCo", "title": "Technical Recruiter",
         "location": {"formattedAddressShort": "New York, NY"},
         "salary": {"salaryMax": 250000, "salaryCurrency": "USD", "salaryType": "yearly"},
         "jobUrl": "https://i/in3", "descriptionText": "...", "datePublished": recent},
        # hourly salary below floor after annualize (40/hr*2080=83200 < 130k) -> dropped
        {"jobKey": "IN4", "companyName": "ShopCo", "title": "Software Engineer",
         "location": {"formattedAddressShort": "New York, NY"},
         "salary": {"salaryMax": 40, "salaryCurrency": "USD", "salaryType": "hourly"},
         "jobUrl": "https://i/in4", "descriptionText": "...", "datePublished": recent},
    ]
    gd_items = [
        # good, derived date from ageInDays
        {"id": "GD1", "employer": {"name": "Initech"}, "title": "Platform Engineer",
         "location": {"name": "San Francisco, CA"},
         "pay": {"min": 160000, "max": 210000, "currency": "USD", "period": "ANNUAL"},
         "url": "https://g/gd1", "description": "...", "ageInDays": 3},
        # employer-flood: 4 DISTINCT Deloitte roles (different titles) in NYC
        # -> survive dedupe -> capped at 3. (Identical-string rows would instead
        # collapse cross-board, which is correct: they're indistinguishable.)
        *[{"id": f"GD_D{i}", "employer": {"name": "Deloitte"},
           "title": t, "location": {"name": "New York, NY"},
           "pay": {"min": 140000, "max": 180000, "currency": "USD", "period": "ANNUAL"},
           "url": f"https://g/d{i}", "description": "...", "ageInDays": 1}
          for i, t in enumerate(["Software Engineer", "Senior Software Engineer",
                                  "Backend Engineer", "Full Stack Engineer"])],
    ]

    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        (run_dir / "raw").mkdir()
        json.dump({"meta": meta, "calls": calls}, (run_dir / "plan.json").open("w"))
        json.dump(li_items, (run_dir / "raw" / f"{li_id}.json").open("w"))
        json.dump(in_items, (run_dir / "raw" / f"{in_id}.json").open("w"))
        json.dump(gd_items, (run_dir / "raw" / f"{gd_id}.json").open("w"))

        meta2, listings, stats = P.process(run_dir, config, seen=[], today=today)

    ids = {r["job_id"] for r in listings}
    drops = stats["drops"]
    print("\nstats:", json.dumps(stats, indent=2))
    print("final ids:", sorted(ids))

    check("within-actor repost collapsed (3->1)", drops.get("dedupe_within_actor") == 2)
    check("cross-board dup collapsed (Acme IN1 == LI1)", "in_IN1" not in ids and "li_LI1" in ids)
    check("Indeed Manager excluded", drops.get("title_exclude", 0) >= 1 and "in_IN2" not in ids)
    check("Indeed Recruiter allowlist-dropped", drops.get("title_allowlist", 0) >= 1 and "in_IN3" not in ids)
    check("hourly-below-floor dropped", drops.get("salary_floor", 0) >= 1 and "in_IN4" not in ids)
    check("unknown-salary kept (LI2)", "li_LI2" in ids)
    check("stale dropped (LI3)", drops.get("date_too_old", 0) >= 1 and "li_LI3" not in ids)
    check("employer cap Deloitte<=3", sum(1 for r in listings if r["company"] == "Deloitte") == 3)
    check("repost survivor merged tag carries entry",
          any(r["job_id"].startswith("li_LI_R") and
              r["source_search_name"] == ["swe_north_america"] for r in listings))
    # salary normalize: hourly conversion sanity on a kept record
    li1 = next(r for r in listings if r["job_id"] == "li_LI1")
    check("LI1 salary object shape",
          set(li1["salary"]) == {"min", "max", "currency", "period"}
          and li1["salary"]["period"] == "annual" and li1["salary"]["currency"] == "CAD")
    check("Glassdoor date derived from ageInDays",
          next(r for r in listings if r["job_id"] == "gd_GD1")["date_posted"]
          == (today - timedelta(days=3)).isoformat())

    print("\nALL INTEGRATION CHECKS PASSED")


if __name__ == "__main__":
    main()
