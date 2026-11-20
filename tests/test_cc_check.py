"""cc-check.py: portfolio-fit math with fake accounts and tickers (no network, no personal data)."""


def allowed(constraints):
    text = " ".join(constraints).lower()
    if "no options" in text:
        return set()
    if "covered calls only" in text:
        return {"cc"}
    return None


DETAILS = {
    "TAXABLE": {"constraints": ["Covered calls only"], "shares": {"XYZ": 450}, "short_calls": {"XYZ": 2}},
    "IRA": {"constraints": ["Options allowed"], "shares": {"XYZ": 120}, "short_calls": {"XYZ": 1}},
    "K401": {"constraints": ["No options trading"], "shares": {"XYZ": 300}, "short_calls": {}},
}


def test_uncovered_lots_respect_account_rules_and_open_calls(ccc):
    fit = ccc.portfolio_fit("XYZ", 50.0, DETAILS, total_value=100_000, conviction=7, allowed_kinds=allowed)
    # TAXABLE: 4 lots - 2 open = 2; IRA: 1 lot - 1 open = 0; K401: options not allowed
    assert fit["uncovered_lots"] == 2
    assert fit["held_shares"] == 870
    assert fit["weight_pct"] == 43.5
    assert fit["overweight"] is True          # conviction 7 band max = 5%
    k401 = next(a for a in fit["accounts"] if a["account"] == "K401")
    assert k401["cc_allowed"] is False and k401["uncovered"] == 0


def test_fit_verdicts(ccc):
    base = {"uncovered_lots": 0, "overweight": False, "new_lot_cost": 5000}
    assert ccc.fit_verdict({**base, "uncovered_lots": 1}, True) == "USE EXISTING"
    assert ccc.fit_verdict({**base, "uncovered_lots": 1}, False).startswith("WAIT")
    assert ccc.fit_verdict({**base, "overweight": True}, True).startswith("OVERWEIGHT")
    assert ccc.fit_verdict(base, True).startswith("BUY FIRST")


def test_band_max(ccc):
    assert ccc.band_max(9.5) == 8.0 and ccc.band_max(7.5) == 5.0
    assert ccc.band_max(5.0) == 3.0 and ccc.band_max(3.0) == 1.0 and ccc.band_max(None) is None


def test_sizing_lots_and_shares_to_buy(ccc):
    # conviction 7 -> 5% band; $700k portfolio -> $35k -> 140 sh at $250 -> 1 lot
    s = ccc.sizing(250.0, 7, 700_000, held_cc_shares=0, held_total=0)
    assert s["max_shares"] == 140 and s["max_lots"] == 1 and s["target_lots"] == 1 and s["shares_to_buy"] == 100
    # conviction 9 -> 8% band -> $56k -> 224 sh -> 2 lots; 54 already held in a CC account
    s = ccc.sizing(250.0, 9, 700_000, held_cc_shares=54, held_total=54)
    assert s["target_lots"] == 2 and s["shares_to_buy"] == 146 and "ladder" in s["verdict"]


def test_sizing_lot_too_big_and_over_band(ccc):
    s = ccc.sizing(600.0, 5, 700_000, 0, 0)        # 3% band = $21k < one $60k lot
    assert s["max_lots"] == 0 and "too big" in s["verdict"]
    s = ccc.sizing(250.0, 7, 700_000, 701, 701)    # $175k held > 5% band
    assert s["verdict"].startswith("OVER BAND")


def test_q_verdicts(ccc):
    assert ccc.q1_verdict({"conviction": 7.5, "age_days": 10}) == "YES"
    assert ccc.q1_verdict({"conviction": 6.0, "age_days": 60}).startswith("OK (stale")
    assert ccc.q1_verdict({"conviction": None, "age_days": None}).startswith("NO RESEARCH")
    assert ccc.q2_verdict({"ann_yield": 20}, 40, 50).startswith("RICH (IV < RV")
    assert ccc.q2_verdict({"ann_yield": 7}, 40, 40) == "THIN"
    assert ccc.q3_verdict({"cycles": 50, "cagr_uplift_pct": 1.5, "beat_hold_1y_pct": 60}) == "HELPS"
    assert ccc.q3_verdict({"cycles": 50, "cagr_uplift_pct": -3, "beat_hold_1y_pct": 30}).startswith("HURTS")


def test_cc_stage_lifecycle(ccc):
    assert ccc.cc_stage(7, 54, True, False) == "ACCUMULATE"
    assert ccc.cc_stage(7, 100, False, False).startswith("HOLD, WAIT")
    assert ccc.cc_stage(7.5, 701, True, True).startswith("SELL CALLS")      # over band but already holds lots
    assert ccc.cc_stage(7, 54, True, True).startswith("OVER BAND")
    assert ccc.cc_stage(5, 300, True, True).startswith("CALLS ON EXISTING ONLY")
    assert ccc.cc_stage(None, 0, True, False).startswith("NOT A CANDIDATE")
