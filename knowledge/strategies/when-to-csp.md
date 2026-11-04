# When to Sell Cash-Secured Puts (CSPs)

## What Is a CSP

You sell a put option and hold enough cash to buy 100 shares at the strike price if assigned. You collect premium upfront. If the stock stays above your strike through expiration, you keep the premium free and clear. If it drops below, you buy shares at the strike — but your effective cost basis is strike minus premium collected.

**Core mindset:** you're getting paid to place a limit buy order. Only sell CSPs on stocks you'd happily own at the strike price.

## The CSP Score Framework

Before selling any CSP, calculate the CSP Score. This is the CSP equivalent of the CC Sharpe Score — a composite that combines premium quality, downside protection, and risk timing into one number.

### Components (each scaled 0-100)

```
CSP Score = (IV Rank × 0.20) + (VRP Edge × 0.10) + (AnnYield Score × 0.25) + (Buffer Score × 0.20) + (Support Score × 0.10) + (Earnings Gate × 0.15)

Components (each scaled 0-100):
  IV Rank:        Use directly (0-100). Measures premium richness relative to its own 52-week range.
  VRP Edge:       IV < 0.9×RV20 = 0, within ±10% = 50, IV > 1.1×RV20 = 100
                  (Volatility Risk Premium — are you selling overpriced insurance? Same as CC Sharpe Gate 3.
                   RV20 = 20-day realized vol, annualized. Not ATR%: that's a daily number and
                   always looks tiny next to annual IV.)
  Compute with: `.venv/bin/python3 scripts/option-scores.py TICKER --csp` (scan) or `--csp --strike X --expiry YYYY-MM-DD`.
  Earnings timing used: inside the trade < 7 days before expiry = 0, 7+ days before = 25;
  after expiry 0-7 days = 50, 8-30 days = 75, later = 100.
  AnnYield Score: <12% = 20, 12-20% = 40, 20-35% = 65, 35-50% = 85, >50% = 100
  Buffer Score:   <5% = 15, 5-8% = 35, 8-12% = 60, 12-18% = 85, >18% = 100
  Support Score:  Above support = 20, >5% below support = 40, at support = 75, at volume shelf/HVN = 100
  Earnings Gate:  Earnings <7 days before expiry = 0, 7-14 days before = 25, within 7 days after = 50,
                  14+ days after = 75, no earnings in window = 100

Verdicts:
  Score > 65  →  SELL CSP — strong risk-adjusted setup
  Score 45-65 →  MARGINAL — only sell if conviction is high and you genuinely want assignment
  Score < 45  →  SKIP — wait for better conditions (IV expansion, pullback to support, earnings clearance)
```

**Design note:** Inspired by PutFinder's 4-stage pipeline (Liquidity Gate → Stock Quality → Contract Fit → Earnings Gate). Our CSP Score combines their Stock Quality (IV Rank + VRP) and Contract Fit (AnnYield + Buffer + Support) into one composite, with an Earnings Gate penalty. We skip PutFinder's Liquidity Gate since we manually check bid-ask spreads during trade execution. See https://putfinder.com/#how-it-works for their full methodology.

### Key Metrics

**Annualized Yield:**
```
AnnYield = (Premium / Strike) × (365 / DTE) × 100
```
Measures return on capital if the put expires worthless. Higher = more income for the risk taken.

**Buffer % (Downside Buffer):**
```
Buffer % = (Stock Price - Breakeven) / Stock Price × 100
where Breakeven = Strike - Premium
```
Measures how far the stock must drop before you're losing money. A 12% buffer means the stock can fall 12% and you still break even. Inspired by PutFinder's methodology — this is more intuitive than delta alone for assessing margin of safety.

| Buffer % | Signal |
|----------|--------|
| < 5% | Thin — one bad day wipes your premium. Aggressive. |
| 5-8% | Moderate — typical for near-the-money CSPs. Standard. |
| 8-12% | Good — meaningful cushion. Sweet spot for income. |
| 12-18% | Strong — wide margin of safety. Conservative income play. |
| > 18% | Very safe — but premium may be thin. Check AnnYield still justifies the trade. |

