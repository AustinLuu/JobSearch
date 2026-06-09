"""Page-fit measurement with pluggable backends.

The resume renderer needs to know, for a given .docx, (a) how many pages it is and
(b) how full the last page is. The catch: the candidate opens the file in **MS Word**,
but the sandbox only has **LibreOffice** — and the two lay this template out
differently (LibreOffice runs ~1in taller on a full page, mostly small line-wrapping
differences with the Carlito stand-in for Calibri). Optimizing against LibreOffice
therefore under-fills the page in the reality that matters.

So measurement is pluggable:

- ``word``    — drive real MS Word via COM (Windows + ``pywin32``). AUTHORITATIVE:
                it measures exactly what the candidate sees. Used automatically on
                Windows when Word + pywin32 are present.
- ``soffice`` — LibreOffice -> PDF, measured with pypdf/pdfplumber. Cross-platform
                fallback for the cloud-headless path (and this dev sandbox). Diverges
                from Word on some templates; treat its fill numbers as approximate.

Backend selection (``RESUME_FIT_BACKEND`` env var):
    ``auto`` (default) -> ``word`` on Windows if available, else ``soffice``
    ``word``           -> force Word (falls back to soffice if Word can't start)
    ``soffice`` / ``libreoffice`` -> force LibreOffice

``measure(path)`` returns a dict:
    {backend, pages, page_h_pt, bottom_margin_pt, usable_bottom_pt,
     last_y_pt?, fill_ratio?, whitespace_pt?, whitespace_in?}
Fill fields are omitted if they can't be determined; ``pages`` may be ``None`` if the
file can't be measured at all (no Word AND no LibreOffice). Nothing here raises — a
measurement failure degrades to fewer fields so the caller can decide.

CLI smoke test (run this on the Windows/Word machine to validate the Word backend):
    python measure_fit.py --file path/to/resume.docx              # auto backend
    python measure_fit.py --file resume.docx --backend word       # force Word
    python measure_fit.py --file resume.docx --backend soffice    # force LibreOffice
    python measure_fit.py --file resume.docx --diagnose           # why a backend fails
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _selected_backend() -> str:
    b = (os.environ.get("RESUME_FIT_BACKEND", "auto") or "auto").strip().lower()
    if b in ("word", "soffice"):
        return b
    if b in ("libreoffice", "lo", "libre"):
        return "soffice"
    # auto: prefer real Word on Windows, else LibreOffice
    return "word" if sys.platform.startswith("win") else "soffice"


# ---------------------------------------------------------------------------
# Word backend (Windows, via COM / pywin32) — AUTHORITATIVE
# ---------------------------------------------------------------------------
# A single hidden Word instance is reused across all measurements in a run
# (launching Word per call would be far too slow), and quit at process exit.

_WORD_APP = None
_WORD_DEAD = False  # set if Word proved unavailable, so we stop retrying

# Word enum constants used (literals, to avoid gencache dependency):
_WD_STATISTIC_PAGES = 2          # ComputeStatistics(wdStatisticPages)
_WD_COLLAPSE_END = 0             # Range.Collapse(wdCollapseEnd)
_WD_VPOS_REL_PAGE = 6            # Information(wdVerticalPositionRelativeToPage)
_WD_ALERTS_NONE = 0              # DisplayAlerts = wdAlertsNone
_WD_UNDEFINED = 9999999          # Word's wdUndefined sentinel (mixed/undefined props)


def _sane_pt(v):
    """Coerce a Word measurement to float points, rejecting the wdUndefined
    sentinel (9999999) and other absurd values. Returns None if unusable."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if -100000.0 < f < 100000.0 else None


def _word_app():
    global _WORD_APP, _WORD_DEAD
    if _WORD_DEAD:
        return None
    if _WORD_APP is not None:
        return _WORD_APP
    try:
        import win32com.client as win32  # type: ignore
    except Exception:
        _WORD_DEAD = True
        return None
    try:
        app = win32.DispatchEx("Word.Application")  # dedicated process
        app.Visible = False
        try:
            app.DisplayAlerts = _WD_ALERTS_NONE
        except Exception:
            pass
        import atexit
        atexit.register(_word_quit)
        _WORD_APP = app
        return app
    except Exception:
        _WORD_DEAD = True
        return None


