---
description: Portfolio advisor — analyze positions against goals and recommend changes
---

Run a portfolio review and generate actionable recommendations.

This is NOT a transaction tracker — it's an investment advisor layer. The brokerage tracks transactions. We track strategy, goals, and what to do next.

## Step 0: Collect Current Positions

**Ask the user to share screenshots of each account.** This is the source of truth for current holdings.

When the user shares account screenshots:

1. **Parse each screenshot** — extract: ticker, shares, cost basis, current price, gain/loss, % of account, and any options positions (strike, expiry, quantity, value).
2. **Update the account files** — overwrite the Positions section in `portfolio/accounts/{account-name}.md` with fresh data from the screenshots. Preserve the YAML frontmatter (goals, constraints, strategy, risk tolerance) — only refresh the numbers.
3. **Update `last_updated` in frontmatter** to today's date.
4. **Update `total_value` and `cash`** in frontmatter.
5. **Preserve Flags section** — update flags based on new data (e.g., concentration %, underwater positions, options status). Remove flags that are no longer relevant, add new ones.
6. **Preserve Review Cadence section** — these are durable notes, don't remove them.

**Account file structure:**
```yaml
---
account_name: NAME
account_id: ID
account_type: brokerage | roth-ira | 401k-brokeragelink
total_value: (from screenshot)
cash: (from screenshot)
last_updated: YYYY-MM-DD
goal: "..."
strategy: ...
risk_tolerance: ...
time_horizon: ...
benchmark: ...
constraints:
  - ...
---

## Positions
(tables of current holdings — refreshed from screenshots)

## Options Positions
(active options — refreshed from screenshots)

## Flags
(concentration warnings, underwater positions, urgent items)

## Review Cadence
(durable notes on when/how to review — preserved across updates)
```

**If the user hasn't shared screenshots** in this conversation, read the existing account files and note their `last_updated` date. If stale (>7 days), ask the user: "Your account data is from [date]. Want to share updated screenshots before I run the review?"

## Step 0b: Execution Tracking — Prior Plan Accountability

Find the most recent plan file: `portfolio/plans/PLAN-*.md` (sort by date, take latest). If no prior plan exists, skip this step.

1. **Read the prior plan's "One-Time Orders" and "Position Management" tables.**
2. **For each item, check against current account files** — did the position change? Was the option rolled/closed? Was the stock sold?
3. **Show an execution scorecard:**

| # | Item (from prior plan) | Status | Weeks Pending |
|---|------------------------|--------|---------------|
| 1 | ... | ✅ Done / ❌ Not Done / ⚠️ Partial | 0 / 1 / 2+ |

4. **Flag CARRY-FORWARD items** — anything "Not Done" that also appeared in the plan before that (check second-most-recent plan). These are chronically deferred actions that need a decision: do it, defer with reason, or drop it.
5. **Execution rate:** Done ÷ total. If < 50%, note: "Execution rate is low — consider whether plans are too ambitious or if there are blocking issues."

This step goes first so the user sees accountability before new analysis.

## Step 1: Read Account Files & Market Context

Read all account files:
```
portfolio/accounts/hold.md
portfolio/accounts/thetagang.md
portfolio/accounts/roth-ira.md
portfolio/accounts/brokeragelink.md
portfolio/accounts/gobig.md
```

Read the latest market overview:
- `research/sectors/market-overview.md` — market regime, key risks

Run the watchlist for context (keep parsed JSON available — referenced in Steps 2-5):
```bash
.venv/bin/python3 scripts/watchlist.py --json
```

## Step 2: Cross-Account Analysis

This is the most important step. Individual account views hide the real risk.

### 2a. Cross-Account Concentration

Aggregate holdings across ALL accounts. For each stock held in multiple accounts:

| Stock | Total Shares | Total Value | % of Total Portfolio | Accounts |
|-------|-------------|-------------|---------------------|----------|

Flag:
- Any single stock >15% of total portfolio
- Any sector >30% of total portfolio
- Leveraged ETFs (TSLL, CONL, etc.) — calculate notional exposure
- Employer stock — flag career concentration risk

### 2b. Sector/Theme Allocation

| Sector/Theme | Value | % of Portfolio | Assessment |
|-------------|-------|---------------|------------|

### 2c. Cash Position

| Account | Cash | Cash % | Notes |
|---------|------|--------|-------|
| **Total** | | | |

**DCA runway alert:** For accounts running daily DCA (e.g., BrokerageLink), calculate cash runway = cash ÷ daily DCA spend.

