#!/usr/bin/env python3
"""
Cash check — validate trading plan orders against account cash balances.

Parses the latest (or specified) PLAN-*.md and all portfolio/accounts/*.md files,
aggregates planned deployments per account, and checks feasibility.

Usage:
    .venv/bin/python3 scripts/cash-check.py                        # latest plan, terminal
    .venv/bin/python3 scripts/cash-check.py --json                  # JSON output
    .venv/bin/python3 scripts/cash-check.py --plan PLAN-2026-09-06.md  # specific plan

Order tables are found by their column headers (an 'Account' column plus an
'Order' or 'Action' column), not by section name. Tables under a "Conditionals"
heading, or with a "Trigger" column, are counted separately as "if triggers fire".

Exit codes: 0 OK, 1 an account is over-committed, 2 the plan couldn't be fully
parsed (no order rows, an unpriced buy, or an unknown account).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ACCOUNTS_DIR = Path("portfolio/accounts")
PLANS_DIR = Path("portfolio/plans")

# Canonical account name mapping — maps various plan references to account file names.
# Keys are lowercase; values are the canonical account_name from frontmatter.
ACCOUNT_ALIASES = {
    "roth ira": "ROTH IRA",
    "roth": "ROTH IRA",
    "hold": "HOLD",
    "thetagang": "THETAGANG",
    "theta gang": "THETAGANG",
    "tg": "THETAGANG",
    "gobig": "GOBIG",
    "go big": "GOBIG",
    "gb": "GOBIG",
    "brokeragelink": "BROKERAGELINK",
    "brokerage link": "BROKERAGELINK",
    "bl": "BROKERAGELINK",
}


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter values using regex (no pyyaml dependency)."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("#") or not line:
            continue
        parts = line.split(":", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().strip('"').strip("'")
            # Try numeric conversion
            try:
                if "." in val:
                    fm[key] = float(val)
                else:
                    fm[key] = int(val)
            except ValueError:
                fm[key] = val
    return fm


def load_accounts() -> dict:
    """Load all account files, return {canonical_name: {cash, total_value, ...}}."""
    accounts = {}
    for f in ACCOUNTS_DIR.glob("*.md"):
        text = f.read_text()
        fm = parse_frontmatter(text)
        name = fm.get("account_name", f.stem.upper())
        accounts[name] = {
            "cash": fm.get("cash", 0),
            "total_value": fm.get("total_value", 0),
            "file": str(f),
        }
    return accounts


def resolve_account(raw: str) -> str:
    """Resolve a raw account name string to canonical account name."""
    cleaned = raw.strip()
    key = cleaned.lower()
    if key in ACCOUNT_ALIASES:
        return ACCOUNT_ALIASES[key]
    # Try substring match
    for alias, canonical in ACCOUNT_ALIASES.items():
        if alias in key or key in alias:
            return canonical
    return cleaned.upper()


OPTION_STRIKE_RE = re.compile(r"\$[\d,]+(?:\.\d+)?\s*([CP])\b")
VERB_RE = re.compile(
    r"\b(buy\s+back|buy\s+to\s+close|buy|add|sell|trim|exit|cut|close|roll|hold|keep|let|pause|stop|set)\w*",
    re.IGNORECASE,
)


def first_verb(text: str) -> str:
    """Return the first action verb in text (lowercased), or ''."""
    m = VERB_RE.search(text)
    return re.sub(r"\s+", " ", m.group(1).lower()) if m else ""


def classify_order(order_text: str, type_text: str, detail: str) -> str:
    """Classify an order row.

    Cash-deploying kinds: 'limit' (share buys), 'leap' (option buys), 'csp' (collateral).
    Non-deploying kinds: 'cc', 'sell', 'close', 'roll', 'stop', 'dca', 'dca_modify',
    'assignment', 'none'.

    Keywords are matched as whole words: a plain substring test for "cc" also
    matches "account" and "accelerate", which used to drop real buy orders.
    """
    combined = f"{order_text} {type_text} {detail}"
    low = combined.lower()

    if re.match(r"\s*no\b", order_text.lower()) or re.match(r"\s*no\b", detail.lower()):
        return "none"
    if re.search(r"trailing stop|stop loss|set trailing|\balert\b", low) and not re.search(r"\bbuy|\badd", low):
        return "stop"
    if re.search(r"let (assign|expire|ride)", low):
        return "assignment"
    dca = re.search(r"\bdca\b|recurring", low)
    lead = VERB_RE.search(combined)
    if dca and (not lead or dca.start() < lead.start()):
        if re.search(r"\b(pause|slow|modify|cut|raise|stop|resume)\w*", low):
            return "dca_modify"
        return "dca"
    if re.search(r"covered call|\bccs?\b", low):
        return "cc"

    verb = first_verb(order_text) or first_verb(type_text) or first_verb(detail)
    strike = OPTION_STRIKE_RE.search(combined)

    if verb in ("buy back", "buy to close"):
        return "close"
    if re.search(r"\bcsps?\b|cash[- ]secured", low) or (
        verb == "sell" and strike and strike.group(1) == "P" and "to close" not in low
    ):
        return "csp"
    if re.search(r"\bleaps?\b|buy to open", low) or (verb in ("buy", "add") and strike):
        return "leap"
    if verb in ("buy", "add"):
        return "limit"
    if verb in ("sell", "trim", "exit", "cut"):
        return "sell"
    if verb == "close":
        return "close"
    if verb == "roll":
        return "roll"
    if verb:
        return "none"
    # Older plans put the action in a Type column ("Limit", "GTC", "Market").
    if re.search(r"\blimit\b|\bgtc\b|\bmarket\b", type_text.lower()):
        return "limit"
    return "none"


def is_deferred(order_text: str, detail: str) -> bool:
    """Check if an order is deferred, struck through, rejected or already done."""
    combined = order_text + " " + detail
    if "~~" in combined:
        return True
    if re.search(r"DEFERRED|CONTINGENT|REJECTED|(?<!not )\bDONE\b|After\s+(Oct|Nov|Dec|Jan|Feb|Mar|Sep)",
                 combined, re.IGNORECASE):
        return True
    return False


def order_cost(kind: str, text: str) -> tuple:
    """Return (cost, method) for a cash-deploying order. method is how it was priced."""
    # Explicit total or collateral wins.
    for label in ("total", "collateral"):
        m = re.search(label + r"\s*~?\$([\d,]+(?:\.\d+)?)\s*([Kk])?", text, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", ""))
            return (val * 1000 if m.group(2) else val), label

    # "10 shares × $220 = $2,200" — a stated result wins over re-computing it.
    m = re.search(r"=\s*~?\$([\d,]+(?:\.\d+)?)\s*([Kk])?\b", text)
    if m:
        val = float(m.group(1).replace(",", ""))
        return (val * 1000 if m.group(2) else val), "stated total"

    if kind == "csp":
        # Collateral = strike × 100 × contracts.
        m = re.search(r"(\d+)\s*[x×]?\s*(?:contracts?\s+)?(?:[A-Z]{1,5}\s+)?\$(\d+(?:\.\d+)?)\s*P\b", text)
        if m:
            return int(m.group(1)) * float(m.group(2)) * 100, "strike×100×contracts"
        m = OPTION_STRIKE_RE.search(text)
        if m:
            strike = float(re.search(r"\$(\d+(?:\.\d+)?)", m.group(0)).group(1))
            return strike * 100, "strike×100 (1 contract assumed)"

    text = text.replace("**", "")
    # "13 @ $214, 4 @ $860 + 3 @ $810", "4 MU @ $860" or "25 shares at $190" — sum every rung.
    rungs = re.findall(
        r"(?<![\d.$])(\d[\d,]*)\s*(?:[A-Z]{1,5}\s+)?(?:sh(?:ares?)?\.?\s*)?(?:@|×|at\s+(?:or\s+below\s+)?)\s*~?\$([\d,]+(?:\.\d+)?)",
        text,
    )
    if rungs:
        total = sum(int(q.replace(",", "")) * float(p.replace(",", "")) for q, p in rungs)
        if kind == "leap":
            total *= 100  # option premium is quoted per share
        return total, "quantity×price"

    m = re.search(r"(\d+)\s+shares?\s*~\$?([\d,]+(?:\.\d+)?)", text)
    if m:
        return int(m.group(1)) * float(m.group(2).replace(",", "")), "quantity×price"

    # Ranges like "Est. cost ~$2-3K" — midpoint.
    m = re.search(r"~?\$([\d,]+(?:\.\d+)?)\s*[-–]\s*\$?([\d,]+(?:\.\d+)?)\s*([Kk])\b", text)
    if m:
        lo, hi = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        return (lo + hi) / 2 * 1000, "range midpoint"

    # "~$300-400 cost" — midpoint of a plain-dollar range labelled as cost/premium.
    m = re.search(r"~?\$([\d,]+(?:\.\d+)?)\s*[-–]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:cost|premium)", text,
                  re.IGNORECASE)
    if m:
        lo, hi = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        return (lo + hi) / 2, "range midpoint"

    # Explicit "$4.5K" style amount.
    m = re.search(r"~?\$([\d,]+(?:\.\d+)?)\s*[Kk]\b", text)
    if m:
        return float(m.group(1).replace(",", "")) * 1000, "stated amount"

    return 0.0, "unpriced"


def iter_tables(plan_text: str):
    """Yield (h2, h3, header_cells, rows) for every markdown table in the plan."""
    h2 = h3 = ""
    lines = plan_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            h2, h3 = line[3:].strip(), ""
        elif line.startswith("### "):
            h3 = line[4:].strip()
        elif line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            header = split_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i].strip()))
                i += 1
            yield h2, h3, header, rows
            continue
        i += 1


def split_row(line: str) -> list:
    """Split a markdown table row into cells, keeping empty cells in place."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def col(header: list, *names) -> int:
    """Index of the first header cell containing any of names (case-insensitive), or -1."""
    for name in names:
        for idx, cell in enumerate(header):
            if name in cell.lower():
                return idx
    return -1