def _word_quit():
    global _WORD_APP
    if _WORD_APP is not None:
        try:
            _WORD_APP.Quit(False)
        except Exception:
            pass
        _WORD_APP = None


def _measure_word(path: str):
    app = _word_app()
    if app is None:
        return None
    p = os.path.abspath(path)
    doc = None
    try:
        # ReadOnly + no recent-files; ConfirmConversions off to avoid dialogs.
        doc = app.Documents.Open(p, False, True, False)
        pages = int(doc.ComputeStatistics(_WD_STATISTIC_PAGES))  # forces repagination
        # Geometry: read from the SECTION page setup first (doc.PageSetup returns
        # the wdUndefined sentinel 9999999 when margins are mixed/undefined), then
        # fall back to doc.PageSetup, then to the file's own geometry via python-docx.
        page_h = bottom = None
        for getter in (lambda: doc.Sections(1).PageSetup, lambda: doc.PageSetup):
            try:
                sps = getter()
                if page_h is None:
                    page_h = _sane_pt(sps.PageHeight)
                if bottom is None:
                    bottom = _sane_pt(sps.BottomMargin)
            except Exception:
                pass
            if page_h is not None and bottom is not None:
                break
        if page_h is None or bottom is None:
            fh, fb = _docx_page_geom(p)  # read straight from the .docx
            if page_h is None:
                page_h = fh
            if bottom is None:
                bottom = fb
        usable_bottom = page_h - bottom
        out = {
            "backend": "word",
            "pages": pages,
            "page_h_pt": round(page_h, 1),
            "bottom_margin_pt": round(bottom, 1),
            "usable_bottom_pt": round(usable_bottom, 1),
        }
        # Best-effort fill: vertical position of the last non-empty paragraph's
        # last line. Information(wdVerticalPositionRelativeToPage) gives the TOP
        # of that line in points from the page top; add a line height for the
        # bottom. Only meaningful for the page the content actually ends on.
        try:
            paras = doc.Paragraphs
            n = int(paras.Count)
            last_y = None
            i = n
            # cap the scan so a pathological doc can't loop forever
            scanned = 0
            while i >= 1 and scanned < 80:
                rng = paras(i).Range
                txt = rng.Text or ""
                if txt.strip("\r\n\x07\x0b\x0c \t"):
                    end = rng.Duplicate
                    end.Collapse(_WD_COLLAPSE_END)
                    top = _sane_pt(end.Information(_WD_VPOS_REL_PAGE))
                    if top is None or top < 0:
                        break  # position unavailable (e.g. headless) -> skip fill
                    try:
                        fs = float(rng.Font.Size)
                    except Exception:
                        fs = 11.0
                    last_y = top + fs * 1.25  # approx line bottom
                    break
                i -= 1
                scanned += 1
            if last_y is not None and usable_bottom > 0:
                ws = max(0.0, usable_bottom - last_y)
                out.update({
                    "last_y_pt": round(last_y, 1),
                    "fill_ratio": round(max(0.0, min(1.0, last_y / usable_bottom)), 3),
                    "whitespace_pt": round(ws, 1),
                    "whitespace_in": round(ws / 72.0, 2),
                })
        except Exception:
            pass  # pages alone is still useful (it's the fit gate)
        return out
    except Exception:
        return None
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# LibreOffice backend (cross-platform fallback) — APPROXIMATE for Word
# ---------------------------------------------------------------------------

def _docx_page_geom(path: str):
    """(page_height_pt, bottom_margin_pt) from the docx itself; safe defaults."""
    page_h, bottom = 792.0, 28.9
    try:
        from docx import Document
        s = Document(path).sections[-1]
        if s.page_height is not None:
            page_h = float(s.page_height.pt)
        if s.bottom_margin is not None:
            bottom = float(s.bottom_margin.pt)
    except Exception:
        pass
    return page_h, bottom