| Runway | Signal | Action |
|--------|--------|--------|
| < 3 weeks | 🔴 **CRITICAL** | DCA will stop. Sell non-thesis positions or reduce DCA immediately. |
| 3-4 weeks | ⚠️ **LOW** | Plan cash infusion (sells, transfers) within 1-2 weeks. |
| 4-6 weeks | Minimum comfortable | Monitor weekly. |
| 6+ weeks | ✅ Healthy | No action needed. |

If any DCA account is below 4 weeks runway, flag it in Step 6 "Do This Week" recommendations with specific sells to extend runway.

### 2d. Portfolio Metrics

| Metric | Value |
|--------|-------|
| Total portfolio value | $X |
| Change since last review | +/-$X (+/-X%) — compare against prior `portfolio/REVIEW-*.md` total |
| Weighted avg conviction | X.X — sum of (conviction × position weight) for each held stock |
| Cash runway at DCA pace | X weeks — total cash across all accounts ÷ weekly DCA spend |
| Options: notional at risk (sold puts) | $X — sum of strike × 100 × contracts for all sold puts |
| Options: upside capped (sold calls) | $X — sum of strike × 100 × contracts for all sold calls |

For conviction scores, pull from the watchlist JSON (`conviction` field) or from `research/stocks/{TICKER}.md` frontmatter. For positions not on the watchlist, use conviction 5.0 (neutral).

### 2e. Sector Momentum Overlay

Run sector momentum:
```bash
.venv/bin/python3 scripts/sector-momentum.py --json
```

