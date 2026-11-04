# When to Sell Covered Calls (CCs)

## What Is a CC

You own 100+ shares and sell a call option against them. You collect premium upfront. If the stock stays below your strike through expiration, you keep the premium AND the shares. If it rises above the strike, your shares get called away at the strike — you sell at that price.

**Core mindset:** You're getting paid to place a limit sell order. Only sell CCs at a strike where you'd be happy exiting the position.

**Key difference from CSPs:** CSPs = you WANT assignment (buying at a discount). CCs = you DON'T want assignment (selling your shares). This means CCs require a higher bar — you're risking giving up a winning position.

## The CC Sharpe Framework

Before selling any CC, run this 4-gate check. ALL must pass.

### Gate 1: Is IV Rank > 50?

| IV Rank | Signal | Action |
|---------|--------|--------|
| > 50 | Premium is rich | **PASS** — proceed to Gate 2 |
| 25-50 | Below average | **MARGINAL** — only proceed if premium yield > 1.5% for 30 DTE |
| < 25 | Premium is thin | **FAIL** — don't sell CCs. Premium doesn't justify capping upside. |

**Why this matters:** IV Rank tells you if you're selling expensive or cheap insurance. Selling CCs when IV is low = collecting pennies while risking dollars of upside. The whole edge of theta gang is selling when premium is rich.

### Gate 2: Is premium yield sufficient?

Calculate annualized premium yield for the candidate strike:

```
Premium Yield = (CC premium per share / stock price) × (365 / DTE) × 100

Thresholds:
  > 15% annualized  →  Excellent — strong CC setup
  8-15% annualized  →  Acceptable — standard CC trade
  < 8% annualized   →  Insufficient — not worth capping upside. FAIL.
```

**Example:** TSLA at $380, selling $430C 30 DTE for $5.00 premium.
- Yield = ($5 / $380) × (365/30) × 100 = 16.0% annualized → **Excellent**

**Example:** AMZN at $233, selling $260C 30 DTE for $1.50 premium.
- Yield = ($1.50 / $233) × (365/30) × 100 = 7.8% annualized → **Insufficient**

### Gate 3: Is IV > Realized Volatility?

```
IV > 20-day Realized Vol  →  PASS — you're selling expensive insurance (edge exists)
IV ≈ 20-day Realized Vol  →  NEUTRAL — no special edge, proceed only if Gates 1-2 are strong
IV < 20-day Realized Vol  →  FAIL — options are cheap, stock is moving more than implied. No edge.
```

**How to measure:** Compare the ~30-day ATM IV with 20-day realized volatility, both annualized. `scripts/option-scores.py` computes both.

```
RV20 = stdev(daily log returns, last 20 days) × √252 × 100
IV > 1.1 × RV20        →  edge in selling (score 100)
within ±10% of RV20    →  neutral (score 50)
IV < 0.9 × RV20        →  no edge (score 0)
```

Don't compare IV with ATR% (ATR / price). ATR% is a *daily* move and IV is *annual*, so IV always looks far higher and the gate always passes. (An earlier version of this doc did that.)

### Gate 4: Would you be happy selling at the strike?

This is the most important gate. Ask:

- If the stock gets called away at this strike, do I regret it?
- Is this above my cost basis? (Never sell CCs below cost basis — locks in a loss if assigned)
- Am I selling at a price that represents fair value or above?
- Would I voluntarily sell my shares at this price without the CC?

If any answer is "no" → **FAIL**. Move the strike higher or don't sell the CC.

## CC Sharpe Score

After passing all 4 gates, calculate a composite score:

```
CC Sharpe Score = (IV Rank × 0.35) + (Yield Score × 0.35) + (IV vs RV Edge × 0.15) + (Earnings Gate × 0.15)

Components (each scaled 0-100):
  IV Rank:           Use directly (0-100)
  Yield Score:       <8% ann = 20, 8-12% = 50, 12-20% = 75, >20% = 100
  IV vs RV Edge:     IV < RV = 0, IV ≈ RV = 50, IV > RV by 10%+ = 100
  Earnings Gate:     Earnings <7 days before expiry = 0, 7-14 days before = 25,
                     within 7 days after = 50, 14+ days after = 75, no earnings in window = 100

Verdicts:
  Score > 60  →  SELL CC — good risk-adjusted trade
  Score 40-60 →  MARGINAL — only sell if you actively want to reduce position or generate income
  Score < 40  →  DON'T SELL — premium doesn't justify the trade. Wait for IV expansion or higher prices.
```

**Compute it, don't estimate it:** `.venv/bin/python3 scripts/option-scores.py TICKER --cc` (scan) or `--cc --strike X --expiry YYYY-MM-DD --cost-basis Y` (one contract). The script applies all four gates and the score. IV Rank comes from `--iv-rank` if you pass one (e.g. from Barchart), otherwise from the daily IV log in `research/iv-history/` once it has 120 days, otherwise an estimate from the 1-year realized-vol range (labelled as such). Earnings Gate timing: earnings inside the trade < 7 days before expiry = 0, 7+ days before = 25; after expiry 0–7 days = 50, 8–30 days = 75, later = 100.

