# Position Sizing Framework

Conviction says how much you believe in a business. It doesn't say how much to own. This framework separates **how much** (target weight) from **when** (timing), and uses several metrics for both. The dashboard Holdings tab (`scripts/dashboard.py`) implements it.

## Decision Flow (how the layers fit)

```
Conviction  ← mostly fundamentals + a little technicals (research snapshot, slow-moving)
     ↓
Target %    ← conviction × valuation × volatility × sector momentum (cluster-capped)
     ↓
Status      ← actual % of total portfolio vs target (±25% = on target)
     ↓
Action      ← status × live technicals (RSI, trend, earnings timing)
```

**Where technicals enter (three places, three jobs):**

| Layer | Technicals used | Role |
|---|---|---|
| Conviction (`/research-stock`) | Trend/SMA stack, RSI/MACD, support/resistance, volume, sector stage, as of the research date | ~1/8 of the score (Business and Growth count 2x). A broken chart nudges conviction; it doesn't define it |
| Target (this framework) | Sector momentum only | Scales the target for the whole group (×1.1 accelerating, ×0.8 downtrend) |
| Action (dashboard, live) | RSI, distance from the 20-day, 200-day + sector (overlay), earnings within 7 days | Decides *when* to add or trim, never *how much* |

**Rule of thumb:** conviction and the target answer **"how much should I own?"** (they change slowly). Live technicals answer **"is now a good moment to change it?"** (every rebuild). An oversold reading on an on-target position means **Hold**, not Buy.

## 1. Target weight = conviction base × adjustments

| Factor | Measure | Multiplier | Rationale |
|---|---|---|---|
| **Conviction (base)** | Research score | 9+: 6.5% · 8: 4.5% · 7: 3.5% · 6: 2.0% · 5: 1.0% · <5: 0% | Midpoints of the conviction allocation bands |
| **Valuation** | Fwd P/E vs. sector band (simplified from `valuation.md`) | Cheap ×1.2 · Fair ×1.0 · Rich ×0.8 | Same belief at a better price → more room |
| **Volatility** | ATR % (14-day mean true range / price) | < 3%: ×1.1 · 3–6%: ×1.0 · > 6%: ×0.75 | Size for equal *risk*, not equal dollars |
| **Sector momentum** | `sector-momentum.py` category | Accelerating Up ×1.1 · Downtrend/Capitulation ×0.8 | Don't build size against the sector tide |
| **Cluster cap** | Correlated clusters (`correlation.py`) | Scale members so a cluster's targets total ≤ 25% | Highly correlated names are one bet |
| **Overrides** | Local file `portfolio/allocation-overrides.md` (gitignored) | Fixed min–max band | Intentional exceptions (long holds, employer-stock caps) |

Sector P/E bands (cheap below / rich above): Technology 20/40 · Communication Services 18/35 · Consumer Discretionary 18/40 · Consumer Staples 16/28 · Healthcare 15/30 · Financials 12/25 · Energy 10/20 · Industrials 18/35 · Utilities 14/22 · Materials 12/25 · Real Estate 15/35.

**Example:** conviction 8 (4.5%), fwd P/E 5x in Technology (cheap ×1.2), ATR 7% (×0.75) → **4.05%**. Conviction 7.3 (3.5%), fwd P/E 32x (fair), ATR 4% → **3.5%**.

## 2. Status = actual vs. target
- **On target:** within ±25% of the target weight.
- **Under / Over:** outside that band. Show the gap in points and dollars.
- **Far under / over:** gap ≥ max(2 pts, 50% of target).

## 3. Action = status × timing
| | Timing good (RSI < 40, or > 8% below SMA20) | Neutral | Timing poor (RSI > 65, or > 10% above SMA20) |
|---|---|---|---|
| **Under** | Add zone | DCA | Wait for pullback |
| **Over** | Trim on bounce | Trim on strength | Trim into strength |

**Overlays:**
- Earnings within 7 days → **Wait: earnings** (don't resize into a binary event).
- Below SMA200 in a Downtrend/Capitulation sector → "Add zone" becomes **DCA slowly**.
- Overrides show **Exception** instead of an action.

## Limits
- Multipliers are heuristics, not optimized. Treat the targets as ±1 pt guidance.
- Fwd P/E is a poor valuation measure for unprofitable or cyclical-peak companies. Read the research file for those.
- The cluster cap depends on 6-month correlations, which shift in regime changes.
- Targets are % of the **total** portfolio across accounts. Which account to buy or sell in is a separate (tax-aware) decision; see `tax-rules.md`.
