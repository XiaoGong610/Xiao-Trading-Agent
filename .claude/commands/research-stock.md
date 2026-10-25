---
description: Deep-dive research on a stock
---

Research the stock: $ARGUMENTS

This is a strategy-agnostic fundamentals and sentiment analysis. Focus on whether this is a good company to have conviction in — the user may use the research to inform any strategy (DCA, theta gang, buy-and-hold, etc.). Do NOT cover options-specific analysis (IV, Greeks, strikes, premiums).

**Step 1:** Run the data script to get current price, technicals, and fundamentals:
```bash
.venv/bin/python3 scripts/technicals.py $ARGUMENTS --options
```

**Step 2a:** Fetch retail sentiment (no API key needed):
```bash
.venv/bin/python3 scripts/sentiment.py $ARGUMENTS --md
```
Use the StockTwits bull/bear ratio and Reddit post volume to inform the Market Sentiment section. If StockTwits skews >65% bullish, flag potential retail hype. If >65% bearish, note as contrarian signal.

**Step 2b:** Use web search to gather qualitative information (news, earnings, analyst opinions, institutional activity).

**Step 2b-ii: Influencer check**

Read `knowledge/reference/influencers.md` for the list of tracked accounts. Search **every** tracked account for this ticker, on every run. **Never skip one because its listed focus doesn't match the sector.** Influencers pick up new names all the time, and the focus column describes what they usually post about, not every stock they cover. For example, Serenity is listed as semis/photonics but has been a public CRCL bull since Feb 2026.

```
"@handle" $TICKER 2026            # one search per tracked account, always
"@handle" sector_keyword 2026     # extra search for accounts whose focus matches the sector
```

Use the X MCP timeline/search tools if they're available. Otherwise use web search.

**Record the result for every account, including "no mention found".** A missing line looks the same as a skipped check, so write it out. If an account turns out to cover a stock or sector its focus didn't list, add that to its row in `influencers.md`.

**What to capture:**
- Thesis alignment or disagreement with our research → note in Market Sentiment section
- New supply chain insights → flag for `knowledge/frameworks/ai-capital-flow.md` update
- Position changes (bought/sold/trimmed) → note as a data point, not a recommendation
- If no relevant posts found, skip — don't force it

**Quality rule:** Influencer views are ONE input, not the conclusion. Always validate against our own fundamentals and technicals. Note the source clearly: _"Serenity (@aleabitoreddit) noted on [date] that..."_

**Step 2c: Sector context check**

Identify the stock's sector and find the matching scan file in `research/sectors/` (e.g., `semiconductors.md`, `energy.md`, `software.md`, `healthcare.md`). Check its last-modified date.

- **If fresh (<14 days):** Read the most recent scan entry (up to the first `---` separator after the header) and use its momentum classification, lifecycle stage, and sector risks to contextualize this stock's technicals. Include a **Sector Context** subsection in the Company Overview.
- **If stale (≥14 days) or missing:** Flag it to the user: _"⚠️ Sector scan for [sector] is [X days] stale. Sector context may be outdated. Consider running `/research-sector [sector]` to refresh."_ Still read whatever exists, but note the staleness caveat.

The sector scan provides: momentum classification (Accelerating/Pulling Back/Sideways/Downtrend), Mansfield RS, Weinstein Stage, and sub-sector themes. Use these to:
- Adjust RSI interpretation (oversold in a downtrending sector ≠ oversold in a pulling-back sector)
- Inform entry timing (pulling back in uptrend = best window, downtrend = patience needed)
- Contextualize valuation (sector re-rating vs. individual story)

**Step 3: Consult knowledge base**
- Read `knowledge/signals/rsi-guide.md` for RSI interpretation (sector beta differences, trend context, common mistakes)
- Read `knowledge/signals/ma-guide.md` — check SMA alignment (bullish stack vs tangled) and which SMA to use for entry levels
- Read `knowledge/signals/volume-guide.md` — validate price moves with relative volume (>2x avg = institutional, <0.5x = ignore)
- Read `knowledge/signals/macd-guide.md` — check for divergences to strengthen Technical Outlook scenarios
- Read `knowledge/frameworks/valuation.md` for sector-appropriate P/E benchmarks
- If the stock is in semiconductors, read `knowledge/sectors/semiconductors.md` for cycle signals and key metrics
- If the stock is AI supply chain related, read `knowledge/frameworks/ai-capital-flow.md` for bottleneck positioning
- If evaluating a breakout entry, read `knowledge/signals/breakout-filter.md` for the 3-way true/false breakout filter

Combine all sources to cover the following sections:

---

## Red Flag Check