**Display the CC Sharpe Score before any CC recommendation.** This prevents the common mistake of selling CCs just because you own shares.

## When CCs Have Edge

- **IV Rank > 50** — premium is rich. You're getting paid well for the risk.
- **Stock near resistance** — natural ceiling reduces probability of blowing past your strike.
- **Range-bound or mildly bearish outlook** — CCs profit when stock goes sideways, slightly up, or down.
- **Post-rally elevated IV** — stock ran up, IV expanded, now you lock in gains via CC premium.
- **You'd be happy to sell at the strike** — this turns an exit plan into income generation.

## Ideal Setup Checklist

- [ ] CC Sharpe Score > 60
- [ ] IV Rank > 50 (prefer > 65)
- [ ] Premium yield > 8% annualized (prefer > 12%)
- [ ] IV > 20-day realized volatility (annualized)
- [ ] Strike above cost basis
- [ ] Strike at identifiable resistance level
- [ ] No earnings within DTE window (unless intentional)
- [ ] Liquid options (bid-ask spread < 5% of mid price)
- [ ] You'd be happy selling shares at the strike price
- [ ] Position size: don't cover ALL shares — keep 30-40% uncovered for upside

## Delta & DTE Selection

| Parameter | Sweet Spot | Notes |
|-----------|-----------|-------|
| **Delta** | 0.15-0.25 | ~75-85% probability of expiring worthless. Conservative. |
| **DTE** | 30-45 days | Peak theta decay zone. |

**When to adjust delta:**
- **Go further OTM (0.10-0.15):** High IV Rank > 75, want to keep shares, just collecting income
- **Go closer to ATM (0.25-0.35):** Actively want to exit the position, stock is near your sell target, want maximum premium

## Coverage Rules

**Never cover 100% of your shares.** If the stock gaps up on a catalyst, uncovered shares participate in the upside.

| Situation | Max Coverage |
|-----------|-------------|
| High conviction, want to keep | 30-40% of shares |
| Moderate conviction, income focus | 50-60% of shares |
| Low conviction, want to exit gradually | 70-80% of shares |
| Actively want out | 100% (accept full assignment) |

**Stagger expirations.** Don't sell all CCs in the same week. Spread across 2-3 different expirations so you're never 100% exposed to one date.

### Ladder Rule (≥ 2 contracts on one stock)

Default to a **ladder**, not N identical calls:
1. **Stagger the strikes.** Spread them ~+20% → +50% OTM (e.g. +22 / +34 / +40 / +48%) so assignment trims gradually on the way up.
2. **Pace the timing.** Sell ~half now, and the rest only on **strength triggers**: a post-earnings close ≥ +10%, or a rally to resistance. Never sell the held-back tranches into weakness.
3. **Mix the expiries.** Use 2-3 dates, per the stagger rule above.

**Backtest evidence** (`scripts/cc-ladder-backtest.py`, Oct 24, 2026). 8 volatile names (COIN, CRCL, TSLA, NVDA, MU, AMZN, MSTR, HOOD), rolling 55-day windows, Black-Scholes at 1.15× realized vol. Overlay P&L is the % of position value vs. holding shares with no calls:

| Strategy | Mean | Win % | Worst 5% | In >30% rallies | Flat | Down >15% |
|---|---|---|---|---|---|---|
| A. 4× uniform +22% now | −1.5% | 78% | **−45%** | **−30%** | +6.8% | +7.2% |
| B. Strike ladder now | −0.8% | 82% | −35% | −20% | +5.0% | +5.2% |
| C. Strike + timing ladder | −0.8% | 82% | **−33%** | **−19%** | +4.4% | +4.0% |

**Reading:**
- **Laddering is risk management, not extra return.** It cuts the worst-case cost of capped upside by about a third (−45% → −33%) and the rally drag from −30% to −19%. The price is ~2–3 pts less income in flat or down windows.
- **Pacing (C vs B) adds a little more tail protection** and gives up some downside cushion, because the held-back calls never get sold in a drop.
- **On strong-trend names (TSLA, NVDA, MU, MSTR), every CC overlay had a negative mean.** CCs there are an exit or income tool, not a free edge. On long-hold trend names, keep CCs far OTM only.

**Limitations:**
- Selection bias: most of these names were big winners.
- No volatility skew or earnings IV bumps in the pricing.
- No commissions.
- The windows overlap.

Treat the direction as reliable and the exact numbers as rough.

## When NOT to Sell CCs

