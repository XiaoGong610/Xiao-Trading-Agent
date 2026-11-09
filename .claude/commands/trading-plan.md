---
description: Generate the weekly trading plan — DCA, orders, position management, key dates
---

Generate the weekly trading plan from the latest portfolio review and research data.

This skill **prescribes** — it turns analysis into specific, executable actions. It reads the portfolio review output, checks that recommendations are backed by `/plan-stock` research, and produces a concrete plan the user can execute in their brokerage.

**Prerequisite:** `/portfolio-review` should be run first to produce `portfolio/REVIEW-YYYY-MM-DD.md`. If no recent review exists, note it and work from account files + watchlist data directly.

---

## Step 1: Gather Context

### 1a. Portfolio Review

Read the most recent portfolio review: `portfolio/REVIEW-YYYY-MM-DD.md` (sort by date, take latest).

Extract:
- Recommendations (Do This Week, Do This Month, Watch)
- DCA assessment (which to accelerate, pause, maintain)
- Options review (rolls, closes, new CCs/CSPs needed)
- Research gaps
- Execution scorecard from prior plan (carry-forward items)

If no recent review exists (<7 days), flag: "No fresh portfolio review. Run `/portfolio-review` first for best results, or I'll work from account files directly."

### 1b. Account Data

Read all account files:
```
portfolio/accounts/hold.md
portfolio/accounts/thetagang.md
portfolio/accounts/roth-ira.md
portfolio/accounts/brokeragelink.md
portfolio/accounts/gobig.md
```

Note: cash levels, active options (expiry dates, ITM/OTM status), DCA schedules from constraints.

### 1c. Watchlist & Market Context

```bash
.venv/bin/python3 scripts/watchlist.py --json --no-save
```

Read market overview: `research/sectors/0-market-overview.md` — pull regime classification.

### 1d. Prior Plan

Read the most recent plan: `portfolio/plans/PLAN-*.md` (sort by date, take latest).
Carry forward anything marked "Not Done" with weeks pending. These appear first in the new plan.

---

## Step 2: Plan-Stock Coverage Gate

Before generating the plan, check that every NEW trade recommendation (new entry, new CC, new CSP, new LEAP) is backed by a recent `/plan-stock`. This is a **gate**, not documentation — resolve gaps now, don't just note them.

1. For each new trade recommendation (>$2K deployment), read `research/stocks/{TICKER}.md` and check for a Pre-Trade Plan entry dated within 14 days.
2. **If missing or stale:** Ask the user: "TICKER needs a fresh /plan-stock before I can recommend specific entry/exit. Run it now, or proceed without?" If user says yes, run `/plan-stock {TICKER}` and integrate the output. If user says proceed, note the gap briefly in the plan header (not as a table).
3. **Exceptions (no /plan-stock needed):** Selling existing positions, rolling/closing options, DCA pace changes, adjustments <$1K.

**Do NOT include a Plan-Stock Coverage table in the final plan output.** This is an internal check, not user-facing content.

---

## Step 3: DCA Schedule

Build the proposed DCA schedule. Pull from the portfolio review's DCA assessment and current account constraints.

| Ticker | Conv | Previous $/Day | Proposed $/Day | Change | RSI | Gap% | Assessment |
|--------|------|---------------|----------------|--------|-----|------|------------|
| **MU** | 9.0 | $150 | $150 | — | 57 | -11.7% | Best setup. Below target. |
| ~~META~~ | 7.8 | $0 | $0 | Paused | 33 | +1.7% | Near target but sector weak. |
| **Total** | | $X | $Y | +/-$Z | | | |

**Rules:**
- Conviction 8+ and gap <0% → ACCELERATE (increase by $25-50/day)
- RSI > 70 → PAUSE (overbought)
- Far above target (gap >30%) → PAUSE
- Conviction <6 → STOP (remove from DCA)
- Total daily DCA must be sustainable: check cash runway ≥ 4 weeks

**Cash runway check:**
```
Cash runway = Account cash ÷ (Daily DCA × trading days per week)
```
If < 4 weeks: flag 🔴 and recommend reducing total DCA or selling non-thesis positions to extend.

---

## Step 4: One-Time Orders

Specific orders to place this week. Each order must have:
1. **Clear action** — buy/sell, quantity, type (market/limit/CC/CSP/LEAP)
2. **Price target** — exact strike, limit price, or "market"
3. **Account** — which account
4. **Rationale** — why now, backed by /plan-stock or portfolio review
5. **Deadline** — when to execute by

| # | Order | Type | Account | Detail | Rationale | Deadline |
|---|-------|------|---------|--------|-----------|----------|

**Order priority:**
1. Carry-forward items from prior plan (overdue actions first)
2. Risk management (rolls, closes on expiring options)
3. Income generation (CCs on uncovered shares)
4. New entries (backed by /plan-stock)
5. Cleanup (sell no-thesis positions)

