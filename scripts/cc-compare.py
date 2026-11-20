#!/usr/bin/env python3
"""
Covered-call comparison across underlyings: which name is the better place to sell calls *now*?

For each ticker it scans live calls (20–50 DTE, 0.15–0.30 delta by default), scores every
contract with the CC Sharpe Score from option-scores.py (same gates as
knowledge/strategies/when-to-cc.md), keeps the best one, and adds a portfolio-fit view
from the local account files:

  held          shares across all accounts, and the % of the portfolio
  CC-able lots  100-share lots in accounts whose constraints allow covered calls,
                minus calls already sold against them ("uncovered lots")
  new lot cost  price x 100, if you'd have to buy shares first
  band          conviction target band (research frontmatter) vs current weight

Fit verdicts:
  USE EXISTING   uncovered lots in a CC account and the best contract passes the gates
  WAIT           uncovered lots exist but the gates fail today
  BUY FIRST      no CC-able lots: needs a /plan-stock for 100 shares (capital shown)
  OVERWEIGHT     already above its conviction band: sell calls on what you hold, don't add

Usage:
    .venv/bin/python3 scripts/cc-compare.py GOOG AMZN TSLA QQQ
    .venv/bin/python3 scripts/cc-compare.py GOOG AMZN --dte 25 45 --delta 0.15 0.25
    .venv/bin/python3 scripts/cc-compare.py GOOG AMZN --basis AMZN=200   # gate 4 per ticker
    .venv/bin/python3 scripts/cc-compare.py GOOG AMZN --json
    .venv/bin/python3 scripts/cc-compare.py GOOG --no-portfolio            # cloud / no account files

Live data from yfinance (via option-scores.py). Holds no personal data: positions are
read at run time from gitignored files.
"""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Conviction -> max target weight (% of portfolio), per CLAUDE.md "Conviction-based allocation targets"
BANDS = ((9, 8.0), (7, 5.0), (5, 3.0), (0, 1.0))


def band_max(conviction):
    if conviction is None:
        return None
    return next(hi for lo, hi in BANDS if conviction >= lo)


