#!/usr/bin/env python3
"""Turn a HyperFrames render into platform-ready deliverables.

  finalize.py --render RAW.mp4 --plan projects/<job>/edit-plan.yaml --out outputs/<job>
              [--memory director.yaml] [--transcript transcript.clean.json] [--no-loudnorm]

- picks the next version number (<job>-vN.mp4; never overwrites)
- two-pass loudnorm to the platform LUFS / true-peak target
- re-encodes to the platform export spec (H.264 High, yuv420p, VBR, AAC 48k, +faststart)
- cover.jpg from plan.cover.t, captions.srt from plan captions (chunks or transcript)
- post.md draft (hook, CTA, AI disclosure note when the plan used generated media)
- appends to outputs/<job>/notes.md
"""
import argparse, datetime, glob, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402
import director_memory as dm  # noqa: E402


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd[:6])}...\n{r.stderr[-1500:]}")
    return r


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", str(s)).strip()


def src_to_out(cuts):
    """Map source-media time -> output time through the plan's cuts (None if the moment was cut)."""
    spans, acc = [], 0.0
    for c in cuts or []:
        s, e = float(c.get("src_start", 0)), float(c.get("src_end", 0))
        spans.append((s, e, acc))
        acc += e - s

    def f(t):
        if not spans:
            return t
        for s, e, base in spans:
            if s - 1e-3 <= t <= e + 1e-3:
                return base + (min(max(t, s), e) - s)
        return None
    return f


def chunks_from_transcript(path, max_words=4, cuts=None):
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    words = j if isinstance(j, list) else j.get("words", [])
    m = src_to_out(cuts)
    mapped = []
    for w in words:
        s, e = m(float(w["start"])), m(float(w["end"]))
        if s is None or e is None:
            continue
        mapped.append({**w, "start": s, "end": e})
    words = mapped
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or str(w.get("text", "")).rstrip().endswith((".", "?", "!", "،", ",", "؟")):
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur)})
            cur = []
    if cur:
        out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--memory", default=dm.DEFAULT_MEM)
    ap.add_argument("--transcript")
    ap.add_argument("--no-loudnorm", action="store_true")
    a = ap.parse_args()

    with open(a.plan, encoding="utf-8") as f:
        plan = yaml.safe_load(f) or {}
    eff = dm.resolve(dm.load(a.memory), plan.get("platform"), plan.get("profile"), plan.get("brand"), None)
    plat = eff["platform"]
    ex = plat.get("export", {})
    ld = plat.get("loudness", {"lufs": -14, "true_peak": -1})
    job = plan.get("job") or os.path.basename(os.path.normpath(a.out))
    os.makedirs(a.out, exist_ok=True)
    existing = [int(m.group(1)) for p in glob.glob(os.path.join(a.out, f"{job}-v*.mp4"))
                if (m := re.search(r"-v(\d+)\.mp4$", p))]
    ver = max(existing, default=0) + 1
    dst = os.path.join(a.out, f"{job}-v{ver}.mp4")

    af = []
    if not a.no_loudnorm:
        i, tp = ld.get("lufs", -14), ld.get("true_peak", -1)
        r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", a.render, "-af",
                 f"loudnorm=I={i}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
        if m:
            st = json.loads(m.group(0))
            af = ["-af", (f"loudnorm=I={i}:TP={tp}:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
                          f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true")]
    mbps = ex.get("video_mbps", 10)
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", a.render, "-c:v", "libx264", "-profile:v", ex.get("profile", "high"),
           "-pix_fmt", ex.get("pix_fmt", "yuv420p"), "-preset", "slow", "-b:v", f"{mbps}M", "-maxrate", f"{ex.get('max_mbps', 25)}M",
           "-bufsize", f"{2 * ex.get('max_mbps', 25)}M", "-r", str(plat.get("fps", 30)), *af,
           "-c:a", "aac", "-ar", str(ex.get("audio_khz", 48) * 1000), "-b:a", f"{ex.get('audio_kbps', 192)}k",
           "-movflags", "+faststart", dst]
    run(cmd)

    # verify
    pr = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height",
                         "-of", "json", dst]).stdout)
    lres = run(["ffmpeg", "-hide_banner", "-nostats", "-i", dst, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", lres)
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"][0]

    # cover
    cov = plan.get("cover") or {}
    ct = float(cov.get("t", 1.0))
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ct}", "-i", dst, "-frames:v", "1", "-q:v", "2", os.path.join(a.out, "cover.jpg")])

    # captions
    cap = plan.get("captions") or {}
    chunks = cap.get("chunks") or []
    tpath = a.transcript or cap.get("source")
    if not chunks and tpath and os.path.exists(tpath):
        chunks = chunks_from_transcript(tpath, cuts=plan.get("cuts"))  # transcript is in source time
    if chunks:
        with open(os.path.join(a.out, "captions.srt"), "w", encoding="utf-8") as f:
            for n, c in enumerate(chunks, 1):
                f.write(f"{n}\n{srt_time(float(c['start']))} --> {srt_time(float(c['end']))}\n{strip_tags(c['text'])}\n\n")

    # post.md (draft; the agent should rewrite it in the brand voice)
    used_ai = any((b.get("gen") or {}).get("provider") for b in plan.get("broll", []) or []) or \
        any(b.get("kind") == "ai_clip" for b in plan.get("broll", []) or [])
    hook = next((strip_tags(" ".join(g.get("content", {}).get("lines", []) or [g.get("content", {}).get("text", "")]))
                 for g in plan.get("graphics", []) or [] if g.get("type") in ("kinetic_title", "hook_text")), "")
    post = os.path.join(a.out, "post.md")
    if not os.path.exists(post):
        with open(post, "w", encoding="utf-8") as f:
            f.write(f"# {job} - post draft\n\n**Caption (draft):** {hook}\n\n")
            cta = (plan.get("ending") or {}).get("cta") or {}
            if cta:
                f.write(f"**CTA:** {cta.get('text', '')}\n\n")
            f.write("**Hashtags:** (add 3-5 specific ones)\n\n")
            f.write(f"**Cover:** cover.jpg (t={ct}s)\n\n")
            if used_ai:
                f.write("**Disclosure:** contains AI-generated imagery -> enable 'AI info' / AI label when posting.\n")

    with open(os.path.join(a.out, "notes.md"), "a", encoding="utf-8") as f:
        f.write(f"\n## v{ver} - {datetime.date.today()}\n- file: {os.path.basename(dst)}\n- plan version: {plan.get('version')}\n"
                f"- {vs['width']}x{vs['height']}, {float(pr['format']['duration']):.2f}s, {int(pr['format']['size']) / 1e6:.1f} MB, "
                f"{lufs[-1] if lufs else '?'} LUFS\n")
    print(json.dumps({"output": dst, "version": ver, "duration": float(pr["format"]["duration"]),
                      "size_mb": round(int(pr["format"]["size"]) / 1e6, 1), "resolution": f"{vs['width']}x{vs['height']}",
                      "lufs": float(lufs[-1]) if lufs else None, "cover": os.path.join(a.out, "cover.jpg"),
                      "captions": bool(chunks), "ai_disclosure": used_ai}, indent=1))


if __name__ == "__main__":
    main()
