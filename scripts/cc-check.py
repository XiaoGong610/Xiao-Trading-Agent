#!/usr/bin/env python3
"""
Covered-call candidate check for ONE stock: should I hold it and sell calls on it, and how many shares?
Pass several tickers and it runs the same single-stock check on each, then adds a comparison table.

Answers four questions per ticker:

  1. CONVICTION  Is it worth holding long term? Research conviction + thesis + freshness
                 from research/stocks/TICKER.md (>= 7 YES, 6 OK, 5 WEAK, < 5 NO; stale > 42 days).
  2. VOLATILITY  Is there enough premium? Live 30-day IV vs realized vol, IV Rank, and the
                 best 20–50 DTE, 0.15–0.30-delta call's annualized premium, scored with the
                 CC Sharpe gates from option-scores.py. (>= 15%/yr RICH, 10–15 GOOD, 6–10 THIN.)
  3. SIMULATION  How much extra would selling calls have earned? Buy-write vs buy-hold from
                 cc-backtest.py since --start, using the playbook rules (skip earnings + oversold): CAGR uplift, premium/yr, how often a rolling
                 1-year window beat holding, and the uplift in up vs down markets.
  Stage (lifecycle): ACCUMULATE to a 100-share lot in an account that allows calls ->
                 HOLD, WAIT while the gates fail -> SELL CALLS. Low conviction or over band = don't add.
  4. SIZING      How many shares to start? Conviction band max (% of portfolio) x portfolio
                 value / price -> max shares and whole 100-share lots (2+ lots lets you ladder
                 strikes), minus shares already held in accounts that allow covered calls.

Usage:
    .venv/bin/python3 scripts/cc-check.py GOOG                    # single-stock check
    .venv/bin/python3 scripts/cc-check.py GOOG AMZN TSLA QQQ      # each, plus a comparison table
    .venv/bin/python3 scripts/cc-check.py GOOG --portfolio-value 700000   # sizing without account files
    .venv/bin/python3 scripts/cc-check.py GOOG AMZN --start 2019-01-01 --sim-delta 0.15
    .venv/bin/python3 scripts/cc-check.py GOOG AMZN --basis AMZN=200     # gate 4 cost basis
    .venv/bin/python3 scripts/cc-check.py GOOG AMZN --json

Live data from yfinance. Holds no personal data: positions and portfolio value are read
at run time from gitignored files (or passed with --portfolio-value).
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


def research_summary(ticker, root=ROOT, today=None):
    """Q1 inputs from research/stocks/TICKER.md: conviction, thesis, latest entry date."""
    import re
    from datetime import date as _date
    f = root / "research" / "stocks" / f"{ticker}.md"
    if not f.exists():
        return {"conviction": None, "thesis": None, "last_date": None, "age_days": None}
    text = f.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---", text, re.S)
    meta = {}
    for line in (fm.group(1).splitlines() if fm else []):
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    try:
        conv = float(meta.get("conviction", ""))
    except ValueError:
        conv = None
    dates = re.findall(r"^# .*\| (\d{4}-\d{2}-\d{2})", text, re.M)
    last = max(dates) if dates else None
    age = ((today or _date.today()) - _date.fromisoformat(last)).days if last else None
    return {"conviction": conv, "thesis": meta.get("thesis"), "last_date": last, "age_days": age}


def q1_verdict(r):
    c = r["conviction"]
    if c is None:
        return "NO RESEARCH (run /research-stock)"
    v = "YES" if c >= 7 else "OK" if c >= 6 else "WEAK" if c >= 5 else "NO"
    if r["age_days"] is not None and r["age_days"] > 42:
        v += f" (stale {r['age_days']}d: refresh)"
    return v


def q2_verdict(best, iv30, rv20):
    if not best:
        return "NO LIQUID CALLS"
    y = best["ann_yield"]
    v = "RICH" if y >= 15 else "GOOD" if y >= 10 else "THIN" if y >= 6 else "TOO LOW"
    if rv20 and iv30 < 0.9 * rv20:
        v += " (IV < RV today: wait to sell)"
    return v


def q3_verdict(sim):
    if not sim or sim.get("cycles", 0) == 0:
        return "NO HISTORY"
    up, beat = sim["cagr_uplift_pct"], sim.get("beat_hold_1y_pct") or 0
    if up >= 1 and beat >= 50:
        return "HELPS"
    if up <= -1:
        return "HURTS (gives up rallies)"
    return "NEUTRAL (income + smoother ride, ~same return)"


def sizing(price, conviction, portfolio_value, held_cc_shares, held_total):
    """Q4 (pure, testable): max shares in the conviction band and whole lots to start."""
    cap = band_max(conviction)
    if cap is None or not portfolio_value:
        return {"band_max_pct": cap, "max_shares": None, "max_lots": None, "target_lots": None,
                "shares_to_buy": None, "lot_pct": None, "verdict": "need conviction + portfolio value"}
    max_value = cap / 100 * portfolio_value
    max_shares = int(max_value // price)
    max_lots = max_shares // 100
    lot_pct = price * 100 / portfolio_value * 100
    over = held_total * price > max_value
    target = min(2, max_lots)
    buy = max(0, target * 100 - int(held_cc_shares)) if target else None
    if over:
        verdict = f"OVER BAND: already {held_total * price / portfolio_value * 100:.1f}% > {cap:g}%; sell calls on what you hold, don't add"
    elif max_lots == 0:
        verdict = f"1 lot = {lot_pct:.1f}% of portfolio > {cap:g}% band: too big at this conviction"
    else:
        verdict = (f"start with {target} lot{'s' if target > 1 else ''} ({target * 100} sh)"
                   + (" to ladder strikes" if target >= 2 else "") + f"; buy {buy} more sh")
    return {"band_max_pct": cap, "max_shares": max_shares, "max_lots": max_lots, "target_lots": target,
            "shares_to_buy": buy, "lot_pct": round(lot_pct, 1), "verdict": verdict}


def cc_stage(q1_conv, held_cc_shares, gates_pass, over_band):
    """Lifecycle (pure, testable): ACCUMULATE -> HOLD (wait) -> SELL CALLS. Conviction gates entry."""
    if q1_conv is None or q1_conv < 6:
        return "NOT A CANDIDATE (conviction < 6)" if held_cc_shares < 100 else "CALLS ON EXISTING ONLY (low conviction: don't add)"
    if held_cc_shares < 100:
        return "ACCUMULATE" if not over_band else "OVER BAND (don't add)"
    return "SELL CALLS (gates pass)" if gates_pass else "HOLD, WAIT (gates fail today)"


def analyze(ticker, os_mod, ccb, args, basis, fit_ctx, portfolio_value):
    m = os_mod.Market(ticker)
    rows = os_mod.candidates(m, "call", args.dte[0], args.dte[1], args.delta[0], args.delta[1])
    scored = [os_mod.score_cc(m, e, r, basis) for e, r in rows]
    passing = [s for s in scored if not s["verdict"].startswith("DON'T")]
    pool = sorted(passing or scored, key=lambda s: (-s["score"], -abs(s["strike"] - m.price)))
    best = pool[0] if pool else None

    research = research_summary(m.ticker)
    try:
        px = ccb.fetch(m.ticker, args.start)
        earn = ccb.earnings_indices(m.ticker, px.index)
        # Simulate the playbook default (when-to-cc.md -> Backtested Rules): skip earnings + oversold
        sim = ccb.simulate_buywrite(px.values, dte=args.sim_dte, delta=args.sim_delta, vrp=args.vrp,
                                    skip_earnings=earn is not None, earnings_idx=earn, skip_oversold=True)
        sim = {k: v for k, v in sim.items() if not k.startswith("_")}
    except Exception as e:  # short history, fetch failure
        sim = {"error": str(e), "cycles": 0}

    held_total = held_cc = 0
    fit = None
    if fit_ctx:
        details, _, _, allowed = fit_ctx
        fit = portfolio_fit(m.ticker, m.price, details, portfolio_value or 0, research["conviction"], allowed)
        held_total = fit["held_shares"]
        held_cc = sum(a["shares"] for a in fit["accounts"] if a["cc_allowed"])
    size = sizing(m.price, research["conviction"], portfolio_value, held_cc, held_total)
    stage = cc_stage(research["conviction"], held_cc, bool(passing), size["verdict"].startswith("OVER"))

    return {"ticker": m.ticker, "price": m.price,
            "q1": {**research, "verdict": q1_verdict(research)},
            "q2": {"iv30": m.iv30, "rv20": m.rv20, "iv_rank": m.iv_rank, "iv_rank_source": m.iv_rank_source,
                   "earnings": str(m.earnings) if m.earnings else None, "best_call": best,
                   "n_scanned": len(scored), "n_passing": len(passing), "verdict": q2_verdict(best, m.iv30, m.rv20)},
            "q3": {**sim, "settings": {"start": args.start, "delta": args.sim_delta, "dte": args.sim_dte},
                   "verdict": q3_verdict(sim)},
            "q4": {**size, "held_total": held_total, "held_in_cc_accounts": held_cc},
            "stage": stage,
            "fit": fit}


def render(results, args):
    out = []
    for r in results:
        q1, q2, q3, q4, b = r["q1"], r["q2"], r["q3"], r["q4"], r["q2"]["best_call"]
        out += [f"\n=== {r['ticker']}  ${r['price']:,.2f}  ·  STAGE: {r['stage']} ===",
                f"1. CONVICTION   {q1['verdict']}  · conv {q1['conviction']} · research {q1['last_date']}"
                + (f"\n               {q1['thesis'][:150]}" if q1["thesis"] else ""),
                f"2. VOLATILITY   {q2['verdict']}  · IV30 {q2['iv30']}% vs RV20 {q2['rv20']}% · IV Rank {q2['iv_rank']} ({q2['iv_rank_source']})"]
        if b:
            out.append(f"               best: ${b['strike']:g}C {b['expiry']} @ ${b['premium']:.2f} · {b['otm_pct']}% OTM · Δ{b['delta']} · "
                       f"{b['ann_yield']}%/yr · score {b['score']} {b['verdict']}")
        if q3.get("cycles"):
            out.append(f"3. SIMULATION   {q3['verdict']}  · {q3['years']}y, {q3['settings']['delta']}-delta / {q3['settings']['dte']}-day cycles, "
                       f"playbook rules (skip earnings + oversold), {q3.get('coverage_pct', 0):.0f}% of days covered")
            out.append(f"               CAGR hold {q3['bh_cagr_pct']:+.1f}% vs covered calls {q3['bw_cagr_pct']:+.1f}% "
                       f"(uplift {q3['cagr_uplift_pct']:+.1f} pts/yr) · premium {q3['premium_yield_ann_pct']}%/yr · called {q3['called_pct']:.0f}% of cycles")
            out.append(f"               1-yr windows: beat hold {q3['beat_hold_1y_pct']}% of the time · median {q3['median_1y_uplift_pts']:+} pts · "
                       f"rallies (>15%) {q3['uplift_1y_up_markets_pts']} pts · down years {q3['uplift_1y_down_markets_pts']} pts · "
                       f"max drawdown {q3['bh_maxdd_pct']}% → {q3['bw_maxdd_pct']}%")
        else:
            out.append(f"3. SIMULATION   {q3['verdict']} {q3.get('error', '')}")
        out.append(f"4. SIZING       {q4['verdict']}"
                   + (f"\n               band max {q4['band_max_pct']}% → up to {q4['max_shares']} sh ({q4['max_lots']} lots); "
                      f"1 lot = {q4['lot_pct']}% of portfolio; held {q4['held_total']:g} sh ({q4['held_in_cc_accounts']:g} in CC-capable accounts)"
                      if q4.get("max_shares") is not None else ""))
    if len(results) > 1:
        out += ["", "=== COMPARISON ===",
                f"{'Ticker':6} {'1 Conviction':16} {'2 Volatility':10} {'Prem/yr':>8} {'3 Simulation':10} {'CAGR +/-':>9} "
                f"{'Beat 1y':>8} {'4 Sizing':>10}  Stage"]
        for r in results:
            q1, q2, q3, q4 = r["q1"], r["q2"], r["q3"], r["q4"]
            b_ = q2["best_call"] or {}
            out.append(f"{r['ticker']:6} {(str(q1['conviction']) + ' ' + q1['verdict'].split()[0]):16} "
                       f"{q2['verdict'].split()[0]:10} {b_.get('ann_yield', 0):>7.1f}% {q3['verdict'].split()[0]:10} "
                       f"{q3.get('cagr_uplift_pct', 0):>+8.1f} {str(q3.get('beat_hold_1y_pct', '—')) + '%':>8} "
                       f"{('over band' if q4['verdict'].startswith('OVER') else (str(q4['target_lots']) + ' lot(s)') if q4.get('target_lots') else '—'):>10}  {r['stage']}")
    out += ["", "Sizing uses the conviction bands in CLAUDE.md; a new position still needs /plan-stock (scaled entry).",
            "Simulation = model prices (realized vol x VRP), no earnings avoidance: compare names, don't forecast income.",
            "Sell calls into strength; ladder strikes with >= 2 lots; re-run on the day you sell."]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Hold + covered-call candidate check")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--dte", nargs=2, type=int, default=(20, 50), metavar=("LO", "HI"), help="live scan DTE range")
    ap.add_argument("--delta", nargs=2, type=float, default=(0.15, 0.30), metavar=("LO", "HI"), help="live scan delta range")
    ap.add_argument("--basis", action="append", default=[], metavar="TICKER=PRICE", help="gate 4 cost basis, repeatable")
    ap.add_argument("--start", default="2016-01-01", help="simulation start date")
    ap.add_argument("--sim-delta", type=float, default=0.20)
    ap.add_argument("--sim-dte", type=int, default=30, help="simulation cycle length in trading days")
    ap.add_argument("--vrp", type=float, default=1.15)
    ap.add_argument("--portfolio-value", type=float, help="override the portfolio value used for sizing")
    ap.add_argument("--no-portfolio", action="store_true", help="don't read account files")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    os_mod = _load("option_scores", "option-scores.py")
    ccb = _load("cc_backtest", "cc-backtest.py")
    basis = {k.upper(): float(v) for k, v in (b.split("=", 1) for b in a.basis)}
    fit_ctx, pv = None, a.portfolio_value
    if not a.no_portfolio and (ROOT / "portfolio" / "accounts").exists():
        pl = _load("plan_lint", "plan-lint.py")
        details = pl.load_account_details()
        total = sum(float(v["total_value"] or 0) for v in pl.cc.load_accounts().values())
        fit_ctx = (details, total, pl.research_info, pl.allowed_option_kinds)
        pv = pv or total

    results = []
    for t in a.tickers:
        try:
            results.append(analyze(t.upper(), os_mod, ccb, a, basis.get(t.upper()), fit_ctx, pv))
        except SystemExit as e:
            print(f"{t}: {e}", file=sys.stderr)
    print(json.dumps(results, indent=2, default=str) if a.json else render(results, a))


if __name__ == "__main__":
    main()