def portfolio_fit(ticker, price, details, total_value, conviction, allowed_kinds):
    """Pure function (testable): holdings + CC capacity for one ticker.

    details: {ACCOUNT: {"constraints": [...], "shares": {T: n}, "short_calls": {T: n}}}
    allowed_kinds: function(constraints) -> set of kinds, or None if unstated
    """
    held = sum(a["shares"].get(ticker, 0) for a in details.values())
    per_acct, uncovered = [], 0
    for name, a in details.items():
        sh = a["shares"].get(ticker, 0)
        if sh <= 0:
            continue
        kinds = allowed_kinds(a["constraints"])
        cc_ok = kinds is None or "cc" in kinds
        lots = int(sh // 100) if cc_ok else 0
        free = max(0, lots - int(a["short_calls"].get(ticker, 0)))
        uncovered += free
        per_acct.append({"account": name, "shares": sh, "cc_allowed": cc_ok,
                         "lots": lots, "short_calls": a["short_calls"].get(ticker, 0), "uncovered": free})
    weight = held * price / total_value * 100 if total_value else 0.0
    cap = band_max(conviction)
    return {"held_shares": held, "weight_pct": round(weight, 1), "band_max_pct": cap,
            "overweight": cap is not None and weight > cap, "uncovered_lots": uncovered,
            "new_lot_cost": round(price * 100), "accounts": per_acct}


def fit_verdict(fit, best_passes):
    if fit is None:
        return "n/a"
    if fit["uncovered_lots"] > 0:
        return "USE EXISTING" if best_passes else "WAIT (gates fail today)"
    if fit["overweight"]:
        return "OVERWEIGHT (don't add)"
    return f"BUY FIRST (~${fit['new_lot_cost']:,}/lot, /plan-stock)"


def analyze(ticker, os_mod, dte, delta, basis, fit_ctx):
    m = os_mod.Market(ticker)
    rows = os_mod.candidates(m, "call", dte[0], dte[1], delta[0], delta[1])
    scored = [os_mod.score_cc(m, e, r, basis) for e, r in rows]
    passing = [s for s in scored if not s["verdict"].startswith("DON'T")]
    pool = passing or scored
    pool.sort(key=lambda s: (-s["score"], -abs(s["strike"] - m.price)))
    best = pool[0] if pool else None
    out = {"ticker": m.ticker, "price": m.price, "iv30": m.iv30, "rv20": m.rv20,
           "iv_rank": m.iv_rank, "iv_rank_source": m.iv_rank_source,
           "earnings": str(m.earnings) if m.earnings else None, "best": best,
           "n_scanned": len(scored), "n_passing": len(passing)}
    if fit_ctx:
        details, total, research_info, allowed = fit_ctx
        conv = research_info(m.ticker).get("conviction")
        fit = portfolio_fit(m.ticker, m.price, details, total, conv, allowed)
        fit["conviction"] = conv
        out["fit"] = fit
        out["fit_verdict"] = fit_verdict(fit, bool(passing))
    return out


def render(results):
    lines = ["", "COVERED-CALL COMPARISON (best contract per name; CC Sharpe gates from option-scores.py)", "",
             f"{'Ticker':6} {'Price':>9} {'IV/RV':>9} {'Best call':>22} {'Prem':>6} {'OTM':>6} {'Δ':>5} "
             f"{'Ann%':>6} {'Score':>6}  {'Verdict':24} {'Held':>6} {'Wt%':>5} {'Unc.lots':>8}  Fit"]
    for r in results:
        b = r["best"]
        call = f"${b['strike']:g}C {b['expiry']}" if b else "—"
        f = r.get("fit") or {}
        lines.append(
            f"{r['ticker']:6} {r['price']:>9.2f} {r['iv30']:>4.0f}/{r['rv20']:<4.0f} {call:>22} "
            f"{(b or {}).get('premium', 0):>6.2f} {(b or {}).get('otm_pct', 0):>5.1f}% {(b or {}).get('delta', 0):>5.2f} "
            f"{(b or {}).get('ann_yield', 0):>6.1f} {(b or {}).get('score', 0):>6.1f}  {(b or {}).get('verdict', '—')[:24]:24} "
            f"{f.get('held_shares', 0):>6g} {f.get('weight_pct', 0):>5.1f} {f.get('uncovered_lots', 0):>8}  {r.get('fit_verdict', '')}")
    lines += ["", "IV/RV = 30-day implied vs 20-day realized vol (gate 3 wants IV >= ~0.9x RV). "
              "Unc.lots = uncovered 100-share lots in accounts that allow covered calls.",
              "Sell calls into strength (when-to-cc.md); ladder strikes for >= 2 contracts; re-run on the day you sell."]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Compare covered-call setups across underlyings")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--dte", nargs=2, type=int, default=(20, 50), metavar=("LO", "HI"))
    ap.add_argument("--delta", nargs=2, type=float, default=(0.15, 0.30), metavar=("LO", "HI"))
    ap.add_argument("--basis", action="append", default=[], metavar="TICKER=PRICE",
                    help="cost basis for gate 4 (strike >= basis), repeatable")
    ap.add_argument("--no-portfolio", action="store_true", help="skip the account-file fit view")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    os_mod = _load("option_scores", "option-scores.py")
    basis = {k.upper(): float(v) for k, v in (b.split("=", 1) for b in a.basis)}
    fit_ctx = None
    if not a.no_portfolio and (ROOT / "portfolio" / "accounts").exists():
        pl = _load("plan_lint", "plan-lint.py")
        details = pl.load_account_details()
        total = sum(float(v["total_value"] or 0) for v in pl.cc.load_accounts().values())
        fit_ctx = (details, total, pl.research_info, pl.allowed_option_kinds)

    results = []
    for t in a.tickers:
        try:
            results.append(analyze(t.upper(), os_mod, a.dte, a.delta, basis.get(t.upper()), fit_ctx))
        except SystemExit as e:
            print(f"{t}: {e}", file=sys.stderr)
    print(json.dumps(results, indent=2, default=str) if a.json else render(results))


if __name__ == "__main__":
    main()
