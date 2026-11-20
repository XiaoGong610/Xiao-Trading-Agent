#!/usr/bin/env python3
"""
Covered-call backtest: buy-write vs buy-hold per underlying, with realistic-ish pricing,
your playbook's rules as testable filters, and a settings grid.

"If I had held TICKER and sold calls by these rules since START, how would total return,
drawdown and the cost of being called away compare with just holding?"

Pricing (model, not historical chains):
  - Black-Scholes; volatility = trailing 30-day realized vol x VRP (implied usually > realized)
  - skew: an OTM call's vol = base x (1 + SKEW x ln(K/S)); equity call wings usually carry
    LOWER vol than ATM, so SKEW < 0 (default -0.5) trims OTM premium a flat model overstates
  - haircut: you sell below mid and buy back above it (default 5% of the option price)
  - the open call is marked to market daily, so equity, drawdown and 1-year windows are daily
  - self-financing, like Cboe's buy-write indexes: premium is reinvested in shares, and a
    call bought back or settled in the money is paid by selling shares (no cash borrowing,
    so equity can't go negative)

Rules (each can be switched on to test whether it adds value):
  --skip-earnings     don't sell a call whose life spans an earnings date (stay uncovered)
  --skip-oversold     only sell when close > 20-day average and RSI(14) >= 35
                      (the playbook's "sell into strength"; re-checked every 5 trading days)
  --early-close 0.5   buy back once 50% of the premium is captured, then re-sell next day

Modes:
  buywrite   (default) one settings set per ticker
  grid       delta x DTE grid per ticker (which settings suit this stock?)
  rules      naive vs each rule vs all rules (do the playbook's rules help?)
  structures the ladder comparison from cc-ladder-backtest.py

Usage:
    .venv/bin/python3 scripts/cc-backtest.py GOOG AMZN TSLA QQQ
    .venv/bin/python3 scripts/cc-backtest.py GOOG --mode grid
    .venv/bin/python3 scripts/cc-backtest.py GOOG AMZN --mode rules
    .venv/bin/python3 scripts/cc-backtest.py TSLA --delta 0.15 --dte 21 --skip-oversold --early-close 0.5
    .venv/bin/python3 scripts/cc-backtest.py GOOG --skew 0 --haircut 0     # the old flat, frictionless model

Limitations: model prices (no historical chains), fixed VRP, no earnings IV spikes, no early
assignment or dividends, no taxes. Compare names, settings and rules; don't forecast income.
"""

import argparse
import importlib.util
import json
from math import exp, log, sqrt
from pathlib import Path

import numpy as np
from scipy.stats import norm

R = 0.04
DTE_GRID = (5, 15, 21, 30)            # trading days: ~weekly, ~3 weeks, ~monthly, ~6 weeks
DELTA_GRID = (0.15, 0.20, 0.30, 0.50)  # 0.50 ~ at the money


# ---------------------------------------------------------------- pricing

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


def skewed_vol(base, S, K, skew):
    """Vol at strike K: base x (1 + skew x ln(K/S)), floored at 30% of base."""
    return max(base * (1 + skew * log(K / S)), 0.3 * base)


# ---------------------------------------------------------------- indicators

def realized_vol(prices, window=30):
    lr = np.diff(np.log(prices))
    out = np.full(len(prices), np.nan)
    for i in range(window, len(prices)):
        out[i] = lr[i - window:i].std(ddof=1) * sqrt(252)
    return out


def sma(prices, n=20):
    out = np.full(len(prices), np.nan)
    c = np.cumsum(np.r_[0.0, prices])
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def rsi(prices, n=14):
    d = np.diff(prices)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    out = np.full(len(prices), np.nan)
    if len(d) < n:
        return out
    au, ad = up[:n].mean(), dn[:n].mean()
    for i in range(n, len(prices)):
        if i > n:
            au = (au * (n - 1) + up[i - 1]) / n
            ad = (ad * (n - 1) + dn[i - 1]) / n
        out[i] = 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)
    return out


# ---------------------------------------------------------------- simulation

