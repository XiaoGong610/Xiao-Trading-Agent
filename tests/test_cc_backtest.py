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
