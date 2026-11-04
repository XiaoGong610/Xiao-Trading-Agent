#!/usr/bin/env python3
"""
Option scores: CC Sharpe, CSP Score and the LEAP gate, computed from live data.

Implements the formulas in knowledge/strategies/when-to-cc.md, when-to-csp.md and
when-to-leaps.md so they don't have to be worked out by hand.

Usage:
    .venv/bin/python3 scripts/option-scores.py AAPL --cc                    # scan calls, 20-50 DTE
    .venv/bin/python3 scripts/option-scores.py AAPL --cc --strike 300 --expiry 2026-12-18 --cost-basis 200
    .venv/bin/python3 scripts/option-scores.py MSFT --csp                   # scan puts, 20-50 DTE
    .venv/bin/python3 scripts/option-scores.py MSFT --csp --strike 400 --expiry 2026-12-18
    .venv/bin/python3 scripts/option-scores.py AAPL --leap                  # IV gate + candidate calls
    .venv/bin/python3 scripts/option-scores.py AAPL --cc --iv-rank 42       # IV Rank from Barchart etc.
    add --json for JSON output, --earnings YYYY-MM-DD to override the earnings date

Inputs and where they come from:
  IV           ATM implied vol of the expiry closest to 30 DTE (call/put average).
  RV           20-day close-to-close realized vol, annualized. The knowledge docs used to
               compare IV with ATR%, but ATR% is a daily number and IV is annual, so that
               comparison always showed an edge.
  IV Rank      in priority order: --iv-rank, then real IV Rank from the daily log in
               research/iv-history/TICKER.csv once it has >= 120 days, else an estimate
               from the stock's 1-year range of 30-day realized vol (labelled "estimate").
               Every run appends today's IV to the log.
  Earnings     --earnings, else yfinance calendar, else research frontmatter next_earnings.
"""

import argparse
import csv
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
IV_LOG_DIR = ROOT / "research" / "iv-history"
RESEARCH_DIR = ROOT / "research" / "stocks"
RISK_FREE = 0.04
IV_LOG_MIN_DAYS = 120


# ---------------------------------------------------------------- math helpers

def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_delta(spot, strike, years, iv, kind):
    if years <= 0 or iv <= 0:
        return None
    d1 = (math.log(spot / strike) + (RISK_FREE + iv * iv / 2) * years) / (iv * math.sqrt(years))
    return norm_cdf(d1) if kind == "call" else norm_cdf(d1) - 1


def step(value, bands):
    """bands: [(upper_bound_exclusive, score), ...] ascending; last bound may be inf."""
    for bound, score in bands:
        if value < bound:
            return score
    return bands[-1][1]


def mid_price(row):
    bid, ask, last = row.get("bid") or 0, row.get("ask") or 0, row.get("lastPrice") or 0
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    return round(last, 2)


# ---------------------------------------------------------------- market data

