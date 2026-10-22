#!/usr/bin/env python3
"""Build a music bed that stays audible under continuous speech.

  music_bed.py --music RAW.mp3 --voice assets/cut.mp4 --duration 54.8 --out assets/music/bed_duck.wav
               [--under 7] [--ratio 1.3] [--fade-out 1.5]

Learned on a real job: a bed judged by its integrated level and ducked
hard (ratio 2.5) sat ~18 dB under the voice whenever the presenter spoke and was inaudible on phones. This
script: high-passes the bed, carves the voice band (-6 dB @2.5 kHz, -2 dB @1 kHz) so it can sit
close to the voice without masking it, applies light sidechain ducking from the voice, fades in/out,
pads to --duration, then MEASURES the bed during speech against the voice and corrects the level
once so the bed lands --under dB under the voice (default 7; director.yaml profile value wins).
Note: loudnorm resamples to 192 kHz internally; the explicit aresample after it is required or
sidechaincompress mis-times and truncates the output.
"""
import argparse, os, re, subprocess, sys, tempfile


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def lufs(path, start=None, dur=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", f"{start}", "-t", f"{dur}"]
    cmd += ["-i", path, "-af", "ebur128", "-f", "null", "-"]
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", run(cmd).stderr)
    return float(m[-1]) if m else None


def build(a, key, target, out):
    fo = max(0.0, a.duration - a.fade_out)
    fc = (f"[0:a]aresample=48000,atrim=0:{a.duration},highpass=f=90,"
          f"equalizer=f=2500:t=o:w=1.4:g=-6,equalizer=f=1000:t=o:w=1:g=-2,"
          f"loudnorm=I={target:.1f}:TP=-2:LRA=5,aresample=48000,"
          f"afade=t=in:d=0.6,afade=t=out:st={fo:.2f}:d={a.fade_out}[m];"
          f"[1:a]aresample=48000,highpass=f=150,lowpass=f=4000[k];"
          f"[m][k]sidechaincompress=threshold=0.06:ratio={a.ratio}:attack=80:release=600:makeup=1,"
          f"apad=whole_len={int(a.duration * 48000)},atrim=0:{a.duration}[o]")
    r = run(["ffmpeg", "-v", "error", "-y", "-i", a.music, "-i", key, "-filter_complex", fc,
             "-map", "[o]", "-ar", "48000", "-c:a", "pcm_s16le", out])
    if r.returncode:
        sys.exit(r.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", required=True)
    ap.add_argument("--voice", required=True, help="voice on the render timeline (cut master)")
    ap.add_argument("--duration", type=float, required=True, help="root composition duration")
    ap.add_argument("--out", required=True)
    ap.add_argument("--under", type=float, default=7.0, help="target dB of bed under voice during speech")
    ap.add_argument("--ratio", type=float, default=1.3, help="sidechain ratio (keep <= 1.6)")
    ap.add_argument("--fade-out", type=float, default=1.5)
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    key = os.path.join(tmp, "voice_key.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", a.voice, "-vn", "-ac", "2",
         "-af", f"aresample=48000,apad=pad_dur=5,atrim=0:{a.duration}", key])
    vdur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice]).stdout or 0)
    s0, s1 = min(2.0, vdur / 4), max(vdur - 1.0, 3.0)
    voice = lufs(a.voice, s0, s1 - s0)
    target = voice - a.under - 4.0          # first guess: integrated bed before ducking/EQ loss
    for _ in range(2):
        build(a, key, target, a.out)
        bed = lufs(a.out, s0, s1 - s0)
        err = (voice - a.under) - bed
        if abs(err) < 0.75:
            break
        target += err
    print(f"voice {voice:.1f} LUFS, bed under speech {bed:.1f} LUFS -> {voice - bed:.1f} dB under (target {a.under})")
    print(a.out)


if __name__ == "__main__":
    main()