Map each portfolio position to its GICS sector (use the stock's `sector` field from watchlist JSON or research file frontmatter) and cross-reference:

| Sector | Portfolio % | Momentum | Weinstein Stage | Strategy Implication |
|--------|------------|----------|-----------------|---------------------|

**Flag misalignments:**
- Portfolio overweight (>20%) in sectors classified as "Downtrend" or Weinstein Stage 3-4 — consider reducing exposure or pausing DCA.
- Portfolio underweight (<5%) in sectors classified as "Accelerating Up" — check watchlist for entry candidates in that sector.
- Any position in a Stage 4 (decline) sector — flag for review regardless of individual stock thesis.

## Step 3: Position-Level Review

For each position across all accounts:

| Ticker | Account | Shares | Value | Cost | P&L% | Action |
|--------|---------|--------|-------|------|------|--------|

**Action categories:**
- **HOLD** — on track, no changes needed
- **ACCELERATE DCA** — oversold + thesis intact → increase DCA pace
- **REDUCE** — overbought + overweight → trim or pause DCA
- **SELL CCs** — holding shares + not selling covered calls = missed income. Run CC Sharpe check first (`knowledge/strategies/when-to-cc.md`).
- **ADD CSP** — IV rich + at support → sell premium
- **ADD LEAPS** — IV cheap + high conviction → buy leverage
- **REVIEW** — thesis may be changing, needs `/research-stock` refresh
- **EXIT** — thesis broken or position no longer fits goals

**Tax-aware sell order:** When recommending EXIT or REDUCE on a position held across multiple accounts, consult `knowledge/frameworks/tax-rules.md` for the correct account priority:
- Selling a **loser** → taxable account first (harvest the tax loss)
- Selling a **winner** → tax-free account first (no tax on gains)
- Flag any position approaching 1-year holding mark in taxable accounts

### Options Review

For each active option:

| Option | Account | Expiry | DTE | Status | P&L | Action |
|--------|---------|--------|-----|--------|-----|--------|

Flag:
- Options expiring within 14 days
- Sold puts that are ITM (assignment risk)
- LEAPs below 90 DTE (roll or close)
- Covered calls near the money (assignment risk)

### Options Intelligence (enhanced)

**Uncovered shares → CC Sharpe screen:** For every held stock with 100+ uncovered shares, calculate the CC Sharpe Score with `.venv/bin/python3 scripts/option-scores.py TICKER --cc --cost-basis Y` (method in `knowledge/strategies/when-to-cc.md`). If CC Sharpe > 60, flag: "SELL CC — Sharpe [score]" with suggested delta/DTE. If < 40, note: "CC not justified — premium too thin."

**CSP recommendations → CSP Score gate:** Before recommending "ADD CSP" on any position, calculate the CSP Score (6-component composite: IV Rank, VRP Edge, AnnYield, Buffer %, Support, Earnings Gate) with `.venv/bin/python3 scripts/option-scores.py TICKER --csp` (method in `knowledge/strategies/when-to-csp.md`). If CSP Score < 45, do not recommend — note "CSP Score [X] < 45 — skip." Only recommend CSPs that score > 45.

**Sold puts → Buffer % monitoring:**

| Put | Strike | Premium | Breakeven | Stock Price | Buffer % | Status |
|-----|--------|---------|-----------|-------------|----------|--------|

Buffer % = (Stock Price - Breakeven) / Stock Price × 100. Flag any with Buffer < 5% as "⚠️ THIN BUFFER — roll or close."

**Sold calls → distance and earnings check:** For each sold call, show distance-to-strike % = (Strike - Stock Price) / Stock Price × 100. If earnings falls within DTE, flag: "⚠️ EARNINGS IN WINDOW — [X] days before expiry."

### Earnings Risk Dashboard

For all held positions, check `earnings_days` from the watchlist JSON. For positions not on the watchlist, check `next_earnings` from `research/stocks/{TICKER}.md` frontmatter.

| Ticker | Earnings Date | Days Out | Shares | $ Exposure | Options Through Earnings? | Max Risk |
|--------|--------------|----------|--------|------------|--------------------------|----------|

Flag:
- Positions with earnings in next 14 days → ensure they appear in Step 7 "Key Dates."
- Sold puts through earnings → calculate max assignment cost if stock gaps down.
- Sold calls through earnings → flag assignment risk if stock could gap above strike.
- Positions with NO research file or stale research (>30 days) going into earnings → flag: "⚠️ RESEARCH NEEDED before earnings."

## Step 4: Research-to-Portfolio Alignment

Compare the research conviction scores against actual portfolio weights:

| Stock | Conviction | Portfolio % | Should Be % | Gap | Action |
|-------|-----------|-------------|-------------|-----|--------|

**Key question:** Are your biggest positions your highest-conviction ideas? If not, what's blocking alignment (taxes, timing, inertia)?

### Watchlist Pipeline: Ready-to-Enter Stocks

From the watchlist JSON (loaded in Step 1), filter for stocks where `gap_pct < 0` (price below entry target) that are NOT currently held in any portfolio account.

| Ticker | Conv | Price | Entry Target | Gap% | Sector | Strategies | Why Not In Portfolio? |
|--------|------|-------|-------------|------|--------|------------|---------------------|

For each stock shown, prompt: "This is below your entry target. Should we plan an entry this week?" If the list is empty, note: "No watchlist stocks are below entry targets right now."

## Step 5: DCA Schedule Review

If the user has active DCA schedules (recurring buys), pull conviction, gap-to-target, and RSI from the watchlist JSON:

| DCA | $/Day | Position Size | Conv | Gap% | RSI | Assessment | Change? |
|-----|-------|--------------|------|------|-----|------------|---------|

**Flags:**
- **Overpaying?** DCA into stocks >20% above entry target (`gap_pct > 20`) — consider pausing or reducing until price returns to target zone.
- **Missing accumulation?** High-conviction stocks (conv ≥ 8) with NO active DCA and position underweight vs. conviction-based target — flag: "No DCA on high-conviction underweight name."
- **RSI-based pacing:** RSI < 35 → "ACCELERATE — oversold." RSI > 70 → "PAUSE — overbought, let it cool." RSI 35-70 → "MAINTAIN."

Recommend adjustments: increase for high-conviction underweight names at or below target, decrease/pause for overweight, above-target, or low-conviction names.

## Step 6: Recommendations

### Do This Week (urgent)

| # | Action | Account | Detail | Why |
|---|--------|---------|--------|-----|
| 1 | ... | ... | ... | ... |

### Do This Month

| # | Action | Account | Detail | Why |
|---|--------|---------|--------|-----|

### Watch (conditional)

| Trigger | Action | Account |
|---------|--------|---------|

### Research Gaps

| Candidate | Why | Next Step |
|-----------|-----|-----------|

## Step 7: Save Review Output

Save the portfolio review to `portfolio/REVIEW-YYYY-MM-DD.md` (Steps 0b-6: execution tracking, analysis, positions, alignment, recommendations).

This review answers: **"How is my portfolio doing? What should I pay attention to?"**

The actionable trading plan (DCA schedule, specific orders, position management, key dates, risk budget) is generated separately by `/trading-plan`. After completing this review, suggest: "Run `/trading-plan` to generate this week's action items."

**Do NOT auto-update account files** — only update when the user shares fresh screenshots. The account files are refreshed at Step 0, not at the end.
