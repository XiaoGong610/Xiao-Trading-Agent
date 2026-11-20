"""cc-backtest.py: pricing helpers and buy-write behavior on synthetic price paths (no network)."""
import numpy as np
import pytest


def test_strike_for_delta_round_trip(ccb):
    S, T, vol = 100.0, 30 / 252, 0.40
    for d in (0.10, 0.20, 0.30, 0.50):
        K = ccb.strike_for_delta(S, T, vol, d)
        assert ccb.call_delta(S, K, T, vol) == pytest.approx(d, abs=1e-6)
    assert ccb.strike_for_delta(S, T, vol, 0.20) > S  # 0.20-delta call is out of the money


def path(daily_ret, n=600, s0=100.0, noise=0.0, seed=1):
    rng = np.random.default_rng(seed)
    r = daily_ret + noise * rng.standard_normal(n)
    return s0 * np.exp(np.cumsum(np.r_[0.0, r]))


def test_flat_market_buywrite_beats_hold(ccb):
    p = path(0.0, noise=0.01)  # sideways chop
    res = ccb.simulate_buywrite(p)
    assert res["cycles"] > 10
    assert res["bw_total_pct"] > res["bh_total_pct"]
    assert res["premium_yield_ann_pct"] > 0


def test_strong_rally_buywrite_lags_hold_and_gets_called(ccb):
    p = path(0.004, noise=0.01)  # ~+100%/yr
    res = ccb.simulate_buywrite(p)
    assert res["bw_total_pct"] < res["bh_total_pct"]
    assert res["called_pct"] > 30


def test_crash_buywrite_cushions_drawdown(ccb):
    p = path(-0.002, noise=0.01)  # steady decline
    res = ccb.simulate_buywrite(p)
    assert res["bw_maxdd_pct"] > res["bh_maxdd_pct"]  # less negative
    assert res["called_pct"] < 20


def test_constant_vol_input_and_no_cycles_edge(ccb):
    p = path(0.0, n=50, noise=0.01)
    res = ccb.simulate_buywrite(p, dte=30, start=30)  # too short for a full cycle
    assert res["cycles"] == 0 and res["called_pct"] == 0.0


def test_skew_and_haircut_reduce_premium(ccb):
    p = path(0.0, noise=0.01)
    flat = ccb.simulate_buywrite(p, skew=0.0, haircut=0.0)
    real = ccb.simulate_buywrite(p, skew=-0.5, haircut=0.05)
    assert real["premium_yield_ann_pct"] < flat["premium_yield_ann_pct"]
    assert ccb.skewed_vol(0.40, 100, 110, -0.5) < 0.40 < ccb.skewed_vol(0.40, 100, 90, -0.5)


def test_indicators(ccb):
    p = np.linspace(100, 120, 40)
    assert ccb.sma(p, 20)[19] == pytest.approx(p[:20].mean())
    assert np.isnan(ccb.sma(p, 20)[18])
    assert ccb.rsi(p, 14)[-1] == 100.0                     # only up-moves
    assert ccb.rsi(p[::-1], 14)[-1] == pytest.approx(0.0)  # only down-moves


def test_skip_oversold_reduces_coverage_in_downtrend(ccb):
    p = path(-0.002, noise=0.01)
    naive = ccb.simulate_buywrite(p)
    filt = ccb.simulate_buywrite(p, skip_oversold=True)
    assert filt["coverage_pct"] < naive["coverage_pct"]


def test_skip_earnings_never_sells_across_an_earnings_date(ccb):
    p = path(0.0, n=700, noise=0.01)
    earn = list(range(60, 700, 63))  # quarterly
    r = ccb.simulate_buywrite(p, dte=21, skip_earnings=True, earnings_idx=earn)
    naive = ccb.simulate_buywrite(p, dte=21)
    assert r["coverage_pct"] < naive["coverage_pct"] and r["cycles"] > 0


def test_early_close_closes_some_cycles_early(ccb):
    p = path(-0.0005, noise=0.01)
    r = ccb.simulate_buywrite(p, early_close=0.5)
    assert r["early_closed_pct"] > 0
    assert ccb.simulate_buywrite(p)["early_closed_pct"] == 0


def test_daily_equity_and_rolling_windows(ccb):
    p = path(0.0005, n=800, noise=0.01)
    r = ccb.simulate_buywrite(p)
    assert len(r["_equity_bw"]) == len(p) - 30
    assert r["windows_1y"] > 0 and r["beat_hold_1y_pct"] is not None
