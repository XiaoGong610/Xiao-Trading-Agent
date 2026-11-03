#!/usr/bin/env python3
"""
Plan lint: the mechanical post-plan gates for a weekly trading plan, as one script.

Run after every /trading-plan (and after any plan edit). Each check reads the plan
plus local data (portfolio/accounts/*.md, research/stocks/*.md), so it reflects the
current files rather than what the plan text claims.

Checks:
  cash            cash-check.py results: parse problems, over-committed accounts
  runway          DCA runway per account: < 3 weeks ERROR, 3-4 weeks WARN
  leap-budget     LEAP buys in an account <= 60% of its cash
  account-rules   option orders allowed by the account's constraints
                  ("No options", "Covered calls only", "Options allowed (CSPs, CCs, ...)")
  contracts       whole contracts only; CC contracts x 100 <= shares not already covered
  terminology     a covered call has a call strike, a CSP has a put strike
  dca-conviction  higher conviction never gets less $/day than lower conviction
                  (conviction from research/stocks/TICKER.md frontmatter)
  plan-coverage   new buys/LEAPs/CSPs over $2K have a /plan-stock entry within 14 days
  expiry          every option reference carries an expiry date
  names           full account names, not BL/TG/GB

Usage:
    .venv/bin/python3 scripts/plan-lint.py                          # latest plan
    .venv/bin/python3 scripts/plan-lint.py --plan PLAN-2026-09-06.md
    .venv/bin/python3 scripts/plan-lint.py --json

Add "lint-ok" to a plan line to accept a deliberate exception (e.g. a user override).
Exit codes: 0 no errors (warnings allowed), 1 at least one ERROR.
"""

import argparse
import importlib.util
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research" / "stocks"

_spec = importlib.util.spec_from_file_location("cash_check", Path(__file__).with_name("cash-check.py"))
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
# A month name next to the strike counts ("Jan $160C" is unambiguous when there's one Jan expiry).
EXPIRY_RE = re.compile(rf"\b{MONTH}(?![a-z])|\b\d{{1,2}}/\d{{1,2}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b")
OPTION_RE = re.compile(r"\$[\d,]+(?:\.\d+)?(?:\s*[-–/]\s*\$?[\d,]+(?:\.\d+)?)?\s*([CP])\b")
TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")
CONTRACTS_RE = re.compile(r"(?<![\d.$])(\d+(?:\.\d+)?)\s*[x×]\s*(?:[A-Z]{1,5}\s+)?(?:\$|[A-Z]{1,5}\b)"
                          r"|\bsell\s+(\d+(?:\.\d+)?)\s+(?:[A-Z]{1,5}\s+)?(?:(?:" + MONTH + r")[^$|]{0,15})?\$",
                          re.IGNORECASE)
NUM_RE = re.compile(r"[−-]?[\d,]+(?:\.\d+)?")


class Report:
    def __init__(self):
        self.items = []  # (level, check, message)
        self.ran = []

    def add(self, level, check, msg):
        self.items.append((level, check, msg))

    def checked(self, check):
        self.ran.append(check)

    @property
    def errors(self):
        return [i for i in self.items if i[0] == "ERROR"]


def to_num(text: str) -> float:
    m = NUM_RE.search(text.replace("−", "-"))
    return float(m.group(0).replace(",", "").replace("−", "-")) if m else 0.0


# ---------------------------------------------------------------- local data

