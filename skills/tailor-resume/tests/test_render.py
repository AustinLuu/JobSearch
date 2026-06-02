"""Tests for render_docx helpers — contact-link parsing, cert de-dup, fit ladder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_docx as r  # noqa: E402


def test_contact_token_email():
    disp, href = r._classify_contact_token("austinowenluu@gmail.com")
    assert href == "mailto:austinowenluu@gmail.com" and disp == "austinowenluu@gmail.com"


def test_contact_token_linkedin_github_labeled():
    disp, href = r._classify_contact_token("linkedin.com/in/austin-luu")
    assert disp == "LinkedIn" and href == "https://linkedin.com/in/austin-luu"
    disp, href = r._classify_contact_token("https://github.com/austinluu")
    assert disp == "GitHub" and href == "https://github.com/austinluu"


def test_contact_token_other_url_is_portfolio():
    disp, href = r._classify_contact_token("https://www.austinluu.me/")
    assert disp == "Portfolio"
    assert href == "https://www.austinluu.me/"        # href preserved as-is


def test_contact_token_label_pipe_override():
    assert r._classify_contact_token("Site|austinluu.me") == ("Site", "https://austinluu.me")


def test_contact_token_location_plain_and_phone_dropped():
    assert r._classify_contact_token("Toronto, Canada") == ("Toronto, Canada", None)
    assert r._classify_contact_token("+1-416-451-3338") == (None, None)   # phone dropped


def test_dedupe_certs_drops_education_overlap():
    edu = [{"degree": "Deep Learning Specialization",
            "institution": "DeepLearning.AI", "details": []}]
    certs = ["DeepLearning.AI Deep Learning Specialization — 2021–2022",
             "Project Management Professional (PMP), PMI — 2026",
             "SolidWorks CSWA Certified"]
    out = r._dedupe_certs(certs, edu)
    assert out == ["Project Management Professional (PMP), PMI — 2026",
                   "SolidWorks CSWA Certified"]


def test_dedupe_certs_keeps_distinct():
    edu = [{"degree": "B.Eng Mechatronics", "institution": "TMU", "details": []}]
    certs = ["AWS Solutions Architect", "PMP"]
    assert r._dedupe_certs(certs, edu) == ["AWS Solutions Architect", "PMP"]


def test_fit_ladder_is_loosest_to_tightest():
    # Contract the fit logic relies on: relaxed is loosest, compact the floor.
    assert r.FIT_LADDER == ["relaxed", "default", "snug", "compact"]
    assert r.COMPACT_DENSITY.body_size <= r.DEFAULT_DENSITY.body_size
    assert r.COMPACT_DENSITY.margin <= r.SNUG_DENSITY.margin <= r.DEFAULT_DENSITY.margin


def test_norm_strips_nonalnum():
    import render_template as rt
    assert rt._norm("FDA 510(k) / ISO 13485.") == "fda510kiso13485"


def test_char_scale_inserts_w_in_order():
    # w:w must sit before w:sz in CT_RPr or the docx fails schema validation.
    import render_template as rt
    from docx import Document
    from docx.oxml.ns import qn
    d = Document()
    p = d.add_paragraph()
    r = p.add_run("x"); r.font.size = __import__("docx").shared.Pt(11)
    rt._set_char_scale(r, 95)
    rpr = r._r.find(qn("w:rPr"))
    tags = [c.tag for c in rpr]
    assert qn("w:w") in tags
    assert tags.index(qn("w:w")) < tags.index(qn("w:sz"))


def test_split_trailing_year():
    import render_template as rt
    assert rt._split_trailing_year("Project Management Professional (PMP), PMI — 2026") == ("Project Management Professional (PMP), PMI", "2026")
    assert rt._split_trailing_year("SolidWorks CSWA Certified") == ("SolidWorks CSWA Certified", "")
    assert rt._split_trailing_year("AWS Certified Solutions Architect, 2024") == ("AWS Certified Solutions Architect", "2024")


def test_apply_budget_tier_trims_whole_items_only():
    import render_template as rt
    d = {"key_achievements": [1, 2, 3],
         "experience": [{"title": "A", "company": "X", "bullets": ["b1", "b2", "b3", "b4"]},
                        {"title": "B", "company": "Y", "bullets": ["c1", "c2", "c3"]},
                        {"title": "C", "company": "Z", "bullets": ["d1"]}],
         "projects": [{"title": "P1"}, {"title": "P2"}]}
    tier = rt.BUDGET_LADDER[2]  # one-project: ka2 / exp3 / top3 / other2 / proj1
    out = rt.apply_budget_tier(d, tier)
    assert len(out["key_achievements"]) == 2
    assert len(out["experience"]) == 3
    assert len(out["experience"][0]["bullets"]) == 3   # top role capped
    assert len(out["experience"][1]["bullets"]) == 2   # other role capped
    assert len(out["projects"]) == 1
    assert out["experience"][0]["bullets"] == ["b1", "b2", "b3"]  # verbatim prefix, text never edited
    assert len(d["experience"][0]["bullets"]) == 4               # original not mutated


def test_budget_ladder_loosest_to_tightest():
    import render_template as rt
    names = [b.name for b in rt.BUDGET_LADDER]
    assert names[0] == "full" and names[-1] == "last-resort"
    assert [b.max_projects for b in rt.BUDGET_LADDER][0] >= [b.max_projects for b in rt.BUDGET_LADDER][-1]
    scales = [b.min_scale for b in rt.BUDGET_LADDER]
    assert scales[0] >= scales[-1]   # condense harder as the budget tightens


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
