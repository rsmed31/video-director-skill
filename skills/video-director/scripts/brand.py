#!/usr/bin/env python3
"""Brand intake: turn a brand kit (folder, file, or chat answers) into a brand in director.yaml.

  brand.py template --id SLUG [--root WS]           write brands/<slug>/brand.yaml to fill in
  brand.py import   PATH [--id SLUG] [--root WS]    PATH = kit folder, brand.yaml/brand.md, or a logo image
                    [--name N] [--url URL] [--set key=value ...] [--dry-run]
  brand.py show     --id SLUG                       print the stored brand + contrast report
  brand.py list
  brand.py map      --id SLUG --client "Name" [--alias a --alias b]   link a client's name(s) to a brand
  brand.py set      --id SLUG key=value [...]       e.g. palette.accent=#f3a54f fonts.display="Archivo Black"

A kit folder may hold: brand.yaml or brand.md (frontmatter), logo files (svg/png, "logo" in the name
wins), fonts (ttf/otf/woff/woff2), guideline docs (pdf/md/txt - read them yourself and pass what they
say via --set). Kit files are copied into <workspace>/brands/<slug>/ so every job can reuse them; the
brand spec itself goes into director.yaml -> brands.<slug>, where feedback rules can target brand:<slug>.
Missing palette -> extracted from the logo (needs Pillow). Values from --set win over the kit file.
"""
import argparse, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402
import director_memory as dm  # noqa: E402

IMG = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
FONT = {".ttf", ".otf", ".woff", ".woff2"}
DOC = {".pdf", ".md", ".txt", ".docx"}
ROLES = ("primary", "secondary", "light", "accent", "ink")

TEMPLATE = """# Brand kit - fill what you know, delete the rest, then: brand.py import brands/{id}
name: {id}
client:                      # the person/company you make these videos for (brand = client)
aliases: []                  # other names you call them by, so "make a video for <name>" finds this brand
description:                 # one line: who they are, what they do
handles: {{instagram: , tiktok: , youtube: , website: }}
platform: instagram_reels    # default platform for this brand's videos
profile: talking_head_edu    # default edit profile
language: {{speech: en, captions: en, ui: en}}
palette:                     # hex; leave empty to extract from the logo
  primary:
  secondary:
  light:                     # light ground / text on dark
  accent:                    # calls to action, highlight word
  ink:                       # dark text
fonts:
  display:                   # family name; drop the font files in this folder
  body:
logo:
  file:                      # e.g. logo.svg (found automatically if 'logo' is in the name)
  placement: end_card        # end_card | corner | intro | none
  corner: top-left           # when placement is corner
  min_height_px: 80
voice:                       # how the brand talks in on-screen text and post copy
  tone: [clear, warm]
  use: []                    # words/phrases to use
  avoid: []                  # words/phrases never to use
cta: {{follow: , save: , link: }}
visual:
  do: []                     # e.g. "real product photos", "rounded corners"
  dont: []                   # e.g. "no red", "no stock photos of handshakes"
taste: {{energy: , motion: , density: }}   # optional 1-10 dials for this brand
ai_media_style:              # style suffix for every generated image/clip
footage_notes:               # anything in their footage to protect (burned-in text, logos)
"""


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "brand"