def simulate_buywrite(prices, vols=None, dte=30, delta=0.20, vrp=1.15, start=30,
                      skew=-0.5, haircut=0.05, skip_earnings=False, earnings_idx=None,
                      skip_oversold=False, early_close=None, recheck=5):
    """Day-by-day, self-financing simulation on a price array (pure, testable). Starts with 1 share;
    premium buys more shares, option losses sell shares. Returns metrics (+ daily equity under _keys)."""
    p = np.asarray(prices, dtype=float)
    n = len(p)
    v = realized_vol(p) if vols is None else np.asarray(vols, dtype=float)
    ma20 = sma(p, 20) if skip_oversold else None
    rs = rsi(p, 14) if skip_oversold else None
    earn = np.sort(np.asarray(earnings_idx if earnings_idx is not None else [], dtype=int))

    def vol_at(d, K):
        base = v[d] * vrp
        return skewed_vol(base, p[d], K, skew) if np.isfinite(base) and base > 0 else None

    def allowed(d):
        if not np.isfinite(v[d]) or v[d] <= 0 or d + dte >= n:
            return False
        if skip_oversold and not (np.isfinite(ma20[d]) and p[d] > ma20[d] and np.isfinite(rs[d]) and rs[d] >= 35):
            return False
        if skip_earnings and len(earn) and np.any((earn > d) & (earn <= d + dte)):
            return False
        return True

    units, call, cycles = 1.0, None, []
    covered_days = 0
    eq_bw, eq_bh = np.empty(n - start), np.empty(n - start)
    next_check = start
    for d in range(start, n):
        if call is not None:                       # settle or manage the open call
            if d >= call["exp"]:
                payoff = max(p[d] - call["K"], 0.0)
                units -= call["n"] * payoff / p[d]
                cycles.append({**call, "payoff": payoff, "called": payoff > 0, "early": False})
                call = None
                next_check = d
            elif early_close:
                T = (call["exp"] - d) / 252
                vol = vol_at(d, call["K"])
                val = bs_call(p[d], call["K"], T, vol) if vol else None
                if val is not None and val <= (1 - early_close) * call["prem"]:
                    cost = val * (1 + haircut)
                    units -= call["n"] * cost / p[d]
                    cycles.append({**call, "payoff": cost, "called": False, "early": True})
                    call = None
                    next_check = d + 1
        if call is None and d >= next_check:
            if allowed(d):
                T = dte / 252
                base = v[d] * vrp
                K = strike_for_delta(p[d], T, base, delta)
                prem = bs_call(p[d], K, T, skewed_vol(base, p[d], K, skew)) * (1 - haircut)
                n_cov = units                              # one call per share held
                units += n_cov * prem / p[d]               # reinvest premium
                call = {"start": d, "exp": d + dte, "S": p[d], "K": K, "prem": prem, "n": n_cov}
            else:
                next_check = d + recheck
        mtm = 0.0
        if call is not None:
            covered_days += 1
            T = max((call["exp"] - d) / 252, 0.0)
            vol = vol_at(d, call["K"])
            mtm = bs_call(p[d], call["K"], T, vol) if vol else max(p[d] - call["K"], 0.0)
        eq_bw[d - start] = units * p[d] - (call["n"] * mtm if call is not None else 0.0)
        eq_bh[d - start] = p[d]

    s0 = p[start]
    years = max((n - 1 - start) / 252, 1e-9)

    def mdd(eq):
        peak = np.maximum.accumulate(eq)
        return float(((eq - peak) / peak).min() * 100)

    def cagr(end):
        return ((end / s0) ** (1 / years) - 1) * 100 if end > 0 else -100.0

    k = len(cycles)
    called = [c for c in cycles if c["called"]]
    out = {
        "cycles": k,
        "years": round(years, 1),
        "settings": {"delta": delta, "dte": dte, "vrp": vrp, "skew": skew, "haircut": haircut,
                     "skip_earnings": skip_earnings, "skip_oversold": skip_oversold, "early_close": early_close},
        "coverage_pct": round(covered_days / max(n - start, 1) * 100, 1),
        "bh_total_pct": round((eq_bh[-1] / s0 - 1) * 100, 1) if n > start else 0.0,
        "bw_total_pct": round((eq_bw[-1] / s0 - 1) * 100, 1) if n > start else 0.0,
        "bh_cagr_pct": round(cagr(eq_bh[-1]), 1) if n > start else 0.0,
        "bw_cagr_pct": round(cagr(eq_bw[-1]), 1) if n > start else 0.0,
        "bh_maxdd_pct": round(mdd(eq_bh), 1) if n > start else 0.0,
        "bw_maxdd_pct": round(mdd(eq_bw), 1) if n > start else 0.0,
        "premium_yield_ann_pct": round(sum(c["prem"] / c["S"] for c in cycles) / years * 100, 1) if k else 0.0,
        "called_pct": round(len(called) / k * 100, 1) if k else 0.0,
        "early_closed_pct": round(sum(1 for c in cycles if c["early"]) / k * 100, 1) if k else 0.0,
        "avg_cost_when_called_pct": round(float(np.mean([c["payoff"] / c["S"] for c in called])) * 100, 1) if called else 0.0,
        "worst_cycle_cost_pct": round(max((c["payoff"] - c["prem"]) / c["S"] for c in cycles) * 100, 1) if k else 0.0,
        "cycle_win_pct": round(sum(1 for c in cycles if c["prem"] >= c["payoff"]) / k * 100, 1) if k else 0.0,
        "_equity_bw": eq_bw, "_equity_bh": eq_bh,
    }
    out["cagr_uplift_pct"] = round(out["bw_cagr_pct"] - out["bh_cagr_pct"], 1)
    out.update(rolling_1y(eq_bw, eq_bh))
    return out


