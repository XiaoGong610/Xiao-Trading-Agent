#!/usr/bin/env python3
"""
Covered-call backtest: buy-and-write vs buy-and-hold, per underlying, over history.

"If I had held TICKER and sold a ~0.20-delta call every ~30 trading days since START,
what would total return, drawdown and the cost of being called away have looked like?"

Method (same pricing approach as cc-ladder-backtest.py):
  - daily closes from yfinance (auto-adjusted)
  - every DTE trading days, sell 1 call per 100 shares at the strike whose Black-Scholes
    delta = DELTA, priced with trailing 30-day realized vol x VRP (implied usually > realized)
  - at expiry the call settles at intrinsic (shares are kept; an ITM call costs its intrinsic)
  - premium is kept as cash (not reinvested); results are per share, relative to the start price

Limitations: model prices (no real bid/ask or skew), no earnings avoidance, no early
assignment, no dividends on cash, no taxes. Use it to compare underlyings and settings,
not to forecast exact income.

Modes:
  buywrite    (default) per-ticker buy-write vs buy-hold summary
  structures  the ladder comparison from cc-ladder-backtest.py for the given tickers

Usage:
    .venv/bin/python3 scripts/cc-backtest.py GOOG AMZN TSLA QQQ
    .venv/bin/python3 scripts/cc-backtest.py GOOG AMZN --start 2018-01-01 --delta 0.15 --dte 21
    .venv/bin/python3 scripts/cc-backtest.py TSLA --mode structures
    .venv/bin/python3 scripts/cc-backtest.py GOOG --json
"""

import argparse
import importlib.util
import json
from math import exp, log, sqrt
from pathlib import Path

import numpy as np
from scipy.stats import norm

R = 0.04


def bs_call(S, K, T, vol, r=R):
    if T <= 0 or vol <= 0:
        return max(S - K, 0.0)
    d1 = (log(S / K) + (r + vol * vol / 2) * T) / (vol * sqrt(T))
    d2 = d1 - vol * sqrt(T)
    return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)


def call_delta(S, K, T, vol, r=R):
    d1 = (log(S / K) + (r + vol * vol / 2) * T) / (vol * sqrt(T))
    return norm.cdf(d1)


def strike_for_delta(S, T, vol, delta, r=R):
    """Strike whose BS call delta equals `delta` (closed form via d1)."""
    d1 = norm.ppf(delta)
    return S * exp(-(d1 * vol * sqrt(T)) + (r + vol * vol / 2) * T)


def realized_vol(prices, window=30):
    lr = np.diff(np.log(prices))
    out = np.full(len(prices), np.nan)
    for i in range(window, len(prices)):
        out[i] = lr[i - window:i].std(ddof=1) * sqrt(252)
    return out


def simulate_buywrite(prices, vols=None, dte=30, delta=0.20, vrp=1.15, start=30):
    """Pure simulation on a price array (testable). Returns metrics + equity series."""
    p = np.asarray(prices, dtype=float)
    v = realized_vol(p) if vols is None else np.asarray(vols, dtype=float)
    cash, cycles = 0.0, []
    eq_bw, eq_bh, t = [p[start]], [p[start]], start
    while t + dte < len(p):
        S, vol = p[t], v[t] * vrp
        if not np.isfinite(vol) or vol <= 0:
            t += dte
            continue
        T = dte / 252
        K = strike_for_delta(S, T, vol, delta)
        prem = bs_call(S, K, T, vol)
        e = t + dte
        payoff = max(p[e] - K, 0.0)
        cash += prem - payoff
        cycles.append({"start": t, "S": S, "K": K, "prem": prem, "payoff": payoff,
                       "ret_stock": p[e] / S - 1, "called": payoff > 0})
        eq_bw.append(p[e] + cash)
        eq_bh.append(p[e])
        t = e
    s0 = p[start]
    end_i = cycles[-1]["start"] + dte if cycles else start
    eq_bw, eq_bh = np.array(eq_bw), np.array(eq_bh)
    years = max((end_i - start) / 252, 1e-9)

    def mdd(eq):
        peak = np.maximum.accumulate(eq)
        return float(((eq - peak) / peak).min() * 100)

    def cagr(end):
        return ((end / s0) ** (1 / years) - 1) * 100 if end > 0 else -100.0

    n = len(cycles)
    called = [c for c in cycles if c["called"]]
    return {
        "cycles": n,
        "years": round(years, 1),
        "bh_total_pct": round((eq_bh[-1] / s0 - 1) * 100, 1),
        "bw_total_pct": round((eq_bw[-1] / s0 - 1) * 100, 1),
        "bh_cagr_pct": round(cagr(eq_bh[-1]), 1),
        "bw_cagr_pct": round(cagr(eq_bw[-1]), 1),
        "bh_maxdd_pct": round(mdd(eq_bh), 1),
        "bw_maxdd_pct": round(mdd(eq_bw), 1),
        "premium_yield_ann_pct": round(float(np.mean([c["prem"] / c["S"] for c in cycles]) * 252 / dte * 100), 1) if n else 0.0,
        "called_pct": round(len(called) / n * 100, 1) if n else 0.0,
        "avg_cost_when_called_pct": round(float(np.mean([c["payoff"] / c["S"] for c in called]) * 100), 1) if called else 0.0,
        "worst_cycle_cost_pct": round(max((c["payoff"] - c["prem"]) / c["S"] for c in cycles) * 100, 1) if n else 0.0,
        "cycle_win_pct": round(sum(1 for c in cycles if c["prem"] >= c["payoff"]) / n * 100, 1) if n else 0.0,
        "cagr_uplift_pct": round(cagr(eq_bw[-1]) - cagr(eq_bh[-1]), 1),
        **rolling_1y(eq_bw, eq_bh, dte),
        "_equity_bw": eq_bw, "_equity_bh": eq_bh,
    }


