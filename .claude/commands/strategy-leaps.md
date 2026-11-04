---
description: LEAP Calls strategy — long-dated options for leveraged bullish exposure
---

LEAP Calls strategy analysis for: $ARGUMENTS

The argument is a ticker (e.g., "AAPL", "NVDA").

Assume the user already has conviction from `/research-stock` or `/plan-stock`. This skill focuses on LEAP call execution: strike selection, expiry, sizing, and risk management.

**Step 1:** Run the data script with options data:
```bash
.venv/bin/python3 scripts/technicals.py $ARGUMENTS --options
```

Use the script's output for price, support/resistance, IV, and options chain. Supplement with web search for catalysts and timeline.

**Step 2: Consult knowledge base**
- Read `knowledge/strategies/when-to-leaps.md` — apply the IV Rank × Conviction decision matrix. **IV Rank < 30 is non-negotiable.** Check it with `.venv/bin/python3 scripts/option-scores.py TICKER --leap` (also checks earnings within 14 days and lists 0.40–0.80 delta calls with cost and breakeven). If IV Rank > 40, recommend shares/DCA instead. If IV Rank > 60, recommend selling premium (CSP).
- Read `knowledge/signals/iv-rank-guide.md` — validate against the IV Rank × RSI matrix
- Read `knowledge/signals/rsi-guide.md` — interpret RSI in context (trend, sector beta, earnings distortion)
- Run `.venv/bin/python3 scripts/sector-momentum.py --json` and consult `knowledge/frameworks/sector-momentum.md` — if sector is in Stage 4 downtrend, flag elevated risk for LEAPs

## LEAP Suitability Check

- Is the stock bullish with identifiable catalysts in the next 6-12 months?
- IV rank / IV percentile — is IV cheap (good for buying) or expensive (bad for buying)?
  - Low IV = cheaper premiums = better entry for LEAPs
  - High IV = consider selling premium (theta gang) instead
- Options liquidity on long-dated strikes: volume, open interest, bid-ask spreads
- Any earnings or binary events in the LEAP window to be aware of?

**Verdict:** Is this a good LEAP setup? If IV is too high, recommend theta gang instead.

## Strike Selection

Compare 2-3 strike options:

| Strike | Delta | Premium | Breakeven | Max Risk | Leverage vs. Shares | DTE |
|--------|-------|---------|-----------|----------|--------------------|----|

Strike guidance:
- **Deep ITM (delta 0.70-0.80)**: stock replacement — moves closely with shares, less time decay, higher cost
- **ATM (delta 0.50)**: balanced leverage and risk
- **Slightly OTM (delta 0.30-0.40)**: max leverage, but higher risk of total loss

Recommend the best strike based on conviction level and risk tolerance.

## Expiry Selection

- Minimum 9 months, prefer 12+ months
- Show available expiry dates and their DTE
- Theta decay is minimal at 12+ months — this is the LEAP advantage
- Flag any earnings dates that fall near expiry

## Recommended Trade

- **Strike**: specific price
- **Expiry**: specific date (DTE)
- **Premium**: cost per contract
- **Delta**: current delta
- **Breakeven at expiry**: strike + premium
- **Max risk**: total premium paid (can lose 100%)
- **Equivalent share exposure**: delta × 100 shares
- **Capital efficiency**: cost of LEAP vs. cost of 100 shares

## Risk Management

- **Position sizing**: LEAPs can go to zero — suggest max % of portfolio (e.g., 3-5% per LEAP position)
- **Stop loss**: close if LEAP loses 50% of value, or if thesis breaks
- **Rolling**: if stock moves in your favor and LEAP reaches 100%+ gain, consider taking profit or rolling up/out
- **Time decay warning**: if DTE drops below 90 days, theta accelerates — either close or roll to a further expiry
- **IV risk**: if IV drops significantly after entry, LEAP loses value even if stock is flat (vega exposure)

## Exit Plan

- **Take profit at**: 50-100% gain on the LEAP premium
- **Roll if**: stock rallies and you want to stay in — roll up to a higher strike and/or further expiry
- **Close if**: thesis breaks, LEAP loses 50%, or DTE < 90 days without rolling

Save the output to `research/stocks/$TICKER.md` (use uppercase ticker as filename).
Start the entry with: `---` followed by `# TICKER — LEAP Calls Plan | YYYY-MM-DD`.
If the file already exists, prepend above previous entries (after YAML frontmatter). Never remove historical entries.

If creating a new file, add YAML frontmatter:
```yaml
---
ticker: TICKER
status: watching
added_date: YYYY-MM-DD
sector: (infer from research)
thesis: "(one-line summary)"
entry_target: (recommended strike)
strategies: [leaps]
---
```

**Update watchlist:** Run `.venv/bin/python3 scripts/watchlist.py` to regenerate `0-WATCHLIST.md`.