def rolling_1y(eq_bw, eq_bh, window=252, step=21):
    """Rolling 1-year windows on daily equity: how often buy-write beat holding, and by how much."""
    if len(eq_bw) <= window:
        return {"windows_1y": 0, "beat_hold_1y_pct": None, "median_1y_uplift_pts": None,
                "uplift_1y_up_markets_pts": None, "uplift_1y_down_markets_pts": None}
    idx = np.arange(0, len(eq_bw) - window, step)
    bw = eq_bw[idx + window] / eq_bw[idx] - 1
    bh = eq_bh[idx + window] / eq_bh[idx] - 1
    diff = (bw - bh) * 100
    up, down = diff[bh > 0.15], diff[bh < 0]
    return {"windows_1y": int(len(diff)),
            "beat_hold_1y_pct": round(float((diff > 0).mean() * 100), 1),
            "median_1y_uplift_pts": round(float(np.median(diff)), 1),
            "uplift_1y_up_markets_pts": round(float(np.median(up)), 1) if len(up) else None,
            "uplift_1y_down_markets_pts": round(float(np.median(down)), 1) if len(down) else None}


# ---------------------------------------------------------------- data

def fetch(ticker, start):
    import yfinance as yf
    px = yf.Ticker(ticker).history(start=start, auto_adjust=True)["Close"].dropna()
    if len(px) < 120:
        raise ValueError(f"{ticker}: not enough history since {start} ({len(px)} days)")
    return px