def _measure_soffice(path: str):
    import subprocess
    import tempfile
    p = os.path.abspath(path)
    page_h, bottom = _docx_page_geom(p)
    td = tempfile.mkdtemp()
    try:
        subprocess.run(
            ["soffice", "--headless", f"-env:UserInstallation=file://{td}/lo",
             "--convert-to", "pdf", "--outdir", td, p],
            check=True, capture_output=True, timeout=180,
        )
    except Exception:
        return None
    pdf = os.path.join(td, os.path.splitext(os.path.basename(p))[0] + ".pdf")
    if not os.path.exists(pdf):
        return None
    out = {
        "backend": "soffice",
        "pages": None,
        "page_h_pt": round(page_h, 1),
        "bottom_margin_pt": round(bottom, 1),
        "usable_bottom_pt": round(page_h - bottom, 1),
    }
    try:
        import pypdf
        out["pages"] = len(pypdf.PdfReader(pdf).pages)
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(pdf) as doc:
            if out["pages"] is None:
                out["pages"] = len(doc.pages)
            pg = doc.pages[-1]
            H = pg.height
            last = max((w["bottom"] for w in pg.extract_words()), default=0.0)
            ub = H - bottom
            if ub > 0:
                ws = max(0.0, ub - last)
                out.update({
                    "page_h_pt": round(H, 1),
                    "usable_bottom_pt": round(ub, 1),
                    "last_y_pt": round(last, 1),
                    "fill_ratio": round(max(0.0, min(1.0, last / ub)), 3),
                    "whitespace_pt": round(ws, 1),
                    "whitespace_in": round(ws / 72.0, 2),
                })
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def measure(path: str) -> dict | None:
    """Measure `path` with the selected backend. Word falls back to LibreOffice
    if Word can't be started, so 'auto'/'word' still works on a machine without
    Word (just less accurately)."""
    backend = _selected_backend()
    if backend == "word":
        m = _measure_word(path)
        if m is not None:
            return m
        # Word unavailable -> degrade to LibreOffice rather than failing.
        return _measure_soffice(path)
    return _measure_soffice(path)


_CACHE: dict = {}


def measure_cached(path: str) -> dict | None:
    """measure(), memoized on (abspath, mtime, size) so that asking for pages and
    then fill on the same rendered file measures it only once."""
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return measure(path)
    if key in _CACHE:
        return _CACHE[key]
    m = measure(path)
    _CACHE[key] = m
    return m


def pages(path: str):
    """Page count (int) or None if unmeasurable."""
    m = measure_cached(path)
    return m.get("pages") if m else None


def fill(path: str) -> dict:
    """Fill signal: {fill_ratio, whitespace_pt, whitespace_in} or {} if unknown."""
    m = measure_cached(path) or {}
    return {k: m[k] for k in ("fill_ratio", "whitespace_pt", "whitespace_in") if k in m}


def active_backend() -> str:
    return _selected_backend()


