#!/usr/bin/env python3
"""Taste engine: dials + dealt directions, so the edit is decided instead of defaulted.

Adapted for video from the decision mechanism of taste-skill (github.com/Leonxlnx/taste-skill, MIT):
v1's three 1-10 dials that drive concrete rules, and v2's "a script deals the directions, you choose".

  taste.py dials  --profile P [--brand B] [--set energy=7,motion=4,density=5]
  taste.py draw   --profile P [--tone T] [--have footage,speech,data] [--options 3] [--seed N]
                  [--exclude id,id] [--want energy=8]
  taste.py sheet  --direction ID [--profile P] [--brand B] [--set ...] [--seed N] [--reason "..."] [--out projects/<job>/direction.yaml]
  taste.py list

Dials (1-10): energy = cut pace, motion = camera/overlay movement, density = things on screen at once.
Baseline: director.yaml profiles.<p>.taste -> brands.<b>.taste -> --set (the user's words in chat), later wins.
Derived numbers are pacing TARGETS; learned rules and bans in director.yaml always win over a dial.
"""
import argparse, json, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402
import director_memory as dm  # noqa: E402

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "directions.yaml")
DIALS = ("energy", "motion", "density")


def clamp(v, lo=1, hi=10):
    return max(lo, min(hi, int(round(float(v)))))