def rolling_1y(eq_bw, eq_bh, dte):
    """Rolling ~1-year windows (cycle ends): how often buy-write beat holding, and by how much."""
    k = max(1, round(252 / dte))
    if len(eq_bw) <= k:
        return {"windows_1y": 0, "beat_hold_1y_pct": None, "median_1y_uplift_pts": None,
                "uplift_1y_up_markets_pts": None, "uplift_1y_down_markets_pts": None}
    bw = eq_bw[k:] / eq_bw[:-k] - 1
    bh = eq_bh[k:] / eq_bh[:-k] - 1
    diff = (bw - bh) * 100
    up, down = diff[bh > 0.15], diff[bh < 0]
    return {"windows_1y": int(len(diff)),
            "beat_hold_1y_pct": round(float((diff > 0).mean() * 100), 1),
            "median_1y_uplift_pts": round(float(np.median(diff)), 1),
            "uplift_1y_up_markets_pts": round(float(np.median(up)), 1) if len(up) else None,
            "uplift_1y_down_markets_pts": round(float(np.median(down)), 1) if len(down) else None}


def fetch(ticker, start):
    import yfinance as yf
    px = yf.Ticker(ticker).history(start=start, auto_adjust=True)["Close"].dropna()
    if len(px) < 120:
        raise ValueError(f"{ticker}: not enough history since {start} ({len(px)} days)")
    return px


def render(rows, args):
    head = (f"\nBUY-WRITE vs BUY-HOLD — {args.delta:.2f}-delta calls, {args.dte} trading-day cycles, "
            f"vol = 30d realized x {args.vrp}, since {args.start}\n")
    cols = ["Ticker", "Yrs", "Hold CAGR", "B-W CAGR", "Hold maxDD", "B-W maxDD",
            "Prem/yr", "Called", "Avg cost if called", "Worst cycle", "Cycle win"]
    lines = [head, " | ".join(cols), " | ".join("---" for _ in cols)]
    for t, r in rows:
        if isinstance(r, str):
            lines.append(f"{t} | {r}")
            continue
        lines.append(" | ".join([
            t, f"{r['years']}", f"{r['bh_cagr_pct']:+.1f}%", f"{r['bw_cagr_pct']:+.1f}%",
            f"{r['bh_maxdd_pct']:.1f}%", f"{r['bw_maxdd_pct']:.1f}%", f"{r['premium_yield_ann_pct']:.1f}%",
            f"{r['called_pct']:.0f}%", f"{r['avg_cost_when_called_pct']:.1f}%",
            f"−{r['worst_cycle_cost_pct']:.1f}%", f"{r['cycle_win_pct']:.0f}%"]))
    lines.append("\nB-W = buy-write. Premium kept as cash. Max drawdown measured at cycle ends. "
                 "Model prices; see the docstring for limitations.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Covered-call backtest per underlying")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--delta", type=float, default=0.20)
    ap.add_argument("--dte", type=int, default=30, help="trading days per cycle (21 ≈ monthly)")
    ap.add_argument("--vrp", type=float, default=1.15, help="implied/realized vol multiplier")
    ap.add_argument("--mode", choices=("buywrite", "structures"), default="buywrite")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.mode == "structures":
        spec = importlib.util.spec_from_file_location("ladder", Path(__file__).with_name("cc-ladder-backtest.py"))
        lad = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lad)
        for t in a.tickers:
            print(lad.summarize(lad.run(t.upper(), a.start), t.upper()))
        return

    rows = []
    for t in a.tickers:
        t = t.upper()
        try:
            r = simulate_buywrite(fetch(t, a.start).values, dte=a.dte, delta=a.delta, vrp=a.vrp)
            rows.append((t, r))
        except Exception as e:
            rows.append((t, f"failed: {e}"))
    if a.json:
        print(json.dumps({t: ({k: v for k, v in r.items() if not k.startswith("_")} if isinstance(r, dict) else r)
                          for t, r in rows}, indent=2))
    else:
        print(render(rows, a))


if __name__ == "__main__":
    main()