class Market:
    def __init__(self, ticker, iv_rank_override=None, earnings_override=None):
        self.ticker = ticker.upper()
        self.stock = yf.Ticker(self.ticker)
        hist = self.stock.history(period="1y")
        if hist.empty:
            raise SystemExit(f"No price data for {self.ticker}")
        self.hist = hist
        self.price = round(float(hist["Close"].iloc[-1]), 2)
        self.today = date.today()
        self.expiries = list(self.stock.options or [])
        if not self.expiries:
            raise SystemExit(f"No listed options for {self.ticker}")
        self._chains = {}

        logret = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
        self.rv20 = round(float(logret.tail(20).std() * math.sqrt(252) * 100), 1)
        hv30 = (logret.rolling(30).std() * math.sqrt(252) * 100).dropna()
        self.hv_min, self.hv_max = float(hv30.min()), float(hv30.max())

        self.iv30, self.iv30_expiry = self._atm_iv_near(30)
        self.iv_rank, self.iv_rank_source = self._iv_rank(iv_rank_override)
        self.earnings, self.earnings_source = self._earnings(earnings_override)
        self.supports, self.hvn, self.sma50, self.sma200 = self._levels()

    def dte(self, expiry):
        return (datetime.strptime(expiry, "%Y-%m-%d").date() - self.today).days

    def chain(self, expiry):
        if expiry not in self._chains:
            c = self.stock.option_chain(expiry)
            self._chains[expiry] = (c.calls, c.puts)
        return self._chains[expiry]

    def _atm_iv_near(self, target_dte):
        usable = [e for e in self.expiries if self.dte(e) >= 7]
        expiry = min(usable or self.expiries, key=lambda e: abs(self.dte(e) - target_dte))
        calls, puts = self.chain(expiry)
        ivs = []
        for df in (calls, puts):
            df = df[df["impliedVolatility"] > 0.01]
            if not df.empty:
                i = (df["strike"] - self.price).abs().idxmin()
                ivs.append(float(df.loc[i, "impliedVolatility"]))
        iv = round(sum(ivs) / len(ivs) * 100, 1) if ivs else None
        return iv, expiry

    def _iv_rank(self, override):
        self._log_iv()
        if override is not None:
            return float(override), "user-supplied"
        rows = self._read_iv_log()
        if len(rows) >= IV_LOG_MIN_DAYS:
            ivs = [r for r in rows[-252:]]
            lo, hi = min(ivs), max(ivs)
            if hi > lo:
                return round((self.iv30 - lo) / (hi - lo) * 100, 1), f"IV log ({len(ivs)} days)"
        if self.iv30 is None or self.hv_max <= self.hv_min:
            return None, "unavailable"
        est = (self.iv30 - self.hv_min) / (self.hv_max - self.hv_min) * 100
        return round(min(100.0, max(0.0, est)), 1), "estimate (IV vs 1y realized-vol range)"

    def _read_iv_log(self):
        f = IV_LOG_DIR / f"{self.ticker}.csv"
        if not f.exists():
            return []
        with f.open() as fh:
            return [float(r["iv30"]) for r in csv.DictReader(fh) if r.get("iv30")]

    def _log_iv(self):
        if self.iv30 is None or not (ROOT / "research").exists():
            return
        IV_LOG_DIR.mkdir(exist_ok=True)
        f = IV_LOG_DIR / f"{self.ticker}.csv"
        today = self.today.isoformat()
        if f.exists() and today in f.read_text():
            return
        new = not f.exists()
        with f.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["date", "iv30", "expiry", "price"])
            w.writerow([today, self.iv30, self.iv30_expiry, self.price])

    def _earnings(self, override):
        if override:
            return datetime.strptime(override, "%Y-%m-%d").date(), "user-supplied"
        try:
            cal = self.stock.calendar
            dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else []
            future = sorted(d for d in dates if d >= self.today)
            if future:
                return future[0], "yfinance calendar"
        except Exception:
            pass
        f = RESEARCH_DIR / f"{self.ticker}.md"
        if f.exists():
            m = re.search(r"^next_earnings:\s*\"?(\d{4}-\d{2}-\d{2})", f.read_text(), re.MULTILINE)
            if m:
                d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                if d >= self.today:
                    return d, "research frontmatter"
        return None, "unknown"

    def _levels(self):
        h = self.hist.tail(126)
        lows = []
        for i in range(2, len(h) - 2):
            lo = h["Low"].iloc[i]
            if lo == h["Low"].iloc[i - 2:i + 3].min():
                lows.append(round(float(lo), 2))
        supports = sorted({s for s in lows if s < self.price}, reverse=True)[:4]
        # Volume shelf: price bin with the most volume over 6 months
        bins = np.linspace(h["Low"].min(), h["High"].max(), 11)
        typical = (h["High"] + h["Low"] + h["Close"]) / 3
        vol = [h["Volume"][(typical >= bins[i]) & (typical < bins[i + 1])].sum() for i in range(10)]
        k = int(np.argmax(vol))
        hvn = round(float((bins[k] + bins[k + 1]) / 2), 2)
        close = self.hist["Close"]
        sma50 = round(float(close.tail(50).mean()), 2)
        sma200 = round(float(close.tail(200).mean()), 2) if len(close) >= 200 else None
        return supports, hvn, sma50, sma200


