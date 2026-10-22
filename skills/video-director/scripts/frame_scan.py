#!/usr/bin/env python3
"""Scan footage for corrupted frames (black blocks, decode garbage) before building on it.

  frame_scan.py VIDEO [--black 12] [--jump 0.02] [--json]

Phone exports can carry broken frames at take joins: one job had 10 frames of black
macro-blocks at src 50.57-50.80 that shipped unnoticed in v1-v6 because every QA sample fell either
side of them. This decodes every frame at 108x192 grey, measures the fraction of near-black pixels
and flags frames that jump above their neighbourhood median by --jump. Prints the bad ranges and a
ready ffmpeg repair (hold the last clean frame over the range, then cut to the first clean one).
Exit 1 when corruption is found. Run it on the source in step 2 and on the cut master after cutting.
"""
import argparse, json, subprocess, sys

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--black", type=int, default=12, help="grey level counted as black")
    ap.add_argument("--jump", type=float, default=0.02, help="black fraction above local median that flags a frame")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--loop", action="store_true", help="also require first frame == last frame (Reels loop)")
    a = ap.parse_args()
    fps_s = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                            "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout.strip()
    n, _, d = fps_s.partition("/"); fps = float(n) / float(d or 1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", "scale=108:192,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108)
    blk = (fr < a.black).reshape(len(fr), -1).mean(axis=1)
    k = int(fps)                                   # 1 s neighbourhood
    bad = []
    for i, v in enumerate(blk):
        lo, hi = max(0, i - k), min(len(blk), i + k + 1)
        med = float(np.median(np.r_[blk[lo:i], blk[i + 1:hi]])) if hi - lo > 1 else 0.0
        if v - med > a.jump:
            bad.append(i)
    ranges = []
    for i in bad:
        if ranges and i - ranges[-1][1] <= 2:
            ranges[-1][1] = i
        else:
            ranges.append([i, i])
    out = [{"start_s": round(s / fps, 3), "end_s": round((e + 1) / fps, 3), "frames": e - s + 1,
            "max_black": round(float(blk[s:e + 1].max()), 3),
            "repair": (f'[0:v]trim=end={(s - 0.5) / fps:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop={e - s + 1}[a];'
                       f'[0:v]trim=start={(e + 0.5) / fps:.3f},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0')} for s, e in ranges]
    loop_diff = None
    if a.loop:
        rgb = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", "scale=108:192", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True).stdout
        f3 = np.frombuffer(rgb, np.uint8).reshape(-1, 192, 108, 3).astype(float)
        loop_diff = round(float(np.abs(f3[0] - f3[-1]).mean()), 2)
    if a.json:
        print(json.dumps({"video": a.video, "fps": fps, "frames": len(fr), "corrupt": out, "loop_diff": loop_diff}, indent=1))
    else:
        print(f"{a.video}: {len(fr)} frames @ {fps:g} fps")
        for r in out:
            print(f"  CORRUPT {r['start_s']:.3f}-{r['end_s']:.3f}s ({r['frames']} frames, max black {r['max_black']})")
            print(f"    repair (video only, keeps duration): -filter_complex \"{r['repair']}\"")
        if loop_diff is not None:
            print(f"  loop: first vs last frame mean abs diff {loop_diff} (want < 1)")
        print("PASS" if not out and (loop_diff is None or loop_diff < 1) else "FAIL")
    sys.exit(1 if out or (loop_diff is not None and loop_diff >= 1) else 0)


if __name__ == "__main__":
    main()
