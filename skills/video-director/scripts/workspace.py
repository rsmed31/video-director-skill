#!/usr/bin/env python3
"""Workspace manager for video-director: inputs/<job> -> projects/<job> -> outputs/<job>.

Commands:
  init  [--root DIR] [--brand ID] [--platform ID]   create folders + video-director.yaml
  scan  [--root DIR] [--json]                        list jobs, status, classified inputs, loose files
  new   --job SLUG [--root DIR]                      create inputs/<slug>/ with a brief.md template
  adopt --job SLUG [--root DIR] [--project DIR] [--output FILE] FILES...
        move loose files into inputs/<slug>/, an existing project into projects/<slug>/,
        and file a previous render as outputs/<slug>/<slug>-v0.mp4
  status --job SLUG --set STATE [--root DIR]         update projects/<slug>/job.yaml status
"""
import argparse, json, os, re, shutil, subprocess, sys, datetime

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML missing: pip install pyyaml")

CLASSES = {
    "footage": {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"},
    "image": {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".heic"},
    "font": {".ttf", ".otf", ".woff", ".woff2"},
    "transcript": {".srt", ".vtt", ".json"},
    "details": {".md", ".txt", ".pdf", ".docx", ".rtf", ".yaml", ".yml"},
}
IGNORE_ROOT = {"inputs", "projects", "outputs", "brands", "video-director.yaml", ".git", ".claude", "node_modules"}
STATES = ["new", "planned", "building", "delivered", "revising"]

BRIEF_TEMPLATE = """---
# Optional fields - delete what you don't know, the director will infer or ask.
platform: instagram_reels      # instagram_reels | tiktok | youtube_shorts | youtube | generic
profile:                       # talking_head_edu | talking_head_story | product_promo | explainer_faceless | tutorial_screen | music_montage
brand:                         # brand id from director.yaml, or a new name (then add a brand/ folder here)
brand_kit:                     # optional: path or website URL of the brand kit (logo, colours, fonts, guidelines)
language:
goal:
audience:
length:
cta:
keep: []
avoid: []
---

Describe the video you want here, in your own words: what it is about, who it is for,
anything that must appear or must not appear, names/spellings, links, deadline.
"""


def classify(path):
    ext = os.path.splitext(path)[1].lower()
    for k, exts in CLASSES.items():
        if ext in exts:
            return k
    return "other"


def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", path], capture_output=True, text=True, timeout=30)
        j = json.loads(out.stdout or "{}")
    except Exception:
        return {}
    info = {"duration": round(float(j.get("format", {}).get("duration", 0) or 0), 2)}
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and "width" in s:
            info["size"] = f'{s["width"]}x{s["height"]}'
            num, _, den = s.get("r_frame_rate", "0/1").partition("/")
            try:
                info["fps"] = round(float(num) / float(den or 1), 2)
            except ZeroDivisionError:
                pass
        if s.get("codec_type") == "audio":
            info["audio"] = True
    return info


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(name)[0].lower()).strip("-")
    return s or "job"


def load_yaml(p):
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_yaml(p, data):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=110)


def job_status(root, job):
    jy = load_yaml(os.path.join(root, "projects", job, "job.yaml"))
    if jy.get("status") in STATES:
        return jy["status"], jy
    proj = os.path.join(root, "projects", job)
    outs = os.path.join(root, "outputs", job)
    has_out = os.path.isdir(outs) and any(f.endswith(".mp4") for f in os.listdir(outs))
    if has_out:
        return "delivered", jy
    if os.path.exists(os.path.join(proj, "edit-plan.yaml")):
        return "planned", jy
    if os.path.isdir(proj):
        return "building", jy
    return "new", jy


def scan(root):
    res = {"root": os.path.abspath(root), "jobs": [], "loose": []}
    inputs = os.path.join(root, "inputs")
    if os.path.isdir(inputs):
        for job in sorted(os.listdir(inputs)):
            jdir = os.path.join(inputs, job)
            if not os.path.isdir(jdir):
                continue
            files = []
            for dp, _, fns in os.walk(jdir):
                for fn in sorted(fns):
                    p = os.path.join(dp, fn)
                    c = classify(p)
                    e = {"file": os.path.relpath(p, root).replace("\\", "/"), "class": c,
                         "kb": round(os.path.getsize(p) / 1024)}
                    if c in ("footage", "audio"):
                        e.update(probe(p))
                    files.append(e)
            st, jy = job_status(root, job)
            outs_dir = os.path.join(root, "outputs", job)
            versions = sorted(f for f in os.listdir(outs_dir) if f.endswith(".mp4")) if os.path.isdir(outs_dir) else []
            res["jobs"].append({"job": job, "status": st, "inputs": files, "versions": versions,
                                "has_details": any(f["class"] == "details" for f in files),
                                "brand_kit": next((f["file"].rsplit("/", 1)[0] for f in files
                                                   if f["file"].lower().endswith(("/brand.yaml", "/brand.yml", "/brand.md"))
                                                   or "/brand/" in f["file"].lower()), None),
                                "brief": {k: jy.get("brief", {}).get(k) for k in ("platform", "profile", "brand")} if jy else {}})
    bdir = os.path.join(root, "brands")
    res["brand_kits"] = sorted(d for d in os.listdir(bdir) if os.path.isdir(os.path.join(bdir, d))) if os.path.isdir(bdir) else []
    for fn in sorted(os.listdir(root)):
        if fn in IGNORE_ROOT or fn.startswith("."):
            continue
        p = os.path.join(root, fn)
        if os.path.isdir(p):
            if os.path.exists(os.path.join(p, "hyperframes.json")):
                res["loose"].append({"file": fn, "class": "hyperframes_project", "suggest_job": slugify(fn)})
            continue
        c = classify(p)
        if c != "other":
            e = {"file": fn, "class": c, "suggest_job": slugify(fn)}
            if c == "footage":
                e.update(probe(p))
            res["loose"].append(e)
    return res