# ---------------------------------------------------------------- shared components

def edge_score(m):
    """IV vs 20-day realized vol: IV < 0.9×RV = 0, within ±10% = 50, IV > 1.1×RV = 100."""
    if m.iv30 is None or not m.rv20:
        return 50
    ratio = m.iv30 / m.rv20
    return 0 if ratio < 0.9 else 100 if ratio > 1.1 else 50


def earnings_gate(m, expiry):
    """Graded earnings gate (when-to-cc.md / when-to-csp.md).

    Earnings inside the trade: < 7 days before expiry = 0, 7+ days before = 25.
    Earnings after expiry: 0-7 days after = 50, 8-30 days after = 75, later = 100.
    Unknown date = 50 (flagged).
    """
    if m.earnings is None:
        return 50, "earnings date unknown"
    exp = datetime.strptime(expiry, "%Y-%m-%d").date()
    gap = (exp - m.earnings).days
    if m.earnings <= exp:
        return (0 if gap < 7 else 25), f"earnings {m.earnings} is {gap}d before expiry"
    after = -gap
    if after <= 7:
        return 50, f"earnings {m.earnings} is {after}d after expiry"
    if after <= 30:
        return 75, f"earnings {after}d after expiry"
    return 100, "no earnings near the trade"


def support_score(m, strike):
    """Strike location: at the volume shelf = 100, at a support/SMA = 75,
    below support = 40, above the nearest support = 20 (within 2% counts as 'at')."""
    near = lambda level: level and abs(strike - level) / strike <= 0.02
    if near(m.hvn):
        return 100, f"at volume shelf ${m.hvn}"
    levels = [s for s in m.supports] + [x for x in (m.sma50, m.sma200) if x]
    for lvl in levels:
        if near(lvl):
            return 75, f"at support ${lvl}"
    nearest = max((s for s in m.supports if s < m.price), default=None)
    if nearest and strike < nearest:
        return 40, f"below support ${nearest}"
    return 20, "above nearest support" if nearest else "no support found"


def contract(m, expiry, strike, kind):
    calls, puts = m.chain(expiry)
    df = calls if kind == "call" else puts
    rows = df[(df["strike"] - strike).abs() < 1e-6]
    if rows.empty:
        near = df.iloc[(df["strike"] - strike).abs().argsort()[:3]]["strike"].tolist()
        raise SystemExit(f"No {kind} at ${strike} for {expiry}. Nearest strikes: {near}")
    row = rows.iloc[0].to_dict()
    return row


def candidates(m, kind, dte_lo=20, dte_hi=50, delta_lo=0.10, delta_hi=0.35):
    out = []
    for e in m.expiries:
        d = m.dte(e)
        if not dte_lo <= d <= dte_hi:
            continue
        calls, puts = m.chain(e)
        df = calls if kind == "call" else puts
        for row in df.to_dict("records"):
            if not (row.get("bid") or 0) > 0:
                continue
            delta = bs_delta(m.price, row["strike"], d / 365, row.get("impliedVolatility") or 0, kind)
            if delta is not None and delta_lo <= abs(delta) <= delta_hi:
                out.append((e, row))
    return out


# ---------------------------------------------------------------- scores

