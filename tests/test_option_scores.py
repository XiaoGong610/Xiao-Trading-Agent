"""option-scores.py CC gates 5-6 (not oversold, no earnings before expiry) with a fake market (no network)."""
from datetime import date, timedelta
from types import SimpleNamespace


def market(price=100.0, sma20=95.0, rsi14=55.0, earnings=None):
    return SimpleNamespace(price=price, sma20=sma20, rsi14=rsi14, earnings=earnings, today=date(2026, 1, 5),
                           iv30=40.0, rv20=35.0, iv_rank=60.0,
                           dte=lambda e: (date.fromisoformat(e) - date(2026, 1, 5)).days)


ROW = {"strike": 110.0, "bid": 1.9, "ask": 2.1, "lastPrice": 2.0, "impliedVolatility": 0.40}
EXP = "2026-02-13"


def test_clean_setup_sells(osc):
    r = osc.score_cc(market(earnings=date(2026, 3, 20)), EXP, ROW, cost_basis=100)
    assert r["gates"]["5 Not oversold"] == "PASS" and r["gates"]["6 No earnings before expiry"] == "PASS"
    assert r["verdict"] == "SELL CC"


def test_oversold_blocks(osc):
    r = osc.score_cc(market(price=90.0, sma20=95.0, rsi14=30.0, earnings=date(2026, 3, 20)), EXP, ROW)
    assert r["gates"]["5 Not oversold"].startswith("FAIL") and "5" in r["verdict"]


def test_earnings_inside_trade_blocks(osc):
    r = osc.score_cc(market(earnings=date(2026, 1, 28)), EXP, ROW)
    assert r["gates"]["6 No earnings before expiry"].startswith("FAIL") and r["verdict"].startswith("DON'T SELL")


def test_unknown_earnings_is_a_check_not_a_fail(osc):
    r = osc.score_cc(market(earnings=None), EXP, ROW)
    assert r["gates"]["6 No earnings before expiry"].startswith("CHECK")
