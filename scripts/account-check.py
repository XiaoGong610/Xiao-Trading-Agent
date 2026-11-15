#!/usr/bin/env python3
"""
Account-file validator: checks portfolio/accounts/*.md before anything downstream reads them.

Bad inputs here poison cash-check, plan-lint, the dashboard and every review, so this
runs first (step 1 of the weekly session, right after the screenshot update) and again
inside plan-lint.

Checks (per account file):
  frontmatter   account_name, total_value, cash, last_updated present; cash/total_value are
                bare numbers (no inline "# comment": downstream parsers read the raw value)
  freshness     last_updated older than 7 days -> WARN
  tickers       position cells are a clean ticker ("AMZN") or an option
                ("AMZN $290C Dec 11 (short)"); extra labels like "SNDK (split pending)" break
                cross-account matching -> ERROR
  duplicates    the same ticker/option listed twice in one account -> ERROR
  pending       cash must be net of pending activity: if the Positions section says
                "Cash $X ... Pending -$Y" and frontmatter cash == X while Y > 0 -> ERROR
  reconcile     sum(position values) + cash ~= total_value (tolerance: max($100, 0.1%))
                -> ERROR outside tolerance; skipped (WARN) if no Value column is found

Usage:
    .venv/bin/python3 scripts/account-check.py            # terminal report
    .venv/bin/python3 scripts/account-check.py --json

Importable: run_checks() -> list of (level, account, check, message).
Exit codes: 0 no errors (warnings allowed), 1 at least one ERROR.
Holds no personal data itself: everything is read from the gitignored account files.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS_DIR = ROOT / "portfolio" / "accounts"

REQUIRED = ("account_name", "total_value", "cash", "last_updated")
STALE_DAYS = 7
TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
# AMZN $290C Dec 11 (short) · CRCL $150C Dec 17 2027 · TSLL $13C Dec 31 '26 · NOW $160C Jan 15 '27 ×2
OPTION_RE = re.compile(
    r"^[A-Z]{1,5} \$\d+(\.\d+)?[CP]\b"
    r"( [A-Z][a-z]{2} \d{1,2}( '?\d{2,4})?)?"
    r"( \((short|long)\))?( ×\d+)?$")
NAME_COLS = ("ticker", "position", "option", "symbol")
VALUE_COLS = ("value",)
NUM_RE = re.compile(r"-?\$?-?[\d,]+(\.\d+)?")


def _num(text: str):
    """'$186,929' -> 186929.0 · '−$235' -> -235.0 · '—' -> None."""
    t = text.replace("−", "-").replace("–", "-").replace("*", "").strip()
    m = NUM_RE.search(t)
    if not m:
        return None
    raw = m.group(0)
    neg = raw.count("-") > 0
    val = float(raw.replace("-", "").replace("$", "").replace(",", ""))
    return -val if neg else val


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if km:
            out[km.group(1)] = km.group(2).strip()
    return out


def positions_section(text: str) -> str:
    m = re.search(r"^## Positions.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def position_rows(section: str):
    """Yield (name_cell, value or None) for each data row of each table in the section."""
    header = None
    for line in section.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        ni = next((i for i, h in enumerate(header) if h in NAME_COLS), None)
        vi = next((i for i, h in enumerate(header) if h in VALUE_COLS), None)
        if ni is None or ni >= len(cells):
            continue
        val = _num(cells[vi]) if vi is not None and vi < len(cells) else None
        yield cells[ni], val, vi is not None


def check_account(path: Path, today: date):
    findings = []
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    acct = fm.get("account_name", path.stem)

    def add(level, check, msg):
        findings.append((level, acct, check, msg))

    # frontmatter
    for k in REQUIRED:
        if not fm.get(k):
            add("ERROR", "frontmatter", f"missing '{k}'")
    for k in ("cash", "total_value"):
        v = fm.get(k, "")
        if v and not re.fullmatch(r"-?\d+(\.\d+)?", v):
            add("ERROR", "frontmatter", f"'{k}: {v}' is not a bare number (downstream parsers will crash)")
    cash = float(fm["cash"]) if re.fullmatch(r"-?\d+(\.\d+)?", fm.get("cash", "")) else None
    total = float(fm["total_value"]) if re.fullmatch(r"-?\d+(\.\d+)?", fm.get("total_value", "")) else None

    # freshness
    try:
        upd = datetime.strptime(fm.get("last_updated", ""), "%Y-%m-%d").date()
        age = (today - upd).days
        if age > STALE_DAYS:
            add("WARN", "freshness", f"last_updated {upd} is {age} days old (> {STALE_DAYS})")
    except ValueError:
        if fm.get("last_updated"):
            add("ERROR", "frontmatter", f"last_updated '{fm['last_updated']}' is not YYYY-MM-DD")

    section = positions_section(text)
    if not section:
        add("ERROR", "reconcile", "no '## Positions' section")
        return findings

    # tickers + duplicates + values
    seen, total_pos, have_values = set(), 0.0, False
    for name, val, has_val_col in position_rows(section):
        clean = re.sub(r"\*\*|~~", "", name).strip()
        base = re.sub(r"\s*\((W|w)\)$", "", clean)        # Fidelity wash-sale marker is OK
        if not (TICKER_RE.match(base) or OPTION_RE.match(base)):
            add("ERROR", "tickers", f"'{clean}' is not a clean ticker or option label "
                                    f"(move notes like splits to the text, not the ticker cell)")
        key = base.upper()
        if key in seen:
            add("ERROR", "duplicates", f"'{base}' listed twice")
        seen.add(key)
        if has_val_col:
            have_values = True
            if val is not None:
                total_pos += val

    # pending: cash must be net of pending activity
    cm = re.search(r"Cash \$([\d,]+(?:\.\d+)?)", section)
    pm = re.search(r"Pending\s*[−-]\$([\d,]+(?:\.\d+)?)", section)
    if cash is not None and cm and pm:
        gross = float(cm.group(1).replace(",", ""))
        pending = float(pm.group(1).replace(",", ""))
        if pending > 0 and abs(cash - gross) < 1:
            add("ERROR", "pending", f"cash {cash:,.0f} equals screenshot cash but pending −${pending:,.0f} "
                                    f"is not subtracted (use {gross - pending:,.0f})")

    # reconcile
    if not have_values:
        add("WARN", "reconcile", "no Value column found in Positions tables; reconcile skipped")
    elif cash is not None and total is not None:
        diff = total_pos + cash - total
        tol = max(100.0, 0.001 * total)
        if abs(diff) > tol:
            add("ERROR", "reconcile", f"positions {total_pos:,.0f} + cash {cash:,.0f} = "
                                      f"{total_pos + cash:,.0f} vs total_value {total:,.0f} "
                                      f"(off by {diff:+,.0f}; tolerance ±{tol:,.0f})")
    return findings


def run_checks(accounts_dir: Path = ACCOUNTS_DIR, today: date = None):
    today = today or date.today()
    out = []
    files = sorted(accounts_dir.glob("*.md")) if accounts_dir.exists() else []
    if not files:
        out.append(("ERROR", "-", "files", f"no account files in {accounts_dir}"))
    for f in files:
        out.extend(check_account(f, today))
    return out, [f.stem for f in files]


def main():
    ap = argparse.ArgumentParser(description="Validate portfolio/accounts/*.md")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    findings, names = run_checks()
    errors = [f for f in findings if f[0] == "ERROR"]
    if args.json:
        print(json.dumps({"accounts": names, "errors": len(errors),
                          "warnings": len(findings) - len(errors),
                          "findings": [dict(zip(("level", "account", "check", "message"), f))
                                       for f in findings]}, indent=2))
    else:
        print(f"\nACCOUNT CHECK — {len(names)} files\n")
        by_acct = {}
        for f in findings:
            by_acct.setdefault(f[1], []).append(f)
        for n in names:
            acct_findings = [f for k, v in by_acct.items() for f in v if k.lower().replace(" ", "-") == n
                             or k.lower().replace(" ", "") == n.replace("-", "")]
            if not acct_findings:
                print(f"  ✅ {n}")
            for lvl, _, chk, msg in acct_findings:
                print(f"  {'❌' if lvl == 'ERROR' else '⚠️ '} {n} · {chk}: {msg}")
        for f in by_acct.get("-", []):
            print(f"  ❌ {f[3]}")
        print(f"\n  {len(errors)} errors, {len(findings) - len(errors)} warnings.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
