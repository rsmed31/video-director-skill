#!/usr/bin/env python3
"""Read/write the video-director learning memory (director.yaml).

  resolve  [--platform P] [--profile Q] [--brand B] [--workspace DIR] [--json]
  feedback add --job J --version V --quote "..." [--items a,b] [--note "..."]
  feedback add  --quote "..." --job J --version vN --brand B --applies generic|client|video   (ask the user when unclear)
  rule add      --for generic|client --brand B --text "..."   (same as --scope global | brand:<B>)
  rescope       --to brand:B (--ids R1,R2 | --from-source user [--from-scope global]) [--except-ids ...]
  rule add      --scope S --text "..." [--source user|research|agent|metric] [--evidence fb-0001] [--confidence 0.6] [--id R-x]
  rule confirm  --id R --evidence fb-0001
  rule weaken   --id R --evidence fb-0001
  ban           --scope S --text "..." --evidence fb-0001 [--id R-x]
  param set     --path profiles.talking_head_edu.max_static_s --value 4 --evidence fb-0001
  metric add    --job J --version V [--skip_rate 0.32] [--avg_watch_s 21] [--retention_3s 0.7] [--saves N] [--sends N] [--views N]
  show     [--section rules|feedback_log|brands|profiles|platforms]
  validate

Scopes: global | platform:<id> | profile:<id> | brand:<id>. Memory file: <skill>/director.yaml
(override with --memory). Workspace overrides: <workspace>/video-director.yaml -> overrides:
"""
import argparse, copy, datetime, json, os, re, sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML missing: pip install pyyaml")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MEM = os.path.join(SKILL_DIR, "director.yaml")
TODAY = str(datetime.date.today())


