"""Tests for integrity_gate.py — the honesty checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import integrity_gate as ig  # noqa: E402

CV = """
# Jane Doe
## Experience
- **X:** Cut deployment time. **Y:** Reduced by 80% (5 days -> 1 day). **Z:** AWS S3, EC2.
- **X:** Built UNets. **Y:** 92.84% Dice score; QA adjustments reduced 27%. **Z:** PyTorch.
- **X:** Endpoint mgmt. **Y:** 30+ endpoints at 99.8% compliance. **Z:** Syxsense, CrowdStrike.
Skills: Python, PyTorch, AWS, Docker, DICOM, FDA 510(k), ISO 13485, SOC 2.
"""


def test_clean_output_passes():
    tailored = {
        "contact": {"name": "Jane Doe", "line": "x"},
        "summary": "Cut deployment time by 80% using AWS.",
        "skills": [{"category": "Cloud", "items": ["AWS", "Docker"]}],
        "experience": [{
            "title": "SDE", "company": "Acme",
            "bullets": ["Reduced deploys by 80% (5 days to 1 day) with AWS S3 and EC2.",
                        "Built PyTorch UNets reaching 92.84% Dice."],
        }],
    }
    report = ig.run_gate(tailored, CV, inserted_keywords=["PyTorch", "DICOM"])
    assert report.passed, report.to_dict()


def test_fabricated_number_flagged():
    tailored = {
        "contact": {"name": "Jane Doe", "line": "x"},
        "summary": "s",
        "skills": [],
        "experience": [{"title": "SDE", "company": "Acme",
                        "bullets": ["Reduced costs by 47% across the org."]}],
    }
    report = ig.run_gate(tailored, CV, inserted_keywords=[])
    assert not report.passed
    assert any(f.value == "47" for f in report.number_flags)


def test_traceable_number_not_flagged():
    # 99.8 and 30 both appear in CV -> must NOT flag.
    tailored = {
        "contact": {"name": "Jane Doe", "line": "x"},
        "summary": "s",
        "skills": [],
        "experience": [{"title": "IT", "company": "Acme",
                        "bullets": ["Managed 30+ endpoints at 99.8% compliance."]}],
    }
    report = ig.run_gate(tailored, CV, inserted_keywords=[])
    assert report.passed, report.to_dict()


def test_untraceable_keyword_flagged():
    report = ig.run_gate(
        {"contact": {"name": "x", "line": "y"}, "summary": "", "skills": [],
         "experience": [{"title": "T", "company": "C", "bullets": []}]},
        CV,
        inserted_keywords=["Kubernetes", "Python"],
    )
    assert not report.passed
    flagged = {f.value for f in report.keyword_flags}
    assert "Kubernetes" in flagged   # not in CV
    assert "Python" not in flagged   # in CV


def test_multiword_keyword_substring():
    traces, _ = ig.keyword_traces("FDA 510(k)", CV)
    assert traces
    traces, _ = ig.keyword_traces("Kubernetes orchestration", CV)
    assert not traces


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