**Earnings Gate (Graded):**
Instead of binary "earnings within DTE = skip," use gradations:

| Earnings Timing | Gate Score | Action |
|----------------|-----------|--------|
| < 7 days before expiry | 0 | **Disqualify** — binary gap risk is uncompensated |
| 7-14 days before expiry | 25 | **Heavy penalty** — only if you'd own through any outcome at strike |
| Within 7 days after expiry | 50 | **Caution** — IV inflated from upcoming earnings, decent premium but post-earnings guidance risk |
| 14+ days after expiry | 75 | **Clear** — earnings resolved, IV normalizing |
| No earnings in window | 100 | **Ideal** — no binary event risk |

### Example

AMD at $510.67, selling $440P expiring 2026-08-21 (32 DTE) for $21.43 mid:
- IV Rank: ~60 (estimated) → Score: 60
- VRP Edge: IV 40% vs 20-day realized vol ~33% → IV > 1.1 × RV, edge → Score: 100
- AnnYield = ($21.43 / $440) × (365/32) × 100 = **55.5%** → Score: 100
- Breakeven = $440 - $21.43 = $418.57
- Buffer = ($510.67 - $418.57) / $510.67 = **18.0%** → Score: 100
- Support: $440 is near SMA50 support → Score: 75
- Earnings: Aug 5 before Aug 21 expiry, ~16 days before → Score: 25
- **CSP Score = (60 × 0.20) + (100 × 0.10) + (100 × 0.25) + (100 × 0.20) + (75 × 0.10) + (25 × 0.15) = 12 + 10 + 25 + 20 + 7.5 + 3.75 = 78.25** → SELL CSP

But note the earnings gate penalty — this is a pre-earnings CSP. The high score is driven by extreme premium, buffer, and VRP edge. If you're uncomfortable with the binary risk, the earnings gate is telling you to be cautious despite the headline number.

---

## When CSPs Have Edge

- **IV Rank > 50** — premium is rich relative to its own history. You're selling expensive insurance.
- **Stock at or near support** — technical floor reduces probability of assignment at a loss.
- **You want to own shares at strike** — this is the filter that prevents bad trades.
- **Range-bound to mildly bullish outlook** — CSPs profit when stock goes up, sideways, or even slightly down.
- **Post-selloff elevated IV** — fear spikes IV, you collect fat premium while others panic.

## Ideal Setup Checklist

- [ ] **CSP Score > 65** (calculate before entering — see CSP Score Framework above)
- [ ] IV Rank > 50 (prefer > 65)
- [ ] RSI 30-50 (oversold to neutral — not chasing)
- [ ] Stock at identifiable support level (SMA, prior low, volume shelf)
- [ ] Buffer % > 8% (meaningful downside cushion)
- [ ] Earnings Gate ≥ 50 (no uncompensated binary risk)
- [ ] Liquid options (bid-ask spread < 5% of mid price)
- [ ] Clear thesis — you know why you'd own this stock
- [ ] Position size < 5% of portfolio

## Delta & DTE Selection

| Parameter | Sweet Spot | Notes |
|-----------|-----------|-------|
| **Delta** | 0.20-0.30 | ~70-80% probability of profit. Balances premium vs. safety. |
| **DTE** | 30-45 days | Peak theta decay zone. Shorter = less premium. Longer = more capital tied up. |

**When to adjust delta:**
- **Go further OTM (0.15-0.20):** high IV Rank > 75, you want income not ownership, wider margin of safety needed
- **Go closer to ATM (0.30-0.40):** you actively want assignment, stock is deeply oversold at strong support, higher premium justifies the risk

## Decision Matrix: IV Rank x RSI

