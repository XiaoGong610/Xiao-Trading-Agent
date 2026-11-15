#!/usr/bin/env python3
"""
Execution diff: what actually happened between two account snapshots, scored against the plan.

Compares last week's snapshot (portfolio/snapshots/<date>/, saved by
`account-check.py --snapshot`) with the current account files, then matches every
position change to the plan's orders and DCA schedule:

  ✅ done        the order's effect is visible (shares sold/bought, option gone)
  ⚠️ partial     some of the size moved
  ⏳ open        GTC / "keep" orders not filled yet (can't tell placed vs not from positions)
  ❌ not done    an unconditional order with no visible effect, or a cancel/pause
                 that didn't happen (the position kept growing)
  ❔ manual      orders positions can't prove (roll terms, alerts, recurring-buy setup)
  OFF-PLAN       a position change no order or DCA line explains

Conditional orders are listed only when their ticker actually moved (then shown as
"conditional fired?"). Execution rate = done / (done + partial + not done).

Usage:
    .venv/bin/python3 scripts/execution-diff.py                         # latest snapshot vs current, plan in between
    .venv/bin/python3 scripts/execution-diff.py --prior portfolio/snapshots/2026-11-13
    .venv/bin/python3 scripts/execution-diff.py --plan PLAN-2026-11-14.md --md   # markdown for the review
    .venv/bin/python3 scripts/execution-diff.py --json

Exit codes: 0 ok, 2 missing inputs. Holds no personal data: everything is read from
gitignored files at run time.
"""

import argparse
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "portfolio" / "snapshots"
ACCOUNTS_DIR = ROOT / "portfolio" / "accounts"
PLANS_DIR = ROOT / "portfolio" / "plans"


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load("account_check", "account-check.py")
cc = _load("cash_check", "cash-check.py")

OPT_RE = re.compile(r"\b([A-Z]{1,5}) \$(\d+(?:\.\d+)?)([CP]) ([A-Z][a-z]{2}) (\d{1,2})\b")
SHARE_VERB_RE = re.compile(r"\b(sell|buy)\s+(?:back\s+)?([\d,]+(?:\.\d+)?)\s*(?:×\s*)?([A-Z]{1,5})\b", re.I)
EPS = 1e-3


def acct_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def pos_key(label: str) -> str:
    """'AMZN $290C Dec 11 (short)' and "AMZN $290C Dec 11 '26" -> 'AMZN 290C Dec 11'."""
    m = OPT_RE.search(label)
    if m:
        t, k, cp, mon, day = m.groups()
        return f"{t} {float(k):g}{cp} {mon} {int(day)}"
    return re.sub(r"\s*\((W|w)\)$", "", re.sub(r"\*\*|~~", "", label)).strip().upper()


