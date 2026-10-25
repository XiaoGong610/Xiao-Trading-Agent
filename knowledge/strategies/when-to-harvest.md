# Harvest Decision Framework

Unified exit and profit-taking logic for all position types. Different instruments have different exit logic -- don't apply theta-gang rules to directional bets, and don't apply swing-trade rules to DCA accumulation.

**Two types of exits:**
1. **Thesis exits** -- the reason you bought changed (conviction dropped, fundamentals broke). Always override mechanical exits.
2. **Mechanical exits** -- position size, time, or technicals trigger a systematic trim. Prevents "I'll hold forever" complacency.

---

## 1. Sold Options (CCs / CSPs) -- Theta Harvest

**Logic:** You sold time decay for premium. Once most decay is captured, close and redeploy capital.

### Profit-Taking Matrix

| Profit Captured | Time Elapsed | Action |
|----------------|-------------|--------|
| **50%+ profit** | **<50% of DTE** | **Close and redeploy.** Edge captured in half the time -- remaining premium has poor risk/reward. |
| 50% profit | 50-75% of DTE | Hold to 65%. Theta accelerating in your favor. |
| 50%+ profit | >75% of DTE | Close. Gamma risk increasing, diminishing returns. |
| <30% profit | >50% of DTE | Monitor. Consider rolling if thesis intact. |
| Any profit | <21 DTE | Close or roll. Gamma risk dominates below 21 DTE. |
| >30% profit | <5 DTE (IV crush) | Close. Post-earnings IV crush = windfall, take it. |
| Underwater | Underlying breaches strike | Roll out/up/down, or accept assignment if happy with the price. |

### Time-Based Rules

- **21 DTE checkpoint:** Close regardless of P&L if profit is >30%. Gamma risk rises sharply inside 21 DTE.
- **<5 DTE:** Close everything. The last few days carry outsized gamma risk for minimal remaining premium.

### Earnings Gate

- Close before earnings if the option expires within the earnings window -- unless the position is intentional (e.g., selling a CC specifically to harvest pre-earnings IV).
- Post-earnings: close at 50%+ profit immediately on IV crush. Don't wait -- the edge is gone.

### Roll Rules

| Scenario | Roll Action | Don't Roll If |
|----------|------------|---------------|
| CC approaching strike, want to keep shares | Roll up (higher strike) and out (+30 days) | Conviction <6 -- let it assign, reduce position |
| CSP approaching strike, thesis intact | Roll down (lower strike) and out (+30 days) | Thesis is broken -- close for loss |
| Profit >50% with 14+ DTE remaining | Close and open new position at better strikes | New setup doesn't pass CC Sharpe / CSP Score |
| Post-earnings IV crush | Close, don't roll -- re-evaluate at new IV levels | - |

### CC-Specific: When to Let Assignment Happen

Don't automatically defend every CC. Assignment is the right outcome when:
- **Conviction <6** -- you should be reducing the position anyway
- **Position is overweight** (>1.5x target allocation) -- assignment naturally trims
- **Strike is above your sell target** -- you planned to sell here regardless
- **Stock is in Stage 3 (Distribution) or Stage 4 (Decline)** -- take the exit

Only roll to prevent assignment when conviction is 7+ AND the position is at or below target allocation.

### CSP-Specific: Post-Assignment Transition

If a CSP gets assigned:
1. Your effective cost basis = strike - premium collected
2. Immediately evaluate for CC management on the new shares
3. If CC Sharpe Score >60 at a strike above your cost basis, sell CCs
4. If not, hold shares and manage as a lump-sum position (see Section 4)

---

## 2. Bought Options (LEAPs) -- Directional Harvest

**Logic:** You paid for time and direction. The premium is sunk cost. LEAPs are directional bets, not income trades. The 50-65% close rule from sold options does NOT apply.

### Multi-Factor Decision Matrix

