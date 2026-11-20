---
description: Full pre-trade analysis plan — research, strategy fit, and trade setup
---

Run a complete pre-trade analysis for: $ARGUMENTS

The argument is just a ticker (e.g., "AAPL", "TSLA").

This is the **orchestrator** — it chains together the research funnel, strategy selection, and trade setup in one shot. It pulls from existing research when available and fills gaps.

---

## Phase 0: Market & Sector Context Check

Before planning any individual trade, check the macro and sector environment. These provide the context that shapes position sizing, strategy selection, and timing.

### 0a. Market Overview

1. Read `research/sectors/0-market-overview.md` — check the most recent Market Regime classification and Action Summary.
2. **Freshness check:**
   - **Fresh (<7 days):** Use as-is — reference regime, key risk, and next catalyst in the plan.
   - **Stale (>7 days):** Flag: "⚠️ Market overview is stale (X days old). Consider running `/research-market` first." If user wants to proceed, note the gap and use the last known regime with a caveat.

**Regime gate:**
- **Strong Uptrend / Uptrend** → proceed with full position sizing
- **Choppy** → proceed but reduce position size by 25-50%, favor theta gang
- **Correction** → proceed only for DCA entries or CSP at deep support
- **Downtrend** → STOP — recommend waiting. Only proceed if user explicitly overrides.

If the regime gates you out, explain why and suggest what trigger to watch for (e.g., "Wait for S&P to reclaim 50-day SMA, then re-run `/plan-stock`").

### 0b. Sector / Theme Context

1. Identify the stock's sector or theme (e.g., semiconductors, crypto, software, energy).
2. Check `research/sectors/` for a matching sector scan file.
3. **Freshness check:**
   - **Fresh (<14 days):** Use it — pull theme lifecycle stage, sector risks, and any sector-level insights that affect this stock.
   - **Stale (>14 days) or missing:** Flag: "⚠️ No recent sector scan for [sector]. Consider running `/research-sector [sector]` for broader context." If user wants to proceed, note the gap.

4. **Integrate sector context into the plan:** The sector scan provides critical framing:
   - **Sector momentum** — is this sector Accelerating Up, Pulling Back, Sideways, or in Downtrend? This directly shapes entry approach (see strategy matrix below).
   - **Theme lifecycle stage** — is this sector Emerging (aggressive) or Exhausting (avoid)?
   - **Sector-specific risks** — cycle dynamics, regulation, competition that affect all stocks in the space
   - **Relative positioning** — how does this stock rank vs. peers in the sector scan?
   - **Knowledge base** — check `knowledge/` for relevant frameworks (e.g., `crypto-cycles.md` for crypto stocks, `valuation.md` for P/E context)

**Document what you found:** In Phase 1, include a brief "Sector Context" section summarizing: momentum classification, lifecycle stage, sector-level risks/tailwinds, and any knowledge base insights that apply to this stock.

---

## Phase 0c: Memory Reflection — Lessons from Past Decisions

Check if we've made previous plans or recommendations for this ticker:

1. Search `research/stocks/$TICKER.md` for prior Pre-Trade Plan entries (format: `# TICKER — Pre-Trade Plan | YYYY-MM-DD`)
2. Check `portfolio/REVIEW-*.md` files for any mentions of this ticker in past portfolio reviews
3. If prior plans exist, extract:
   - What was recommended last time (strategy, entry price, targets)
   - What actually happened (did the thesis play out? did we enter? at what price?)
   - Any lessons: was the entry too early/late? Was the stop too tight? Did we miss a catalyst?
4. Note these lessons in Phase 4 when making the new recommendation — avoid repeating past mistakes.

If no prior plans exist for this ticker, skip this step.

---

## Phase 1: Research

**Check for existing research FIRST — do NOT re-run research if fresh data exists:**

1. Read `research/stocks/$TICKER.md`
2. Find the most recent entry header (format: `# TICKER — Research | YYYY-MM-DD` or `# TICKER — Deep Dive | YYYY-MM-DD`)
3. Parse the date and check freshness:

   - **Fresh (≤7 days old):** ✅ SKIP `/research-stock`. Extract these from the existing entry:
     - Conviction Score
     - Thesis summary
     - Key catalysts and risks
     - Strategy Fit recommendation
     - Then proceed directly to Phase 2.

   - **Stale (>7 days old) or missing:** Run `/research-stock $TICKER` to get fresh data.

4. Pull the **Conviction Score**. If score < 5, flag: "Low conviction — consider whether this stock warrants a full plan."