def earnings_indices(ticker, index):
    """Past earnings dates mapped to positions in the price index (empty if unavailable)."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).get_earnings_dates(limit=100)
        dates = sorted({d.tz_localize(None).normalize() for d in df.index})
    except Exception:
        return None
    idx = index.tz_localize(None).normalize() if getattr(index, "tz", None) else index.normalize()
    pos = np.searchsorted(idx.values, np.array(dates, dtype="datetime64[ns]"))
    return [int(i) for i in pos if 0 < i < len(idx)]


# ---------------------------------------------------------------- output

def public(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


def row(label, r):
    return (f"{label:28} | {r['bw_cagr_pct']:+6.1f}% | {r['cagr_uplift_pct']:+5.1f} | {r['bw_maxdd_pct']:6.1f}% | "
            f"{r['premium_yield_ann_pct']:5.1f}% | {r['coverage_pct']:4.0f}% | {r['called_pct']:4.0f}% | "
            f"{(r['beat_hold_1y_pct'] if r['beat_hold_1y_pct'] is not None else 0):4.0f}% | "
            f"{(r['uplift_1y_up_markets_pts'] or 0):+5.1f} | {(r['uplift_1y_down_markets_pts'] or 0):+5.1f}")


HEAD = ("Variant                      |  CAGR   | +/-pts | maxDD   | Prem/y | Cov. | Call | Beat1y | Rally | Down\n"
        "---------------------------- | ------- | ------ | ------- | ------ | ---- | ---- | ------ | ----- | -----")


def main():
    ap = argparse.ArgumentParser(description="Covered-call backtest per underlying")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--delta", type=float, default=0.20)
    ap.add_argument("--dte", type=int, default=30, help="trading days per cycle (21 ≈ monthly)")
    ap.add_argument("--vrp", type=float, default=1.15, help="implied/realized vol multiplier")
    ap.add_argument("--skew", type=float, default=-0.5, help="call-wing vol slope per unit ln(K/S); 0 = flat")
    ap.add_argument("--haircut", type=float, default=0.05, help="bid/ask cost as a fraction of option price")
    ap.add_argument("--skip-earnings", action="store_true")
    ap.add_argument("--skip-oversold", action="store_true")
    ap.add_argument("--early-close", type=float, default=None, help="e.g. 0.5 = buy back at 50%% captured")
    ap.add_argument("--mode", choices=("buywrite", "grid", "rules", "structures"), default="buywrite")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.mode == "structures":
        spec = importlib.util.spec_from_file_location("ladder", Path(__file__).with_name("cc-ladder-backtest.py"))
        lad = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lad)
        for t in a.tickers:
            print(lad.summarize(lad.run(t.upper(), a.start), t.upper()))
        return

    base = dict(dte=a.dte, delta=a.delta, vrp=a.vrp, skew=a.skew, haircut=a.haircut,
                skip_earnings=a.skip_earnings, skip_oversold=a.skip_oversold, early_close=a.early_close)
    out_json, lines = {}, []
    for t in (x.upper() for x in a.tickers):
        try:
            px = fetch(t, a.start)
        except Exception as e:
            lines.append(f"\n{t}: failed: {e}")
            continue
        earn = earnings_indices(t, px.index) if (a.skip_earnings or a.mode == "rules") else None
        prices = px.values
        hold = simulate_buywrite(prices, **{**base, "skip_earnings": False, "skip_oversold": False, "early_close": None})
        lines.append(f"\n=== {t} · {hold['years']}y since {a.start} · hold CAGR {hold['bh_cagr_pct']:+.1f}%, "
                     f"maxDD {hold['bh_maxdd_pct']:.1f}% · vrp {a.vrp}, skew {a.skew}, haircut {a.haircut:.0%} ===")
        variants = []
        if a.mode == "buywrite":
            variants = [("as configured", base)]
        elif a.mode == "grid":
            variants = [(f"delta {dl:.2f} · {dt:>2} days", {**base, "delta": dl, "dte": dt})
                        for dl in DELTA_GRID for dt in DTE_GRID]
        elif a.mode == "rules":
            naive = {**base, "skip_earnings": False, "skip_oversold": False, "early_close": None}
            variants = [("naive (sell every cycle)", naive),
                        ("+ skip earnings", {**naive, "skip_earnings": True}),
                        ("+ skip oversold (strength)", {**naive, "skip_oversold": True}),
                        ("+ early close at 50%", {**naive, "early_close": 0.5}),
                        ("skip earnings + oversold", {**naive, "skip_earnings": True, "skip_oversold": True}),
                        ("all three rules", {**naive, "skip_earnings": True, "skip_oversold": True, "early_close": 0.5})]
            if earn is None:
                lines.append("  (earnings dates unavailable: 'skip earnings' variants equal naive)")
        lines.append(HEAD)
        res = {}
        for label, kw in variants:
            r = simulate_buywrite(prices, earnings_idx=earn, **kw)
            res[label] = public(r)
            lines.append(row(label, r))
        if a.mode == "grid":
            best = max(res.items(), key=lambda kv: (kv[1]["cagr_uplift_pct"] + 0.1 * (kv[1]["bw_maxdd_pct"] - kv[1]["bh_maxdd_pct"])))
            lines.append(f"Best balance of return and drawdown: {best[0]}")
        out_json[t] = {"hold": {k: hold[k] for k in ("bh_cagr_pct", "bh_maxdd_pct", "years")}, "variants": res}
    lines.append("\nCAGR / maxDD = buy-write. +/-pts = CAGR vs holding. Cov. = % of days with a call open. "
                 "Beat1y = % of rolling 1-year windows ahead of holding; Rally / Down = median 1-year uplift "
                 "when the stock rose > 15% / fell. Model prices: compare, don't forecast.")
    print(json.dumps(out_json, indent=2, default=str) if a.json else "\n".join(lines))


if __name__ == "__main__":
    main()