| Factor | Hold | Take Partial (sell half) | Close |
|--------|------|--------------------------|-------|
| **Gain size** | <100% | 100-200% | >200% |
| **DTE remaining** | >120 days | 60-120 days | <60 days |
| **Sector momentum** | Accelerating / Steady | Pulling Back | Downtrend / Stage 4 |
| **Conviction** | 7+ (unchanged or rising) | 5-6 (weakening) | <5 (broken) |
| **IV environment** | Low IV (cheap to hold) | Rising IV | Spiking IV (sell into vol) |
| **Underlying trend** | Above all SMAs, MACD bullish | Breaking SMA50 | Below SMA200, MACD bearish |

**How to read:** Count how many factors point to each column. The majority wins. But any single factor in the "Close" column with conviction <5 or DTE <60 is a hard override -- close regardless of other factors.

### Decision Logic

**Default: HOLD** when sector is accelerating, conviction is 7+, and >120 DTE remains. Set a trailing mental stop instead of selling into strength.

**Take partial** when 2+ factors shift toward caution:
- Sell half the contracts (or one of two)
- Keep the remaining position with a tighter trailing stop
- If only 1 contract, set a hard trailing stop at 50% of peak gain

**Close** when:
- Any single hard override triggers (conviction <5, DTE <60, thesis broken)
- 3+ factors align toward exit
- Gain >300% (extraordinary -- lock it in regardless of other factors)

### Trailing Stop Rules for LEAPs

| Stage | Trigger | Stop Level |
|-------|---------|------------|
| After +100% gain | Activate trailing stop | Trail at 50% of peak gain (e.g., peak +150% -> stop at +75%) |
| After +200% gain | Sell half, trail remainder | Sell 50% of contracts; trail rest at +100% of entry |
| After +300% gain | Take the win | Sell all. Extraordinary outcome -- don't get greedy. |

### Time-Based Management

| DTE | Action |
|-----|--------|
| >120 days | Standard management. No urgency. |
| 90-120 days | **Roll decision window.** If profitable and want to continue, roll to 12-18 month expiry. |
| 60-90 days | **Roll or close.** Theta decay accelerating. Do not hold past this without a plan. |
| <60 days | **Close.** Theta cliff. A winning LEAP decaying into expiry is money burned. |

**Roll trigger:** If >90 DTE, position is profitable, conviction 7+, and sector momentum is steady or better -- roll to a new 12-18 month expiry. This resets theta decay and maintains the directional bet.

### Case Study: The IGV LEAP Incident (Aug 15, 2026)

**What happened:** The system recommended selling an IGV LEAP that was up +105% with ~7 months remaining. The software sector was accelerating. Conviction was high.

**Why the old logic was wrong:** The system applied the 50-65% profit-taking rule from sold options (theta harvest) to a bought option (directional bet). These are fundamentally different:
- Sold option at +50%: you've captured most of the edge, remaining premium has poor risk/reward -> close
- Bought option at +105%: the directional thesis is WORKING, sector is accelerating, time remaining is ample -> hold

**What the new logic says:**
- Gain: +105% -> "Take Partial" range, but only 1 factor
- DTE: ~210 days -> "Hold"
- Sector momentum: Accelerating -> "Hold"
- Conviction: High -> "Hold"
- Result: 4 Hold, 1 Take Partial -> **HOLD.** Set trailing stop at +50% of peak.

**Lesson:** The cost of selling a winning directional bet too early (missing the remaining +100%) far exceeds the cost of holding through a pullback (giving back some gains). LEAPs give you time -- use it.

---

## 3. Shares (DCA Positions) -- Accumulation Harvest

**Logic:** DCA is accumulation-oriented. You're building a position over time for long-term compounding. Don't sell DCA positions for routine profit-taking -- that defeats the purpose. Exit logic is about conviction decay, concentration management, and pause/resume decisions.

### DCA Pause / Resume Rules

| Condition | Action | Resume When |
|-----------|--------|-------------|
| RSI >70 (overbought) | **Pause DCA** -- don't buy at extremes | RSI <60 |
| >30% above entry target | **Pause DCA** -- price has run away | Price returns within 10% of target |
| Conviction drops below 6 | **Pause DCA** -- reassess thesis | Conviction restored to 6+ after research |
| Sector enters Stage 4 | **Pause DCA** -- don't fight the sector | Sector returns to Stage 1-2 |
| Earnings <7 days | **Half-pace DCA** -- reduce binary risk | Post-earnings, thesis intact |
| Stock >20% above SMA20 | **Half-pace DCA** -- extended, likely mean-revert | Pulls back toward SMA20 |