**Pre-trade gates:**
- New CC → verify CC Sharpe > 60: `scripts/option-scores.py TICKER --cc --strike X --expiry D --cost-basis Y`
- New CSP → verify CSP Score > 45: `scripts/option-scores.py TICKER --csp --strike X --expiry D`
- New entry → verify /plan-stock exists and entry target/stop are set
- New LEAP → verify the IV Rank < 30 gate: `scripts/option-scores.py TICKER --leap`

For any order that fails a gate, note the failure and either skip or flag for user decision.

---

## Step 5: Position Management

Actions on existing positions — everything currently held that needs attention:

| Action | Ticker | Account | Detail | Deadline |
|--------|--------|---------|--------|----------|
| **SELL CCs** | TSLA 3x | ThetaGang | $370C Sep 18 | Monday |
| **ROLL** | AMZN $255C | HOLD | → $275C Oct 2 | By Aug 20 |
| **HOLD** | COIN | All | Underwater, hold | — |
| **MONITOR** | IGV $110C | GoBig | +105%, partial at 125% | — |

**Action types:**
- **SELL CC / CSP** — income generation on existing shares
- **ROLL** — extend expiry on options approaching expiry
- **CLOSE** — take profit or cut loss on options
- **TRIM** — reduce overweight position
- **HOLD** — no action needed, thesis intact
- **MONITOR** — watch for trigger (profit target, support break, earnings)
- **DELIBERATE HOLD** — user explicitly chose to hold despite signals
- **LET EXPIRE** — option is worthless, let it expire

---

## Step 6: Key Dates

All events in the next 2 weeks that require preparation:

| Date | Event | Ticker | $ Exposure | Action If... |
|------|-------|--------|------------|-------------|
| Aug 25 | NVDA earnings | NVDA | $20,065 | Beat → continue DCA. Miss → pause, reassess. |
| Aug 28 | AMZN $255C expiry | AMZN | 100 shares | Roll before this date. |
| Sep 18 | TSLA CCs expiry | TSLA | 300 shares | Monitor. OTM = keep premium. |

Sources:
- Earnings dates from watchlist JSON (`earnings_days` field)
- Options expiry dates from account files
- FOMC meetings, jobs reports from `research/sectors/0-market-overview.md`

---

## Step 7: Risk Budget

How much capital is being deployed and what's the exposure:

| Metric | Value |
|--------|-------|
| Total portfolio | $X |
| Total cash across accounts | $X (Y%) |
| DCA this week | $X (daily × 5 days) |
| New capital deployed (one-time orders) | $X |
| Expected CC/CSP income | $X |
| Cash remaining after deployment | $X per account |
| DCA runway after deployment | X weeks |
| Top 3 concentration | X%, Y%, Z% = total% |
| Biggest single-position risk | TICKER $X (describe risk) |
| Earnings exposure next 7 days | $X total |

---

## Step 8: Summary — Top 3 Priorities

Distill everything into the 3 most important actions this week. These are the "if you do nothing else, do these" items.

Write them as numbered paragraphs with:
- What to do (specific, actionable)
- Why it matters (urgency, $ at stake, opportunity cost)
- Deadline

Prioritize by: (1) risk management → (2) income generation → (3) growth.

---

## Step 9: Save Outputs

1. **Save the plan** → `portfolio/plans/PLAN-YYYY-MM-DD.md`

Format:
```markdown
# Weekly Trading Plan | YYYY-MM-DD

## At a Glance
| When | Account | Order | Price / Trigger |
|------|---------|-------|-----------------|
| Mon 10:00–11:30 | AccountName | GTC sell 100 XYZ | $123.45 |
| On trigger | AccountName | Sell 1× XYZ $150C Jan 15 | first green day with XYZ ≥ $140 |

**DCA:** AccountName $X/day (TICKER $a · TICKER $b) · **Key dates:** Tue CPI · Thu ABC earnings · …

*(Keep this section ≤ 12 rows, one line per order, full account names, no reasoning. The dashboard shows it first and collapses everything else under "Show full plan".)*

---

**Regime:** [from market overview]

**Portfolio: $XXX,XXX (+/-$X / +/-X% WoW).** [key narrative]

**Execution rate last plan: X%.** [scorecard summary]

---

## DCA Schedule (AccountName — $X/day)
[Table from Step 3]

---

## One-Time Orders (This Week)
[Table from Step 4]

---

## Position Management
[Table from Step 5]

---

## Key Dates
[Table from Step 6]

---

## Risk Budget
[Table from Step 7]

---

## Summary: 3 Things That Matter Most This Week
[From Step 8]
```

2. **Run the post-plan gates:**
```bash
.venv/bin/python3 scripts/plan-lint.py
```
Fix every ERROR in the plan and re-run until it exits 0. If the user deliberately overrides a rule (e.g. DCA out of conviction order), add `lint-ok` to that plan line instead. Don't report the plan as checked while errors remain. Still do the non-mechanical gates by hand: harvest scan of sold options (>50% captured) and off-plan positions that contradict conviction.

3. **Regenerate the dashboard:**
```bash
.venv/bin/python3 scripts/watchlist.py
```
This saves 0-WATCHLIST.md and generates the unified HTML dashboard (which automatically picks up the new PLAN markdown for the Trading Plan tab).
