"""
make_template.py — emit a canonical, ATS-safe template_0.docx.

This is the base the renderer loads when no user-supplied template exists. It
carries only styles + page setup (Arial, US Letter, 1" margins, a real
List Bullet style) and an empty body. Swap in your own template_0.docx with
the same path to override fonts/branding — the renderer preserves whatever
styles the base document defines.

Usage:
    python make_template.py [--out ~/Documents/JobSearch/templates/template_0.docx]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docx import Document

try:
    from . import render_docx, common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render_docx  # type: ignore
    import common  # type: ignore


def build_template(out_path: Path) -> Path:
    doc = Document()  # ships with built-in styles incl. 'List Bullet'
    render_docx._ensure_default_font(doc)
    render_docx._set_page(doc)
    render_docx._fix_settings(doc)
    # Touch List Bullet so it is materialized in the file's styles.xml.
    try:
        p = doc.add_paragraph(style="List Bullet")
        p._p.getparent().remove(p._p)  # remove the sample paragraph, keep the style
    except KeyError:
        pass
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate canonical template_0.docx")
    ap.add_argument("--out", default=str(common.TEMPLATE_PATH))
    args = ap.parse_args(argv)
    out = build_template(Path(args.out))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
