#!/usr/bin/env python3
"""Tests for validate_score.py — defensive parsing, schema, threshold."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "validate_score.py"


def _run(score_obj_or_text, *, threshold: int | None = None, env: dict | None = None):
    """Run the validator on a temp file; return (returncode, stdout, stderr)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        if isinstance(score_obj_or_text, (dict, list)):
            json.dump(score_obj_or_text, f)
        else:
            f.write(score_obj_or_text)
        path = f.name
    try:
        argv = [sys.executable, str(SCRIPT), "--score", path]
        if threshold is not None:
            argv += ["--threshold", str(threshold)]
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        # Don't inherit an outer SCORE_THRESHOLD unless test sets one.
        if env is None or "SCORE_THRESHOLD" not in env:
            full_env.pop("SCORE_THRESHOLD", None)
        r = subprocess.run(argv, capture_output=True, text=True, env=full_env)
        return r.returncode, r.stdout, r.stderr
    finally:
        os.unlink(path)


VALID_OBJ = {
    "job_id": "li_abc123",
    "fit_score": 82,
    "rationale": "Strong overlap on ML platform and AWS.",
    "matched_strengths": ["AWS S3 + EC2 HPC", "PyTorch UNets", "Production monitoring"],
    "likely_gaps": ["No Kubernetes shown"],
}


# ---------- happy path ----------

def test_shortlist_above_default_threshold():
    rc, out, err = _run(VALID_OBJ)
    assert rc == 0
    assert "SHORTLIST" in out
    assert "fit_score=82" in out
    assert "threshold=70" in out


def test_skip_below_default_threshold():
    obj = dict(VALID_OBJ, fit_score=55)
    rc, out, err = _run(obj)
    assert rc == 0
    assert "SKIP" in out
    assert "fit_score=55" in out


def test_shortlist_at_exact_threshold():
    obj = dict(VALID_OBJ, fit_score=70)
    rc, out, err = _run(obj)
    assert rc == 0
    assert "SHORTLIST" in out


def test_explicit_threshold_overrides_default():
    obj = dict(VALID_OBJ, fit_score=75)
    rc, out, err = _run(obj, threshold=80)
    assert rc == 0
    assert "SKIP" in out
    assert "threshold=80" in out


def test_env_threshold_used_when_no_arg():
    obj = dict(VALID_OBJ, fit_score=60)
    rc, out, err = _run(obj, env={"SCORE_THRESHOLD": "55"})
    assert rc == 0
    assert "SHORTLIST" in out
    assert "threshold=55" in out


def test_arg_threshold_beats_env():
    obj = dict(VALID_OBJ, fit_score=60)
    rc, out, err = _run(obj, threshold=90, env={"SCORE_THRESHOLD": "55"})
    assert rc == 0
    assert "SKIP" in out
    assert "threshold=90" in out


# ---------- fence stripping ----------

def test_strips_triple_backtick_json_fence():
    text = "```json\n" + json.dumps(VALID_OBJ) + "\n```"
    rc, out, err = _run(text)
    assert rc == 0
    assert "SHORTLIST" in out


def test_strips_triple_backtick_plain_fence():
    text = "```\n" + json.dumps(VALID_OBJ) + "\n```"
    rc, out, err = _run(text)
    assert rc == 0
    assert "SHORTLIST" in out


def test_leading_whitespace_tolerated():
    text = "   \n\n" + json.dumps(VALID_OBJ) + "\n\n"
    rc, out, err = _run(text)
    assert rc == 0


# ---------- malformed input ----------

def test_empty_file_is_invalid():
    rc, out, err = _run("")
    assert rc == 2
    assert "INVALID" in out
    assert "empty" in out.lower() or "empty" in err.lower()


def test_garbage_text_is_invalid():
    rc, out, err = _run("hello there, not json at all")
    assert rc == 2
    assert "INVALID" in out


def test_top_level_array_rejected():
    rc, out, err = _run([VALID_OBJ])
    assert rc == 2
    assert "INVALID" in out


def test_prose_around_json_rejected():
    # The fence stripper only strips well-formed fenced blocks; bare prose
    # around JSON should fail (the prompt forbids it; defensive parse catches it).
    text = "Sure, here's the score: " + json.dumps(VALID_OBJ)
    rc, out, err = _run(text)
    assert rc == 2


# ---------- schema errors ----------

def test_missing_key_rejected():
    obj = dict(VALID_OBJ)
    del obj["rationale"]
    rc, out, err = _run(obj)
    assert rc == 2
    assert "rationale" in out or "rationale" in err


def test_wrong_type_rejected():
    obj = dict(VALID_OBJ, fit_score="82")  # string, not int
    rc, out, err = _run(obj)
    assert rc == 2


def test_bool_score_rejected():
    obj = dict(VALID_OBJ, fit_score=True)  # bool is an int subclass; must reject
    rc, out, err = _run(obj)
    assert rc == 2


def test_score_out_of_range_low():
    obj = dict(VALID_OBJ, fit_score=-1)
    rc, out, err = _run(obj)
    assert rc == 2


def test_score_out_of_range_high():
    obj = dict(VALID_OBJ, fit_score=101)
    rc, out, err = _run(obj)
    assert rc == 2


def test_empty_job_id_rejected():
    obj = dict(VALID_OBJ, job_id="   ")
    rc, out, err = _run(obj)
    assert rc == 2


def test_empty_rationale_rejected():
    obj = dict(VALID_OBJ, rationale="")
    rc, out, err = _run(obj)
    assert rc == 2


def test_non_string_in_strengths_rejected():
    obj = dict(VALID_OBJ, matched_strengths=["good", 42, "also good"])
    rc, out, err = _run(obj)
    assert rc == 2


def test_empty_gaps_list_allowed():
    obj = dict(VALID_OBJ, likely_gaps=[])
    rc, out, err = _run(obj)
    assert rc == 0


def test_invalid_env_threshold_rejected():
    rc, out, err = _run(VALID_OBJ, env={"SCORE_THRESHOLD": "high"})
    assert rc == 2


def test_missing_file_rejected():
    argv = [sys.executable, str(SCRIPT), "--score", "/nonexistent/score.json"]
    env = os.environ.copy()
    env.pop("SCORE_THRESHOLD", None)
    r = subprocess.run(argv, capture_output=True, text=True, env=env)
    assert r.returncode == 2
    assert "INVALID" in r.stdout