SKIP_SECTIONS = ("dca schedule", "key dates", "risk budget", "summary", "position management",
                 "post-plan gates", "reconciliation")


def iter_order_rows(plan_text: str):
    """Yield every order row in the plan as a dict, whatever its kind.

    Plans have used several layouts ("One-Time Orders", "MUST-DO", "Should-Do",
    "Conditionals", per-stock tranche tables), so tables are found by their
    column headers rather than by section name. Also used by plan-lint.py.
    """
    for h2, h3, header, rows in iter_tables(plan_text):
        section = f"{h2} {h3}".lower()
        head = " ".join(header).lower()
        if any(s in h2.lower() for s in SKIP_SECTIONS) or "reference" in head:
            continue
        acct_i = col(header, "account")
        if acct_i < 0:
            continue
        conditional = "conditional" in section or header[0].lower().startswith("trigger")
        order_i = col(header, "action") if conditional else col(header, "order")
        if order_i < 0:
            order_i = col(header, "action", "trigger")
        if order_i < 0:
            continue
        trigger_i = col(header, "trigger")
        type_i = col(header, "type")
        num_i = col(header, "#")
        detail_idx = [i for i, h in enumerate(header)
                      if i not in (order_i, acct_i)
                      and re.search(r"detail|exact order|action|order", h.lower())]

        for cells in rows:
            if len(cells) <= max(order_i, acct_i):
                continue
            order_text = cells[order_i]
            if re.sub(r"[*\s]", "", order_text).lower() in ("", "total"):
                continue
            type_text = cells[type_i] if 0 <= type_i < len(cells) else ""
            detail = " ".join(cells[i] for i in detail_idx if i < len(cells))
            trigger = cells[trigger_i] if conditional and 0 <= trigger_i < len(cells) else ""
            # A conditional's verb can sit in the trigger ("WDC: SELL 10 Monday").
            kind = classify_order(order_text if first_verb(order_text) else f"{order_text} {trigger}",
                                  type_text, detail)
            desc = re.sub(r"\*\*", "", trigger or order_text).strip()
            yield {
                "num": cells[num_i] if 0 <= num_i < len(cells) else "",
                "description": desc[:60] + ("…" if len(desc) > 60 else ""),
                "order_text": order_text,
                "type": type_text,
                "detail": detail,
                "trigger": trigger,
                "account": resolve_account(cells[acct_i]),
                "kind": kind,
                "conditional": conditional,
                "deferred": is_deferred(order_text, detail),
                "section": h2,
            }