Before diving in, read `knowledge/frameworks/evidence-ladder.md` for the red flag checklist. Flag any of these during research — they downgrade confidence:

**Evidence red flags:**
1. Thesis relies on a single customer rumor
2. Stock moved mainly on social media attention
3. Company needs financing before opportunity converts to revenue
4. Customer unnamed, revenue impact vague
5. Inventories/receivables rising faster than revenue
6. Gross margin not improving despite claimed scarcity
7. Management uses theme language while segment data is unchanged

**US financing risk flags (check for US-listed stocks):**
8. Active shelf registration (S-3) — company can issue shares at any time
9. At-the-market (ATM) offering program in place — ongoing dilution risk
10. Large convertible debt outstanding — dilutive if stock rises above conversion price
11. Stock-based compensation >10% of revenue — silent dilution eroding shareholder value
12. Insider selling cluster with no purchases — insiders don't believe in the upside

If 2+ evidence red flags (1-7) fire, note them prominently in the Summary section and reduce conviction by 1-2 points. Financing risk flags (8-12) don't reduce conviction directly but must be noted in Risks.

## Quick Screen (5 questions — gate before deep dive)

Answer these 5 yes/no questions first. If 3+ are "No", stop here and mark as **PASS** — don't waste time on a deep dive.

| # | Question | Answer |
|---|----------|--------|
| 1 | Revenue growing >10% YoY (or accelerating)? | |
| 2 | Stock above 200-day SMA (long-term uptrend intact)? | |
| 3 | No earnings within 7 days (avoid binary risk)? | |
| 4 | Clear catalyst or thesis in next 3-6 months? | |
| 5 | Market cap >$2B (sufficient liquidity)? | |

**Result:** PASS (stop) / PROCEED (continue to deep dive)

If PASS: write a brief 2-3 line summary of why this stock doesn't pass the screen, save to file, and stop.

---

## Company Overview
- What the company does, sector, market cap
- Key products/services and revenue breakdown
- Competitive moat (network effects, switching costs, scale, IP, brand)

## Growth & Financials
- Revenue and earnings growth (recent quarters + YoY)
- Margins (gross, operating, net) and trends
- Balance sheet health (debt, cash position)
- Free cash flow
- How does this compare to sector peers? (above/below average)

## Recent Earnings
- Revenue: actual vs. estimate, YoY growth
- EPS: actual vs. estimate, YoY growth
- Management commentary: tone, strategic priorities, key quotes
- Guidance: next quarter and full year vs. consensus (raised, maintained, lowered?)
- Analyst Q&A highlights: toughest questions, any evasiveness or surprising candor
- Market reaction: stock move after earnings, analyst rating/target changes
- Next earnings date

## Institutional & Insider Activity
- Institutional ownership % and recent changes (increasing or decreasing?)
- Notable 13F filers adding/trimming (hedge funds, mutual funds)
- Insider transactions in last 90 days (cluster buying = strong signal)
- Major shareholder pledge ratio — are insiders pledging shares as collateral? (forced selling risk)
- **Alignment signal:** Institutions increasing AND insiders buying = highest conviction. Institutions selling AND insiders selling = red flag.

## Market Sentiment
- Analyst consensus (buy/hold/sell breakdown, average price target)
- Recent news or catalysts
- **Anomaly check:** Is the market reacting as expected to news? If good news is being ignored or bad news isn't pushing price down, flag it — this is often more informative than the news itself.

## Technical Outlook

Provide 2-3 probabilistic scenarios based on current technicals:

| Scenario | Probability | Target | Invalidation | Trigger |
|----------|-------------|--------|--------------|---------|
| Bull | % | $X | Below $Y | What needs to happen |
| Base | % | $X | Below $Y | Default path |
| Bear | % | $X | Below $Y | What goes wrong |

Probabilities must sum to 100%. Every scenario needs an explicit invalidation price — the level where that thesis breaks.

## Risks
- Key risks to the thesis (rank by likelihood and impact)
- Upcoming binary events (earnings, FDA, regulatory, macro)
- **Governance checks** (flag if any are concerning):
  - Core team turnover frequency — high C-suite turnover = internal instability
  - Related-party transaction frequency — frequent = potential window-dressing
  - Channel inventory truth — is reported inventory actually reaching end consumers?
- **Thesis killer:** What single event or data point would make you abandon this stock entirely?

## Conviction Score

Rate the stock on 6 dimensions (1-10 each). Be honest — most stocks score 4-7, not 8-10.