**Why this matters:** `/research-stock` and `/plan-stock` serve different purposes. Research answers "should I own this?" (thesis conviction, strategy-agnostic). Plan answers "how should I enter?" (strategy-specific, price/IV-dependent). If conviction is already established, don't waste tokens re-establishing it — go straight to strategy execution.

**Skill boundary: Do NOT update conviction scores.** Conviction is owned by `/research-stock`. This skill reads the existing conviction and uses it for position sizing — it does not change it. If new information during planning suggests conviction should change, note it as a recommendation ("consider upgrading conviction to X based on Y") but do not modify the frontmatter conviction field. Entry targets may be updated based on technical analysis (support levels, valuation changes).

**Sector Context** (from Phase 0b):
- Theme lifecycle stage: [from sector scan]
- Sector tailwinds/headwinds: [key factors affecting all stocks in this space]
- Knowledge base insights: [any relevant frameworks — e.g., crypto 4-year cycle, CAPE valuation, sector-specific metrics]
- Peer ranking: [where does this stock sit vs. sector scan candidates?]

**Conviction check** — based on the research output AND sector context:
- **Verdict:** Pass / Fail — do you have conviction? (Score ≥ 5 = Pass)
- If the sector lifecycle is **Exhausting**, require conviction ≥ 7 to proceed (higher bar for crowded trades)
- If Fail → stop here.

---

## Phase 2: Market Context & Timing

Run the data script for current price, technicals, and options data:
```bash
.venv/bin/python3 scripts/technicals.py $TICKER --options
```

Read `knowledge/signals/rsi-guide.md` and `knowledge/signals/iv-rank-guide.md` to interpret RSI and IV data correctly. Read `knowledge/signals/ma-guide.md` for SMA alignment and entry level selection. Check `knowledge/signals/volume-guide.md` for volume confirmation and `knowledge/signals/macd-guide.md` for divergences. Read `knowledge/signals/market-day-types.md` to classify the current market day (Trend/Range/Reversal/Munger/Event) — Event Days require waiting for the first shock wave before entering.

If the stock is in the semiconductor sector, read `knowledge/sectors/semiconductors.md` for cycle and sub-sector context.

**Anti-hallucination rule:** Treat `technicals.py` output as the source of truth for all price levels, support/resistance, RSI, MACD, ATR, and IV values. Never claim a support level, price target, or technical reading that isn't directly from the script output or a clearly labeled web search result. If two sources conflict, flag the discrepancy rather than inventing a reconciled number.

Use the script's `price`, `technicals`, `support`, `resistance`, and `options` data:
- Current stock price, 5-day and 1-month trend
- Technical levels: key support AND resistance
- Where is price relative to 52-week range?
- IV rank and IV percentile — is premium rich or cheap?
- Upcoming events: earnings date, ex-dividend date, binary catalysts
- Is now a good entry point, or should you wait?

---

## Phase 3: Run Strategy Analysis

Run the applicable strategy skills to get concrete trade setups. Which skills to run depends on what's available:

**Always run:**
- `/strategy-buy-and-hold $TICKER`
- `/strategy-dca $TICKER`

**Run if US-listed options are available AND the user is not restricted from trading options on this stock:**
- `/strategy-theta-gang analyze $TICKER`
- `/strategy-leaps $TICKER`

**Trading restrictions check:** If the user has restrictions on this stock (check memory — e.g., trading windows, no options), skip restricted strategies and note the constraint.

Each skill will produce its own detailed analysis (entry, sizing, exit rules, risk management). Collect all outputs before proceeding to Phase 4.

---

## Phase 4: Compare & Recommend

### 4a. Sector Momentum → Entry Approach

**This is the most important input for timing.** The sector's momentum (from Phase 0b) determines HOW you enter — it overrides stock-level RSI signals when they conflict.