def parse_one_time_orders(plan_text: str) -> tuple:
    """Parse the cash-deploying orders in the plan. Returns (orders, stats)."""
    orders = []
    stats = {"tables": 0, "rows": 0, "unpriced": []}
    seen_sections = set()

    for row in iter_order_rows(plan_text):
        stats["rows"] += 1
        seen_sections.add(row["section"])
        if row["deferred"] or row["kind"] not in ("limit", "leap", "csp"):
            continue
        cost, method = order_cost(row["kind"], f"{row['order_text']} {row['detail']}")
        order = dict(row, cost=cost, cost_method=method)
        if cost == 0:
            stats["unpriced"].append(order)
        orders.append(order)

    stats["tables"] = len(seen_sections)
    return orders, stats


def dca_rows(account: str, header: list, rows: list) -> list:
    """Parse DCA table rows into {account, ticker, daily, description}."""
    out = []
    proposed_i = col(header, "proposed")
    if proposed_i < 0:
        proposed_i = 3
    for cells in rows:
        if len(cells) <= proposed_i:
            continue
        ticker = re.sub(r"\*\*", "", cells[0]).strip()
        if ticker.lower() in ("total", "") or ticker.startswith("~~"):
            continue
        cell = cells[proposed_i]
        if "PAUSED" in cell.upper() or re.match(r"\W*\$0\b", cell):
            continue
        m = re.search(r"\$(\d+)", cell)
        if m and int(m.group(1)) > 0:
            daily = int(m.group(1))
            out.append({"account": account, "ticker": ticker, "daily": daily,
                        "description": f"{ticker} ${daily}/d"})
    return out