def score_cc(m, expiry, row, cost_basis=None):
    strike, d = float(row["strike"]), m.dte(expiry)
    prem = mid_price(row)
    ann_yield = prem / m.price * (365 / max(d, 1)) * 100
    yield_30 = prem / m.price * (30 / max(d, 1)) * 100
    ivr = m.iv_rank if m.iv_rank is not None else 0
    y_score = step(ann_yield, [(8, 20), (12, 50), (20, 75), (math.inf, 100)])
    e_score = edge_score(m)
    eg, eg_note = earnings_gate(m, expiry)
    score = ivr * 0.35 + y_score * 0.35 + e_score * 0.15 + eg * 0.15

    gates = {}
    gates["1 IV Rank"] = ("PASS" if ivr > 50 else
                          ("PASS (marginal: 30-day yield > 1.5%)" if ivr >= 25 and yield_30 > 1.5 else "FAIL"))
    gates["2 Yield >= 8% ann"] = "PASS" if ann_yield >= 8 else "FAIL"
    gates["3 IV vs RV"] = "FAIL" if e_score == 0 else ("PASS" if e_score == 100 else "NEUTRAL")
    if cost_basis is not None:
        gates["4 Strike >= cost basis"] = "PASS" if strike >= cost_basis else "FAIL"
    else:
        gates["4 Happy to sell at strike"] = "CHECK (pass --cost-basis)"
    failed = [g for g, v in gates.items() if v.startswith("FAIL")]
    verdict = ("DON'T SELL (gate " + ", ".join(g.split()[0] for g in failed) + " failed)" if failed else
               "SELL CC" if score > 60 else "MARGINAL" if score >= 40 else "DON'T SELL")
    return {
        "type": "CC", "expiry": expiry, "dte": d, "strike": strike, "premium": prem,
        "delta": round(bs_delta(m.price, strike, d / 365, row.get("impliedVolatility") or 0, "call") or 0, 2),
        "otm_pct": round((strike - m.price) / m.price * 100, 1),
        "ann_yield": round(ann_yield, 1),
        "components": {"iv_rank": ivr, "yield": y_score, "iv_vs_rv": e_score, "earnings": eg},
        "earnings_note": eg_note, "gates": gates,
        "score": round(score, 1), "verdict": verdict,
    }


def score_csp(m, expiry, row):
    strike, d = float(row["strike"]), m.dte(expiry)
    prem = mid_price(row)
    ann_yield = prem / strike * (365 / max(d, 1)) * 100
    breakeven = strike - prem
    buffer = (m.price - breakeven) / m.price * 100
    ivr = m.iv_rank if m.iv_rank is not None else 0
    y_score = step(ann_yield, [(12, 20), (20, 40), (35, 65), (50, 85), (math.inf, 100)])
    b_score = step(buffer, [(5, 15), (8, 35), (12, 60), (18, 85), (math.inf, 100)])
    s_score, s_note = support_score(m, strike)
    e_score = edge_score(m)
    eg, eg_note = earnings_gate(m, expiry)
    score = (ivr * 0.20 + e_score * 0.10 + y_score * 0.25 + b_score * 0.20
             + s_score * 0.10 + eg * 0.15)
    verdict = "SELL CSP" if score > 65 else "MARGINAL" if score >= 45 else "SKIP"
    return {
        "type": "CSP", "expiry": expiry, "dte": d, "strike": strike, "premium": prem,
        "delta": round(bs_delta(m.price, strike, d / 365, row.get("impliedVolatility") or 0, "put") or 0, 2),
        "collateral": round(strike * 100), "breakeven": round(breakeven, 2),
        "buffer_pct": round(buffer, 1), "ann_yield": round(ann_yield, 1),
        "components": {"iv_rank": ivr, "vrp_edge": e_score, "yield": y_score, "buffer": b_score,
                       "support": s_score, "earnings": eg},
        "support_note": s_note, "earnings_note": eg_note,
        "score": round(score, 1), "verdict": verdict,
    }


def leap_gate(m):
    gates = {}
    ivr = m.iv_rank
    gates["IV Rank < 30"] = "UNKNOWN" if ivr is None else ("PASS" if ivr < 30 else "FAIL")
    if m.earnings is None:
        gates["No earnings within 14 days"] = "UNKNOWN"
    else:
        days = (m.earnings - m.today).days
        gates["No earnings within 14 days"] = "PASS" if days > 14 else f"FAIL (earnings in {days}d)"
    failed = [g for g, v in gates.items() if v.startswith("FAIL")]
    verdict = "WAIT: " + "; ".join(failed) if failed else ("BUY OK" if all(v == "PASS" for v in gates.values())
                                                          else "CHECK: missing data")
    return gates, verdict


