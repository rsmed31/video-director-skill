#!/usr/bin/env python3
"""Backtest a rendered video's sound before delivering it (checkpoint B gate).

  audio_backtest.py --render R.mp4 [--voice VOICE] [--music BED] [--speech START,END]
                    [--music-under MIN,MAX] [--quiet-db 18] [--json]

Measures, on the render's own audio:
  * loudness per second, and any second far below the median (unintended silence, e.g. a misplaced
    afade that muted the hook in an early version);
  * with --voice/--music stems (aligned to the render timeline: the cut master's audio and the bed
    file the composition plays), a least-squares fit render ~ a*voice + b*music per 10 s window:
    both gains must be ~1 (the layer is really in the mix) and the music must sit inside
    --music-under dB under the voice *during speech* (default 6..12 dB, see director.yaml
    profiles.<p>.music_bed_db_under_voice). Integrated loudness of the bed hides ducking; this does not.
Exit 1 when a check fails, so it can gate finalize.py.
"""
import argparse, json, subprocess, sys

import numpy as np

SR = 16000


def pcm(path, start=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start}", "-i", path]
    if dur:
        cmd += ["-t", f"{dur}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(out, np.int16).astype(np.float64)


def align(stem, mix, max_ms=150):
    """Shift a stem onto the mix timeline. AAC stems decode with a priming offset (1024 samples @48k
    = 21.3 ms) that breaks sample-level regression; find it by FFT cross-correlation and undo it."""
    w = slice(int(2 * SR), int(min(len(stem), len(mix), 22 * SR)))
    a, b = mix[w] - mix[w].mean(), stem[w] - stem[w].mean()
    n = 1 << int(np.ceil(np.log2(2 * len(a))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    k = int(SR * max_ms / 1000)
    cand = np.r_[c[:k], c[-k:]]
    i = int(np.argmax(cand))
    lag = i if i < k else i - 2 * k
    out = np.zeros_like(stem)
    if lag >= 0:
        out[lag:] = stem[:len(stem) - lag]
    else:
        out[:lag] = stem[-lag:]
    return out, lag


def db(x):
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -180.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--voice", help="voice stem on the render timeline (e.g. assets/cut.mp4)")
    ap.add_argument("--music", help="music bed on the render timeline (e.g. assets/music/bed_duck.wav)")
    ap.add_argument("--speech", help="START,END of the spoken part (default: voice stem length)")
    ap.add_argument("--music-under", default="6,12", help="allowed dB of music under voice during speech")
    ap.add_argument("--quiet-db", type=float, default=18.0, help="flag seconds this far below the median")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    mix = pcm(a.render)
    secs = [db(mix[i * SR:(i + 1) * SR]) for i in range(len(mix) // SR)]
    med = float(np.median(secs)) if secs else -180
    res = {"render": a.render, "seconds": len(secs), "median_db": round(med, 1),
           "per_second_db": [round(s, 1) for s in secs], "fail": []}
    quiet = [i for i, s in enumerate(secs) if s < med - a.quiet_db]

    voice = pcm(a.voice) if a.voice else None
    s0, s1 = 0.0, len(secs)
    if a.speech:
        s0, s1 = map(float, a.speech.split(","))
    elif voice is not None:
        s1 = len(voice) / SR
    res["quiet_seconds_in_speech"] = [i for i in quiet if s0 <= i < s1 - 1]
    if res["quiet_seconds_in_speech"]:
        res["fail"].append(f"near-silent seconds inside speech: {res['quiet_seconds_in_speech']}")

    if voice is not None and a.music:
        music = pcm(a.music)
        voice, lv = align(voice, mix)
        music, lm = align(music, mix)
        res["stem_lag_ms"] = {"voice": round(lv / SR * 1000, 1), "music": round(lm / SR * 1000, 1)}
        lo, hi = map(float, a.music_under.split(","))
        wins = []
        for w0 in np.arange(s0, max(s0 + 1, s1 - 1), 10.0):
            i0, i1 = int(w0 * SR), int(min(w0 + 10, s1) * SR)
            m, v, b = mix[i0:i1], voice[i0:i1], music[i0:i1]
            n = min(len(m), len(v), len(b))
            if n < SR:
                continue
            m, v, b = m[:n], v[:n], b[:n]
            (gv, gb), *_ = np.linalg.lstsq(np.vstack([v, b]).T, m, rcond=None)
            under = db(gv * v) - db(gb * b)
            wins.append({"t": float(w0), "voice_gain": round(float(gv), 2), "music_gain": round(float(gb), 2),
                         "music_under_voice_db": round(under, 1)})
        res["windows"] = wins
        if wins:
            mg = float(np.median([w["music_gain"] for w in wins]))
            mu = float(np.median([w["music_under_voice_db"] for w in wins]))
            res["music_gain_median"], res["music_under_voice_db_median"] = round(mg, 2), round(mu, 1)
            if mg < 0.5:
                res["fail"].append(f"music barely present in the mix (gain {mg:.2f})")
            if not lo <= mu <= hi:
                res["fail"].append(f"music sits {mu:.1f} dB under the voice during speech (want {lo:g}..{hi:g})")
            if float(np.median([w["voice_gain"] for w in wins])) < 0.5:
                res["fail"].append("voice stem barely present in the mix")

    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"{a.render}: {len(secs)} s, median {med:.1f} dB")
        print("per second:", " ".join(f"{i}:{s:.0f}" for i, s in enumerate(secs)))
        for w in res.get("windows", []):
            print(f"  {w['t']:5.1f}s  voice x{w['voice_gain']}  music x{w['music_gain']}  music {w['music_under_voice_db']} dB under voice")
        print("PASS" if not res["fail"] else "FAIL: " + "; ".join(res["fail"]))
    sys.exit(1 if res["fail"] else 0)


if __name__ == "__main__":
    main()
