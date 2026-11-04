---
description: Theta gang options analysis — analyze setup, roll positions, or check leaders
---

Theta gang skill: $ARGUMENTS

Parse the first word as the subcommand:

- **`analyze TICKER`** — Analyze options setup for selling premium (e.g., "analyze AAPL")
- **`pick TICKER STRATEGY`** — Compare strike/expiry combos (e.g., "pick AAPL CSP", "pick TSLA CC")
- **`roll TICKER STRIKE EXPIRY STRATEGY`** — Analyze whether to roll a position (e.g., "roll AAPL 170P 2026-05-16 CSP")
- **`leaders TICKER`** — Check what top thetagang.com traders are doing (e.g., "leaders AAPL")

---

# If subcommand is `analyze`

Analyze the options setup for theta gang trading on the given ticker.

This is a pure options mechanics analysis. Do NOT cover company fundamentals, growth, or earnings quality — that belongs in `/research`. Assume the user already has conviction on the stock.

**Step 1:** Run the data script:
```bash
.venv/bin/python3 scripts/technicals.py TICKER --options
```

Use the script's output for IV, price, support/resistance levels, and expiry data. Supplement with web search only for qualitative info the script can't provide.

**Step 2: Consult knowledge base**
- Read `knowledge/strategies/when-to-csp.md` — calculate the **CSP Score** (6-component composite: IV Rank, VRP Edge, AnnYield, Buffer %, Support, Earnings Gate) for CSP trades. Compute it with `.venv/bin/python3 scripts/option-scores.py TICKER --csp` (scan) or `--csp --strike X --expiry YYYY-MM-DD`, don't work it out by hand. If CSP Score < 45, explicitly recommend against selling CSPs.
- Read `knowledge/strategies/when-to-cc.md` — run the CC Sharpe 4-gate check and score BEFORE recommending any covered call, using `.venv/bin/python3 scripts/option-scores.py TICKER --cc` (scan) or `--cc --strike X --expiry YYYY-MM-DD --cost-basis Y` (one contract). If CC Sharpe Score < 40, explicitly recommend against selling CCs.
- Read `knowledge/signals/iv-rank-guide.md` — if IV Rank < 25, flag: "Premium too thin — consider LEAPs or shares instead"
- Read `knowledge/signals/rsi-guide.md` — interpret RSI in sector context (high-beta sectors hit extremes routinely)
- Run `.venv/bin/python3 scripts/sector-momentum.py --json` and consult `knowledge/frameworks/sector-momentum.md` — if sector is in Stage 4 downtrend, flag that support levels may not hold

