#!/usr/bin/env python3
"""Analyze a source video/audio for planning.

  analyze_media.py INPUT --out DIR [--every 2] [--canvas 1080x1920] [--cols 6] [--rows 2]
                   [--silence-db -30] [--silence-min 0.3] [--scene 0.12]

Writes DIR/analysis.json (probe, loudness, silences, scene cuts, speech gaps) and
DIR/sheet_NN.jpg contact sheets: one frame every --every seconds, scaled to the target canvas
coordinate system, with a 10% grid, canvas-pixel tick labels and timestamps, so boxes read off
the sheets can go straight into edit-plan.yaml (keepout / graphics boxes).
"""
import argparse, glob, json, math, os, re, shutil, subprocess, sys, tempfile


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def probe(path):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
               "-of", "json", path])
    j = json.loads(out.stdout or "{}")
    info = {"duration": float(j.get("format", {}).get("duration", 0) or 0), "streams": j.get("streams", [])}
    for s in info["streams"]:
        if s.get("codec_type") == "video":
            n, _, d = s.get("r_frame_rate", "0/1").partition("/")
            info.update(width=s.get("width"), height=s.get("height"), fps=round(float(n) / float(d or 1), 3))
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def loudness(path):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    res = {}
    for key, pat in (("integrated_lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+(-?[\d.]+) LU"),
                     ("true_peak_dbtp", r"Peak:\s+(-?[\d.]+) dBFS")):
        m = re.findall(pat, err)
        if m:
            res[key] = float(m[-1])
    return res


def silences(path, db, dmin):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", f"silencedetect=n={db}dB:d={dmin}", "-f", "null", "-"]).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    return [{"start": round(max(0, s), 3), "end": round(e, 3), "dur": round(e - max(0, s), 3)} for s, e in zip(starts, ends)]


def scenes(path, thr):
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"]).stderr
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", err)]


def sheets(path, out, every, canvas, cols, rows, duration):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        tile = f"{cols}x{rows}"
        run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", f"fps=1/{every},scale=240:-1,tile={tile}", os.path.join(out, "sheet_%02d.jpg")])
        return sorted(glob.glob(os.path.join(out, "sheet_*.jpg")))
    cw, ch = canvas
    tw = 270                                 # thumb width
    th = round(tw * ch / cw)
    sx = tw / cw
    tmp = tempfile.mkdtemp(prefix="vd_frames_")
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf",
             f"fps=1/{every},scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},scale={tw}:{th}",
             os.path.join(tmp, "f_%04d.png")], timeout=1800)
        frames = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
        try:
            font = ImageFont.truetype("arial.ttf", 13)
            big = ImageFont.truetype("arialbd.ttf", 16)
        except OSError:
            font = big = ImageFont.load_default()
        per = cols * rows
        paths = []
        for si in range(math.ceil(len(frames) / per)):
            sheet = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 26) + 6), (24, 24, 24))
            for k, fp in enumerate(frames[si * per:(si + 1) * per]):
                idx = si * per + k
                t = idx * every
                im = Image.open(fp).convert("RGB")
                d = ImageDraw.Draw(im, "RGBA")
                for g in range(1, 10):           # 10% grid in canvas pixels
                    x = g * tw / 10; y = g * th / 10
                    d.line([(x, 0), (x, th)], fill=(255, 0, 80, 90), width=1)
                    d.line([(0, y), (tw, y)], fill=(255, 0, 80, 90), width=1)
                    if g % 2 == 0:
                        d.text((x + 2, 2), str(round(g * cw / 10)), fill=(255, 255, 0, 230), font=font)
                        d.text((2, y + 1), str(round(g * ch / 10)), fill=(255, 255, 0, 230), font=font)
                cx = 6 + (k % cols) * (tw + 6)
                cy = 6 + (k // cols) * (th + 26)
                sheet.paste(im, (cx, cy + 20))
                ImageDraw.Draw(sheet).text((cx + 2, cy + 1), f"t={t:.1f}s", fill=(255, 255, 255), font=big)
            p = os.path.join(out, f"sheet_{si + 1:02d}.jpg")
            sheet.save(p, quality=85)
            paths.append(p)
        return paths
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--canvas", default="1080x1920")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--silence-db", type=float, default=-30)
    ap.add_argument("--silence-min", type=float, default=0.3)
    ap.add_argument("--scene", type=float, default=0.12)
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    canvas = tuple(int(x) for x in a.canvas.lower().split("x"))

    info = probe(a.input)
    res = {"input": os.path.abspath(a.input), "probe": info, "canvas": list(canvas)}
    if info.get("has_audio"):
        res["loudness"] = loudness(a.input)
        res["silences"] = silences(a.input, a.silence_db, a.silence_min)
        res["removable_pauses"] = [s for s in res["silences"] if s["dur"] >= 0.4 and s["start"] > 0.05
                                   and s["end"] < info["duration"] - 0.05]
    if info.get("width"):
        res["scene_cuts"] = scenes(a.input, a.scene)
        if not a.no_sheets:
            res["sheets"] = [os.path.basename(p) for p in sheets(a.input, a.out, a.every, canvas, a.cols, a.rows, info["duration"])]
            res["sheet_every_s"] = a.every
    with open(os.path.join(a.out, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    print(f"duration {info['duration']:.2f}s  {info.get('width')}x{info.get('height')} @ {info.get('fps')}fps  audio={bool(info.get('has_audio'))}")
    if "loudness" in res:
        print(f"loudness {res['loudness']}")
        print(f"silences>={a.silence_min}s: {len(res['silences'])}  removable pauses (>=0.4s, mid-take): "
              + ", ".join(f"{s['start']:.2f}-{s['end']:.2f}" for s in res["removable_pauses"]) or "none")
    if "scene_cuts" in res:
        print(f"scene cuts: {res['scene_cuts'] or 'none (single take)'}")
    if res.get("sheets"):
        print(f"sheets ({a.every}s/frame, grid in canvas px {canvas[0]}x{canvas[1]}): " + ", ".join(res["sheets"]))
    print(f"-> {os.path.join(a.out, 'analysis.json')}")


if __name__ == "__main__":
    main()