### Trim / Exit Triggers (the only reasons to sell DCA shares)

| Trigger | Action | Why |
|---------|--------|-----|
| **Conviction drops to <5** (thesis broken) | Exit position. Sell in tax-optimal order. | No conviction = no reason to hold. DCA without thesis is gambling. |
| **Position grows to >2x target allocation** from appreciation | Trim to 1.5x target. Sell on green days. | Concentration risk -- appreciation has made you overweight. |
| **Sector enters Stage 4 AND conviction <7** | Trim to half position. Pause DCA. | Don't ride a sector decline with moderate conviction. High conviction (7+) justifies holding through. |
| **Tax-loss harvesting opportunity** | Sell lots with >$1K unrealized loss in taxable accounts. | Harvest the tax benefit. Check wash sale rule (no rebuy within 30 days across accounts). |
| **Conviction drops 2+ points in one review** | Pause DCA immediately. Research what changed within 2 weeks. If conviction stays low, exit. | Rapid conviction decay signals something fundamental shifted. |

### What NOT to Do with DCA Positions

- **Don't sell at +20-25% profit** -- that's swing trade logic, not accumulation logic
- **Don't trim to "rebalance" into underperformers** -- cutting flowers, watering weeds
- **Don't stop DCA because the price went up** -- overbought pauses are temporary, not permanent exits
- **Don't panic-sell on red days** -- DCA is designed to buy through volatility

---

## 4. Shares (Lump Sum / Scaled Entry) -- Position Harvest

**Logic:** You entered at a specific price for a specific reason. Exit is tied to the thesis playing out, targets being hit, or stops being triggered.

### Scaled Exit Template

| Tranche | Target | Size | Method |
|---------|--------|------|--------|
| Target 1 | +1 ATR above avg entry | 25% of position | Limit sell (GTC) |
| Target 2 | +2 ATR above avg entry | 25% of position | Limit sell (GTC) |
| Trailing | After Target 2 fills | 25% of position | 15% trailing stop from high |
| Core | Hold indefinitely | 25% of position | Until thesis breaks or conviction <5 |

### Trailing Stop Methods

| Method | How It Works | Best For |
|--------|-------------|----------|
| **ATR-based** | Trail by 2x ATR below the high | Adapts to volatility -- best default |
| **Moving average** | Exit on close below SMA50 (trending) or 10-week SMA (longer holds) | Trend-following positions |
| **Percentage** | Fixed 15-20% trail from high | Simple but doesn't adapt to volatility |

For volatile names (MU, TSLA, AMD): use 12-15% trailing or 2.5x ATR. A 5% trail on a high-beta stock = constant whipsaws.

### Conviction-Decay Trigger

| Conviction Change | Action |
|-------------------|--------|
| Drops 2+ points in one review | Trim to new conviction-based target allocation (conviction x 1% = target %) |
| Drops below 5 | Exit entirely. Broken thesis. |
| Unchanged but position >15% from appreciation | See Concentration Management (Section 6) |

### Time Stop

If a lump-sum position hasn't moved +10% in 90 days, reassess. Capital has an opportunity cost. Either:
- Reaffirm thesis and hold (with a written note on why)
- Exit and redeploy to a higher-conviction idea

---

## 5. Leveraged ETFs (TSLL, CONL, etc.) -- Decay Harvest

**Logic:** Structural decay from daily reset makes long-term holding a losing proposition in choppy markets. These are tactical trades, not investments. Treat them with strict discipline.

### Harvest Rules

| Trigger | Action |
|---------|--------|
| **Underlying up >3% in a day** | Sell 25-50% of leveraged position. This IS your exit window. |
| **Position is profitable** | Sell into strength. Don't hold for "more upside" on a decaying instrument. |
| **RSI >65 on the leveraged ETF** | Sell -- momentum peak for a decaying instrument. |
| **Held >90 days with no profit** | Exit. Decay is eating you alive. |
| **Conviction on underlying drops below 5** | Exit ALL leveraged exposure immediately. Leveraged + low conviction = gambling. |
| **Bounce from oversold (RSI <30 -> >40)** | This IS the exit window. Sell the bounce. Don't wait for "more recovery." |