## Options Environment
- Current stock price and recent trend (from script's `price` and `technicals`)
- IV rank and IV percentile — is premium rich right now? (from script's `options`)
- Options liquidity: volume, open interest, bid-ask spreads on near-the-money strikes
- Theta decay curve: where are we on the 90→0 DTE curve?

## Key Dates (Disqualifiers)
- Next earnings date — if within 30-45 DTE window, flag as a risk or disqualifier
- Next ex-dividend date — stock typically drops by dividend amount
- Any other binary events (FDA, legal rulings, etc.)

## Recommended Trades
Suggest 1-2 setups. For each:
- **Strategy**: CSP / CC / PMCC / Iron Condor
- **Strike(s)**: specific prices with delta (target 0.20-0.30 for selling)
- **Expiration**: specific date, DTE (target 30-45 DTE sweetspot)
- **Premium**: estimated credit received per share and per contract
- **Greeks snapshot**: delta, theta ($/day earned), vega exposure, gamma risk
- **Probability of profit** (PoP ≈ 1 - |delta|)
- **Max profit / Max loss / Breakeven**
- **Buffer %**: (stock price - breakeven) / stock price × 100
- **Buying power reduction**
- **Annualized return**: if held to expiry, and if closed at 50% profit
- **CSP Score** (for CSP trades) or **CC Sharpe Score** (for CC trades) — display the composite score with component breakdown

## Risk Assessment
- Gamma risk (especially if DTE < 21)
- Vega risk (will IV likely expand or contract?)
- Assignment risk at this strike
- What would trigger a roll or early close?

## Verdict
- **CSP Score** or **CC Sharpe Score** with full component breakdown — display prominently before the go/no-go decision
- Go / no-go for theta gang right now (CSP Score > 65 = go, 45-65 = marginal, < 45 = skip; CC Sharpe > 60 = go, 40-60 = marginal, < 40 = skip)
- If go: best specific trade with reasoning
- Check what other traders are doing on this ticker at [thetagang.com/symbols/TICKER](https://thetagang.com/symbols/TICKER) — filter by strategy type, look at winners/losers to validate your setup

Save the output to `research/stocks/TICKER.md` (use uppercase ticker as filename).
Start the entry with a date separator: `---` followed by `# TICKER — Theta Gang Analysis | YYYY-MM-DD`.
If the file already exists, prepend the new analysis above all previous entries (after the YAML frontmatter block). Never remove historical entries.

If creating a new file, add YAML frontmatter at the top:
```yaml
---
ticker: TICKER
status: watching
added_date: YYYY-MM-DD
sector: (infer from context)
thesis: "(one-line summary)"
entry_target: (recommended strike)
strategies: [CSP, CC]
---
```

If the file already exists and has frontmatter, do not modify the frontmatter — only prepend the new analysis entry below it.

**Update watchlist:** Run `.venv/bin/python3 scripts/watchlist.py` to regenerate `0-WATCHLIST.md`.

---

# If subcommand is `pick`

Compare strike and expiry options for the given ticker and strategy. Arguments after `pick`: TICKER STRATEGY (e.g., "pick AAPL CSP", "pick TSLA CC", "pick NVDA PMCC", "pick AMZN IC")

**Step 1:** Run the data script:
```bash
.venv/bin/python3 scripts/technicals.py TICKER --options
```

Use the script's output for price, support/resistance, IV, and options chain data. Supplement with web search only if needed.

## Current Setup
- Stock price, 52-week range, recent trend
- IV rank / IV percentile
- Next earnings date and ex-dividend date (flag if within the trade window)

## Strike/Expiry Comparison Table

Build a comparison table with 3-5 candidates. Follow these rules:
- **CSP**: delta 0.20-0.30, strike at support levels or a price you'd be happy owning
- **CC**: strike above cost basis, at resistance / take-profit level
- **PMCC**: long leg delta 0.80-0.90 (far out expiry), short leg delta 0.20-0.30 (30-45 DTE)
- **Iron Condor**: sell both sides at ~16 delta, buy wings further out

For each candidate, include:
| Strike | Expiry (DTE) | Delta | Premium | PoP | Max Profit | Max Loss | Breakeven | Buffer % | AnnYield | CSP/CC Score |

For CSP candidates, calculate the CSP Score (from `knowledge/strategies/when-to-csp.md`).
For CC candidates, calculate the CC Sharpe Score (from `knowledge/strategies/when-to-cc.md`).

## Theta Decay Analysis
- How much theta ($/day) does each candidate earn?
- Is the DTE in the 30-45 day sweetspot?
- Gamma risk assessment — any candidates too close to expiry?

## Recommendation
- Which specific strike/expiry combo offers the best risk/reward?
- Why this one over the others?

Do NOT save output to a file — this is a live analysis tool for decision-making.

---

# If subcommand is `roll`

Analyze rolling options for the given position. Arguments after `roll`: TICKER CURRENT_STRIKE CURRENT_EXPIRY STRATEGY (e.g., "roll AAPL 170P 2026-05-16 CSP")

**Step 1:** Run the data script:
```bash
.venv/bin/python3 scripts/technicals.py TICKER --options
```

Use the script's output for current price, support/resistance, and options chain data. Supplement with web search for any additional context needed.

Consult management rules in knowledge/strategies/when-to-csp.md for roll decision criteria (close at 50% profit, roll when tested, cut if thesis breaks).

## Current Position Status
- Current stock price vs. your strike
- How far ITM/OTM is the position?
- Days to expiry remaining
- Current P&L estimate (premium collected vs. current cost to close)

## Should You Roll?

First, check the prerequisites:
1. **Do you still have conviction in the underlying?** Rolling only makes sense if you're still bullish (for CSP) or still want to hold (for CC). If not → close the position and take the loss.
2. **Can you roll for a net credit?** If you can't get a credit, rolling just digs a deeper hole.

## Rolling Options

Compare 2-3 rolling alternatives:

| Roll Type | New Strike | New Expiry | Cost to Close Current | New Premium | Net Credit/Debit | New Breakeven | New PoP |

Rolling types to consider:
- **Roll out**: same strike, later expiry (more time = more premium)
- **Roll out & down** (for puts): later expiry + lower strike — reduces assignment risk
- **Roll out & up** (for calls): later expiry + higher strike — gives more room

## Alternatives to Rolling
- Close the position entirely (realize the loss/gain)
- Let it expire / take assignment (if you're happy owning at this price)
- Do nothing and wait (if still OTM with time left)

## Recommendation
- Clear roll / don't roll decision with reasoning
- If roll: specify exact new strike, expiry, and expected net credit

Save the output by prepending to `portfolio/TICKER.md` (after the YAML frontmatter block).
Start the entry with: `---` followed by `# TICKER — Roll Analysis | YYYY-MM-DD`.
Never remove historical entries.

If the portfolio file's frontmatter has a `strike` or `expiry` field and you recommend a roll, note that the user should update the frontmatter after executing the roll.

---

# If subcommand is `leaders`

Check what the top theta gang traders are doing on the given ticker.

Reference the leader list at `leaders.md` (in the project root) for the top 10 traders.

For the given ticker, check the following profiles and summarize any recent trades:

1. [jrue](https://thetagang.com/jrue) — #1, 5,882 trades
2. [dom747](https://thetagang.com/dom747) — #2, 3,993 trades
3. [major](https://thetagang.com/major) — #3, 3,535 trades
4. [bobthetrader](https://thetagang.com/bobthetrader) — #4, 2,576 trades
5. [Slomotion](https://thetagang.com/Slomotion) — #5, 3,001 trades
6. [gruffalo](https://thetagang.com/gruffalo) — #6, 2,347 trades
7. [epilektoi](https://thetagang.com/epilektoi) — #7, 1,992 trades
8. [Stizzle](https://thetagang.com/Stizzle) — #8, 2,073 trades
9. [simofin](https://thetagang.com/simofin) — #9, 1,568 trades
10. [Hirad](https://thetagang.com/Hirad) — #10, 1,723 trades

Try to fetch each profile page to find trades on the given ticker. If the pages don't render trade data (they use dynamic loading), then instead:

1. Direct the user to check these profiles manually on thetagang.com
2. Also check the ticker-specific community page: `thetagang.com/symbols/TICKER`
3. Suggest filtering by: Winners, strategy type (CSP, CC), and recent trades

## What to Look For
- Are any top traders currently active on this ticker?
- What strategies are they using (CSP, CC, IC, etc.)?
- What strikes and expirations are they choosing?
- Win rate on this ticker across the community
- Any patterns: do they sell at similar delta/DTE to our rules?

## Output
Summarize findings and note any insights that should inform your own trade decision. Do NOT save to a file — this is a live lookup tool.