def load_account_details() -> dict:
    """{CANONICAL: {cash, constraints[], shares{TICKER: n}, short_calls{TICKER: n}}}"""
    out = {}
    for f in sorted(cc.ACCOUNTS_DIR.glob("*.md")):
        text = f.read_text()
        fm = cc.parse_frontmatter(text)
        name = fm.get("account_name", f.stem.upper())
        fm_block = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        constraints = []
        if fm_block:
            m = re.search(r"^constraints:\s*\n((?:\s+-.*\n?)+)", fm_block.group(1), re.MULTILINE)
            if m:
                constraints = [c.strip()[1:].strip() for c in m.group(1).splitlines() if c.strip()]
        shares, short_calls = {}, {}
        for _, _, header, rows in cc.iter_tables(text):
            qty_i = cc.col(header, "qty", "shares")
            name_i = cc.col(header, "position", "ticker", "option")
            if qty_i < 0 or name_i < 0:
                continue
            for cells in rows:
                if len(cells) <= max(qty_i, name_i):
                    continue
                label = cells[name_i].replace("**", "").strip()
                qty = to_num(cells[qty_i])
                opt = OPTION_RE.search(label)
                tick = re.match(r"([A-Z]{1,5})\b", label)
                if not tick:
                    continue
                if opt:
                    if opt.group(1) == "C" and (qty < 0 or "short" in label.lower()):
                        short_calls[tick.group(1)] = short_calls.get(tick.group(1), 0) + abs(qty)
                elif re.fullmatch(r"[A-Z]{1,5}", label):
                    shares[label] = shares.get(label, 0) + qty
        out[name] = {"cash": fm.get("cash", 0), "constraints": constraints,
                     "shares": shares, "short_calls": short_calls}
    return out


def allowed_option_kinds(constraints: list):
    """Return a set of allowed opening option kinds, or None when nothing is stated."""
    text = " ".join(constraints).lower()
    if re.search(r"no options", text):
        return set()
    if "covered calls only" in text:
        return {"cc"}
    m = re.search(r"options allowed\s*\(([^)]*)\)", text)
    if m:
        kinds = set()
        listed = m.group(1)
        if re.search(r"\bcsps?\b|puts?", listed):
            kinds.add("csp")
        if re.search(r"\bccs?\b|covered", listed):
            kinds.add("cc")
        if re.search(r"leaps?|calls\b", listed):
            kinds.add("leap")
        return kinds
    return None


def research_info(ticker: str) -> dict:
    """{conviction, plan_dates[]} from research/stocks/TICKER.md, or {} if missing."""
    f = RESEARCH_DIR / f"{ticker}.md"
    if not f.exists():
        return {}
    text = f.read_text()
    conv = re.search(r"^conviction:\s*([\d.]+)", text, re.MULTILINE)
    dates = re.findall(rf"^#\s*{ticker}\s*[—–-]\s*Pre-Trade Plan\s*\|\s*(\d{{4}}-\d{{2}}-\d{{2}})", text, re.MULTILINE)
    return {"conviction": float(conv.group(1)) if conv else None,
            "plan_dates": [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]}


RUNG_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\s+\d[\d,]*\s*(?:sh\w*\s*)?(?:@|×)"
                            r"|\b\d[\d,]*\s+([A-Z]{2,5})\s*(?:@|×)")


def row_tickers(row: dict) -> list:
    """Tickers an order row trades that have a research file.

    When the row prices rungs ("COHR 13 @ $214", "4 MU @ $860"), only those tickers
    count, so a side note like "NVDA keeps DCA" isn't treated as a buy.
    """
    text = re.sub(r"\*\*", "", f"{row['order_text']} {row['trigger']} {row['detail']}")
    rung = [a or b for a, b in RUNG_TICKER_RE.findall(text)]
    candidates = rung if any((RESEARCH_DIR / f"{t}.md").exists() for t in rung) else TICKER_RE.findall(text)
    seen = []
    for t in candidates:
        if t not in seen and (RESEARCH_DIR / f"{t}.md").exists():
            seen.append(t)
    return seen


def row_text(row: dict) -> str:
    return f"{row['order_text']} {row['type']} {row['detail']}"


def ok_line(plan_text: str, needle: str) -> bool:
    """True when a plan line containing needle is marked lint-ok."""
    return any(needle in line and "lint-ok" in line for line in plan_text.splitlines())


# ---------------------------------------------------------------- checks

