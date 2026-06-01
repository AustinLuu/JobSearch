"""
Unit tests for the /fetch-jobs deterministic core (common.py).
Run:  python -m pytest tests/ -q     (or: python tests/test_fetch_jobs.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common as C  # noqa: E402


ENTRY_NAMES = ["swe_north_america", "ml_remote_north_america",
               "product_manager_north_america", "project_manager_north_america",
               "consultant_north_america"]


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    assert cond, name


def test_arg_parsing():
    # defaults
    M, src, ent = C.parse_args("", ENTRY_NAMES)
    check("default M None", M is None)
    check("default source linkedin", src == [C.LINKEDIN])
    check("default entry all", ent is None)

    M, src, ent = C.parse_args("7", ENTRY_NAMES)
    check("N only", M == 7 and src == [C.LINKEDIN] and ent is None)

    M, src, ent = C.parse_args("1 indeed", ENTRY_NAMES)
    check("N + source", M == 1 and src == [C.INDEED])

    M, src, ent = C.parse_args("7 all", ENTRY_NAMES)
    check("all sources", src == [C.LINKEDIN, C.INDEED, C.GLASSDOOR])

    # order independence: entry before source
    M, src, ent = C.parse_args("7 swe_north_america all", ENTRY_NAMES)
    check("order independent", src == [C.LINKEDIN, C.INDEED, C.GLASSDOOR]
          and ent == "swe_north_america")

    M, src, ent = C.parse_args("swe_north_america", ENTRY_NAMES)
    check("entry only, defaults else", M is None and src == [C.LINKEDIN]
          and ent == "swe_north_america")

    # full slug
    M, src, ent = C.parse_args("cheap/linkedin-scraper", ENTRY_NAMES)
    check("full slug source", src == ["cheap/linkedin-scraper"])

    # errors
    for bad in ["frobnicate", "swe_north", "7 indeed glassdoor", "indeed all",
                "swe_north_america ml_remote_north_america", "3 4"]:
        try:
            C.parse_args(bad, ENTRY_NAMES)
            check(f"error raised for {bad!r}", False)
        except C.ArgError:
            check(f"error raised for {bad!r}", True)


def test_recency():
    check("snap absent", C.snap_window(None) == 7)
    check("snap 0", C.snap_window(0) == 1)
    check("snap 1", C.snap_window(1) == 1)
    check("snap 2 up to 7", C.snap_window(2) == 7)
    check("snap 3 up to 7", C.snap_window(3) == 7)
    check("snap 30 clamp 7", C.snap_window(30) == 7)
    check("eff days absent=7", C.effective_days(None) == 7)
    check("eff days 3=3", C.effective_days(3) == 3)
    check("eff days 1=1", C.effective_days(1) == 1)
    check("eff days 30 clamp 7", C.effective_days(30) == 7)
    check("li 1=24h", C.time_range_linkedin(1) == "24h")
    check("li 7=7d", C.time_range_linkedin(7) == "7d")
    check("indeed 1='1' str", C.from_days_indeed(1) == "1" and isinstance(C.from_days_indeed(1), str))
    check("indeed 7='7' str", C.from_days_indeed(7) == "7")
    check("gd 1=1 int", C.days_old_glassdoor(1) == 1)


def test_locations():
    check("li Toronto", C.li_location_string("Toronto, ON", "CA") == "Toronto, Ontario, Canada")
    check("li NY", C.li_location_string("New York, NY", "US") == "New York, New York, United States")
    check("li SF (CA region=California)",
          C.li_location_string("San Francisco, CA", "US") == "San Francisco, California, United States")
    check("indeed loc passthrough", C.indeed_location_string("Toronto, ON") == "Toronto, ON")
    check("indeed country ca", C.indeed_country_code("CA") == "ca")
    check("indeed country uk exception", C.indeed_country_code("GB") == "uk")
    check("gd loc", C.glassdoor_location_string("Newark, NJ", "US") == "Newark, NJ")

    # country_of: positional region read, CA collision
    check("country_of SF=US", C.country_of("San Francisco, CA", ["US", "CA"]) == "US")
    check("country_of Toronto=CA", C.country_of("Toronto, ON", ["CA", "US"]) == "CA")

    # sanity bound failure
    try:
        C.country_of("New York, NY", ["CA"])  # US not in countries
        check("country_of sanity raises", False)
    except C.ArgError:
        check("country_of sanity raises", True)

    # COUNTRY_LEVEL
    cl = C.country_level_token("CA")
    check("country_level li", C.li_location_string(cl, "CA") == "Canada")
    check("country_level indeed empty", C.indeed_location_string(cl) == "")
    check("country_level gd fallback", C.glassdoor_location_string(cl, "CA") == "Canada")


def test_jobtype_workplace():
    check("li jobtype array", C.translate_jobtype(["full-time", "contract"], C.LINKEDIN)
          == ["FULL_TIME", "CONTRACTOR"])
    check("indeed jobtype single", C.translate_jobtype("full-time", C.INDEED) == "fulltime")
    check("indeed contract", C.translate_jobtype("contract", C.INDEED) == "contract")
    try:
        C.translate_jobtype(["full-time", "contract"], C.INDEED)
        check("indeed array raises", False)
    except C.ArgError:
        check("indeed array raises", True)

    # workplace
    check("li all -> None (unconstrained)",
          C.translate_workplace_linkedin(["on_site", "hybrid", "remote"]) is None)
    check("li remote subset",
          C.translate_workplace_linkedin(["remote"]) == ["Remote OK", "Remote Solely"])
    check("li hybrid+onsite",
          C.translate_workplace_linkedin(["on_site", "hybrid"]) == ["On-site", "Hybrid"])
    check("indeed all -> unset", C.workplace_to_indeed(["on_site", "hybrid", "remote"]) is None)
    check("indeed remote-only", C.workplace_to_indeed(["remote"]) == "remote")
    check("indeed hybrid-only", C.workplace_to_indeed(["hybrid"]) == "hybrid")
    check("constraining all = False", C.workplace_is_constraining(["on_site", "hybrid", "remote"]) is False)
    check("constraining subset = True", C.workplace_is_constraining(["remote"]) is True)


def test_ids():
    check("job_id", C.make_job_id("gd", "abc123") == "gd_abc123")
    check("strip", C.strip_prefix("gd_abc123") == "abc123")
    seen = ["gd_111", "li_222", "in_333", "gd_444"]
    check("raw_ids gd", C.raw_ids_for("gd", seen) == ["111", "444"])
    check("raw_ids li", C.raw_ids_for("li", seen) == ["222"])
    check("expand_variants identity",
          C.expand_variants(["VP", "Vice President"]) == ["VP", "Vice President"])
    check("or_join", C.or_join(["A", "B"]) == "A OR B")


def run_all():
    for fn in [test_arg_parsing, test_recency, test_locations,
               test_jobtype_workplace, test_ids]:
        print(f"\n--- {fn.__name__} ---")
        fn()
    print("\nALL UNIT TESTS PASSED")


if __name__ == "__main__":
    run_all()
