"""Tests for common.py — filenames, number extraction, schema validation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common  # noqa: E402


def test_sanitize_strips_illegal_and_collapses_spaces():
    assert common.sanitize_component('Sr. SWE: Data/ML * "Cloud"') == "Sr._SWE_DataML_Cloud"
    assert common.sanitize_component("  Senior   Data  Engineer ") == "Senior_Data_Engineer"
    assert common.sanitize_component("a<b>c|d") == "abcd"


def test_short_id_strips_prefix():
    assert common.short_id_from_job_id("li_8f3a2b") == "8f3a2b"
    assert common.short_id_from_job_id("in_XYZ") == "XYZ"
    assert common.short_id_from_job_id("gd_123") == "123"
    assert common.short_id_from_job_id("noprefix") == "noprefix"


def test_output_stem_matches_locked_convention():
    listing = {"title": "Senior Data Engineer", "company": "Acme", "job_id": "li_8f3a"}
    assert common.output_stem(listing) == "Senior_Data_Engineer__Acme_8f3a"
    assert common.resume_filename(listing) == "Senior_Data_Engineer__Acme_8f3a.docx"
    assert common.critique_filename(listing) == "Senior_Data_Engineer__Acme_8f3a-critique.md"


def test_extract_numbers_canonicalizes():
    canon = {c for c, _ in common.extract_numbers("reduced by 80% and 92.84% Dice")}
    assert "80" in canon and "92.84" in canon

    canon = {c for c, _ in common.extract_numbers("served 1,000 customers; $10,000 revenue")}
    assert "1000" in canon and "10000" in canon

    canon = {c for c, _ in common.extract_numbers("~$1.5M annual savings")}
    assert "1500000" in canon

    canon = {c for c, _ in common.extract_numbers("up to 5x throughput across 4+ projects")}
    assert "5" in canon and "4" in canon


def test_cv_number_set_membership():
    cv = "Reduced deployment by 80% (5 days -> 1 day). 92.84% Dice score."
    s = common.cv_number_set(cv)
    assert {"80", "5", "1", "92.84"} <= s
    assert "47" not in s


def test_validate_tailored_resume():
    good = {
        "contact": {"name": "A", "line": "x"},
        "summary": "s",
        "skills": [],
        "experience": [{"title": "T", "company": "C", "bullets": []}],
    }
    assert common.validate_tailored_resume(good).ok

    bad = {"summary": "s", "skills": [], "experience": []}
    res = common.validate_tailored_resume(bad)
    assert not res.ok
    assert any("contact" in e for e in res.errors)
    assert any("experience" in e for e in res.errors)


def test_strip_undergrad_achievements():
    edu = [{"degree": "B.Eng", "institution": "TMU",
            "details": ["GPA 3.70; Dean's Honour List.", "Relevant coursework: Control Systems",
                        "Led a team of 15 students"]}]
    out = common.strip_undergrad_achievements(edu)
    assert out[0]["details"] == ["Led a team of 15 students"]   # GPA/Dean's/coursework removed
    assert len(edu[0]["details"]) == 3                          # original not mutated
    assert common.strip_undergrad_achievements(edu, keep=True) == edu  # opt-out passes through


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