### Structural Decay Monitoring

Check monthly: if the underlying is flat or slightly up over the past month but the leveraged ETF is down, decay is eating value. This is the signal to exit, not to hold and hope.

### Hard Rules (No Exceptions)

- **Never hold leveraged ETFs >6 months** unless the underlying has a clear, sustained directional trend (all SMAs aligned, MACD bullish)
- **Size rule:** Leveraged ETFs should never exceed 2% of total portfolio
- **Never buy long-dated options on leveraged ETFs** -- you're adding leverage on top of leverage on top of decay
- **Never hold through earnings** on the underlying -- the gap risk is amplified

### User Preference: TSLL Timing

The user prefers timing sells for a bounce rather than immediate execution at oversold levels. When TSLL or similar is oversold:
- Set price alerts at RSI 40 (bounce confirmation)
- Sell into the bounce, not at the bottom
- But don't wait indefinitely -- if no bounce in 2 weeks, cut anyway

---

## 6. Concentration Management

When a position grows large from appreciation (not from buying), it requires active management regardless of instrument type.

### Decision Matrix

| Position Size (% of portfolio) | Conviction 8+ | Conviction 6-7 | Conviction <6 |
|-------------------------------|---------------|----------------|---------------|
| **>20%** | Intentional hold -- document in account flags. Trim to 15% if not RSU/locked. | Trim to 10% on strength. Sell into rallies, not dips. | Trim to target allocation immediately. |
| **15-20%** | Intentional hold -- document why. Consider selling CCs for income on excess. | Trim to 10% over 2-4 weeks. | Trim to target allocation. |
| **10-15%** | Monitor. No action unless conviction drops. | At upper limit -- tighten stops. | Reduce to conviction-based target (conv x 1%). |
| **<10%** | On target. | On target. | Consider exit if <5. |

### Locked-Concentration Exception (RSUs, short-term lots)

Equity grants can create involuntary concentration. If a large lot is close to its long-term date, document it as an intentional overweight with a planned trim after that date. Don't trim before it unless conviction drops below 5. Vested RSUs themselves have basis = vest FMV, so they can be sold right away with ~no tax (see `knowledge/frameworks/tax-rules.md`).

### Trim Execution

When trimming for concentration:
- **Sell on green days** -- never panic-trim on red days
- **Sell in tax-optimal order** (see Tax-Aware Sell Priority below)
- **Sell over 2-4 weeks** -- don't dump the entire excess in one day
- **Set limit sells at resistance levels** -- get better prices

---

## Cross-Cutting Rules

### Earnings

| Situation | Action |
|-----------|--------|
| Big position (>5% of portfolio) + earnings <7 days | Trim 10-20% pre-earnings to reduce binary risk |
| Options through earnings | Know your max risk. Decide before the report, not after. |
| Post-earnings gap up >5% | Sell 25% into the gap. Reassess at new levels. |
| Post-earnings gap down, thesis intact | Hold or add. Markets overreact to single quarters. |
| Post-earnings gap down, thesis broken | Exit. Don't average down on broken thesis. |

### Sector Stage Transitions

| Sector Transition | Action on Holdings |
|-------------------|-------------------|
| Stage 2 -> Stage 3 (Distribution) | Tighten stops. Pause DCA. Sell CCs aggressively. Take partial on LEAPs. |
| Stage 3 -> Stage 4 (Decline) | Exit swing positions. Pause all DCA. Only hold core compounders with conv 8+. Close LEAPs. |
| Stage 4 -> Stage 1 (Basing) | Watch. Don't buy yet. Thesis must re-emerge. |
| Stage 1 -> Stage 2 (Advancing) | Resume DCA. New entries viable. Consider LEAPs if IV is low. |

### Tax-Aware Sell Priority

When trimming, account order matters (from `knowledge/frameworks/tax-rules.md`):