def parse_dca_schedule(plan_text: str) -> list:
    """Parse the DCA Schedule section.

    Handles:
    - "### Account — $X/day ..." sub-headings, with or without a table under them
      (a heading-only line like "### HOLD — CRCL $100/day: keep running" counts as one DCA)
    - "## DCA Schedule (Account — $X/day)" single-account sections
    Paused / $0 headings are skipped.
    """
    dcas = []
    sec = re.search(r"^##\s+DCA Schedule(.*?)$(.*?)(?=^##\s|\Z)", plan_text, re.DOTALL | re.MULTILINE)
    if not sec:
        return dcas
    title, body = sec.group(1), sec.group(2)

    # Single-account form: "## DCA Schedule (BrokerageLink — $600/day)"
    single = re.match(r"\s*\(([^)—–-]*?)\s*[—–-]+\s*\$(\d+)/day", title)

    blocks = re.split(r"^###\s+", body, flags=re.MULTILINE)
    preamble, subsections = blocks[0], blocks[1:]

    if single and not subsections:
        account = resolve_account(single.group(1))
        for _, _, header, rows in iter_tables(preamble):
            dcas.extend(dca_rows(account, header, rows))
        return dcas

    for block in subsections:
        heading, _, rest = block.partition("\n")
        m = re.match(r"(.*?)\s*[—–]\s*(.*)$", heading) or re.match(r"(.*?)\s+-\s+(.*)$", heading)
        if not m:
            continue
        account = resolve_account(m.group(1).strip(" *"))
        tail = m.group(2)
        day = re.search(r"\$(\d+)/day", tail)
        if not day or int(day.group(1)) == 0 or re.match(r"\W*(PAUSED|\$0\b)", tail, re.IGNORECASE):
            continue
        parsed = []
        for _, _, header, rows in iter_tables(rest):
            parsed.extend(dca_rows(account, header, rows))
        if not parsed:
            before = tail[:day.start()]
            tick = re.findall(r"\b[A-Z]{1,5}\b", before)
            label = tick[-1] if tick else "DCA"
            daily = int(day.group(1))
            parsed = [{"account": account, "ticker": label, "daily": daily,
                       "description": f"{label} ${daily}/d"}]
        dcas.extend(parsed)

    return dcas


def parse_leap_orders(orders: list) -> list:
    """Filter LEAP orders from one-time orders."""
    return [o for o in orders if o["kind"] == "leap"]


def find_latest_plan() -> Path:
    """Find the most recent PLAN-*.md file."""
    plans = sorted(PLANS_DIR.glob("PLAN-*.md"))
    if not plans:
        print("ERROR: No PLAN-*.md files found in portfolio/plans/", file=sys.stderr)
        sys.exit(1)
    return plans[-1]