def check_cash(rep, plan_name, plan_text, accounts):
    rep.checked("cash")
    rep.checked("runway")
    rep.checked("leap-budget")
    orders, stats = cc.parse_one_time_orders(plan_text)
    dcas = cc.parse_dca_schedule(plan_text)
    summaries = cc.build_account_summary(cc.load_accounts(), orders, dcas)
    if stats["rows"] == 0:
        rep.add("ERROR", "cash", "No order rows parsed. Order tables need an 'Account' column "
                                 "and an 'Order' or 'Action' column.")
    for o in stats["unpriced"]:
        rep.add("ERROR", "cash", f"Unpriced {o['kind']} in {o['account']}: {o['description']} "
                                 f"(write 'N @ $price' or 'Total ~$X')")
    for s in summaries:
        if s["status"] == "OVER-COMMITTED":
            rep.add("ERROR", "cash", f"{s['name']} over-committed: {cc.format_money(s['remaining'])} "
                                     f"after DCA + orders")
        if s.get("status_if_triggered") == "OVER-COMMITTED":
            rep.add("WARN", "cash", f"{s['name']} over-committed if all conditionals fire: "
                                    f"{cc.format_money(s['remaining_if_triggered'])}")
        weeks = s["dca_runway_weeks"]
        if weeks is not None:
            if weeks < 3:
                rep.add("ERROR", "runway", f"{s['name']} DCA runway {weeks} weeks (< 3: critical)")
            elif weeks < 4:
                rep.add("WARN", "runway", f"{s['name']} DCA runway {weeks} weeks (3-4: low)")
        leap_total = s["leap_total"] + sum(o["cost"] for o in s["conditional_orders"] if o["kind"] == "leap")
        if s["cash"] > 0 and leap_total > 0.6 * s["cash"]:
            rep.add("ERROR", "leap-budget", f"{s['name']} LEAP buys {cc.format_money(leap_total)} = "
                                            f"{leap_total / s['cash']:.0%} of cash (max 60%)")
    return orders