| Dimension | Score | Notes |
|-----------|-------|-------|
| Business Quality (moat, margins, management) | /10 | |
| Growth (revenue, earnings trajectory) | /10 | |
| Valuation (relative to growth + sector) | /10 | |
| Technicals (trend, support, entry timing) | /10 | |
| Catalyst (upcoming events, narrative strength) | /10 | |
| Institutional Support (smart money alignment) | /10 | |
| **Overall Conviction** | **/10** | Weighted avg — Business & Growth count 2x |

For Valuation scoring, use sector-appropriate Forward P/E benchmarks from knowledge/frameworks/valuation.md — don't rely on absolute P/E alone.

**Conviction guide:** 8-10 = high conviction (worth a full position), 6-7 = moderate (DCA or smaller size), 4-5 = speculative (watch only), 1-3 = avoid.

## Summary
- Bull case vs. bear case (1-2 sentences each)
- Overall take: bullish, neutral, or bearish — with reasoning
- **Red flags triggered:** list any from the Red Flag Check above, or "None"
- **Financing risks noted:** list any from flags 8-12, or "None"

## What the Market May Be Missing

Assess whether the market is categorizing this company correctly. This is the re-rating/mislabeling framework — it identifies where the real upside (or downside) surprise could come from.

| | Assessment |
|---|-----------|
| **Current market category** | How does the market currently price/view this company? (e.g., "cyclical memory maker," "mature SaaS," "speculative biotech") |
| **Possible new category** | What could the company actually be or become? (e.g., "AI infrastructure bottleneck," "platform compounder," "secular growth") |
| **Why investors may be slow** | What structural bias, historical pattern, or information gap is keeping the market in the old category? |
| **What would trigger re-categorization** | Specific event or data point that forces the market to re-price (e.g., "2 more quarters of 80%+ GM proves this isn't cyclical") |

If the current and possible categories are the same (market is pricing it correctly), say so — not every stock is mislabeled. The value of this section is forcing explicit thought about whether there's a category gap.

## Bottleneck Scorecard (supply-chain stocks only)

**Only run this section if the stock is in a supply-chain-heavy sector:** semiconductors, AI infrastructure, power equipment, materials, optical interconnect, advanced packaging, robotics, defense electronics, industrial equipment, or similar hardware/manufacturing sectors.

**Skip for:** pure SaaS/software, financials, REITs, consumer brands, healthcare (non-device), macro trades.

If applicable:
1. Identify the company's **value-chain layer** (end customer → OEM → module → chip/component → process/packaging → equipment → materials → infrastructure)
2. Assess 8 factors (0-5 each): demand inflection, chokepoint severity, evidence quality, supplier concentration, expansion difficulty, valuation disconnect, architecture coupling, catalyst timing
3. Assess penalties (0-5 each): dilution/financing, governance, geopolitics, liquidity, hype risk, accounting quality, cyclicality, alternative design risk
4. Generate a scorecard JSON and run:
```bash
echo 'JSON_CONTENT' | .venv/bin/python3 scripts/bottleneck-scorecard.py - --md
```
5. Include the markdown output in this section

**Verdict thresholds:** ≥85 = Top research priority, ≥70 = High, ≥55 = Worth tracking, <55 = Early lead

The bottleneck score is **supplemental** to the conviction score — it measures how constrained and irreplaceable the company is in its supply chain, not general investment quality.

## Strategy Fit

Based on the research above, recommend which strategy fits best. Consult `knowledge/signals/iv-rank-guide.md` for the IV Rank × RSI decision matrix:
- **IV Rank < 25 + RSI < 30** → LEAP Calls (see `knowledge/strategies/when-to-leaps.md`)
- **IV Rank < 25 + RSI 30-70** → Buy & Hold or DCA
- **IV Rank 50-75 + RSI < 50** → Theta Gang / CSP (see `knowledge/strategies/when-to-csp.md`)
- **IV Rank > 75** → Sell premium aggressively (CSP/CC)

Note: This is a directional recommendation. Run `technicals.py TICKER --options` for IV data, or note that strategy fit will be validated by `/plan-stock` or strategy-specific skills.

Pick one (or a combination) and explain why it suits this stock right now.

---

Save the output to `research/stocks/$ARGUMENTS.md` (use uppercase ticker as filename).
Start the entry with a date separator: `---` followed by `# TICKER — Research | YYYY-MM-DD`.
If the file already exists, prepend the new analysis above all previous entries (after the YAML frontmatter block). Never remove historical entries.

If creating a new file, add YAML frontmatter at the top:
```yaml
---
ticker: TICKER
status: researched
added_date: YYYY-MM-DD
sector: (infer from research)
thesis: "(one-line summary)"
conviction: (overall score from Conviction Score)
---
```

If updating an existing file, update the `conviction` field in frontmatter.

**Update watchlist:**
```bash
.venv/bin/python3 scripts/watchlist.py
```