| IV Rank | RSI < 30 (oversold) | RSI 30-50 (neutral-low) | RSI 50-70 (neutral-high) | RSI > 70 (overbought) |
|---------|---------------------|------------------------|-------------------------|----------------------|
| **> 75** | **Best setup** — sell aggressively at support, 0.25-0.30 delta | Sell at 0.20-0.25 delta | Sell far OTM, 0.15-0.20 delta | Skip — wait for pullback |
| **50-75** | Sell at support, 0.20-0.25 delta | Standard CSP, 0.20 delta | Small position, far OTM | Skip |
| **25-50** | Consider DCA instead — not enough premium | Marginal — only if setup is perfect | Skip — use Buy & Hold | Skip |
| **< 25** | **Don't sell CSPs** — buy LEAPs instead | Skip — premium too thin | Skip | Skip |

## Earnings Considerations

The CSP Score's Earnings Gate handles this quantitatively (see above), but here's the qualitative guidance:

- **< 7 days before expiry (Gate = 0, disqualifier):** Gap risk is uncompensated. The stock can move 10-20% overnight and your buffer is meaningless. Skip unless you have a very specific thesis on the earnings outcome.
- **7-14 days before expiry (Gate = 25, heavy penalty):** IV is inflated — premium is rich. But you accept full binary risk. Only sell if you'd genuinely own shares through any outcome at your strike. The CSP Score will be dragged down by this penalty, so other components need to be very strong.
- **Within 7 days after expiry (Gate = 50, caution):** Earnings resolved but IV is still elevated and post-earnings drift can continue. Decent setup — you know the news, premium is still rich.
- **14+ days after expiry (Gate = 75, clear):** Earnings behind you, IV normalizing. Standard setup.
- **No earnings in window (Gate = 100, ideal):** No binary event risk. Full score.

**Never sell CSPs through earnings you don't understand.** Biotech FDA decisions, uncertain guidance — the gap risk isn't worth the premium.

**Post-earnings IV crush:** if you sold pre-earnings and it went your way, close at 50%+ profit immediately. Don't wait — the edge is gone.

## When NOT to Sell CSPs

- **IV Rank < 25** — you're selling cheap insurance. The math doesn't work.
- **Strong downtrend** — falling knife. Support levels break in downtrends. Wait for stabilization.
- **Thesis-breaking news** — regulatory action, fraud, competitive destruction. No amount of premium compensates.
- **Illiquid options** — wide bid-ask spreads eat your edge. If spread > 5% of mid, walk away.
- **You don't want to own the stock** — this is the #1 filter. If assignment would make you uncomfortable, don't sell the put.

## Management Rules

| Scenario | Action |
|----------|--------|
| Hit 50% of max profit | **Close.** Take the money. Re-sell at better levels if setup still valid. |
| Hit 65% of max profit | **Close.** Diminishing returns — remaining premium isn't worth the risk. |
| Stock drops to strike (tested) | **Roll down and out** — lower strike, extend 30 days. Only if thesis intact. |
| Stock drops through strike, thesis broken | **Close for a loss.** Don't roll a broken thesis. |
| Near expiration, stock well above strike | Let expire worthless or close for pennies to free up capital. |
| Assigned | **Own the shares.** Sell covered calls against them. This was the plan. |

**Close early rule of thumb:** close at 50% profit in the first half of the DTE period. After that, theta is your friend — let it run unless tested.

## Position Sizing

- **Max 5% of portfolio per CSP** (based on max loss = strike x 100 x contracts).
- Don't sell more contracts than shares you'd actually want to own. 5 contracts = 500 shares. Would you really buy 500 shares?
- **Diversify strikes and expirations.** Don't concentrate all CSPs in the same expiration week.

## Common Mistakes

1. **Selling CSPs on stocks you don't want to own** — chasing premium on garbage. When the stock drops 30%, you'll regret it.
2. **Ignoring assignment risk** — "it won't get assigned" is not a plan. If you'd panic at assignment, don't sell the put.
3. **No management plan** — decide your close target, roll trigger, and loss limit before entering.
4. **Selling in low IV** — collecting $0.50 on a $100 stock is not worth tying up $10,000.
5. **Oversizing** — selling 10 CSPs on one stock because "the premium is amazing." That's a concentrated bet, not income.
6. **Holding to expiration for max profit** — the last 20% of premium carries 80% of the remaining risk. Close early.
