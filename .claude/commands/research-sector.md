---
description: Research a market sector and identify candidate stocks
---

Research the following sector or theme and identify candidate stocks: $ARGUMENTS

The argument can be a traditional sector (e.g., "healthcare", "energy", "financials") or a cross-sector investment theme (e.g., "ai-infrastructure", "defense", "glp-1"). Themes cut across traditional sector boundaries — pull relevant stocks from wherever they sit.

Use web search to analyze the current state of this sector.

**Run sector momentum analysis first** to get quantitative momentum data:
```bash
.venv/bin/python3 scripts/sector-momentum.py --json
```
This provides Mansfield Relative Strength, Weinstein Stage, ROC, and RSI for all sectors. Use it to populate the Sector Momentum & Trend section below.

**Check for sector-specific knowledge:** If a knowledge file exists for this sector (e.g., `knowledge/sectors/semiconductors.md`), read it first for sector-specific metrics, cycle dynamics, sub-sector hierarchy, and common mistakes. This provides informed context before web search.

**For AI-related sectors** (semiconductors, networking, cloud, power/cooling): consult `knowledge/frameworks/ai-capital-flow.md` to identify which supply chain track is at the inflection point and which names benefit.

**Sector-specific scripts:** If the sector has a dedicated data script, run it as well:
- **Crypto:** Run `.venv/bin/python3 scripts/crypto-cycle.py` for the on-chain cycle dashboard (MVRV, NUPL, cycle composite). Reference the output in the analysis.

Cover:

## Sector Overview
- What's driving the sector right now (macro trends, catalysts, headwinds)
- Recent performance vs. S&P 500 (outperforming, underperforming, in line?)
- Key themes (e.g., AI spend, rate sensitivity, regulatory changes)

## Sector Momentum & Trend

Classify the sector's current momentum. This directly drives strategy selection for stocks in this sector.

Use the sector ETF (if available) or a basket of top stocks to assess:

| Factor | Reading | How to Check |
|--------|---------|-------------|
| 1-week performance | % | Sector ETF or top stocks avg |
| 1-month performance | % | Sector ETF or top stocks avg |
| 3-month performance | % | Sector ETF or top stocks avg |
| Sector vs. S&P 500 (1-month) | Over/under | Compare sector 1-month return vs. SPY 1-month return |
| Sector RSI (14-day) | Value | Sector ETF RSI |

**Momentum classification:**

| Pattern | Classification | Strategy Implication |
|---------|---------------|---------------------|
| 1W > 0, 1M > 0, outperforming S&P | **Accelerating Up** | Buy strength — momentum entries work. Don't wait for pullback. Trail stops. |
| 1W > 0, 1M > 0, in line with S&P | **Steady Uptrend** | Normal DCA. Buy support tests. Standard sizing. |
| 1W < 0, 1M > 0 | **Pulling Back in Uptrend** | Best entry window — buy the dip. Accelerate DCA. CSP at support. |
| 1W ~0, 1M ~0 | **Sideways/Choppy** | Theta gang territory. Sell premium. Reduce directional bets. |
| 1W < 0, 1M < 0, underperforming S&P | **Downtrend** | Slow DCA only. Accumulate for the turn. Small positions. Save cash. |
| 1W < 0, 1M < 0, RSI < 30 | **Capitulation** | Contrarian buy zone. Aggressive accumulation if thesis intact. |

**Current momentum:** [pick one]
**Evidence:** [1W/1M/3M performance, vs. S&P, RSI]
**Strategy implication:** [what approach stocks in this sector should use — this carries forward to `/plan-stock`]

## Theme Lifecycle Stage

Assess where this sector/theme sits in its lifecycle. This gates how aggressively we pursue candidates.

| Stage | Definition | Action |
|-------|-----------|--------|
| **Emerging** | Early narrative, few players, limited coverage | Aggressive — find first movers |
| **Accelerating** | Adoption inflecting, earnings confirming thesis | Aggressive — ride the wave |
| **Trending** | Mainstream coverage, ETFs launching, broad participation | Selective — only best-in-class |
| **Mature** | Well-known trade, crowded positioning, growth decelerating | Cautious — trim, don't add |
| **Exhausting** | Multiple ETFs, retail crowding, "everyone owns it" | Avoid new entries — look for exits |

**Current stage:** [pick one]
**Evidence:** [2-3 data points — ETF count, media coverage intensity, institutional positioning, earnings growth trajectory]
**Implication:** [what this means for candidate selection below]

## Value-Chain Layer Ranking (supply-chain sectors only)

**Only include this section for supply-chain-heavy sectors:** semiconductors, AI infrastructure, power equipment, materials, optical interconnect, advanced packaging, robotics, defense electronics, industrial equipment, or similar hardware/manufacturing sectors. **Skip for:** SaaS, financials, REITs, consumer brands, healthcare (non-device).

If applicable, rank the VALUE-CHAIN LAYERS before ranking companies. This prevents the output from being a "popular ticker list."