def hexnorm(v):
    if v is None:
        return None
    v = str(v).strip()
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", v)
    if not m:
        return v
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def lum(h):
    h = hexnorm(h)
    if not h or not re.fullmatch(r"#[0-9a-f]{6}", h):
        return None
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = lum(a), lum(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def contrast_report(p):
    out = []
    for fg, bg, need in (("ink", "light", 7), ("light", "primary", 4.5), ("ink", "accent", 3), ("light", "accent", 3)):
        r = contrast(p.get(fg), p.get(bg))
        if r is not None:
            out.append(f"{fg} on {bg}: {r}:1 {'ok' if r >= need else f'LOW (want >= {need})'}")
    return out


def palette_from_image(path):
    """Dominant non-background colours of a logo, assigned to roles by lightness."""
    try:
        from PIL import Image
    except ImportError:
        return {}
    if path.lower().endswith(".svg"):
        txt = open(path, encoding="utf-8", errors="ignore").read()
        cols = [hexnorm(c) for c in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", txt)]
        cols = list(dict.fromkeys(c for c in cols if c not in ("#ffffff", "#000000")))
    else:
        im = Image.open(path).convert("RGBA")
        im.thumbnail((200, 200))
        data = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
        px = [p for p in data if p[3] > 200]
        if not px:
            return {}
        q = Image.new("RGB", (len(px), 1))
        q.putdata([p[:3] for p in px])
        q = q.quantize(colors=6)
        pal = q.getpalette()[:18]
        counts = sorted(q.getcolors(), reverse=True)
        cols = []
        for _, idx in counts:
            r, g, b = pal[idx * 3: idx * 3 + 3]
            h = f"#{r:02x}{g:02x}{b:02x}"
            if max(r, g, b) - min(r, g, b) < 18 and (min(r, g, b) > 235 or max(r, g, b) < 20):
                continue  # near-white / near-black backgrounds
            cols.append(h)
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    distinct = []
    for c in cols:  # drop near-duplicates (anti-aliasing shades of the same colour)
        if all(sum(abs(x - y) for x, y in zip(rgb(c), rgb(d))) > 60 for d in distinct):
            distinct.append(c)
    cols = distinct
    if not cols:
        return {}
    sat = lambda h: (lambda r, g, b: max(r, g, b) - min(r, g, b))(*[int(h[i:i + 2], 16) for i in (1, 3, 5)])
    by_sat = sorted(cols, key=sat, reverse=True)
    out = {"primary": cols[0]}
    rest = [c for c in by_sat if c != cols[0]]
    if rest:
        out["accent"] = rest[0]
    if len(rest) > 1:
        out["secondary"] = rest[1]
    return out


def read_kit_file(path):
    txt = open(path, encoding="utf-8", errors="ignore").read()
    if path.lower().endswith((".yaml", ".yml")):
        return yaml.safe_load(txt) or {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", txt, re.S)
    if m:
        d = yaml.safe_load(m.group(1)) or {}
        if m.group(2).strip():
            d.setdefault("notes", m.group(2).strip())
        return d
    return {"notes": txt.strip()}


def set_path(d, key, value):
    parts = key.split(".")
    for p in parts[:-1]:
        if not isinstance(d.get(p), dict):
            d[p] = {}
        d = d[p]
    if value.strip().startswith("#"):
        v = value.strip()  # a hex colour, not a YAML comment
    else:
        try:
            v = yaml.safe_load(value)
        except yaml.YAMLError:
            v = value
    d[parts[-1]] = v


def prune(x):
    if isinstance(x, dict):
        y = {k: prune(v) for k, v in x.items()}
        return {k: v for k, v in y.items() if v not in (None, "", [], {})}
    if isinstance(x, list):
        return [prune(v) for v in x if v not in (None, "")]
    return x


def find_workspace(root):
    r = os.path.abspath(root or os.getcwd())
    cur = r
    while True:
        if os.path.exists(os.path.join(cur, "video-director.yaml")) or os.path.isdir(os.path.join(cur, "inputs")):
            return cur
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return r
        cur = nxt


def do_import(a, mem):
    src = os.path.abspath(a.path)
    if not os.path.exists(src):
        sys.exit(f"not found: {src}")
    files = []
    if os.path.isdir(src):
        for dp, _, fs in os.walk(src):
            files += [os.path.join(dp, f) for f in fs]
    else:
        files = [src]
    kit = {}
    for f in files:
        b = os.path.basename(f).lower()
        if b in ("brand.yaml", "brand.yml", "brand.md") or (len(files) == 1 and b.endswith((".yaml", ".yml", ".md"))):
            kit = read_kit_file(f)
            break
    bid = slugify(a.id or kit.get("id") or kit.get("name") or a.name or os.path.basename(src.rstrip("/\\")).split(".")[0])
    brand = dict((mem.get("brands") or {}).get(bid) or {})
    brand = dm.deep_merge(brand, prune(kit))
    if a.name:
        brand["name"] = a.name
    if a.client:
        brand["client"] = a.client
    if a.alias:
        brand["aliases"] = sorted(set(brand.get("aliases") or []) | set(a.alias))
    if a.url:
        brand.setdefault("handles", {})["website"] = a.url
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        set_path(brand, k.strip(), v)

    ws = find_workspace(a.root)
    kitdir = os.path.join(ws, "brands", bid)
    logos = [f for f in files if os.path.splitext(f)[1].lower() in IMG]
    logos.sort(key=lambda f: (("logo" not in os.path.basename(f).lower()), not f.lower().endswith(".svg")))
    fonts = [f for f in files if os.path.splitext(f)[1].lower() in FONT]
    docs = [f for f in files if os.path.splitext(f)[1].lower() in DOC and os.path.basename(f).lower() != "brand.md"]
    copied = []
    if not a.dry_run and (logos or fonts or docs):
        os.makedirs(kitdir, exist_ok=True)
        for f in logos + fonts + docs:
            dst = os.path.join(kitdir, os.path.basename(f))
            if os.path.abspath(f) != os.path.abspath(dst):
                shutil.copy2(f, dst)
            copied.append(os.path.basename(f))
    rel = os.path.relpath(kitdir, ws).replace("\\", "/")
    if logos:
        if not isinstance(brand.get("logo"), dict):
            brand["logo"] = {"file": brand["logo"]} if brand.get("logo") else {}
        lg = brand["logo"]
        lg.setdefault("file", os.path.basename(logos[0]))
        lg.setdefault("placement", "end_card")
        if len(logos) > 1:
            lg.setdefault("alternates", [os.path.basename(f) for f in logos[1:]])
    if fonts:
        brand["font_files"] = sorted({os.path.basename(f) for f in fonts})
    if docs:
        brand["guidelines"] = sorted({os.path.basename(f) for f in docs})
    if copied or brand.get("kit"):
        brand["kit"] = rel
    pal = {k: hexnorm(v) for k, v in (brand.get("palette") or {}).items() if v}
    if logos and not all(pal.get(k) for k in ("primary", "accent")):
        ext = palette_from_image(logos[0])
        for k, v in ext.items():
            pal.setdefault(k, v)
        if ext:
            brand["palette_source"] = f"extracted from {os.path.basename(logos[0])} - confirm at checkpoint A"
    pal.setdefault("light", "#f7f5f2")
    pal.setdefault("ink", "#141414")
    brand["palette"] = {k: pal[k] for k in ROLES if k in pal} | {k: v for k, v in pal.items() if k not in ROLES}
    brand = prune(brand)

    missing = [f for f in ("description", "platform", "profile", "fonts", "cta") if not brand.get(f)]
    print(f"# brand {bid}  kit -> {rel if copied else '(no files copied)'}")
    print(yaml.safe_dump(brand, sort_keys=False, allow_unicode=True, width=110))
    for line in contrast_report(brand["palette"]):
        print("contrast  " + line)
    if missing:
        print("missing   " + ", ".join(missing) + "  (infer from footage/website or ask at checkpoint A)")
    if docs:
        print("read      " + ", ".join(docs) + "  -> pass what they say with brand.py set")
    if a.dry_run:
        print("(dry run - nothing saved)")
        return
    mem.setdefault("brands", {})[bid] = brand
    dm.save(a.memory, mem)
    print(f"saved director.yaml -> brands.{bid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["template", "import", "show", "list", "set", "map"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--id")
    ap.add_argument("--name")
    ap.add_argument("--url")
    ap.add_argument("--client")
    ap.add_argument("--alias", action="append")
    ap.add_argument("--root")
    ap.add_argument("--set", action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--memory", default=dm.DEFAULT_MEM)
    a = ap.parse_args()
    mem = dm.load(a.memory)
    brands = mem.get("brands") or {}

    if a.cmd == "list":
        for k, b in brands.items():
            who = b.get("client") or "-"
            print(f"{k:22} client={who:18} {b.get('platform', ''):17} {b.get('profile', ''):19} {b.get('description', '')}")
    elif a.cmd == "map":
        bid = dm.find_brand(mem, a.id or a.path)
        if bid not in brands:
            sys.exit(f"unknown brand {bid}; known: {', '.join(brands) or 'none'}")
        b = brands[bid]
        if a.client:
            b["client"] = a.client
        b["aliases"] = sorted(set(b.get("aliases") or []) | set(a.alias or []))
        dm.save(a.memory, mem)
        print(f"{bid}: client={b.get('client')} aliases={b['aliases']}")
    elif a.cmd == "template":
        bid = slugify(a.id or a.path or "my-brand")
        d = os.path.join(find_workspace(a.root), "brands", bid)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "brand.yaml")
        if os.path.exists(p):
            sys.exit(f"exists: {p}")
        open(p, "w", encoding="utf-8").write(TEMPLATE.format(id=bid))
        print(f"wrote {p} - put the logo and font files next to it, then: brand.py import {d}")
    elif a.cmd == "import":
        if not a.path:
            sys.exit("brand.py import PATH")
        do_import(a, mem)
    elif a.cmd in ("show", "set"):
        bid = dm.find_brand(mem, a.id or (a.path if a.cmd == "show" else None))
        if bid not in brands:
            sys.exit(f"unknown brand {bid}; known: {', '.join(brands) or 'none'} (brand.py import <kit>)")
        b = brands[bid]
        if a.cmd == "set":
            pairs = ([a.path] if a.path else []) + a.pairs + (a.set or [])
            for kv in pairs:
                k, _, v = kv.partition("=")
                set_path(b, k.strip(), v)
            if b.get("palette"):
                b["palette"] = {k: hexnorm(v) for k, v in b["palette"].items()}
            dm.save(a.memory, mem)
        print(yaml.safe_dump({bid: b}, sort_keys=False, allow_unicode=True, width=110))
        for line in contrast_report(b.get("palette") or {}):
            print("contrast  " + line)


if __name__ == "__main__":
    main()
