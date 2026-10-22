#!/usr/bin/env python3
"""Generate caption clips from a cleaned transcript into a composition.

  build_captions.py PROJECT_DIR [--transcript transcript.clean.json] [--html index.html] [--track 20] [--offset 0]

transcript.clean.json: {"chunks": [{"s": 2.6, "e": 3.15, "t": "...", "provisional": true}, ...]} on the
OUTPUT timeline. In "t", [[...]] marks a Latin term (ltr span, class "lat") and {{...}} a highlighted
word (class "hl"). Clips are written between <!--CAPTIONS:BEGIN--> and <!--CAPTIONS:END--> in the
HTML (wrap those markers in a non-timed #capLayer so captions can follow the head, see
motion-recipes#captions-follow-head). Re-run after every transcript edit; the transcript stays the
source of truth.
"""
import argparse, html, json, pathlib, re


def fmt(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\[\[(.+?)\]\]", r'<span class="lat" dir="ltr">\1</span>', t)
    return re.sub(r"\{\{(.+?)\}\}", r'<span class="hl">\1</span>', t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--transcript", default="transcript.clean.json")
    ap.add_argument("--html", default="index.html")
    ap.add_argument("--track", type=int, default=20)
    ap.add_argument("--offset", type=float, default=0.0, help="seconds added to every chunk (e.g. a prepended intro)")
    a = ap.parse_args()
    root = pathlib.Path(a.project)
    chunks = json.loads((root / a.transcript).read_text(encoding="utf-8"))["chunks"]
    lines = [f'      <div id="cap{i:02d}" class="cap clip" data-start="{c["s"] + a.offset:.2f}" data-duration="{round(c["e"] - c["s"], 2)}" '
             f'data-track-index="{a.track}"><span class="in" dir="rtl">{fmt(c["t"])}</span></div>'
             for i, c in enumerate(chunks)]
    page = (root / a.html).read_text(encoding="utf-8")
    if "<!--CAPTIONS:BEGIN-->" not in page:
        raise SystemExit("add <!--CAPTIONS:BEGIN--> / <!--CAPTIONS:END--> markers to the composition first")
    page = re.sub(r"(<!--CAPTIONS:BEGIN-->)(.*?)(\s*<!--CAPTIONS:END-->)",
                  lambda m: m.group(1) + "\n" + "\n".join(lines) + m.group(3), page, flags=re.S)
    (root / a.html).write_text(page, encoding="utf-8")
    prov = sum(1 for c in chunks if c.get("provisional"))
    print(f"{len(lines)} caption clips written" + (f" ({prov} provisional - confirm with the user)" if prov else ""))


if __name__ == "__main__":
    main()