def score_leap(m, expiry, row):
    strike, d = float(row["strike"]), m.dte(expiry)
    prem = mid_price(row)
    return {
        "type": "LEAP", "expiry": expiry, "dte": d, "strike": strike, "premium": prem,
        "delta": round(bs_delta(m.price, strike, d / 365, row.get("impliedVolatility") or 0, "call") or 0, 2),
        "contract_cost": round(prem * 100), "breakeven": round(strike + prem, 2),
        "breakeven_pct": round((strike + prem - m.price) / m.price * 100, 1),
        "contract_iv": round((row.get("impliedVolatility") or 0) * 100, 1),
    }


# ---------------------------------------------------------------- output

def header(m):
    return {
        "ticker": m.ticker, "price": m.price,
        "iv30": m.iv30, "iv30_expiry": m.iv30_expiry, "rv20": m.rv20,
        "iv_rank": m.iv_rank, "iv_rank_source": m.iv_rank_source,
        "earnings": m.earnings.isoformat() if m.earnings else None, "earnings_source": m.earnings_source,
        "supports": m.supports, "volume_shelf": m.hvn, "sma50": m.sma50, "sma200": m.sma200,
    }


def print_header(h):
    print(f"\n{h['ticker']} ${h['price']}   IV30 {h['iv30']}% ({h['iv30_expiry']})   RV20 {h['rv20']}%   "
          f"IV Rank {h['iv_rank']} [{h['iv_rank_source']}]")
    print(f"  Earnings {h['earnings'] or 'unknown'} [{h['earnings_source']}]   Supports {h['supports']}   "
          f"Volume shelf ${h['volume_shelf']}   SMA50 ${h['sma50']}   SMA200 ${h['sma200']}")
    if h["iv_rank_source"].startswith("estimate"):
        print("  IV Rank is an estimate. For a real value pass --iv-rank (e.g. from Barchart); "
              "the daily IV log takes over after 120 days.")


def print_scored(items, kind):
    if kind == "CC":
        print(f"\n  {'Expiry':<11}{'DTE':>4}{'Strike':>9}{'OTM%':>6}{'Delta':>6}{'Prem':>7}{'Ann%':>6}"
              f"{'IVR':>5}{'Yld':>4}{'Edge':>5}{'Earn':>5}{'Score':>7}  Verdict")
        for s in items:
            c = s["components"]
            print(f"  {s['expiry']:<11}{s['dte']:>4}{s['strike']:>9.1f}{s['otm_pct']:>6.1f}{s['delta']:>6.2f}"
                  f"{s['premium']:>7.2f}{s['ann_yield']:>6.1f}{c['iv_rank']:>5.0f}{c['yield']:>4}{c['iv_vs_rv']:>5}"
                  f"{c['earnings']:>5}{s['score']:>7.1f}  {s['verdict']}")
    else:
        print(f"\n  {'Expiry':<11}{'DTE':>4}{'Strike':>9}{'Delta':>6}{'Prem':>7}{'Ann%':>6}{'Buf%':>6}"
              f"{'IVR':>5}{'VRP':>4}{'Yld':>4}{'Buf':>4}{'Sup':>4}{'Earn':>5}{'Score':>7}  Verdict")
        for s in items:
            c = s["components"]
            print(f"  {s['expiry']:<11}{s['dte']:>4}{s['strike']:>9.1f}{s['delta']:>6.2f}{s['premium']:>7.2f}"
                  f"{s['ann_yield']:>6.1f}{s['buffer_pct']:>6.1f}{c['iv_rank']:>5.0f}{c['vrp_edge']:>4}{c['yield']:>4}"
                  f"{c['buffer']:>4}{c['support']:>4}{c['earnings']:>5}{s['score']:>7.1f}  {s['verdict']}")
    if len(items) == 1:
        s = items[0]
        print(f"\n  {s['earnings_note']}" + (f"; {s['support_note']}" if "support_note" in s else ""))
        if "gates" in s:
            for g, v in s["gates"].items():
                print(f"  Gate {g}: {v}")
        if "collateral" in s:
            print(f"  Collateral ${s['collateral']:,}  Breakeven ${s['breakeven']}")


