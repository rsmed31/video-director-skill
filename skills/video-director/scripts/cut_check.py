#!/usr/bin/env python3
"""Verify planned cuts against the real speech energy before cutting.

  cut_check.py SOURCE --plan projects/<job>/edit-plan.yaml      (uses plan.cuts src ranges)
  cut_check.py SOURCE --cuts 0-8.05,8.5-21.5,22.12-30.3          (explicit kept ranges)
               [--hop 0.03] [--min-gap 0.12] [--rel 0.35]

analyze_media.py's silencedetect list is unreliable on quiet phone audio (-36 LUFS):
in one job it reported speech as silence and two planned cuts would have clipped words.
This script builds a 30 ms energy envelope with an adaptive threshold (lo + rel*(hi-lo) between the
15th and 70th percentiles) and, for every removed range, reports how much of it is speech. A removed
range with speech longer than --min-gap is flagged, with the nearest quiet runs to move the cut into.
Exit 1 when any removed range holds speech.
"""
import argparse, subprocess, sys

import numpy as np

SR = 16000


def envelope(path, hop):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float64)
    n = int(SR * hop)
    frames = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)


def runs(mask):
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--plan")
    ap.add_argument("--cuts", help="kept src ranges a-b,c-d,...")
    ap.add_argument("--hop", type=float, default=0.03)
    ap.add_argument("--min-gap", type=float, default=0.12)
    ap.add_argument("--rel", type=float, default=0.35)
    a = ap.parse_args()

    if a.plan:
        import yaml
        kept = [(float(c["src_start"]), float(c["src_end"])) for c in yaml.safe_load(open(a.plan, encoding="utf-8"))["cuts"]]
    else:
        kept = [tuple(map(float, r.split("-"))) for r in a.cuts.split(",")]
    E = envelope(a.source, a.hop)
    dur = len(E) * a.hop
    srt = np.sort(E)
    lo, hi = srt[int(len(E) * 0.15)], srt[int(len(E) * 0.70)]
    th = lo + a.rel * (hi - lo)
    quiet = runs(E < th)
    quiet_s = [(i * a.hop, j * a.hop) for i, j in quiet if (j - i) * a.hop >= a.min_gap]
    print(f"threshold {th:.1f} dB (lo {lo:.1f}, hi {hi:.1f}); {len(quiet_s)} quiet runs >= {a.min_gap}s")

    removed, prev = [], 0.0
    for s, e in sorted(kept):
        if s - prev > 0.02:
            removed.append((prev, s))
        prev = e
    if dur - prev > 0.05:
        removed.append((prev, dur))

    bad = 0
    for r0, r1 in removed:
        i0, i1 = int(r0 / a.hop), int(r1 / a.hop)
        speech = runs(E[i0:i1] >= th)
        longest = max(((j - i) * a.hop for i, j in speech), default=0.0)
        ok = longest < a.min_gap
        near = [q for q in quiet_s if q[1] > r0 - 1.0 and q[0] < r1 + 1.0]
        print(f"removed {r0:6.2f}-{r1:6.2f}  speech {longest:.2f}s  {'OK' if ok else 'CLIPS SPEECH'}"
              + ("" if ok else "  quiet runs nearby: " + ", ".join(f"{q0:.2f}-{q1:.2f}" for q0, q1 in near)))
        bad += not ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