| Sector Momentum | Stock Extended (RSI >70) | Stock Neutral (RSI 40-70) | Stock Oversold (RSI <30) |
|-----------------|-------------------------|--------------------------|-------------------------|
| **Accelerating Up** | Buy a starter now, add on first dip. Don't wait — momentum carries higher | Full DCA or lump sum. You're riding a wave | Rare combo — buy aggressively |
| **Steady Uptrend** | Start small DCA, accelerate on pullback | Normal DCA. Buy support tests | Buy the dip — sector supports recovery |
| **Pulling Back in Uptrend** | Wait for RSI to cool, then buy | Best entry — pullback in an uptrend | Strong buy — oversold in healthy sector |
| **Sideways/Choppy** | Wait — no momentum to carry you | Theta gang. Sell premium. | DCA slowly — no catalyst to drive recovery |
| **Downtrend** | Avoid — falling knife in a falling sector | Small DCA only. Save cash. | Contrarian accumulation — but slow |
| **Capitulation** | N/A (won't be extended in capitulation) | Aggressive DCA if thesis intact | Back up the truck — cycle bottom |

**Key insight:** "Stock is overbought (RSI 75)" means something very different when the sector is Accelerating Up vs. Sideways. In an accelerating sector, RSI 75 is momentum — in a sideways sector, RSI 75 is overextension.

### 4b. Strategy Selection

With sector momentum context AND strategy outputs in hand, pick the best fit:

| Factor | Consider |
|--------|----------|
| **Sector momentum** | Accelerating → favor momentum/Buy & Hold. Downtrend → favor DCA/accumulation. Sideways → favor theta gang |
| Valuation | Stretched → favors DCA over lump sum. Fair/cheap → Buy & Hold viable |
| IV environment | High IV → theta gang. Low IV → LEAPs or Buy & Hold |
| Timing | At support → Buy & Hold. Uncertain → DCA. Pre-earnings → Wait |
| Options liquidity | Illiquid or unavailable → stock-based strategies only |
| Growth profile | Compounder → Buy & Hold/DCA. Range-bound → Theta Gang |
| User's position | Already owns shares? → CC or add via DCA. No position → CSP or Buy & Hold. **Hold + covered-call candidate?** Run `scripts/cc-check.py TICKER`: conviction, premium, buy-write simulation, sizing (lots in the conviction band) and stage; plan the accumulation to whole lots, then the call-start conditions (gates 5–6 pass: not oversold, no earnings before expiry) |

Consult `knowledge/strategies/when-to-csp.md` and `knowledge/strategies/when-to-leaps.md` to validate that the stock meets the ideal setup checklist for the recommended strategy.

**Recommendation:** Pick the best strategy (or combination) with clear reasoning. The sector momentum should be the FIRST factor considered — it sets the tempo. Then stock-level factors refine the entry.

---

## Phase 5: Execution Plan

Consult `knowledge/strategies/execution-framework.md` for the full decision framework. Every plan must specify concrete orders across all three phases: entry, protection, and exit.

### 5a. Entry Orders

Use the execution framework's decision matrix (sector momentum × price location) to select entry type, then use `technicals.py` output (support levels, SMA, ATR) to set specific prices. If the entry type is **Breakout buy**, validate with `knowledge/signals/breakout-filter.md` — all three must confirm (volume >1.5x avg + ATR move >1x + IV Rank <50). Grade the signal A-D and only proceed on A or B.

```
Market day type: [Trend / Range / Reversal / Munger / Event — from market-day-types.md]
Entry strategy: [Market buy / Limit buy / Scaled limits / DCA / CSP / Breakout buy]
Orders:
  - Order 1: [type] [size%] at $X — [rationale: SMA support, prior low, HVN, etc.]
  - Order 2: [type] [size%] at $X — [rationale: Entry 1 minus 1 ATR]
  - Order 3: [type] [size%] at $X — [rationale: Entry 2 minus 1 ATR]
DCA: $X/day in [account] — [full/half pace based on sector momentum + RSI]
Order duration: GTC / cancel after 30 days
```

**DCA pacing rules:**
- Sector Accelerating + RSI 30-60 → full pace
- Sector Accelerating + RSI >70 → half pace
- Sector Downtrend + RSI >50 → half pace
- Sector Downtrend + RSI <30 → full pace (contrarian)
- Earnings <7 days → half pace
- Stock >20% above SMA20 → half pace

**Scaled entry principle: Never lump-sum into a new position.** Always scale in with multiple orders at different price levels. This is a core principle, not optional.

- **Default split:** 40% starter / 30% second tranche / 30% third tranche
- **Spacing:** Use ATR to space orders — Entry 1 at target, Entry 2 at target minus 1 ATR, Entry 3 at target minus 2 ATR
- **Earnings within 14 days:** Cap pre-earnings entry at 40% max. Hold 60% for post-earnings deployment based on outcome (beat/miss/inline → different prices).
- **Why:** Lump-sum at entry target feels precise but assumes perfect timing. Scaling in captures better average cost if the stock dips further, and limits damage if the thesis is wrong or earnings surprise.

The only exception is tiny positions (<$1K) where splitting adds unnecessary complexity.

### 5b. Protection

Select based on position size relative to portfolio:

| Position Size | Protection Type |
|--------------|----------------|
| >15% of portfolio | Trailing stop or collar — MANDATORY |
| 5-15% | Trailing stop recommended |
| <5% | Mental stop — monitor weekly |

```
Stop type: [Hard stop / Trailing stop % / Collar / Protective put / Mental stop]
Stop level: $X (-Y% from entry)
Rationale: [below SMA50, 1.5x ATR below entry, thesis invalidation level]
Max loss: $X (Z% of portfolio)
```

**Stop placement methods (use the HIGHER of both):**
- ATR method: 1.5x ATR below entry (standard) or 2.0x ATR (conservative)
- SMA method: below SMA50 (uptrend) or below SMA200 (neutral)

**When NOT to use stops:** During DCA accumulation phase, deep value contrarian plays, options (risk already defined), tax-locked positions (use protective puts instead).

### 5c. Exit / Profit Taking

```
Target 1: $X (+Y%) — [sell Z%] — [rationale: analyst consensus, resistance level]
Target 2: $X (+Y%) — [sell Z%] — [rationale: stretch target, valuation-based]
Trailing stop: X% from high — [for remaining position after targets hit]
Time stop: [date] — [reassess or close if no progress]
Catalyst exit: [specific event that means immediate exit, regardless of price]
```

**Scaled exit template for large positions:**
- 25% at Target 1 (analyst consensus or first resistance)
- 25% at Target 2 (stretch target)
- 25% via trailing stop (let it run)
- 25% hold indefinitely (core compounder position)

**Risk/reward check:** Target 1 reward / stop loss risk should be >= 2:1. If less than 2:1, the entry price is too high — wait for a better level or widen the target.

### 5d. Execution Summary

End every plan with a target allocation and concrete order list. Do NOT specify which account — the user decides where to place orders.

```
## Execution Summary

Target allocation: Y% of total portfolio (based on conviction Z/10)
Current allocation: X% — [underweight/on-target/overweight]

Orders:
1. DCA: $X/day [full/half pace] — [duration or "ongoing"]
2. Limit buy: X shares at $X (GTC) — [support level rationale]
3. Limit buy: X shares at $X (GTC) — [deeper support rationale]
4. Stop: [type] at $X — [rationale]
5. Profit target: Limit sell X shares at $X — [rationale]
```

---

## Phase 6: Final Checklist

- [ ] Market regime allows new entries? (Phase 0)
- [ ] Conviction in the company (score ≥ 5)? (Phase 1)
- [ ] Entry timing makes sense given technicals? (Phase 2)
- [ ] Strategy skills have been run and outputs collected? (Phase 3)
- [ ] Best strategy selected with clear reasoning? (Phase 4)
- [ ] Execution plan with entry + protection + exit defined? (Phase 5)
- [ ] Risk/reward >= 2:1? (Phase 5d)
- [ ] Max loss on this trade < 2% of total portfolio? (Phase 5)
- [ ] No earnings/ex-div landmines in the trade window? (Phase 2)
- [ ] Position sizing appropriate for conviction level? (Phase 5)

**Final Verdict:** Go / No-Go / Wait — with a one-line summary, recommended strategy, and next action.

If "Wait": specify the concrete trigger to revisit:
- **Price trigger:** "Wait for pullback to $X support, then re-run"
- **Event trigger:** "Wait for post-earnings May 11, then re-run `/plan-stock`"
- **Regime trigger:** "Wait for market regime to improve (S&P reclaims 50 SMA)"
- **Time trigger:** "Revisit in 2 weeks if thesis holds"

---

Save the output to `research/stocks/$TICKER.md` (use uppercase ticker as filename).
Start the entry with a date separator: `---` followed by `# TICKER — Pre-Trade Plan | YYYY-MM-DD`.
If the file already exists, prepend the new analysis above all previous entries (after the YAML frontmatter block). Never remove historical entries.

If creating a new file, add YAML frontmatter at the top:
```yaml
---
ticker: TICKER
status: watching
added_date: YYYY-MM-DD
sector: (infer from research)
thesis: "(one-line summary of why this stock is interesting)"
entry_target: (target entry price from Phase 4)
strategies: [(recommended strategy from Phase 3)]
---
```

If the file already exists and has frontmatter:
- If status is `researched`, update it to `watching` (plan promotes to watchlist)
- Update `entry_target` and `strategies` based on Phase 4 results
- Prepend the new analysis entry below the frontmatter

**Update watchlist:**
```bash
.venv/bin/python3 scripts/watchlist.py
```