def build_account_summary(accounts: dict, orders: list, dcas: list) -> list:
    """Build per-account deployment summary."""
    summaries = {}

    # Initialize from accounts
    for name, acct in accounts.items():
        summaries[name] = {
            "name": name,
            "cash": acct["cash"],
            "total_value": acct["total_value"],
            "dca_items": [],
            "dca_daily": 0,
            "dca_monthly": 0,
            "limit_orders": [],
            "limit_total": 0,
            "leap_orders": [],
            "leap_total": 0,
            "csp_collateral": 0,
            "csp_items": [],
            "conditional_orders": [],
            "conditional_total": 0,
        }

    # Aggregate DCA
    for dca in dcas:
        acct = dca["account"]
        if acct not in summaries:
            continue
        summaries[acct]["dca_items"].append(dca["description"])
        summaries[acct]["dca_daily"] += dca["daily"]

    # Calculate monthly DCA (5 days/week × 4 weeks)
    for s in summaries.values():
        s["dca_monthly"] = s["dca_daily"] * 5 * 4  # 20 trading days

    # Aggregate orders
    for order in orders:
        acct = order["account"]
        if acct not in summaries:
            continue

        if order.get("conditional"):
            # Only spent if the trigger fires; reported separately.
            summaries[acct]["conditional_orders"].append(order)
            if order["kind"] != "csp":
                summaries[acct]["conditional_total"] += order["cost"]
            continue

        if order["kind"] == "csp":
            summaries[acct]["csp_collateral"] += order["cost"]
            summaries[acct]["csp_items"].append(order["description"])
        elif order["kind"] == "leap":
            summaries[acct]["leap_orders"].append(order)
            summaries[acct]["leap_total"] += order["cost"]
        else:
            summaries[acct]["limit_orders"].append(order)
            summaries[acct]["limit_total"] += order["cost"]

    # Calculate remaining and status
    for s in summaries.values():
        total_committed = s["dca_monthly"] + s["limit_total"] + s["leap_total"]
        # CSP collateral is reserved but not consumed — show separately
        remaining = s["cash"] - total_committed
        remaining_pct = (remaining / s["cash"] * 100) if s["cash"] > 0 else 0

        s["total_committed"] = total_committed
        s["remaining"] = remaining
        s["remaining_pct"] = round(remaining_pct, 1)

        # DCA runway
        weekly_dca = s["dca_daily"] * 5
        if weekly_dca > 0:
            s["dca_runway_weeks"] = int(remaining / weekly_dca) if remaining > 0 else 0
        else:
            s["dca_runway_weeks"] = None

        # Status
        s["status"] = cash_status(remaining, s["cash"])
        s["remaining_if_triggered"] = remaining - s["conditional_total"]
        s["status_if_triggered"] = cash_status(s["remaining_if_triggered"], s["cash"])
        if any(o["cost"] == 0 for o in s["conditional_orders"]):
            s["status_if_triggered"] = "UNKNOWN"

    return list(summaries.values())


def cash_status(remaining: float, cash: float) -> str:
    """OVER-COMMITTED below zero, TIGHT under 15% of cash left, else OK."""
    if remaining < 0:
        return "OVER-COMMITTED"
    if cash > 0 and remaining / cash * 100 < 15:
        return "TIGHT"
    return "OK"


def format_money(amount: float) -> str:
    """Format a number as $X,XXX."""
    if amount < 0:
        return f"-${abs(amount):,.0f}"
    return f"${amount:,.0f}"


def status_icon(status: str) -> str:
    """Return status indicator."""
    if status == "OK":
        return "\u2705 OK"
    elif status == "TIGHT":
        return "\u26a0\ufe0f  TIGHT"
    elif status == "UNKNOWN":
        return "\u2753 UNKNOWN (unpriced order)"
    else:
        return "\U0001f534 OVER-COMMITTED"