def main():
    p = argparse.ArgumentParser(description="CC Sharpe, CSP Score and LEAP gate from live data")
    p.add_argument("ticker")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cc", action="store_true", help="Covered call (CC Sharpe Score)")
    mode.add_argument("--csp", action="store_true", help="Cash-secured put (CSP Score)")
    mode.add_argument("--leap", action="store_true", help="LEAP call gate + candidates")
    p.add_argument("--strike", type=float, help="Score one contract (needs --expiry)")
    p.add_argument("--expiry", help="YYYY-MM-DD")
    p.add_argument("--cost-basis", type=float, help="CC gate 4: strike must be >= cost basis")
    p.add_argument("--iv-rank", type=float, help="Override IV Rank (0-100), e.g. from Barchart")
    p.add_argument("--earnings", help="Override next earnings date YYYY-MM-DD")
    p.add_argument("--top", type=int, default=8, help="Rows to show when scanning (default 8)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if a.strike is not None and not a.expiry:
        p.error("--strike needs --expiry")

    m = Market(a.ticker, a.iv_rank, a.earnings)
    out = header(m)

    if a.leap:
        gates, verdict = leap_gate(m)
        out.update({"leap_gates": gates, "leap_verdict": verdict})
        if a.strike is not None:
            items = [score_leap(m, a.expiry, contract(m, a.expiry, a.strike, "call"))]
        else:
            far = [e for e in m.expiries if m.dte(e) >= 270]
            items = []
            if far:
                # The second LEAP expiry past 270 DTE: more time than the first, more liquid than the furthest.
                far.sort(key=m.dte)
                e = far[min(1, len(far) - 1)]
                for row in m.chain(e)[0].to_dict("records"):
                    dl = bs_delta(m.price, row["strike"], m.dte(e) / 365, row.get("impliedVolatility") or 0, "call")
                    if dl and 0.40 <= dl <= 0.80 and (row.get("bid") or 0) > 0:
                        items.append(score_leap(m, e, row))
        out["contracts"] = items[: a.top] if a.strike is None else items
    else:
        kind, scorer = ("call", score_cc) if a.cc else ("put", score_csp)
        if a.strike is not None:
            rows = [(a.expiry, contract(m, a.expiry, a.strike, kind))]
        else:
            rows = candidates(m, kind)
        if a.cc:
            items = [score_cc(m, e, r, a.cost_basis) for e, r in rows]
        else:
            items = [score_csp(m, e, r) for e, r in rows]
        # Ties (yield bands saturate) go to the further-OTM strike: more upside kept.
        items.sort(key=lambda s: (-s["score"], -abs(s["strike"] - m.price)))
        out["contracts"] = items if a.strike is not None else items[: a.top]

    if a.json:
        print(json.dumps(out, indent=2, default=str))
        return

    print_header(out)
    if a.leap:
        print(f"\n  LEAP gate: {out['leap_verdict']}")
        for g, v in out["leap_gates"].items():
            print(f"    {g}: {v}")
        if out["contracts"]:
            print(f"\n  {'Expiry':<11}{'DTE':>5}{'Strike':>9}{'Delta':>6}{'Prem':>8}{'Cost':>8}{'B/E':>9}{'B/E%':>6}{'IV':>6}")
            for s in out["contracts"]:
                print(f"  {s['expiry']:<11}{s['dte']:>5}{s['strike']:>9.1f}{s['delta']:>6.2f}{s['premium']:>8.2f}"
                      f"{s['contract_cost']:>8,}{s['breakeven']:>9.2f}{s['breakeven_pct']:>6.1f}{s['contract_iv']:>6.1f}")
    elif not out["contracts"]:
        print("\n  No contracts with a bid at 0.10-0.35 delta in 20-50 DTE.")
    else:
        print_scored(out["contracts"], "CC" if a.cc else "CSP")
    print()


if __name__ == "__main__":
    main()
