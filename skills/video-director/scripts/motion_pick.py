#!/usr/bin/env python3
"""Pick the animation for each beat from the motion library, with variety built in.

  motion_pick.py pick  --beat number [--motion 6] [--direction data-desk] [--plan edit-plan.yaml] [--n 3]
  motion_pick.py audit edit-plan.yaml [--motion 6]
  motion_pick.py list  [--family data]

pick: ranks moves whose `beats` match, closest to the motion dial, favoured by the direction's
families, and penalised when the plan already uses that move or family a lot. Prints the top N
with their recipes (hf: /hyperframes-animation rule or blueprint, mr: motion-recipes.md section,
registry: search terms) so you compose real, tested patterns instead of improvising.
audit: reads every plan item's `motion:` id and reports variety, repeats and dial fit.
"""
import argparse, collections, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references")
DIRECTION_FAMILIES = {  # which families each taste direction leans on (references/directions.yaml)
    "documentary-calm": ["camera", "broll", "text"], "kinetic-explainer": ["text", "diagram", "transition"],
    "split-teacher": ["data", "diagram", "emphasis"], "creator-punch": ["emphasis", "camera", "text"],
    "editorial-magazine": ["text", "broll", "transition"], "data-desk": ["data", "camera", "diagram"],
    "field-notes": ["emphasis", "overlay", "broll"], "product-stage": ["ui", "camera", "data"],
    "cinematic-story": ["camera", "broll", "transition"], "retro-broadcast": ["text", "overlay", "transition"],
    "minimal-type": ["text", "transition"], "whiteboard-builder": ["diagram", "camera", "emphasis"],
}
PLAN_KEYS = ("graphics", "broll", "transitions", "camera", "layouts")


def load_lib():
    with open(os.path.join(REF, "motion-library.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["moves"]


def plan_moves(plan):
    used = []
    for k in PLAN_KEYS:
        for it in (plan or {}).get(k, []) or []:
            if isinstance(it, dict) and it.get("motion"):
                used.append((str(it["motion"]).split("#")[0], float(it.get("start", it.get("at", it.get("t", 0))) or 0), it.get("id")))
    return used


def rank(lib, beat, motion, direction, used):
    by_id = {m["id"]: m for m in lib}
    cnt = collections.Counter(u for u, _, _ in used)
    fam = collections.Counter(by_id[u]["family"] for u, _, _ in used if u in by_id)
    last = [u for u, _, _ in sorted(used, key=lambda x: x[1])][-2:]
    pref = DIRECTION_FAMILIES.get(direction or "", [])
    out = []
    for m in lib:
        if beat not in m["beats"]:
            continue
        s = 10.0 - abs(m["level"] - motion) * 1.2
        if m["family"] in pref:
            s += 2.5 - pref.index(m["family"]) * 0.7
        s -= 2.5 * cnt[m["id"]] + 0.6 * fam[m["family"]]
        if m["id"] in last:
            s -= 4  # never the same move on consecutive beats
        out.append((round(s, 2), m))
    return sorted(out, key=lambda x: -x[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pick", "audit", "list"])
    ap.add_argument("plan_path", nargs="?")
    ap.add_argument("--beat")
    ap.add_argument("--motion", type=int)
    ap.add_argument("--direction")
    ap.add_argument("--plan")
    ap.add_argument("--family")
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    lib = load_lib()

    if a.cmd == "list":
        for m in lib:
            if not a.family or m["family"] == a.family:
                print(f"{m['id']:22} {m['family']:10} L{m['level']:<2} {','.join(m['beats'])}")
        return

    path = a.plan or a.plan_path
    plan = yaml.safe_load(open(path, encoding="utf-8")) if path and os.path.exists(path) else {}
    dials = ((plan.get("taste") or {}).get("dials") or {})
    motion = a.motion or int(dials.get("motion", 5))
    direction = a.direction or (plan.get("taste") or {}).get("direction")
    used = plan_moves(plan)

    if a.cmd == "pick":
        if not a.beat:
            sys.exit("--beat required (see motion-library.yaml header for beat names)")
        ranked = rank(lib, a.beat, motion, direction, used)
        if not ranked:
            sys.exit(f"no move for beat '{a.beat}'")
        print(f"# beat={a.beat} motion={motion} direction={direction} (already used: {len(used)} moves)")
        for s, m in ranked[:a.n]:
            print(f"- {m['id']}  [{m['family']}, L{m['level']}, {m['dur'][0]}-{m['dur'][1]}s, {m['ease']}, sfx {m['sfx']}]  score {s}")
            print(f"    {m['what']}")
            print(f"    recipes: {', '.join(m['recipes'])}   then search /hyperframes-registry for \"{m['id'].replace('-', ' ')}\"")
        return

    issues, distinct, fams = audit(lib, plan, motion, used)
    print(f"motion audit: {len(used)} animated items, {distinct} distinct moves, families: {', '.join(sorted(fams)) or '-'}")
    for i in issues:
        print("  warn   " + i)
    if not issues:
        print("  ok")


def audit(lib, plan, motion, used=None):
    used = plan_moves(plan) if used is None else used
    by_id = {m["id"]: m for m in lib}
    dur = float(plan.get("duration") or 60)
    issues = []
    unknown = sorted({u for u, _, _ in used if u not in by_id and not u.startswith(("mr:", "hf:", "bp:", "custom:"))})
    if unknown:
        issues.append(f"unknown motion ids (use a library id or prefix custom:): {', '.join(unknown)}")
    cnt = collections.Counter(u for u, _, _ in used)
    for u, n in cnt.items():
        if u in by_id and by_id[u]["family"] not in ("camera", "transition") and n > max(2, dur / 20):
            issues.append(f"'{u}' used {n}x in {dur:.0f}s - vary it")
    seq = [u for u, _, _ in sorted(used, key=lambda x: x[1]) if u in by_id and by_id[u]["family"] not in ("camera", "transition")]
    for i in range(len(seq) - 1):
        if seq[i] == seq[i + 1]:
            issues.append(f"'{seq[i]}' on two consecutive beats")
            break
    fams = {by_id[u]["family"] for u in cnt if u in by_id}
    distinct = len([u for u in cnt if u in by_id])
    if dur >= 30 and distinct < min(6, max(3, int(dur / 10))):
        issues.append(f"only {distinct} distinct moves in {dur:.0f}s (aim for ~1 new move per 10 s)")
    far = [u for u in cnt if u in by_id and abs(by_id[u]["level"] - motion) >= 4]
    if far:
        issues.append(f"moves far from motion dial {motion}: {', '.join(far)}")
    if used and not any(by_id.get(u, {}).get("family") == "ending" for u in cnt):
        issues.append("no ending move (logo-lockup / cta-press / loop-return)")
    return issues, distinct, fams


if __name__ == "__main__":
    main()