| Action | Account Order |
|--------|--------------|
| **Selling winners** | Tax-free first (Roth), then taxable with long-term lots, then short-term last |
| **Selling losers** | Taxable first (harvest the loss), then tax-free |
| **Wash sale rule** | Don't rebuy within 30 days across ANY account (Roth included) |

---

## Quick Reference: Position Type -> Exit Logic

| Position Type | Primary Exit Logic | Profit Target | Time Pressure | Key Mistake to Avoid |
|--------------|-------------------|--------------|---------------|---------------------|
| **Sold Options (CC/CSP)** | Close at 50-65% profit or 21 DTE | 50-65% of premium collected | Yes -- gamma risk rises near expiry | Holding to expiry for last 10% |
| **Bought Options (LEAPs)** | Multi-factor matrix; trail winners | No fixed target -- let thesis play out | Yes -- roll at 90 DTE, close at 60 DTE | Applying sold-option rules (50-65% close) |
| **Shares (DCA)** | Conviction decay + concentration | No profit target (accumulation) | No -- long-term by design | Selling winners for short-term profit |
| **Shares (Lump Sum)** | Scaled exits at ATR targets | 25/25/25/25 at ascending targets | 90-day time stop if no progress | No exit plan at entry |
| **Leveraged ETFs** | Sell into strength, bounce-and-sell | Any profit is the target | Yes -- decay is constant | Holding >6 months hoping for recovery |

---

## Anti-Patterns (Common Mistakes)

1. **Applying CC/CSP rules to LEAPs** -- "close at +50% profit" on a LEAP is leaving directional upside on the table. The IGV incident.
2. **"I'll sell when it gets back to even"** -- sunk cost fallacy. If you wouldn't buy it today, sell it.
3. **"It can't go lower"** -- leveraged ETFs, broken theses, and Stage 4 sectors prove this daily.
4. **Cutting flowers, watering weeds** -- trimming winners to buy more of losers. Only trim for concentration, not to "rebalance" into underperformers.
5. **No sell discipline at all** -- "I'm a long-term investor" is not a sell strategy. Even Buffett sells.
6. **Selling on red days** -- panic selling locks in losses at the worst prices. Sell on green days, into strength.
7. **One-size-fits-all % targets** -- "sell everything at +20%" ignores instrument type, conviction, sector, and time remaining.
8. **Holding leveraged ETFs as "long-term positions"** -- daily reset decay will destroy returns in choppy markets.

---

## Integration Points

| Skill | How It Uses This Framework |
|-------|---------------------------|
| `/portfolio-review` Step 3 | Reference the appropriate section for every HOLD/TRIM/EXIT recommendation. Match position type to the correct matrix. |
| `/trading-plan` Step 5 (Position Management) | Use the position-type-specific matrix for each holding. Don't apply blanket rules. |
| `/strategy-theta-gang` | Reference Section 1 (Sold Options) for CC/CSP management. |
| `/strategy-leaps` | Reference Section 2 (Bought Options) for LEAP profit-taking. Cross-ref `when-to-leaps.md` management rules. |
| `/plan-stock` Phase 5c | Include instrument-appropriate exit logic in the execution plan. |

---

## Sources

- [O'Neil 20-25% Profit Rule](https://www.moomoo.com/my/learn/detail-when-to-sell-stock-the-20-25-profit-taking-rule-117056-240283205)
- [Minervini's Exit Criteria](https://www.tradingview.com/chart/COIN/dRQXnzm3-Minervini-s-Specific-Exit-Criteria/)
- [Conviction-Based Position Sizing Playbook](https://fluentinquality.substack.com/p/the-position-sizing-playbook-of-26)
- [Position Management: When to Trim, Hold, Add](https://www.dividend.school/p/the-position-management-playbook)
- [Trimming for Size Discipline](https://vistack.io/learning/sell-04)
- [Fidelity: Managing Positions](https://www.fidelity.com/learning-center/trading-investing/trading/managing-positions)
- [Strategic Selling Framework](https://stocktradingapproach.substack.com/p/strategic-selling-and-profit-taking)
- IGV LEAP Incident (Aug 15, 2026) -- internal case study