def diagnose(path: str) -> dict:
    """Step-by-step probe of both backends, reporting the ACTUAL failure reason at
    each step (import, COM dispatch, document open, page count, soffice presence).
    Run this when measure() returns 'unmeasurable' to see why."""
    rep = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "python_exe": sys.executable,
        "selected_backend": _selected_backend(),
        "file": os.path.abspath(path),
        "file_exists": os.path.exists(path),
    }

    # --- Word / pywin32 probe ---
    w: dict = {}
    try:
        import win32com  # type: ignore
        w["pywin32_import"] = "ok"
        w["pywin32_location"] = getattr(win32com, "__file__", "?")
        try:
            import win32com.client as win32
            app = None
            try:
                app = win32.DispatchEx("Word.Application")
                w["dispatch_word"] = "ok"
                try:
                    app.Visible = False
                    try:
                        app.DisplayAlerts = 0
                    except Exception:
                        pass
                    if rep["file_exists"]:
                        doc = app.Documents.Open(os.path.abspath(path), False, True, False)
                        w["open_document"] = "ok"
                        try:
                            w["pages"] = int(doc.ComputeStatistics(_WD_STATISTIC_PAGES))
                        except Exception as e:
                            w["compute_pages_error"] = repr(e)
                        # also surface the geometry the real backend will use
                        try:
                            ph = bm = None
                            for getter in (lambda: doc.Sections(1).PageSetup, lambda: doc.PageSetup):
                                try:
                                    sps = getter()
                                    if ph is None:
                                        ph = _sane_pt(sps.PageHeight)
                                    if bm is None:
                                        bm = _sane_pt(sps.BottomMargin)
                                except Exception:
                                    pass
                            fh, fb = _docx_page_geom(os.path.abspath(path))
                            w["page_height_pt"] = ph if ph is not None else f"undefined->{fh}"
                            w["bottom_margin_pt"] = bm if bm is not None else f"undefined->{fb}"
                        except Exception as e:
                            w["geometry_error"] = repr(e)
                        try:
                            doc.Close(False)
                        except Exception:
                            pass
                    else:
                        w["open_document"] = "skipped (file not found)"
                except Exception as e:
                    w["open_document_error"] = repr(e)
                finally:
                    try:
                        app.Quit(False)
                    except Exception:
                        pass
            except Exception as e:
                w["dispatch_word_error"] = repr(e)
        except Exception as e:
            w["win32com_client_error"] = repr(e)
    except Exception as e:
        w["pywin32_import_error"] = repr(e)
    rep["word_backend"] = w

    # --- LibreOffice probe ---
    s: dict = {}
    import shutil
    exe = shutil.which("soffice") or shutil.which("soffice.exe") or shutil.which("soffice.bin")
    s["soffice_on_path"] = exe
    if not exe:
        for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                  r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                  "/usr/bin/soffice", "/opt/libreoffice/program/soffice"):
            if os.path.exists(c):
                s["soffice_found_at"] = c
                break
    rep["soffice_backend"] = s

    # --- verdict ---
    word_ok = w.get("open_document") == "ok" or "pages" in w
    soffice_ok = bool(exe or s.get("soffice_found_at"))
    if word_ok:
        rep["verdict"] = "Word backend WORKS — measure() should now return word measurements."
    elif "pywin32_import_error" in w:
        rep["verdict"] = ("pywin32 is not importable in THIS Python. Install it into this exact "
                          "interpreter: \"" + sys.executable + "\" -m pip install pywin32")
    elif "dispatch_word_error" in w:
        rep["verdict"] = ("pywin32 imports but Word won't start via COM — confirm MS Word (desktop) "
                          "is installed and licensed, and that this Python isn't a sandboxed/Store build.")
    elif "open_document_error" in w:
        rep["verdict"] = "Word starts but couldn't open the file — check the path/permissions printed above."
    elif soffice_ok:
        rep["verdict"] = "Word unavailable, but LibreOffice is present — soffice fallback should work."
    else:
        rep["verdict"] = "Neither Word (pywin32) nor LibreOffice is available to this Python."
    return rep


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Measure .docx page fit (Word or LibreOffice).")
    ap.add_argument("--file", required=True, help="path to a .docx")
    ap.add_argument("--backend", default=None, choices=["auto", "word", "soffice", "libreoffice"],
                    help="override RESUME_FIT_BACKEND for this run")
    ap.add_argument("--diagnose", action="store_true",
                    help="probe both backends and report why each does/doesn't work")
    args = ap.parse_args()
    if args.backend:
        os.environ["RESUME_FIT_BACKEND"] = args.backend
    if args.diagnose:
        print(json.dumps(diagnose(args.file), indent=2))
    else:
        result = measure(args.file)
        if result is not None:
            print(json.dumps(result, indent=2))
        else:
            # don't fail silently — show why
            print(json.dumps({"error": "unmeasurable", "diagnosis": diagnose(args.file)}, indent=2))
