#!/usr/bin/env python3
"""Lint an edit-plan.yaml against platform safe zones, keep-out boxes, pacing and caps.

  plan_lint.py projects/<job>/edit-plan.yaml [--memory director.yaml] [--workspace DIR] [--json]

Exit code 1 when there are errors (warnings alone exit 0).
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402
import director_memory as dm  # noqa: E402
import taste  # noqa: E402
import motion_pick  # noqa: E402

TEXT_GRAPHICS = {"kinetic_title", "name_tag", "section_title", "step_list", "callout", "sticker", "cta", "hook_text"}
LAYOUT_LIMITS = {  # kind: (min_s, max_s) - references/layouts.md
    "full_speaker": (0.5, 999), "speaker_overlay": (0.8, 3.5), "split": (4.0, 999), "pip_speaker": (4.0, 999),
    "cutaway": (1.5, 5.0), "speaker_cutout": (2.0, 999), "text_full": (0.8, 3.0), "side_by_side": (4.0, 999),
}
CAP_KEYS = {"light_leak": "light_leak", "glitch": "glitch", "flash": "flash", "whip": "whip_transition"}


def area(b):
    return max(0, b[2]) * max(0, b[3])


def inter(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x2 - x1) * max(0, y2 - y1)


def t_overlap(s1, e1, s2, e2):
    return min(e1, e2) - max(s1, s2) > 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--memory", default=dm.DEFAULT_MEM)
    ap.add_argument("--workspace")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with open(a.plan, encoding="utf-8") as f:
        plan = yaml.safe_load(f) or {}
    eff = dm.resolve(dm.load(a.memory), plan.get("platform"), plan.get("profile"), plan.get("brand"), a.workspace)
    plat, prof, caps = eff["platform"], eff["profile"], eff["caps"]
    # taste dials (references/taste.md) set pacing targets; memory rules/bans still win
    tst = plan.get("taste") or {}
    tgt = taste.derive(taste.baseline(dm.load(a.memory), plan.get("profile"), plan.get("brand"),
                                      {k: taste.clamp(v) for k, v in (tst.get("dials") or {}).items() if k in taste.DIALS}))
    if tst.get("dials"):
        prof = dict(prof)
        prof["max_static_s"] = min(float(prof.get("max_static_s", 99)), tgt["max_static_s"])
        prof["hook_change_by_s"] = min(float(prof.get("hook_change_by_s", 99)), tgt["hook_change_by_s"])
    W, H = plan.get("canvas") or plat.get("canvas") or [1080, 1920]
    dur = float(plan.get("duration") or 0)
    errors, warns, info = [], [], []

    # ---- collect boxed items -------------------------------------------------------------
    items = []
    for g in plan.get("graphics", []) or []:
        items.append(("graphic", g, g.get("start", 0), g.get("start", 0) + g.get("dur", 0)))
    for b in plan.get("broll", []) or []:
        items.append(("broll", b, b.get("start", 0), b.get("start", 0) + b.get("dur", 0)))
    cap = plan.get("captions") or {}
    if cap.get("band"):
        y0, y1 = cap["band"]
        mw = cap.get("max_width") or (plat.get("caption_band") or {}).get("max_width")             or W - 2 * plat.get("safe_zone", {}).get("left", 60)
        box = cap.get("box") or [round((W - mw) / 2), y0, mw, y1 - y0]   # explicit box wins (e.g. shifted off a gesture)
        items.append(("captions", {"id": "captions", "box": box}, 0, dur))

    sz = plat.get("safe_zone") or {}
    rail = sz.get("right_rail")
    for kind, it, s, e in items:
        box = it.get("box")
        iid = it.get("id", "?")
        if not box:
            if it.get("layout") != "fullframe":
                warns.append(f"{kind} {iid}: no box -> cannot check placement")
            continue
        if it.get("layout") == "fullframe" or it.get("allow_unsafe"):
            continue
        x, y, w, h = box
        bad = []
        if x < sz.get("left", 0): bad.append("left")
        if y < sz.get("top", 0): bad.append("top")
        if x + w > W - sz.get("right", 0): bad.append("right")
        if y + h > H - sz.get("bottom", 0): bad.append(f"bottom (ends y={y + h}, limit {H - sz.get('bottom', 0)})")
        if rail and x + w > rail["x_min"] and y + h > rail["y_min"]: bad.append("right rail")
        if bad:
            errors.append(f"{kind} {iid} @{s:.1f}s box {box} outside safe zone: {', '.join(bad)}")
        for ko in plan.get("keepout", []) or []:
            if t_overlap(s, e, ko.get("start", 0), ko.get("end", dur)) and not it.get("allow_overlap"):
                frac = inter(box, ko["box"]) / max(1, area(box))
                if frac > 0.04:
                    (errors if frac > 0.25 else warns).append(
                        f"{kind} {iid} @{s:.1f}s overlaps keep-out '{ko.get('what', '')}' by {frac:.0%}")

    # ---- hook + static gaps --------------------------------------------------------------
    events = set()
    for k in plan.get("camera", []) or []:
        events.add(round(k.get("t", 0), 2));
        if k.get("dur"): events.add(round(k["t"] + k["dur"], 2))
    t = 0.0
    for c in plan.get("cuts", []) or []:
        t += c.get("src_end", 0) - c.get("src_start", 0)
        events.add(round(t, 2))
    for kind, it, s, e in items:
        if kind != "captions":
            events.add(round(s, 2)); events.add(round(e, 2))
    for tr in plan.get("transitions", []) or []:
        events.add(round(tr.get("at", 0), 2))
    for ch in (cap.get("chunks") or []):
        if "<b>" in str(ch.get("text", "")) or ch.get("emphasis"):
            events.add(round(ch.get("start", 0), 2))
    ev = sorted(x for x in events if 0 <= x <= dur) if dur else sorted(events)
    hook_by = float(prof.get("hook_change_by_s", 3))
    if not any(0 < x <= hook_by for x in ev):
        errors.append(f"no visual change within the first {hook_by}s (hook)")
    text_early = [g for g in plan.get("graphics", []) or [] if g.get("type") in TEXT_GRAPHICS and g.get("start", 99) <= hook_by]
    if not text_early and not (cap.get("chunks") and cap["chunks"][0].get("start", 99) <= 0.5):
        warns.append("no on-screen text hook in the first seconds")
    max_static = float(prof.get("max_static_s", 6))
    pts = [0.0] + ev + ([dur] if dur else [])
    gaps = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1) if pts[i + 1] - pts[i] > max_static]
    for g0, g1 in gaps:
        warns.append(f"static stretch {g0:.1f}-{g1:.1f}s ({g1 - g0:.1f}s > {max_static}s)")

    # ---- caps ----------------------------------------------------------------------------
    minutes = max(dur / 60.0, 0.25) if dur else 1
    for typ, capkey in CAP_KEYS.items():
        n = sum(1 for tr in plan.get("transitions", []) or [] if typ in str(tr.get("type", "")))
        if capkey in caps and n / minutes > caps[capkey] + 1e-9:
            warns.append(f"{n} '{typ}' transitions = {n / minutes:.1f}/min > cap {caps[capkey]}/min")
    sfx = []
    for coll in ("graphics", "broll", "transitions"):
        for it in plan.get(coll, []) or []:
            for c in it.get("sfx", []) or []:
                if isinstance(c, dict):
                    sfx.append((float(c.get("at", it.get("start", it.get("at", 0)))), c.get("key")))
                else:
                    sfx.append((float(it.get("start", it.get("at", 0))), str(c)))
    for c in (plan.get("audio") or {}).get("sfx", []) or []:
        sfx.append((float(c.get("at", 0)), c.get("key")))
    sfx.sort()
    run_key, run_n = None, 0
    for _, k in sfx:
        run_n = run_n + 1 if k == run_key else 1
        run_key = k
        if run_n > caps.get("same_sfx_in_a_row", 99):
            warns.append(f"sfx '{k}' used {run_n}x in a row")
            break
    win = caps.get("sfx_per_10s")
    if win:
        for i, (t0, _) in enumerate(sfx):
            n = sum(1 for t1, _ in sfx[i:] if t1 - t0 < 10)
            if n > win:
                warns.append(f"{n} sfx within 10s from {t0:.1f}s (cap {win})")
                break

    # ---- bans the linter can see ---------------------------------------------------------
    for b in eff["bans"]:
        txt = b["text"].lower()
        for typ in ("glitch", "light leak", "emoji"):
            if typ in txt and ("never" in txt or "no " in txt):
                if any(typ.replace(" ", "_") in str(tr.get("type", "")) for tr in plan.get("transitions", []) or []):
                    errors.append(f"ban {b['id']} violated: {b['text']}")

    # ---- taste: direction, idea, dial targets, tells ------------------------------------
    if not tst:
        warns.append("no taste block: run taste.py dials/draw/sheet and write dials, direction, idea (references/taste.md)")
    else:
        for k in ("direction", "idea"):
            if not tst.get(k) or "<-" in str(tst.get(k)) or "[" in str(tst.get(k)):
                warns.append(f"taste.{k} missing or not filled in")
        for r in tst.get("redraws") or []:
            if not r.get("reason"):
                errors.append(f"redraw from {r.get('from')} has no stated reason")
    mins = minutes if dur else 1
    pis = [k for k in plan.get("camera", []) or [] if float(k.get("scale", 1)) > 1.0 and not k.get("cut")]
    if dur and len(pis) / (mins * 2) > tgt["punch_in_per_30s_max"] + 1e-9:
        warns.append(f"{len(pis)} punch-ins = {len(pis) / (mins * 2):.1f}/30s > taste target {tgt['punch_in_per_30s_max']}/30s")
    for k in plan.get("camera", []) or []:
        sc = float(k.get("scale", 1))
        if sc > tgt["punch_in_scale"][1] + 0.05:
            warns.append(f"camera {k.get('id')} scale {sc} above taste range {tgt['punch_in_scale']}")
    for tr in plan.get("transitions", []) or []:
        if "layout" in str(tr.get("type", "")) or "split" in str(tr.get("type", "")):
            if float(tr.get("dur", 1)) < tgt["layout_transition_min_s"]:
                warns.append(f"transition {tr.get('id')} {tr.get('dur')}s < taste min {tgt['layout_transition_min_s']}s for layout changes")
    ng = len(plan.get("graphics", []) or [])
    if dur and ng / mins > tgt["graphics_per_min"] * 1.5:
        warns.append(f"{ng} graphics = {ng / mins:.1f}/min, well above density target {tgt['graphics_per_min']}/min")
    if win is None or tgt["sfx_per_10s"] < (win or 99):
        for i, (t0, _) in enumerate(sfx):
            n = sum(1 for t1, _ in sfx[i:] if t1 - t0 < 10)
            if n > tgt["sfx_per_10s"]:
                warns.append(f"{n} sfx within 10s from {t0:.1f}s > taste target {tgt['sfx_per_10s']}")
                break
    ncuts = len(plan.get("cuts", []) or [])
    whoosh_cuts = sum(1 for _, k in sfx if k and "whoosh" in str(k))
    if ncuts >= 4 and whoosh_cuts >= 0.8 * ncuts:
        warns.append(f"tell: whoosh on nearly every cut ({whoosh_cuts}/{ncuts}); keep hard cuts silent")
    for g in plan.get("graphics", []) or []:
        if "emoji" in str(g.get("type", "")) + str(g.get("content", "")) and g.get("allow_emoji") is not True:
            warns.append(f"tell: emoji sticker {g.get('id')}; draw the sticker from the subject's real objects")
    hook_txt = " ".join(str(g.get("text", "")) for g in plan.get("graphics", []) or [] if g.get("type") in ("hook_text", "kinetic_title") and g.get("start", 99) <= 1)
    if any(p in hook_txt.lower() for p in ("did you know", "wait for it", "you won't believe", "watch till the end")):
        warns.append("tell: stock hook phrase; open on the strongest real line instead")

    # ---- speaker layouts per beat (references/layouts.md) --------------------------------
    lays = sorted(plan.get("layouts", []) or [], key=lambda l: float(l.get("start", 0)))
    talking = str(eff["profile_id"]).startswith("talking_head")
    if not lays and talking and dur:
        warns.append("no layouts timeline: choose a speaker layout per beat (references/layouts.md)")
    hidden, kinds_seq, prev_end = 0.0, [], 0.0
    for l in lays:
        k, s0, e0 = l.get("kind"), float(l.get("start", 0)), float(l.get("end", 0))
        ln = e0 - s0
        lid = l.get("id", k)
        if k not in LAYOUT_LIMITS:
            errors.append(f"layout {lid}: unknown kind '{k}' (one of {', '.join(LAYOUT_LIMITS)})")
            continue
        lo, hi = LAYOUT_LIMITS[k]
        if ln < lo - 1e-6 or ln > hi + 1e-6:
            warns.append(f"layout {lid} {k} lasts {ln:.1f}s (fits {lo}-{hi}s)")
        if k in ("cutaway", "text_full"):
            hidden += ln
        if k == "pip_speaker":
            bx = l.get("box")
            if not bx:
                warns.append(f"layout {lid} pip_speaker has no box for the speaker bubble")
            else:
                x, y, w, h = bx
                if not 260 <= min(w, h) <= 420:
                    warns.append(f"layout {lid} pip bubble {w}x{h}px (keep 260-420 px)")
                if (x < sz.get("left", 0) or y < sz.get("top", 0) or x + w > W - sz.get("right", 0)
                        or y + h > H - sz.get("bottom", 0) or (rail and x + w > rail["x_min"] and y + h > rail["y_min"])):
                    errors.append(f"layout {lid} pip bubble {bx} outside safe zone or under the right rail")
        if kinds_seq and s0 - prev_end > 0.3:
            kinds_seq.append("full_speaker")  # an unplanned gap is the speaker full frame
        if not kinds_seq or kinds_seq[-1] != k:
            kinds_seq.append(k)
        prev_end = e0
    if talking and dur and hidden / dur > 0.3:
        warns.append(f"speaker hidden {hidden / dur:.0%} of the runtime (cutaway/text_full); keep the speaker visible >= 70%")
    alt = [k for k in kinds_seq if k != "full_speaker"]  # returns to the speaker don't break a repeat
    for i in range(len(alt) - 2):
        if alt[i] == alt[i + 1] == alt[i + 2]:
            warns.append(f"layout '{alt[i]}' used 3x in a row; vary it (overlay, split, pip, cutaway...)")
            break
    distinct = len(set(l.get("kind") for l in lays))
    density = taste.clamp((tst.get("dials") or {}).get("density", 5))
    if dur >= 30 and lays and density >= 4 and distinct < min(3, len(lays)):
        warns.append(f"only {distinct} layout kind(s) in {dur:.0f}s; use >= 3 for density >= 4")

    # ---- animation variety (references/animation.md) ------------------------------------
    animated = [g for g in plan.get("graphics", []) or [] if not g.get("motion")]
    if animated:
        warns.append(f"{len(animated)} graphic(s) without a `motion:` move: " + ", ".join(str(g.get("id")) for g in animated[:5]))
    for w in motion_pick.audit(motion_pick.load_lib(), plan, taste.clamp((tst.get("dials") or {}).get("motion", 5)))[0]:
        warns.append("motion: " + w)

    # ---- brand: exists, logo placed, voice respected ------------------------------------
    if plan.get("brand") and eff.get("brand_missing"):
        errors.append(f"brand '{plan['brand']}' not in director.yaml: run brand.py import <kit> first")
    bspec = eff.get("brand") or {}
    blob = yaml.safe_dump({k: plan.get(k) for k in ("graphics", "captions", "ending", "cover")}, allow_unicode=True).lower()
    lg = bspec.get("logo") if isinstance(bspec.get("logo"), dict) else {}
    if lg.get("file") and lg.get("placement", "end_card") != "none" and "logo" not in blob:
        warns.append(f"brand logo {lg['file']} ({lg.get('placement', 'end_card')}) is not placed in the plan")
    for w in (bspec.get("voice") or {}).get("avoid") or []:
        if str(w).lower() in blob:
            errors.append(f"brand voice: '{w}' is on the brand's avoid list")

    # ---- cost / ending -------------------------------------------------------------------
    for p in (plan.get("cost") or {}).get("paid", []) or []:
        if not p.get("approved"):
            errors.append(f"paid generation not approved yet: {p.get('provider')} {p.get('model')} ~${p.get('est_usd')}")
    end = plan.get("ending") or {}
    src_dur = plan.get("source_duration")
    if end.get("preserve_source_ending") and src_dur and plan.get("cuts"):
        last = plan["cuts"][-1].get("src_end", 0)
        if last < float(src_dur) - 0.1:
            errors.append(f"ending not preserved: last cut ends at src {last}s, source is {src_dur}s")
    if not plan.get("cover"):
        warns.append("no cover frame chosen")
    if dur and plat.get("max_recommended_s") and dur > plat["max_recommended_s"]:
        warns.append(f"duration {dur}s exceeds recommendation limit {plat['max_recommended_s']}s")

    res = {"errors": errors, "warnings": warns, "events": len(ev)}
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(f"plan_lint: {len(errors)} error(s), {len(warns)} warning(s)  [{eff['platform_id']}/{eff['profile_id']}/{eff['brand_id']}]")
        for e in errors: print("  ERROR  " + e)
        for w in warns: print("  warn   " + w)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