def load_positions(directory: Path) -> dict:
    """{account_key: {"name": display, "pos": {pos_key: qty}}} from account files in a directory."""
    out = {}
    for f in sorted(directory.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        fm = ac.parse_frontmatter(text)
        name = fm.get("account_name", f.stem)
        pos = {}
        header = None
        for line in ac.positions_section(text).splitlines():
            if not line.startswith("|"):
                header = None
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if header is None:
                header = [c.lower() for c in cells]
                continue
            ni = next((i for i, h in enumerate(header) if h in ac.NAME_COLS), None)
            qi = next((i for i, h in enumerate(header) if h in ("qty", "shares", "quantity")), None)
            if ni is None or qi is None or max(ni, qi) >= len(cells):
                continue
            qty = ac._num(cells[qi])
            if qty is not None:
                pos[pos_key(cells[ni])] = pos.get(pos_key(cells[ni]), 0) + qty
        out[acct_key(name)] = {"name": name, "pos": pos}
    return out


def diff_positions(prior: dict, current: dict) -> list:
    """[{account, key, before, after, delta, kind}] for every changed position."""
    changes = []
    for ak in sorted(set(prior) | set(current)):
        a = prior.get(ak, {}).get("pos", {})
        b = current.get(ak, {}).get("pos", {})
        name = (current.get(ak) or prior.get(ak))["name"]
        for k in sorted(set(a) | set(b)):
            before, after = a.get(k, 0.0), b.get(k, 0.0)
            if abs(after - before) > EPS:
                kind = "new" if k not in a else "closed" if k not in b else "changed"
                changes.append({"account": name, "akey": ak, "key": k, "before": before,
                                "after": after, "delta": after - before, "kind": kind, "used": False})
    return changes


def find_change(changes, key, akey=None):
    """Best change for a position key: same account first, else an unclaimed change in another
    account (multi-account plan rows resolve to one account; never reuse another order's evidence)."""
    same = [c for c in changes if c["key"] == key and (akey is None or c["akey"] == akey)]
    if same:
        return same[0]
    return next((c for c in changes if c["key"] == key and not c["used"]), None)


def held_qty(prior, key, akey):
    """Prior quantity of a position: same account first, else the first account holding it."""
    if akey in prior and key in prior[akey]["pos"]:
        return prior[akey]["pos"][key]
    return next((a["pos"][key] for a in prior.values() if key in a["pos"]), 0.0)


def score_order(row: dict, changes: list, prior: dict) -> dict:
    text = f"{row['order_text']} {row['detail']}"
    clean = re.sub(r"\*\*|`|~~", "", text)
    low = clean.lower()
    akey = acct_key(row["account"])
    gtc = bool(re.search(r"\bgtc\b|\bkeep\b", low))
    res = {"account": row["account"], "order": re.sub(r"\*\*|`", "", row["order_text"]).strip()[:90],
           "conditional": row["conditional"], "status": "❔ manual", "evidence": ""}

    # 1) Option exits / buy-backs: the option row should be gone (or smaller)
    opt = OPT_RE.search(clean)
    opt_key = pos_key(opt.group(0)) if opt else None
    before = held_qty(prior, opt_key, akey) if opt else 0.0
    is_exit = bool(opt) and (
        re.search(r"close|buy[- ]?backs?|roll", low)
        or (before > 0 and re.search(r"\bsell\b", low))       # selling a long option
        or (before < 0 and re.search(r"\bbuy\b", low)))       # buying back a short one
    if is_exit:
        key = opt_key
        ch = find_change(changes, key, akey)
        if ch and ch["kind"] == "closed":
            ch["used"] = True
            res["status"], res["evidence"] = "✅ done", f"{key} closed ({ch['account']})"
            if "roll" in low:
                res["status"] = "✅ done (verify new strike)"
        elif ch:
            ch["used"] = True
            res["status"], res["evidence"] = "⚠️ partial", f"{key} {ch['before']:g} → {ch['after']:g}"
        else:
            trigger_based = "roll" in low      # rolls fire on a price trigger
            res["status"] = "⏳ open" if gtc or row["conditional"] or trigger_based else "❌ not done"
            res["evidence"] = f"{key} unchanged"
        return res

    # 2) Recurring-buy changes: cancel/pause should stop growth; start should show growth
    rec = re.search(r"(cancel|pause|start)\b.*?\b([A-Z]{2,5})\b.*?(recurring|daily|/day)", clean, re.I) or \
        re.search(r"(cancel|pause|start)\b.*?(recurring|daily).*?\b([A-Z]{2,5})\b", clean, re.I)
    if rec:
        verb = rec.group(1).lower()
        tick = next((g for g in rec.groups()[1:] if g and g.isupper()), None)
        ch = find_change(changes, tick, akey) if tick else None
        grew = ch is not None and ch["delta"] > 0
        if ch:
            ch["used"] = True
        if verb in ("cancel", "pause"):
            res["status"] = "❌ still buying" if grew else "✅ done (no growth)"
        else:
            res["status"] = "✅ running" if grew else "❌ not started"
        res["evidence"] = f"{tick} {ch['before']:g} → {ch['after']:g}" if ch else f"{tick} unchanged"
        return res

    # 3) Share orders: "sell 1,000 XYZ", "GTC sell 200 ABC", "buy 10 DEF"
    m = SHARE_VERB_RE.search(clean)
    if m and not opt:
        verb, n, tick = m.group(1).lower(), float(m.group(2).replace(",", "")), m.group(3).upper()
        want = -n if verb == "sell" else n
        ch = find_change(changes, tick, akey)
        moved = ch["delta"] if ch else 0.0
        if ch and moved * want > 0:
            ch["used"] = True
            frac = abs(moved) / abs(want)
            res["status"] = "✅ done" if frac >= 0.9 else "⚠️ partial"
            res["evidence"] = f"{tick} {ch['before']:g} → {ch['after']:g} ({ch['account']})"
        else:
            res["status"] = "⏳ open" if gtc or row["conditional"] else "❌ not done"
            res["evidence"] = f"{tick} no {verb} seen"
        return res

    # 4) Opening options (sell CC/CSP, buy LEAP): a new option row should appear
    if opt:
        key = pos_key(opt.group(0))
        ch = find_change(changes, key, akey)
        if ch and ch["kind"] == "new":
            ch["used"] = True
            res["status"], res["evidence"] = "✅ done", f"{key} opened"
        else:
            res["status"] = "⏳ open" if gtc or row["conditional"] else "❌ not done"
            res["evidence"] = f"{key} not opened"
    return res


def dca_tickers(plan_text: str) -> set:
    """(account_key, ticker) pairs with a non-zero daily buy in the plan's DCA schedule."""
    out = set()
    for d in cc.parse_dca_schedule(plan_text):
        if d.get("daily", 0) > 0:
            out.add((acct_key(d["account"]), d["ticker"].upper()))
    return out


def pick_inputs(prior_arg, plan_arg):
    snaps = sorted(p for p in SNAP_DIR.glob("*") if p.is_dir()) if SNAP_DIR.exists() else []
    cur_dates = {ac.parse_frontmatter(f.read_text(encoding="utf-8")).get("last_updated")
                 for f in ACCOUNTS_DIR.glob("*.md")}
    cur_date = max((d for d in cur_dates if d), default=date.today().isoformat())
    if prior_arg:
        prior = Path(prior_arg)
    else:
        older = [p for p in snaps if p.name < cur_date]
        prior = older[-1] if older else None
    if plan_arg:
        plan = PLANS_DIR / plan_arg if (PLANS_DIR / plan_arg).exists() else Path(plan_arg)
    elif prior:
        cands = [p for p in sorted(PLANS_DIR.glob("PLAN-*.md")) if prior.name <= p.stem[5:] <= cur_date]
        plan = cands[-1] if cands else None
    else:
        plan = None
    return prior, plan, cur_date


def run(prior_dir: Path, current_dir: Path, plan_path: Path) -> dict:
    prior, current = load_positions(prior_dir), load_positions(current_dir)
    changes = diff_positions(prior, current)
    plan_text = plan_path.read_text(encoding="utf-8")

    scored, seen = [], set()
    for row in cc.iter_order_rows(plan_text):
        r = score_order(row, changes, prior)
        sig = (r["status"].split()[0], r["evidence"], r["conditional"])
        if r["evidence"] and sig in seen:          # the same order in At a Glance and One-Time Orders
            continue
        seen.add(sig)
        if r["conditional"] and not r["status"].startswith(("✅", "⚠️")):
            continue                                # conditionals only matter when they fired
        if r["conditional"]:
            r["status"] += " (conditional fired?)"
        scored.append(r)

    dca = dca_tickers(plan_text)
    for c in changes:
        if not c["used"] and c["delta"] > 0 and (c["akey"], c["key"]) in dca:
            c["used"] = "dca"
    off_plan = [c for c in changes if not c["used"]]
    dca_moves = [c for c in changes if c["used"] == "dca"]

    counted = [s for s in scored if not s["conditional"] and s["status"].startswith(("✅", "⚠️", "❌"))]
    done = sum(1 for s in counted if s["status"].startswith("✅"))
    return {"prior": prior_dir.name, "plan": plan_path.name, "orders": scored,
            "dca": [{k: c[k] for k in ("account", "key", "before", "after")} for c in dca_moves],
            "off_plan": [{k: c[k] for k in ("account", "key", "before", "after", "kind")} for c in off_plan],
            "execution_rate": {"done": done, "counted": len(counted),
                               "pct": round(100 * done / len(counted)) if counted else None}}


def render(res: dict, md: bool) -> str:
    er = res["execution_rate"]
    rate = f"{er['done']}/{er['counted']} = {er['pct']}%" if er["counted"] else "n/a"
    lines = [f"## Execution Diff — snapshot {res['prior']} → current, scored against {res['plan']}", "",
             f"**Execution rate:** {rate} (done ÷ unconditional orders with a verdict)", "",
             "| Status | Account | Order | Evidence |", "|---|---|---|---|"]
    for o in res["orders"]:
        lines.append(f"| {o['status']} | {o['account']} | {o['order']} | {o['evidence']} |")
    lines += ["", f"**Off-plan changes ({len(res['off_plan'])}):** position moves no order or DCA line explains", ""]
    if res["off_plan"]:
        lines += ["| Account | Position | Before → After | Kind |", "|---|---|---|---|"]
        for c in res["off_plan"]:
            lines.append(f"| {c['account']} | {c['key']} | {c['before']:g} → {c['after']:g} | {c['kind']} |")
    else:
        lines.append("None.")
    if res["dca"]:
        lines += ["", "**Explained by the DCA schedule:** " +
                  " · ".join(f"{c['key']} ({c['account']}) {c['before']:g} → {c['after']:g}" for c in res["dca"])]
    out = "\n".join(lines)
    return out if md else out.replace("**", "")


def main():
    ap = argparse.ArgumentParser(description="Score last week's plan against actual position changes")
    ap.add_argument("--prior", help="prior snapshot dir (default: latest portfolio/snapshots/<date> before current)")
    ap.add_argument("--current", default=str(ACCOUNTS_DIR), help="current account files dir")
    ap.add_argument("--plan", help="plan to score (default: latest PLAN between the two dates)")
    ap.add_argument("--md", action="store_true", help="markdown output (for the review)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    prior, plan, cur_date = pick_inputs(args.prior, args.plan)
    if not prior or not prior.exists():
        print(f"No prior snapshot older than {cur_date} in {SNAP_DIR}. "
              f"Run `account-check.py --snapshot` each week to build history.", file=sys.stderr)
        sys.exit(2)
    if not plan or not plan.exists():
        print(f"No plan found between {prior.name} and {cur_date}.", file=sys.stderr)
        sys.exit(2)
    res = run(prior, Path(args.current), plan)
    print(json.dumps(res, indent=2, default=str) if args.json else render(res, args.md))


if __name__ == "__main__":
    main()