- **CC Sharpe Score < 40** — the math doesn't work. Wait.
- **IV Rank < 25** — premium is thin. You're giving away upside for pennies.
- **Stock is oversold (RSI < 35) with intact thesis** — bounce is the highest-probability move. Selling CCs here caps the recovery for minimal premium.
- **Strong catalyst approaching** — earnings, product launch, macro event within the DTE window. Gap risk through your strike.
- **Stock in a secular uptrend with accelerating momentum** — you're fighting the trend. The opportunity cost of capping upside exceeds the premium.
- **Strike is below cost basis** — getting assigned means locking in a loss. Never do this unless you're tax-loss harvesting intentionally.
- **You'd regret losing the shares** — if assignment would make you anxious, the CC is wrong.

## Earnings Considerations

- **Pre-earnings (7-14 days out):** IV inflates → premium is rich. Sell CCs only if you'd be happy selling at the strike regardless of the earnings outcome. Set strikes 15-20% OTM to give room for a beat.
- **Never sell CCs through earnings if a beat could gap the stock 20%+.** The premium isn't worth the risk on names like MU, NVDA, AMD that routinely move 10-15% on earnings.
- **Post-earnings:** IV crushes → close at 50%+ profit immediately if the stock stayed below your strike. Re-evaluate for a new CC at the new IV level.

## Timing Evidence (external research, Oct 2026)

| Factor | Finding | Source |
|---|---|---|
| DTE | **~30–45 DTE** performed best; theta is most favorable there | [ORATS covered-call backtest](https://orats.com/blog/covered-call-backtest-finding-the-best-maturity-strike-iv-and-earnings-methods) (3.5M parameter combos, S&P 500, 2007+); tastylive |
| IV | Sell when **IV percentile > ~66%** (practitioners: IVR > 30–50%) | ORATS |
| Earnings | **Avoiding earnings beat trading through them** | ORATS |
| Into strength | Waiting **1–2 up days** helps slightly. Longer waits add no reliable edge, because IV usually *falls* in rallies and premium thins | [tastylive Market Measures](https://www.tastylive.com/shows/market-measures/episodes/selling-calls-multiple-up-days-01-12-2017) |
| Exit | **Holding to expiry beat early profit-taking** in the ORATS backtest | ORATS |

**How we apply it:**
- **Default: sell new CCs *after* earnings** (post-IV-crush, 30–45 DTE), not before. Pre-earnings CCs are the exception. Use them only when you'd genuinely welcome assignment at the strike, or when the premium is deliberately bought as a hedge into the print.
- **Strength triggers:** act after 1–2 up days into resistance. Don't wait for a large multi-day rally.
- **Early close (50–65%) vs. hold to expiry:** the backtest favors holding for return. Our harvest rule trades some return for lower gap and assignment risk, so keep it for high-beta names and around events, and consider holding low-beta CCs to expiry.

## Management Rules

**Rolled CC check:** If the CC was rolled from a prior position, the brokerage P&L is artificial — it reflects the new premium minus the roll debit, not the true strategy return. Before applying the 50-65% profit rule, verify the P&L is from genuine premium collection, not accounting artifacts from rolls. For rolled CCs, manage based on distance to strike and DTE, not displayed P&L.

| Scenario | Action |
|----------|--------|
| Hit 50% of max profit (genuine, not rolled) | **Close.** Re-sell at a better strike/expiry if setup still valid. |
| Hit 65% of max profit (genuine, not rolled) | **Close.** Remaining premium isn't worth the risk. |
| Stock approaches strike (within 2%) | **Roll up and out** — higher strike, extend 30 days. Only if you want to keep shares. |
| Stock blows through strike | Close for a loss OR let shares get called away if you're happy with the exit price. |
| Near expiration, stock well below strike | Let expire worthless or close for pennies. |

## Position Sizing

- **Max 5% of portfolio notional per CC position** (shares covered × strike × 100).
- Keep at least 30% of shares uncovered (see Coverage Rules above).
- Diversify expirations — don't have all CCs expire the same week.

## Common Mistakes

1. **Selling CCs just because you own shares** — "I have 300 shares, might as well sell CCs." No. Check the CC Sharpe Score first. If IV is low, you're giving away upside for nothing.
2. **Selling CCs on oversold stocks** — RSI 30, stock is beaten down, and you sell a CC that caps the recovery. The bounce you need is the one you just sold away.
3. **Covering 100% of shares** — stock gaps up 15% on news, all shares called away. Keep 30-40% uncovered.
4. **Strike below cost basis** — guaranteed loss on assignment. The only exception is intentional tax-loss harvesting.
5. **Ignoring premium yield** — a $0.50 CC on a $400 stock is 0.12% return. Not worth the trade execution, commission, or mental energy.
6. **Holding to expiration for max profit** — the last 20% of premium carries 80% of the risk. Close early at 50-65%.
7. **Not checking IV vs realized vol** — selling CCs when IV is below realized vol means you're selling underpriced insurance. The stock moves more than the options imply. Bad trade.