def print_terminal(plan_name: str, summaries: list, stats: dict):
    """Print terminal dashboard."""
    W = 70

    print()
    print("=" * W)
    print(f"  CASH CHECK \u2014 {plan_name}")
    print("=" * W)

    total_cash = 0
    total_committed = 0
    over_committed = 0

    # Sort: accounts with activity first, then alphabetical
    def has_activity(s):
        return s["total_committed"] > 0 or s["csp_collateral"] > 0 or s["conditional_orders"]

    active = [s for s in summaries if has_activity(s)]
    inactive = [s for s in summaries if not has_activity(s)]
    display = sorted(active, key=lambda x: -x["total_committed"]) + sorted(inactive, key=lambda x: x["name"])

    for s in display:
        total_cash += s["cash"]
        total_committed += s["total_committed"]
        if s["status"] == "OVER-COMMITTED":
            over_committed += 1

        print()
        print(f"  {s['name']}")
        print(f"  {'-' * (W - 4)}")

        print(f"    {'Available cash:':<26} {format_money(s['cash']):>10}")

        if s["dca_monthly"] > 0:
            dca_desc = " + ".join(s["dca_items"])
            print(f"    {'DCA (1 month):':<26} {format_money(-s['dca_monthly']):>10}  ({dca_desc})")

        if s["limit_total"] > 0:
            limit_descs = []
            for o in s["limit_orders"]:
                limit_descs.append(f"{o['description']} {format_money(o['cost'])}")
            desc_str = " + ".join(limit_descs) if len(limit_descs) <= 3 else f"{len(limit_descs)} orders"
            print(f"    {'Limit orders (if fill):':<26} {format_money(-s['limit_total']):>10}  ({desc_str})")

        if s["leap_total"] > 0:
            leap_descs = []
            for o in s["leap_orders"]:
                leap_descs.append(f"{o['description']} {format_money(o['cost'])}")
            desc_str = " + ".join(leap_descs)
            print(f"    {'LEAP purchases:':<26} {format_money(-s['leap_total']):>10}  ({desc_str})")

        if s["csp_collateral"] > 0:
            csp_desc = " + ".join(s["csp_items"])
            print(f"    {'CSP collateral:':<26} {format_money(s['csp_collateral']):>10}  ({csp_desc}) [reserved, not consumed]")
        elif s["total_committed"] > 0:
            print(f"    {'CSP collateral:':<26} {'$0':>10}  (none active)")

        if s["total_committed"] > 0 or s["csp_collateral"] > 0 or s["conditional_orders"]:
            print(f"  {'-' * (W - 4)}")
            pct_str = f"({s['remaining_pct']}%)"
            print(f"    {'Remaining:':<26} {format_money(s['remaining']):>10}  {pct_str:<12} {status_icon(s['status'])}")

            if s["dca_runway_weeks"] is not None:
                print(f"    {'DCA runway:':<26} {s['dca_runway_weeks']} weeks")

            # Warn about CSP collateral impact
            if s["csp_collateral"] > 0:
                remaining_with_csp = s["remaining"] - s["csp_collateral"]
                pct_with_csp = (remaining_with_csp / s["cash"] * 100) if s["cash"] > 0 else 0
                if remaining_with_csp < 0:
                    print(f"    {'If CSPs assigned:':<26} {format_money(remaining_with_csp):>10}  ({pct_with_csp:.1f}%)   \U0001f534 NEGATIVE")
                elif pct_with_csp < 15:
                    print(f"    {'If CSPs assigned:':<26} {format_money(remaining_with_csp):>10}  ({pct_with_csp:.1f}%)   \u26a0\ufe0f  TIGHT")

            if s["conditional_orders"]:
                print()
                print(f"    Conditional (only if triggers fire):")
                for o in s["conditional_orders"]:
                    cost = "UNPRICED" if o["cost"] == 0 else format_money(-o["cost"])
                    tag = " [CSP collateral]" if o["kind"] == "csp" else ""
                    print(f"      {cost:>10}  {o['description']}{tag}")
                print(f"    {'If all fire:':<26} {format_money(s['remaining_if_triggered']):>10}  "
                      f"{status_icon(s['status_if_triggered'])}")
        else:
            print(f"    {'Planned deployment:':<26} {'$0':>10}  (no orders this plan)")

    # Summary
    total_remaining = total_cash - total_committed
    total_pct = (total_remaining / total_cash * 100) if total_cash > 0 else 0

    print()
    print(f"  SUMMARY")
    print(f"  {'-' * (W - 4)}")
    print(f"    {'Total cash:':<26} {format_money(total_cash):>10}")
    print(f"    {'Total committed:':<26} {format_money(total_committed):>10}")
    print(f"    {'Total remaining:':<26} {format_money(total_remaining):>10}  ({total_pct:.1f}%)")
    print(f"    {'Over-committed accounts:':<26} {over_committed}")
    print(f"    {'Parsed:':<26} {stats['rows']} order rows in {stats['tables']} sections")
    print("=" * W)
    print()