def check_rows(rep, plan_text, plan_date, accounts, rows):
    for c in ("account-rules", "contracts", "terminology", "plan-coverage"):
        rep.checked(c)
    new_ccs = {}
    for row in rows:
        if row["deferred"]:
            continue
        text = row_text(row)
        if "lint-ok" in text:
            continue
        acct = accounts.get(row["account"])
        kind = row["kind"]
        label = f"{row['account']}: {row['description']}"
        opening = kind in ("cc", "csp", "leap")

        # account-rules
        if acct and opening:
            allowed = allowed_option_kinds(acct["constraints"])
            if allowed is not None and kind not in allowed:
                level = "ERROR" if not allowed or allowed == {"cc"} else "WARN"
                rep.add(level, "account-rules", f"{kind.upper()} not allowed by {row['account']} constraints: "
                                                f"{row['description']}")

        # terminology
        strikes = [m.group(1) for m in OPTION_RE.finditer(text)]
        if kind == "cc" and strikes and all(s == "P" for s in strikes):
            rep.add("ERROR", "terminology", f"Covered call with only put strikes: {label}")
        if kind == "csp" and strikes and all(s == "C" for s in strikes):
            rep.add("ERROR", "terminology", f"CSP with only call strikes: {label}")

        # contracts
        if kind in ("cc", "csp", "leap", "sell", "close", "roll") and strikes:
            for m in CONTRACTS_RE.finditer(text.replace("**", "")):
                n = float(m.group(1) or m.group(2))
                if n != int(n):
                    rep.add("ERROR", "contracts", f"Fractional contracts ({n:g}): {label}")
        if kind == "cc" and not row["conditional"]:
            m = CONTRACTS_RE.search(text.replace("**", ""))
            n = int(float(m.group(1) or m.group(2))) if m else 1
            for t in row_tickers(row)[:1]:
                new_ccs.setdefault((row["account"], t), []).append((n, label))

        # plan-coverage (new deployments over $2K)
        if kind in ("limit", "leap", "csp"):
            cost, _ = cc.order_cost(kind, f"{row['order_text']} {row['detail']}")
            if cost > 2000:
                for t in row_tickers(row):
                    info = research_info(t)
                    recent = [d for d in info.get("plan_dates", []) if 0 <= (plan_date - d).days <= 14]
                    if not recent:
                        last = max((d for d in info.get("plan_dates", []) if d <= plan_date), default=None)
                        when = f"last {last}" if last else "none on file"
                        rep.add("ERROR", "plan-coverage",
                                f"{t}: no /plan-stock within 14 days of {plan_date} ({when}) for "
                                f"{cc.format_money(cost)} order in {row['account']}")

    # CC share coverage: new + open short calls must fit in 100-share lots
    for (account, t), items in new_ccs.items():
        acct = accounts.get(account)
        if not acct:
            continue
        held = acct["shares"].get(t, 0)
        open_calls = acct["short_calls"].get(t, 0)
        new = sum(n for n, _ in items)
        capacity = int(held // 100)
        if new + open_calls > capacity:
            rep.add("ERROR", "contracts", f"{account} {t}: {new} new + {open_calls:g} open CCs > "
                                          f"{capacity} lots ({held:g} sh)")


def check_dca(rep, plan_text):
    rep.checked("dca-conviction")
    per_ticker = {}
    for d in cc.parse_dca_schedule(plan_text):
        per_ticker[d["ticker"]] = per_ticker.get(d["ticker"], 0) + d["daily"]
    convs = {}
    for t in per_ticker:
        c = research_info(t).get("conviction")
        if c is None:
            rep.add("WARN", "dca-conviction", f"{t}: no conviction score in research/stocks/{t}.md")
        else:
            convs[t] = c
    ranked = sorted(convs, key=lambda t: -convs[t])
    for i, hi in enumerate(ranked):
        for lo in ranked[i + 1:]:
            if convs[hi] > convs[lo] and per_ticker[hi] < per_ticker[lo]:
                if ok_line(plan_text, hi) or ok_line(plan_text, lo):
                    continue
                rep.add("ERROR", "dca-conviction",
                        f"{hi} (conv {convs[hi]:g}) gets ${per_ticker[hi]}/day < {lo} "
                        f"(conv {convs[lo]:g}) at ${per_ticker[lo]}/day")


def check_text(rep, plan_text):
    rep.checked("expiry")
    rep.checked("names")
    for no, line in enumerate(plan_text.splitlines(), 1):
        if "lint-ok" in line or line.lstrip().startswith("#"):
            continue
        plain = line.replace("**", "")
        for m in OPTION_RE.finditer(plain):
            window = plain[max(0, m.start() - 30): m.end() + 30]
            if not EXPIRY_RE.search(window):
                rep.add("WARN", "expiry", f"line {no}: '{plain[max(0, m.start() - 12): m.end() + 4].strip()}' "
                                          f"has no expiry date")
        for m in re.finditer(r"\b(BL|TG|GB)\b", plain):
            rep.add("WARN", "names", f"line {no}: abbreviation '{m.group(1)}', use the full account name")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Mechanical post-plan gates for a trading plan")
    parser.add_argument("--plan", help="Plan file (default: latest PLAN-*.md)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.plan:
        plan_path = cc.PLANS_DIR / args.plan
        if not plan_path.exists():
            plan_path = Path(args.plan)
        if not plan_path.exists():
            print(f"ERROR: plan not found: {args.plan}", file=sys.stderr)
            sys.exit(2)
    else:
        plan_path = cc.find_latest_plan()
    plan_text = plan_path.read_text()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", plan_path.name)
    plan_date = datetime.strptime(m.group(1), "%Y-%m-%d").date() if m else date.today()

    accounts = load_account_details()
    rows = list(cc.iter_order_rows(plan_text))

    rep = Report()
    check_cash(rep, plan_path.name, plan_text, accounts)
    check_rows(rep, plan_text, plan_date, accounts, rows)
    check_dca(rep, plan_text)
    check_text(rep, plan_text)

    if args.json:
        print(json.dumps({
            "plan": plan_path.name,
            "errors": len(rep.errors),
            "warnings": len(rep.items) - len(rep.errors),
            "findings": [{"level": l, "check": c, "message": msg} for l, c, msg in rep.items],
            "checks_run": rep.ran,
        }, indent=2))
    else:
        print(f"\nPLAN LINT — {plan_path.name}  ({len(rows)} order rows)\n")
        for check in rep.ran:
            found = [i for i in rep.items if i[1] == check]
            if not found:
                print(f"  ✅ {check}")
                continue
            worst = "❌" if any(l == "ERROR" for l, _, _ in found) else "⚠️ "
            print(f"  {worst} {check}")
            for level, _, msg in found:
                print(f"       {'ERROR' if level == 'ERROR' else 'warn '}  {msg}")
        print(f"\n  {len(rep.errors)} errors, {len(rep.items) - len(rep.errors)} warnings. "
              f"Mark deliberate exceptions with 'lint-ok' on the plan line.\n")

    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