1. Map the value chain for this sector/theme:
   - End customers → System integrators → Modules/subsystems → Chips/components → Process/packaging → Equipment/testing → Materials/consumables → Physical infrastructure

2. Identify the **scarce layers** — where are the real constraints?
   - Low supplier count, long qualification cycles, hard to expand capacity
   - Customer urgency signals: prepayments, capacity reservations, price acceptance
   - Look for less obvious upstream layers when evidence supports them

3. Rank layers by: demand pressure × supplier concentration × expansion difficulty

| Priority | Layer | Why It's Constrained | Evidence to Check | What Could Weaken It |
|----------|-------|---------------------|-------------------|---------------------|

4. **Explicitly downgrade one popular/obvious area** and explain why it ranks lower than expected. This forces intellectual honesty.

Use the layer ranking to inform the Candidate Scoring below — companies controlling scarce layers should score higher on Moat and Catalyst.

## Top Performers
- 3-5 stocks leading the sector and why
- Recent earnings highlights from sector leaders

## Laggards / Turnaround Candidates
- 2-3 stocks underperforming that could be interesting on a pullback
- What would need to change for them to turn around

## Sector Risks
- Key risks that could hurt the sector broadly
- Upcoming events (earnings season, regulatory decisions, macro data)

## Candidate Scoring

Rank 5-10 stocks from this sector using weighted scoring. Score each dimension 1-10:

| Rank | Ticker | Growth (25%) | Valuation (20%) | Moat (15%) | Catalyst (15%) | Technicals (15%) | Options (10%) | **Score** | Verdict |
|------|--------|-------------|-----------------|-----------|---------------|-----------------|--------------|-----------|---------|

**Scoring guide:**
- **Growth (25%):** Revenue/earnings growth rate vs. peers. >30% = 8-10, 15-30% = 5-7, <15% = 1-4
- **Valuation (20%):** Fwd P/E or PEG relative to sector. Use sector-appropriate benchmarks from `knowledge/frameworks/valuation.md`. Below sector avg = 7-10, in line = 4-6, premium = 1-3
- **Moat (15%):** Competitive advantage durability. Wide moat = 8-10, narrow = 5-7, none = 1-4
- **Catalyst (15%):** Upcoming positive event within 3 months. Strong catalyst = 8-10, moderate = 5-7, none = 1-4
- **Technicals (15%):** Trend + proximity to entry. Uptrend at support = 8-10, extended = 4-6, downtrend = 1-3
- **Options (10%):** Liquid options chain + IV environment. Consult `knowledge/signals/iv-rank-guide.md` — IV Rank >50 = theta gang viable, <25 = LEAPs territory. Liquid + high IV = 8-10, liquid + low IV = 5-7, illiquid = 1-4

**Weighted Score** = (Growth×0.25) + (Valuation×0.20) + (Moat×0.15) + (Catalyst×0.15) + (Technicals×0.15) + (Options×0.10)

**Lifecycle adjustment:** If theme stage is Mature or Exhausting, subtract 1 from all candidate scores. Note this in the table.

**Verdict:** Score ≥7 = Strong, 5-6.9 = Moderate, <5 = Watch Later

**Validate top candidates:** For the top 3-5 scoring stocks, run `technicals.py` to get real data:
```bash
.venv/bin/python3 scripts/technicals.py TICKER1 && .venv/bin/python3 scripts/technicals.py TICKER2
```
Adjust scores based on actual technicals if they differ from web search estimates.

## Relevant ETFs

Identify ETFs that cover this sector or theme:

| ETF | Name | Thesis Match % | IV / Options | Verdict |
|-----|------|---------------|-------------|---------|

For each ETF, note:
- How well it matches the sector thesis (what % of holdings are relevant vs. dead weight?)
- Whether it has liquid options (for theta gang viability)
- Whether DCA into the ETF makes more sense than picking individual stocks

## Influencer Check

Read `knowledge/reference/influencers.md` and search **every** tracked account. Don't filter on the listed focus, because influencers pick up new sectors and names. For each account, search the sector/theme keyword plus the top candidate tickers. Look for signals not in mainstream coverage: new picks, thesis changes, supply chain insights. Note anything relevant in Top Picks or Candidate Scoring, and record "no mention found" per account. If an account covers something its focus didn't list, add it to `influencers.md`.

## Top Picks
Highlight the top 2-3 candidates (highest scoring) and suggest next steps:
- Run `/research-stock TICKER` for a deep-dive on fundamentals
- Run `/plan-stock TICKER` for full pre-trade analysis

If theme lifecycle is **Exhausting**: recommend no new entries — suggest reviewing existing positions instead.

Save the output to `research/sectors/$SECTOR.md` (use lowercase sector name as filename, e.g., `software.md`).
Start the entry with a date separator: `---` followed by `# Sector — SECTOR | YYYY-MM-DD`.
If the file already exists, prepend the new analysis above all previous entries (after the file title). Never remove historical entries.