def load(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save(p, data):
    data["updated"] = TODAY
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# video-director memory - edit via scripts/director_memory.py; reasoning lives in `text`/`quote`/`note` fields.\n")
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=120)
    os.replace(tmp, p)


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def next_id(items, prefix, width=4):
    n = 0
    for it in items:
        m = re.match(rf"{prefix}-(\d+)$", str(it.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"{prefix}-{n + 1:0{width}d}"


def find_rule(mem, rid):
    for r in mem.get("rules", []):
        if r["id"] == rid:
            return r
    sys.exit(f"no rule {rid}")


def scope_applies(scope, platform, profile, brand):
    if scope == "global":
        return True
    kind, _, val = scope.partition(":")
    return {"platform": platform, "profile": profile, "brand": brand}.get(kind) == val


def find_brand(mem, key):
    """Brand id for a brand id, display name, client name or alias (brands are per client)."""
    if not key:
        return key
    brands = mem.get("brands") or {}
    if key in brands:
        return key
    k = str(key).strip().lower()
    for bid, b in brands.items():
        names = [b.get("name"), b.get("client")] + list(b.get("aliases") or [])
        if any(k == str(n).strip().lower() for n in names if n):
            return bid
    return key


def resolve(mem, platform, profile, brand, workspace):
    ws = {}
    if workspace:
        wp = os.path.join(workspace, "video-director.yaml")
        if os.path.exists(wp):
            ws = load(wp)
    wsd = ws.get("workspace", {}) or {}
    brand = find_brand(mem, brand or wsd.get("brand"))
    b = (mem.get("brands") or {}).get(brand, {}) if brand else {}
    platform = platform or b.get("platform") or wsd.get("platform") or "generic"
    profile = profile or b.get("profile") or "generic"
    eff = {
        "platform_id": platform, "profile_id": profile, "brand_id": brand,
        "preferences": mem.get("preferences", {}),
        "platform": (mem.get("platforms") or {}).get(platform, {}),
        "profile": deep_merge((mem.get("profiles") or {}).get("generic", {}), (mem.get("profiles") or {}).get(profile, {})),
        "caps": mem.get("caps", {}), "sfx_map": mem.get("sfx_map", {}), "brand": b,
    }
    if b.get("profile_overrides"):  # per-client numbers (e.g. music level) learned from that client's feedback
        eff["profile"] = deep_merge(eff["profile"], b["profile_overrides"])
    eff = deep_merge(eff, ws.get("overrides") or {})
    rules = [r for r in mem.get("rules", []) if r.get("status") != "retired"
             and scope_applies(r.get("scope", "global"), platform, profile, brand)]
    eff["bans"] = [r for r in rules if r.get("status") == "ban"]
    eff["rules"] = sorted([r for r in rules if r.get("status") != "ban"], key=lambda r: -float(r.get("confidence", 0)))
    fbl = mem.get("feedback_log", [])
    eff["recent_feedback"] = [f for f in fbl if not f.get("brand") or f.get("brand") == brand][-5:]
    eff["tooling"] = mem.get("tooling", {})
    eff["brand_missing"] = bool(brand) and brand not in (mem.get("brands") or {})
    return eff


def print_resolved(e):
    print(f"# effective director settings  platform={e['platform_id']}  profile={e['profile_id']}  brand={e['brand_id']}")
    if e.get("brand_missing"):
        print(f"# WARNING brand '{e['brand_id']}' is not in director.yaml: import it first (scripts/brand.py import <kit> | template --id {e['brand_id']})")
    for key in ("preferences", "platform", "profile", "caps", "sfx_map", "brand", "tooling"):
        if e.get(key):
            print(f"\n## {key}")
            print(yaml.safe_dump(e[key], allow_unicode=True, sort_keys=False, width=120).rstrip())
    print("\n## bans (never violate)")
    for r in e["bans"]:
        print(f"- [{r['id']}] {r['text']}")
    print("\n## rules (apply; candidates should be mentioned at checkpoint A)")
    for r in e["rules"]:
        print(f"- [{r['id']}] ({r.get('status')}, {r.get('confidence')}, {r.get('scope')}) {r['text']}")
    print("\n## recent feedback")
    for f in e["recent_feedback"]:
        print(f"- {f['id']} {f.get('date')} {f.get('job')} {f.get('version')}: \"{f.get('quote')}\" -> {f.get('rules')}")


def validate(mem):
    errs = []
    ids = [r.get("id") for r in mem.get("rules", [])]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errs.append(f"duplicate rule ids: {sorted(dup)}")
    fids = {f.get("id") for f in mem.get("feedback_log", [])}
    for r in mem.get("rules", []):
        for k in ("id", "scope", "status", "text"):
            if k not in r:
                errs.append(f"rule {r.get('id')} missing {k}")
        if r.get("status") not in ("candidate", "default", "ban", "retired"):
            errs.append(f"rule {r.get('id')} bad status {r.get('status')}")
        sc = r.get("scope", "")
        if sc != "global" and not re.match(r"^(platform|profile|brand):[\w-]+$", sc):
            errs.append(f"rule {r.get('id')} bad scope {sc}")
        if sc.startswith("brand:") and sc[6:] not in (mem.get("brands") or {}):
            errs.append(f"rule {r.get('id')} scoped to unknown brand {sc[6:]}")
        for ev in r.get("evidence", []) or []:
            if isinstance(ev, str) and re.match(r"^fb-\d+$", ev) and ev not in fids:
                errs.append(f"rule {r.get('id')} cites missing {ev}")
    for f in mem.get("feedback_log", []):
        for rid in f.get("rules", []) or []:
            if rid not in ids:
                errs.append(f"feedback {f.get('id')} cites missing rule {rid}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--memory", default=DEFAULT_MEM)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    for k in ("platform", "profile", "brand", "workspace"):
        r.add_argument(f"--{k}")
    r.add_argument("--json", action="store_true")
    fb = sub.add_parser("feedback"); fb.add_argument("action", choices=["add"])
    for k in ("job", "version", "quote", "items", "note", "brand"):
        fb.add_argument(f"--{k}")
    fb.add_argument("--applies", choices=["generic", "client", "video"],
                    help="generic = every client; client = only this brand's client; video = this video only")
    ru = sub.add_parser("rule"); ru.add_argument("action", choices=["add", "confirm", "weaken"])
    for k in ("id", "scope", "text", "source", "evidence", "brand"):
        ru.add_argument(f"--{k}")
    ru.add_argument("--for", dest="for_", choices=["generic", "client"], help="shortcut: global or brand:<--brand>")
    ru.add_argument("--confidence", type=float)
    bn = sub.add_parser("ban")
    for k in ("id", "scope", "text", "evidence"):
        bn.add_argument(f"--{k}")
    pa = sub.add_parser("param"); pa.add_argument("action", choices=["set"])
    for k in ("path", "value", "evidence"):
        pa.add_argument(f"--{k}", required=k != "evidence")
    me = sub.add_parser("metric"); me.add_argument("action", choices=["add"])
    for k in ("job", "version", "skip_rate", "avg_watch_s", "retention_3s", "saves", "sends", "views", "likes", "comments", "note"):
        me.add_argument(f"--{k}")
    rs = sub.add_parser("rescope", help="move rules to another scope (e.g. a client's feedback that was saved as global)")
    rs.add_argument("--to", required=True)
    rs.add_argument("--ids", help="comma list of rule ids")
    rs.add_argument("--from-source", help="every rule with this source (user|agent|research)")
    rs.add_argument("--from-scope", default="global")
    rs.add_argument("--except-ids", default="")
    sh = sub.add_parser("show"); sh.add_argument("--section")
    sub.add_parser("validate")
    a = ap.parse_args()

    mem = load(a.memory)
    if a.cmd == "resolve":
        e = resolve(mem, a.platform, a.profile, a.brand, a.workspace)
        print(json.dumps(e, ensure_ascii=False, indent=1)) if a.json else print_resolved(e)
        return
    if a.cmd == "show":
        print(yaml.safe_dump(mem.get(a.section) if a.section else mem, allow_unicode=True, sort_keys=False, width=120))
        return
    if a.cmd == "validate":
        errs = validate(mem)
        print("\n".join(errs) if errs else "director.yaml OK")
        sys.exit(1 if errs else 0)

    if a.cmd == "feedback":
        if not a.quote:
            sys.exit("--quote required")
        log = mem.setdefault("feedback_log", [])
        fid = next_id(log, "fb")
        e = {"id": fid, "date": TODAY, "job": a.job, "version": a.version, "quote": a.quote, "rules": []}
        if a.brand:
            e["brand"] = find_brand(mem, a.brand)
        if a.applies:
            e["applies"] = a.applies
        else:
            e["applies"] = "ask"
            print(f"ASK the user: is this note for every client (generic) or only for {e.get('brand') or 'this client'}? "
                  f"then: rule add --for generic|client --brand <b> ... (default client)", file=sys.stderr)
        if a.items:
            e["items"] = [i.strip() for i in a.items.split(",")]
        if a.note:
            e["note"] = a.note
        log.append(e)
        print(fid)
    elif a.cmd in ("rule", "ban"):
        rules = mem.setdefault("rules", [])
        action = "ban" if a.cmd == "ban" else a.action
        if action in ("add", "ban") and getattr(a, "for_", None):
            if a.for_ == "client":
                if not a.brand:
                    sys.exit("--for client needs --brand")
                a.scope = "brand:" + find_brand(mem, a.brand)
            else:
                a.scope = "global"
        if action in ("add", "ban"):
            if not (a.scope and a.text):
                sys.exit("--scope and --text required")
            rid = a.id or ("R-" + re.sub(r"[^a-z0-9]+", "-", a.text.lower())[:40].strip("-"))
            if any(x["id"] == rid for x in rules):
                rid = rid + "-" + next_id(rules, "n", 2).split("-")[1]
            conf = a.confidence if a.confidence is not None else (0.95 if action == "ban" else 0.6)
            rule = {"id": rid, "scope": a.scope, "status": "ban" if action == "ban" else "candidate",
                    "text": a.text, "source": getattr(a, "source", None) or "user", "confidence": conf,
                    "evidence": [a.evidence] if a.evidence else [], "created": TODAY}
            rules.append(rule)
            print(rid)
        else:
            rule = find_rule(mem, a.id)
            rule.setdefault("evidence", [])
            if a.evidence:
                rule["evidence"].append(a.evidence)
            c = float(rule.get("confidence", 0.5))
            if action == "confirm":
                rule["confidence"] = round(min(0.99, c + 0.1), 2)
                rule["confirmations"] = int(rule.get("confirmations", 0)) + 1
                if rule.get("status") == "candidate" and rule["confirmations"] >= 2:
                    rule["status"] = "default"
            else:
                rule["confidence"] = round(max(0.0, c - 0.2), 2)
                if rule["confidence"] < 0.3 and rule.get("status") != "ban":
                    rule["status"] = "retired"
            rule["updated"] = TODAY
            print(f"{rule['id']}: {rule['status']} {rule['confidence']}")
        if getattr(a, "evidence", None) and re.match(r"^fb-\d+$", a.evidence):
            for f in mem.get("feedback_log", []):
                if f["id"] == a.evidence:
                    rid = rule["id"]
                    if rid not in f.setdefault("rules", []):
                        f["rules"].append(rid)
    elif a.cmd == "rescope":
        ids = {x.strip() for x in (a.ids or "").split(",") if x.strip()}
        keep = {x.strip() for x in a.except_ids.split(",") if x.strip()}
        moved = []
        for r in mem.get("rules", []):
            hit = r["id"] in ids or (a.from_source and r.get("source") == a.from_source and r.get("scope") == a.from_scope)
            if hit and r["id"] not in keep:
                r["scope_was"], r["scope"], r["updated"] = r.get("scope"), a.to, TODAY
                moved.append(r["id"])
        print(f"rescoped {len(moved)} rule(s) -> {a.to}: " + ", ".join(moved))
    elif a.cmd == "param":
        keys = a.path.split(".")
        node = mem
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        try:
            val = yaml.safe_load(a.value)
        except yaml.YAMLError:
            val = a.value
        old = node.get(keys[-1])
        node[keys[-1]] = val
        mem.setdefault("param_history", []).append({"date": TODAY, "path": a.path, "old": old, "new": val, "evidence": a.evidence})
        print(f"{a.path}: {old} -> {val}")
    elif a.cmd == "metric":
        m = {k: getattr(a, k) for k in ("job", "version", "skip_rate", "avg_watch_s", "retention_3s", "saves", "sends", "views", "likes", "comments", "note") if getattr(a, k) is not None}
        m["date"] = TODAY
        mem.setdefault("metrics", []).append(m)
        print("metric added")

    errs = validate(mem)
    if errs:
        print("WARNING:\n" + "\n".join(errs), file=sys.stderr)
    save(a.memory, mem)


if __name__ == "__main__":
    main()