def print_scan(res):
    print(f"workspace: {res['root']}")
    if not res["jobs"]:
        print("  no jobs in inputs/ yet")
    for j in res["jobs"]:
        print(f"\n[{j['status']}] {j['job']}  versions: {', '.join(j['versions']) or '-'}"
              f"{'' if j['has_details'] else '  (no details file)'}")
        if j.get("brand_kit"):
            print(f"    brand kit  {j['brand_kit']}  -> brand.py import {j['brand_kit']}")
        for f in j["inputs"]:
            extra = " ".join(f"{k}={v}" for k, v in f.items() if k in ("duration", "size", "fps", "audio"))
            print(f"    {f['class']:<10} {f['file']}  {extra}")
    if res.get("brand_kits"):
        print(f"\nbrand kits in brands/: {', '.join(res['brand_kits'])}  (brand.py list shows imported brands)")
    if res["loose"]:
        print("\nloose items at workspace root (not in a job):")
        for f in res["loose"]:
            extra = " ".join(f"{k}={v}" for k, v in f.items() if k in ("duration", "size"))
            print(f"    {f['class']:<18} {f['file']}  {extra}  -> suggest job '{f['suggest_job']}'")
        print("  propose to the user: workspace.py adopt --job <slug> <files> [--project DIR] [--output FILE]")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "scan", "new", "adopt", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("--root", default=".")
        if name == "init":
            sp.add_argument("--brand"); sp.add_argument("--platform")
        if name == "scan":
            sp.add_argument("--json", action="store_true")
        if name in ("new", "adopt", "status"):
            sp.add_argument("--job", required=True)
        if name == "adopt":
            sp.add_argument("--project"); sp.add_argument("--output")
            sp.add_argument("files", nargs="*")
        if name == "status":
            sp.add_argument("--set", required=True, choices=STATES)
    a = ap.parse_args()
    root = a.root

    if a.cmd == "init":
        for d in ("inputs", "projects", "outputs", "brands"):
            os.makedirs(os.path.join(root, d), exist_ok=True)
        wy = os.path.join(root, "video-director.yaml")
        if not os.path.exists(wy):
            save_yaml(wy, {"workspace": {"brand": a.brand, "platform": a.platform or "instagram_reels"},
                           "overrides": {}, "created": str(datetime.date.today())})
        print(f"initialized {os.path.abspath(root)}")
    elif a.cmd == "scan":
        res = scan(root)
        print(json.dumps(res, ensure_ascii=False, indent=1)) if a.json else print_scan(res)
    elif a.cmd == "new":
        d = os.path.join(root, "inputs", a.job)
        os.makedirs(d, exist_ok=True)
        bp = os.path.join(d, "brief.md")
        if not os.path.exists(bp):
            with open(bp, "w", encoding="utf-8") as f:
                f.write(BRIEF_TEMPLATE)
        print(f"created {d} (drop footage/assets here, fill brief.md)")
    elif a.cmd == "adopt":
        d = os.path.join(root, "inputs", a.job)
        os.makedirs(d, exist_ok=True)
        for f in a.files:
            shutil.move(os.path.join(root, f) if not os.path.isabs(f) else f, os.path.join(d, os.path.basename(f)))
            print(f"moved {f} -> inputs/{a.job}/")
        if a.project:
            dst = os.path.join(root, "projects", a.job)
            if os.path.exists(dst):
                sys.exit(f"projects/{a.job} already exists")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(os.path.join(root, a.project), dst)
            print(f"moved {a.project} -> projects/{a.job}/")
        if a.output:
            od = os.path.join(root, "outputs", a.job)
            os.makedirs(od, exist_ok=True)
            shutil.move(os.path.join(root, a.output), os.path.join(od, f"{a.job}-v0.mp4"))
            print(f"moved {a.output} -> outputs/{a.job}/{a.job}-v0.mp4")
    elif a.cmd == "status":
        p = os.path.join(root, "projects", a.job, "job.yaml")
        jy = load_yaml(p)
        jy["status"] = a.set
        jy.setdefault("history", []).append({"date": str(datetime.date.today()), "status": a.set})
        save_yaml(p, jy)
        print(f"{a.job}: {a.set}")


if __name__ == "__main__":
    main()
