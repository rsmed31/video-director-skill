#!/usr/bin/env python3
"""Make a full-bleed 9:16 still from a non-9:16 photo: Codex outpaint + seamless paste-back.

  outpaint_fill.py --photo hook.png --out assets/img/photo_9x16_fill.png [--workdir work/outpaint]
                   [--generated outpaint.png --x 24 --y 300]      (skip generation, only fix the seam)

Why: a 3:4 presenter photo shown "in the middle" with blurred bars was rejected; cover-crop
cut her hand. Step 1 asks Codex (free on the user's ChatGPT plan) to outpaint to 1080x1920 and to place
the original unchanged. Step 2 fixes what generators leave behind: a tone step and a 1-2 px line along
the original's border. It colour-matches each generated side to the photo (gain measured 40-70 px out),
extends the photo's edge pixels a few px, and feathers into the generated area (40 px top/sides,
14 px bottom where coat textures smear). Inspect seam crops at 200% afterwards.
"""
import argparse, os, pathlib, re, shutil, subprocess

import numpy as np
from PIL import Image

PROMPT = ("Use your image generation tool to OUTPAINT the attached photo into a vertical 9:16 image (1080x1920). "
          "Keep the person, face, hands and every existing pixel exactly as they are, at the same scale; only ADD new area "
          "above and below (continue the wall/background above, continue clothing below), matching lighting, grain and "
          "perspective. No text, no borders, no blur bands. Save the final image as outpaint.png in the current directory, "
          "and print the X,Y where the original's top-left corner sits.")


def codex(workdir, photo):
    rel = sorted(pathlib.Path(os.path.expanduser("~/.codex/packages/standalone/releases")).glob("*/bin"))
    env = dict(os.environ, PATH=os.pathsep.join([str(rel[-1])] + [os.environ["PATH"]])) if rel else os.environ
    shutil.copy(photo, os.path.join(workdir, "photo.png"))
    # prompt BEFORE -i: -i takes several files and would swallow it
    r = subprocess.run(["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check", PROMPT, "-i", "photo.png"],
                       cwd=workdir, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
    log = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"X,\s*Y\s*=\s*(\d+),\s*(\d+)", log)
    return os.path.join(workdir, "outpaint.png"), (int(m.group(1)), int(m.group(2))) if m else None


def blend(gen_path, photo_path, X, Y, out_path, inset=4):
    G = np.asarray(Image.open(gen_path).convert("RGB")).astype(float)
    O0 = np.asarray(Image.open(photo_path).convert("RGB")).astype(float)
    O = O0[inset:-inset, inset:-inset]; X += inset; Y += inset
    h, w = O.shape[:2]; H, W = G.shape[:2]
    gain = lambda a, b: b.reshape(-1, 3).mean(0) / np.maximum(a.reshape(-1, 3).mean(0), 1)
    yy, xx = np.mgrid[0:H, 0:W]
    dx = np.maximum(np.maximum(X - xx, xx - (X + w - 1)), 0); dy = np.maximum(np.maximum(Y - yy, yy - (Y + h - 1)), 0)
    d = np.sqrt(dx ** 2 + dy ** 2)
    Gc = G.copy()
    regions = {"top": yy < Y, "bot": yy >= Y + h, "left": (yy >= Y) & (yy < Y + h) & (xx < X), "right": (yy >= Y) & (yy < Y + h) & (xx >= X + w)}
    bands = {"top": (G[max(Y - 70, 0):max(Y - 40, 1), X:X + w], O[:30]), "bot": (G[Y + h + 40:Y + h + 70, X:X + w], O[-30:]),
             "left": (G[Y:Y + h, 0:max(X - 1, 1)], O[:, :max(X, 1)]), "right": (G[Y:Y + h, X + w + 8:W], O[:, -max(W - X - w - 8, 1):])}
    for k, m in regions.items():
        a, b = bands[k]
        if a.size and b.size:
            Gc[m] = G[m] * gain(a, b)
    E = O[np.clip(yy - Y, 0, h - 1), np.clip(xx - X, 0, w - 1)]
    fade = np.where(yy >= Y + h, 14.0, 40.0)
    wgt = np.clip(1 - (d - 5) / fade, 0, 1)[..., None]
    Image.fromarray(np.clip(E * wgt + Gc * (1 - wgt), 0, 255).astype(np.uint8)).save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="work/outpaint")
    ap.add_argument("--generated"); ap.add_argument("--x", type=int); ap.add_argument("--y", type=int)
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    gen, xy = (a.generated, (a.x, a.y)) if a.generated else codex(a.workdir, a.photo)
    if not os.path.exists(gen):
        raise SystemExit("Codex produced no outpaint.png; fall back to fal bria/fibo-edit-1.5/expand (paid, ~$0.04, ask first)")
    if not xy or None in xy:
        raise SystemExit("could not read the original's X,Y from Codex; pass --generated/--x/--y after locating it")
    blend(gen, a.photo, xy[0], xy[1], a.out)
    print(f"{a.out}  (original at {xy}); inspect seam crops before use")


if __name__ == "__main__":
    main()