def build_json(plan_name: str, summaries: list, stats: dict, problems: list) -> dict:
    """Build JSON output."""
    total_cash = sum(s["cash"] for s in summaries)
    total_committed = sum(s["total_committed"] for s in summaries)
    total_remaining = total_cash - total_committed

    accounts_json = []
    for s in summaries:
        entry = {
            "name": s["name"],
            "cash": s["cash"],
            "dca_monthly": s["dca_monthly"],
            "limit_orders": s["limit_total"],
            "leap_purchases": s["leap_total"],
            "csp_collateral": s["csp_collateral"],
            "total_committed": s["total_committed"],
            "remaining": s["remaining"],
            "remaining_pct": s["remaining_pct"],
            "status": s["status"],
            "conditional_total": s["conditional_total"],
            "remaining_if_triggered": s["remaining_if_triggered"],
            "status_if_triggered": s["status_if_triggered"],
        }
        if s["dca_runway_weeks"] is not None:
            entry["dca_runway_weeks"] = s["dca_runway_weeks"]
        if s["dca_items"]:
            entry["dca_detail"] = s["dca_items"]
        if s["limit_orders"]:
            entry["limit_detail"] = [
                {"description": o["description"], "cost": o["cost"]}
                for o in s["limit_orders"]
            ]
        if s["leap_orders"]:
            entry["leap_detail"] = [
                {"description": o["description"], "cost": o["cost"]}
                for o in s["leap_orders"]
            ]
        if s["csp_items"]:
            entry["csp_detail"] = s["csp_items"]
        if s["conditional_orders"]:
            entry["conditional_detail"] = [
                {"description": o["description"], "cost": o["cost"], "kind": o["kind"]}
                for o in s["conditional_orders"]
            ]
        accounts_json.append(entry)

    over_committed = sum(1 for s in summaries if s["status"] == "OVER-COMMITTED")

    return {
        "plan_file": plan_name,
        "accounts": sorted(accounts_json, key=lambda x: -x["total_committed"]),
        "summary": {
            "total_cash": total_cash,
            "total_committed": total_committed,
            "total_remaining": total_remaining,
            "remaining_pct": round(total_remaining / total_cash * 100, 1) if total_cash > 0 else 0,
            "over_committed": over_committed,
        },
        "parse": {"tables": stats["tables"], "order_rows": stats["rows"]},
        "problems": problems,
    }


def main():
    parser = argparse.ArgumentParser(description="Cash check — validate plan orders against account cash")
    parser.add_argument("--plan", help="Specific plan file (e.g., PLAN-2026-09-06.md)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--allow-empty", action="store_true",
                        help="Don't fail when the plan has no order tables")
    args = parser.parse_args()

    # Find plan file
    if args.plan:
        plan_path = PLANS_DIR / args.plan
        if not plan_path.exists():
            # Try without directory
            plan_path = Path(args.plan)
        if not plan_path.exists():
            print(f"ERROR: Plan file not found: {args.plan}", file=sys.stderr)
            sys.exit(1)
    else:
        plan_path = find_latest_plan()

    plan_name = plan_path.stem
    plan_text = plan_path.read_text()

    # Load accounts
    accounts = load_accounts()
    if not accounts:
        print("ERROR: No account files found in portfolio/accounts/", file=sys.stderr)
        sys.exit(1)

    # Parse plan
    orders, stats = parse_one_time_orders(plan_text)
    dcas = parse_dca_schedule(plan_text)

    # Build summaries
    summaries = build_account_summary(accounts, orders, dcas)

    # Parse problems make the check fail loudly instead of reporting a false OK.
    problems = []
    if stats["rows"] == 0 and not args.allow_empty:
        problems.append("No order rows found. The plan format may have changed: order tables "
                        "need an 'Account' column and an 'Order' or 'Action' column.")
    for o in stats["unpriced"]:
        problems.append(f"Couldn't price {o['kind']} order in {o['account']}: {o['description']} "
                        f"(write it as 'N @ $price' or 'Total ~$X')")
    known = set(accounts)
    for o in orders:
        if o["account"] not in known:
            problems.append(f"Unknown account '{o['account']}' on order: {o['description']}")

    # Output
    if args.json:
        result = build_json(plan_name, summaries, stats, problems)
        print(json.dumps(result, indent=2))
    else:
        print_terminal(plan_name, summaries, stats)
        for p in problems:
            print(f"  \u274c {p}", file=sys.stderr)

    if problems:
        sys.exit(2)
    if any(s["status"] == "OVER-COMMITTED" for s in summaries):
        sys.exit(1)


if __name__ == "__main__":
    main()