def parse_set(s):
    out = {}
    for part in (s or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip().lower()
            if k in DIALS:
                out[k] = clamp(v)
    return out


def baseline(mem, profile, brand, override=None):
    brand = dm.find_brand(mem, brand)
    d = {k: 5 for k in DIALS}
    d.update({k: clamp(v) for k, v in ((mem.get("profiles", {}).get(profile or "", {}) or {}).get("taste") or {}).items() if k in DIALS})
    d.update({k: clamp(v) for k, v in ((mem.get("brands", {}).get(brand or "", {}) or {}).get("taste") or {}).items() if k in DIALS})
    d.update(override or {})
    return d


def derive(d):
    """Map dials to the numbers plan_lint and the build use (taste v1: dials drive the rules)."""
    e, m, n = d["energy"], d["motion"], d["density"]
    return {
        "max_static_s": round(max(2.0, 8.0 - 0.6 * e), 1),
        "hook_change_by_s": round(max(1.0, 3.5 - 0.2 * e), 1),
        "remove_silence_over_s": round(max(0.15, 0.7 - 0.05 * e), 2),
        "punch_in_per_30s_max": max(1, round(m * 0.6)),
        "punch_in_scale": [round(1.0 + 0.012 * m, 3), round(1.06 + 0.04 * m, 2)],
        "layout_transition_min_s": 0.6 if m <= 7 else 0.4,
        "camera_drift": m >= 3,
        "overlays_on_screen_max": 1 + n // 3,
        "graphics_per_min": round(0.6 * n + 0.4, 1),
        "sfx_per_10s": 1 + (e + n) // 5,
        "rules": [r for r, on in (
            ("motion<=3: no punch-ins faster than 1 s, no whips; drift only", m <= 3),
            ("motion>=7: every overlay has an entrance AND an exit; camera never still", m >= 7),
            ("energy>=8: jump cuts allowed mid-sentence on breaths; first change by ~1.5 s", e >= 8),
            ("energy<=3: cut on breaths only; hold reactions", e <= 3),
            ("density<=2: one element on screen besides the speaker, ever", n <= 2),
            ("density>=7: group information in one layout (rail/board), never stacked floating cards", n >= 7),
        ) if on],
    }


def load_lib():
    with open(LIB, encoding="utf-8") as f:
        return yaml.safe_load(f)["directions"]


def score(dr, profile, tone, have, want):
    w = 1.0
    if profile and profile in dr.get("fits", []):
        w += 2
    elif profile:
        w *= 0.35
    if tone and tone in dr.get("tones", []):
        w += 2
    if have is not None and not set(dr.get("needs", [])) <= have:
        return 0.0
    if want:
        dist = sum(abs(dr["dials"][k] - v) for k, v in want.items()) / len(want)
        w *= max(0.15, 1 - dist / 6)
    return w


def deal(lib, n, rng, **kw):
    pool = [(d, score(d, **kw)) for d in lib]
    pool = [(d, w) for d, w in pool if w > 0]
    out = []
    while pool and len(out) < n:
        tot = sum(w for _, w in pool)
        r, acc = rng.random() * tot, 0
        for i, (d, w) in enumerate(pool):
            acc += w
            if acc >= r:
                out.append(d)
                pool.pop(i)
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dials", "draw", "sheet", "list"])
    ap.add_argument("--profile")
    ap.add_argument("--brand")
    ap.add_argument("--tone")
    ap.add_argument("--have", help="comma list of assets that really exist")
    ap.add_argument("--options", type=int, default=3)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--want", help="dials the user asked for, biases the deal")
    ap.add_argument("--set", help="dial overrides from the user's words")
    ap.add_argument("--direction")
    ap.add_argument("--reason", help="why this direction (or why a redraw)")
    ap.add_argument("--out")
    ap.add_argument("--memory", default=dm.DEFAULT_MEM)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    mem = dm.load(a.memory)
    lib = load_lib()

    if a.cmd == "list":
        for d in lib:
            print(f"{d['id']:20} {d['name']:22} fits={','.join(d['fits'])}  tones={','.join(d['tones'])}  dials={d['dials']}")
        return

    if a.cmd == "dials":
        d = baseline(mem, a.profile, a.brand, parse_set(a.set))
        res = {"dials": d, "derived": derive(d)}
        print(json.dumps(res, indent=1) if a.json else yaml.safe_dump(res, sort_keys=False, allow_unicode=True))
        return

    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1, 10 ** 6)
    if a.cmd == "draw":
        excl = {x for x in a.exclude.split(",") if x}
        have = {x.strip() for x in a.have.split(",") if x.strip()} if a.have is not None else None
        picks = deal([d for d in lib if d["id"] not in excl], a.options, random.Random(seed),
                     profile=a.profile, tone=a.tone, have=have, want=parse_set(a.want))
        if not picks:
            sys.exit("no direction fits these constraints; drop --tone or widen --have")
        print(f"# dealt {len(picks)} directions  seed={seed}  profile={a.profile} tone={a.tone} have={a.have}")
        print("# hold each against the subject inventory; pick the one that can carry something only this subject has.\n")
        for d in picks:
            print(f"- {d['id']}  ({d['name']})  dials={d['dials']}")
            print(f"    signature: {d['signature_move']}")
            print(f"    grammar:   {d['transitions']}")
        print(f"\nnext: taste.py sheet --direction <id> --profile {a.profile} --seed {seed} --reason \"<why it carries the idea>\" --out projects/<job>/direction.yaml")
        return

    # sheet
    d = next((x for x in lib if x["id"] == a.direction), None)
    if not d:
        sys.exit(f"unknown direction {a.direction}; see taste.py list")
    base = baseline(mem, a.profile, a.brand)
    # the direction's dials pull the baseline halfway; the user's explicit words win outright
    dials = {k: clamp((base[k] + d["dials"][k]) / 2) for k in DIALS}
    dials.update(parse_set(a.set))
    sheet = {
        "direction": d["id"], "name": d["name"], "seed": seed, "reason": a.reason or "",
        "dials": dials, "derived": derive(dials),
        "signature_move": d["signature_move"], "layouts": d.get("layouts", []), "transitions": d["transitions"], "captions": d["captions"],
        "graphics": d["graphics"], "type": d["type"], "sound": d["sound"], "palette": d["palette"],
        "avoid": d.get("avoid", []),
        "idea": "On this video, [something only this subject has] becomes [the device the signature move calls for]  <- fill in",
    }
    b = (mem.get("brands") or {}).get(dm.find_brand(mem, a.brand) or "", {}) or {}
    if b.get("palette"):
        sheet["palette"] = {"brand": b["palette"], "use": "keep the direction's proportions: " + d["palette"]}
    if b.get("fonts"):
        sheet["type"] = {"brand": b["fonts"], "use": "brand faces in the direction's roles: " + d["type"]}
    if b.get("logo"):
        sheet["logo"] = b["logo"]
    if (b.get("visual") or {}).get("dont"):
        sheet["avoid"] = list(dict.fromkeys(sheet["avoid"] + b["visual"]["dont"]))
    txt = yaml.safe_dump(sheet, sort_keys=False, allow_unicode=True, width=110)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("# direction sheet - the art direction for this job. Adopt it; redraw only for a stated reason.\n" + txt)
        print(f"wrote {a.out}")
    print(txt)


if __name__ == "__main__":
    main()
