"""Backtest: uniform covered calls vs strike ladder vs strike+timing ladder.

400 shares, 4 contracts, ~55 trading-day horizon (like Dec/Jan expiries).
Historical daily closes; options priced with Black-Scholes using trailing
30-day realized vol x VRP (implied usually trades above realized).
Rolling start every 5 trading days.
"""
import numpy as np, pandas as pd, yfinance as yf
from math import log, sqrt, exp
from scipy.stats import norm

R = 0.04
VRP = 1.15          # implied / realized vol ratio
H = 55              # holding period in trading days
SH = 100            # shares per contract

def bs_call(S, K, T, vol):
    if T <= 0 or vol <= 0:
        return max(S - K, 0.0)
    d1 = (log(S / K) + (R + vol * vol / 2) * T) / (vol * sqrt(T))
    d2 = d1 - vol * sqrt(T)
    return S * norm.cdf(d1) - K * exp(-R * T) * norm.cdf(d2)

def call_pnl(path, vols, t0, K, T_end):
    """Sell 1 call at day t0 expiring at T_end (index); returns premium - payoff at expiry."""
    S = path[t0]
    prem = bs_call(S, K, (T_end - t0) / 252, vols[t0] * VRP)
    payoff = max(path[T_end] - K, 0.0)
    return (prem - payoff) * SH

def run(ticker, start="2016-01-01"):
    px = yf.Ticker(ticker).history(start=start, auto_adjust=True)["Close"].dropna()
    rv = np.log(px).diff().rolling(30).std() * sqrt(252)
    p, v = px.values, rv.values
    rows = []
    for s in range(30, len(p) - H, 5):
        e = s + H
        S0, path, vols = p[s], p, v
        base = 4 * SH * (p[e] - S0)  # shares only
        # A: 4 calls at +22% now
        A = sum(call_pnl(path, vols, s, 1.22 * S0, e) for _ in range(4))
        # B: strike ladder now: +22/+34/+40/+48%
        B = sum(call_pnl(path, vols, s, k * S0, e) for k in (1.22, 1.34, 1.40, 1.48))
        # C: 2 now (+22, +34); tranche 3 (+40%) after day 8 on close >= +10%;
        #    tranche 4 (+48%) on close >= +16%. Unfilled triggers = no call.
        C = call_pnl(path, vols, s, 1.22 * S0, e) + call_pnl(path, vols, s, 1.34 * S0, e)
        for k, trig, after in ((1.40, 1.10, 8), (1.48, 1.16, 0)):
            hit = next((t for t in range(s + after, e - 10) if p[t] >= trig * S0), None)
            if hit is not None:
                C += call_pnl(path, vols, hit, k * S0, e)
        ret = p[e] / S0 - 1
        rows.append(dict(ret=ret, base=base, A=A, B=B, C=C, notional=4 * SH * S0))
    df = pd.DataFrame(rows)
    for c in "ABC":
        df[c] = df[c] / df.notional * 100   # option overlay P&L as % of position
    df["ret"] *= 100
    return df

def summarize(df, name):
    out = {"ticker": name, "n": len(df)}
    for c in "ABC":
        x = df[c]
        out[f"{c}_mean"] = x.mean()
        out[f"{c}_win%"] = (x > 0).mean() * 100
        out[f"{c}_p5"] = x.quantile(0.05)
        rally = df.ret > 30
        out[f"{c}_rally"] = x[rally].mean() if rally.any() else np.nan
        flat = df.ret.between(-10, 15)
        out[f"{c}_flat"] = x[flat].mean()
        down = df.ret < -15
        out[f"{c}_down"] = x[down].mean() if down.any() else np.nan
    out["rally%"] = (df.ret > 30).mean() * 100
    return out

if __name__ == "__main__":
    res = []
    for t, st in [("COIN", "2021-05-01"), ("CRCL", "2025-06-05"), ("TSLA", "2016-01-01"),
                  ("NVDA", "2016-01-01"), ("MU", "2016-01-01"), ("AMZN", "2016-01-01"),
                  ("MSTR", "2018-01-01"), ("HOOD", "2021-08-01")]:
        try:
            res.append(summarize(run(t, st), t))
        except Exception as ex:
            print(t, "failed", ex)
    r = pd.DataFrame(res).set_index("ticker")
    pd.set_option("display.width", 250)
    print("Overlay P&L as % of position value (vs. holding shares with no calls)\n")
    for c, lab in (("A", "A: 4x uniform +22% now"), ("B", "B: strike ladder now"), ("C", "C: strike + timing ladder")):
        print(lab)
        print(r[[f"{c}_mean", f"{c}_win%", f"{c}_p5", f"{c}_down", f"{c}_flat", f"{c}_rally"]].round(2).to_string())
        print()
    print("share of windows with a >30% rally:\n", r["rally%"].round(1).to_string())
    print("\nAVERAGE across tickers:")
    print(r.drop(columns=["n"]).mean().round(2).to_string())
