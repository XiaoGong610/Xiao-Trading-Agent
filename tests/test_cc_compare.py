"""cc-compare.py: portfolio-fit math with fake accounts and tickers (no network, no personal data)."""


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
