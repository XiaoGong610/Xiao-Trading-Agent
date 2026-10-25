# When to Buy LEAPs

## What Are LEAPs

Long-dated call options with **>9 months to expiry**. You're buying leveraged bullish exposure with defined risk — your max loss is the premium paid. LEAPs behave like stock (high delta) but cost a fraction of shares, freeing up capital.

## When LEAPs Have Edge

- **IV Rank < 30** — options are cheap relative to the stock's own history. You're buying vol at a discount.
- **High conviction** — you have a clear thesis, not just "it might go up."
- **Clear catalysts 6-18 months out** — product launches, earnings inflections, regulatory tailwinds, sector rotation.
- **Want leverage without margin** — LEAPs give 3-5x notional exposure with zero margin risk.

## Ideal Setup Checklist

- [ ] IV Rank < 30 (non-negotiable — this is your edge)
- [ ] RSI < 45 or oversold bounce confirmed (buying into strength after a pullback, not chasing)
- [ ] Price at or near support (moving averages, prior lows, volume shelf)
- [ ] Catalyst within the LEAP's expiry window
- [ ] Thesis is specific and falsifiable ("X revenue accelerates in Q3" not "stock should go up")
- [ ] Delta selected based on conviction and capital (see below)

## Delta Selection

| Delta | Style | Cost | When to Use |
|-------|-------|------|-------------|
| **0.70-0.80** | Deep ITM / stock replacement | Highest | Highest conviction. Moves ~1:1 with stock. Best risk/reward for core positions. |
| **0.50-0.60** | ATM / balanced | Medium | Good conviction but want more leverage per dollar. Balanced decay vs. exposure. |
| **0.30-0.40** | OTM / speculative | Lowest | Max leverage, highest risk. Only when thesis has explosive upside and you're sizing small. |

**Default recommendation: 0.70 delta** *for stock-replacement positions.* It gives you stock-like exposure at 15-25% of the capital. For a deliberate lottery sleeve, OTM is the right tool. Pick the structure by intent (below), not by default.

### Deep ITM vs Far OTM: Pick by Intent

Two different instruments, not better and worse versions of the same one:
- **Deep ITM (0.70–0.85 delta) = leveraged stock.** You win if you're right about **direction**.
- **Far OTM (0.20–0.35 delta) = lottery ticket.** You win only if you're right about **direction, size and speed**.

**Illustration** (stock $100, 12-month calls, IV 50%, Black-Scholes estimates):

| | Deep ITM $70 call | Far OTM $150 call |
|---|---|---|
| Cost | ~$37.60 ($30 intrinsic + $7.60 time) | ~$8.00 (all time value) |
| Delta | ~0.85 | ~0.32 |
| Breakeven at expiry | $107.60 (+7.6%) | $158 (+58%) |
| Odds of finishing ITM | ~70% | ~16% |

**Per contract, % return at expiry** (ITM looks better):

| Stock at expiry | $70 call | $150 call |
|---|---|---|
| −30% | −100% | −100% |
| Flat | **−20%** | −100% |
| +20% | **+33%** | −100% |
| +60% | +139% | +25% |
| +100% | +246% | **+525%** |

**Same dollars ($3,760 → 1 ITM contract vs ~4.7 OTM contracts)** (OTM's real benefit shows):

| Stock at expiry | Deep ITM | Far OTM |
|---|---|---|
| −30% | −$3,760 | −$3,760 |
| Flat | **−$760** | −$3,760 |
| +20% | **+$1,240** | −$3,760 |
| +60% | **+$5,240** | +$940 |
| +100% | +$9,240 | **+$19,740** |
| +150% | +$14,240 | **+$43,240** |

**Crossover ≈ +72%.** Below it ITM wins; above it OTM wins by an accelerating margin. That's convexity.

**Benefits of OTM LEAPs:**
1. **Convexity:** for the same dollars, far more payoff on a big move.
2. **Small, fixed max loss:** you can own most of a doubling for ~1/5 the capital. One 5–10x winner pays for several zeros.
3. **Speed pays before expiry:** an early move inflates the option well before the stock reaches the expiry breakeven (gamma plus remaining time value). Real case: an OTM software-ETF LEAP showed +160% while the ETF was still *below* its expiry breakeven. **OTM calls make their money on speed, not at expiry.**
4. **Vega kicker:** rallies and events lift IV, and OTM calls gain on top of the price move.

**Costs of OTM:** flat or modestly-up outcomes lose 100%; most expire worthless; you pay full price for IV.

**OTM playbook:**
1. **Size each as a total loss.** Treat them as a basket (cap the lottery sleeve, e.g. ≤30% of a LEAP account).
2. **Buy cheap volatility:** after earnings, in calm markets. Avoid buying right before a print or on names whose options imply ±15% per event, unless you accept overpaying.
3. **Sell into speed:** take +100%, or convert to a vertical spread (sell a higher strike against it). The time value *is* the profit and it evaporates. Waiting for expiry gives it back.
4. **Pick names that can plausibly move +70% or more within the window**, e.g. beaten-down sectors recovering. That's where OTM beats ITM.
5. **Never on leveraged ETFs** (TSLL, CONL, etc.). Daily-reset decay works against long-dated calls structurally. Use calls on the underlying instead.

**Why take profit at +100% (OTM calls):** the number isn't magic. The rule exists because of how OTM winners behave:
1. **Gains sit in time value and IV, which decay even if the stock stalls.** Illustration: a $5 call at $10 = ~$2 intrinsic + ~$8 time/IV. Two flat months can bleed it to ~$7 with no stock decline; an earnings IV crush takes more overnight.
2. **Leverage cuts both ways.** Real case: a −7.4% ETF week took its OTM LEAP −41% (~5.5x). A +160% gain became +52% in a week.
3. **At +100% your original stake is back on the table.** Banking winners is what makes a lottery basket profitable; unbanked winners revert to zero.
4. **A pre-set level overrides the "it'll come back" urge.**

**Counter-argument:** always selling at +100% caps the convexity that's the reason to own OTM. So treat **+100% as a decision point**, not a forced sale:

| At +100% | Effect | Best when |
|---|---|---|
| Sell all | Bank it | IV crush/earnings ahead, < 90 DTE, or thesis played out |
| Sell half | Freeroll: cost recovered, rest runs at zero risk | Holding 2+ contracts |
| Convert to vertical spread (sell a higher strike) | Locks a profit floor, keeps upside to the short strike | Single contract, still bullish |
| Roll up (sell, rebuy a higher strike) | Banks most gains, keeps a smaller bet | Strong trend |

**Let the updated verdict pick the action; let the instrument set the urgency.** The verdict answers *"do I still want this exposure?"*; time-to-expiry and upcoming IV events answer *"is this call still the right vehicle?"*

| Updated verdict | Event / IV crush ahead, or < 90 DTE | > 90 DTE, IV normal |
|---|---|---|
| **Weakened** | Sell all | Sell all |
| **Unchanged** | Bank: sell or convert to spread | Spread, or hold with a profit floor |
| **Strengthened** | Roll out (keep the view, reset the clock) or spread | **Hold and let it run**, with a trailing floor (e.g. sell if it falls back to ~+50%) |

Research cadence is weekly but option gains can vanish in days, so **always pair the verdict with a mechanical floor** (alert or stop) to avoid acting on a stale view.

**Execution timing when selling options:**
- **Time of day:** skip the first 15–30 min after the open (wide spreads); best fills ~10:00–11:30 ET or 2:00–3:30 ET. Limit near mid, walk down $0.05–0.10.
- **Sell into strength:** park a GTC limit slightly above the mark early in the week so an up-day fills it; set a hard deadline fallback (lower to mid).
- **Before earnings:** IV usually rises into the print. When *selling* a leg (closing a long call, or the short leg of a spread conversion), the richest premium is typically the afternoon before / day-of, before the close. Balance that against stock-move risk by placing the order early and keeping a deadline **before the close on report day** for after-close reports.
- **Event weeks (FOMC, mega-cap capex):** close or protect positions exposed to the event before it, not after.

**Buy OTM calls in pairs (2+ contracts) when budget allows,** so +100% can become "sell one, freeroll one." Single contracts leave only all-or-nothing or the spread conversion.

**Use deep ITM when** you want stock-like exposure with less capital, expect a moderate move (+10–50%), or want to stay in the game if the move is slow.

## Expiry Selection

- **Minimum 9 months.** Anything shorter and theta decay is already punishing you.
- **Sweet spot: 12-18 months.** You're buying time cheaply — theta is nearly flat this far out.
- **Roll before 90 DTE.** Theta decay accelerates sharply inside 90 days. Don't hold and hope.
- **Align expiry with catalyst.** If the catalyst is Q1 2027 earnings, buy Jan 2028 LEAPs — give yourself a full quarter of buffer after the event.

## Vega Risk — Why IV Rank Matters

LEAPs are **long vega** — their price rises and falls with implied volatility. This cuts both ways:

- **Buy at IV Rank 20, IV expands to 40** — your LEAP gains value even if the stock is flat. Free money.
- **Buy at IV Rank 60, IV contracts to 30** — your LEAP loses value even if the stock goes up. You're fighting the current.

This is why **IV Rank < 30 is the single most important filter**. You want vega working for you, not against you.

## When NOT to Buy LEAPs

- **IV Rank > 50** — you're overpaying for vol. Sell premium instead (CSP, CC).
- **Earnings within 2 weeks** — IV is artificially inflated. Wait for the crush, then buy.
- **No clear catalyst** — LEAPs have a time limit. Without a catalyst, you're paying theta for nothing.
- **Stock in sustained downtrend** — falling knife + leverage = accelerated losses. Wait for trend reversal.
- **Uncertain thesis** — if you can't articulate why the stock moves higher in 2 sentences, you don't have conviction. Do more research first.

## Decision Matrix

| IV Rank | High Conviction | Moderate Conviction | Low/No Conviction |
|---------|----------------|--------------------|--------------------|
| **< 25** | **Buy LEAPs** — best setup. Go 0.70 delta, 12-18 mo. | LEAPs viable — use 0.60 delta, smaller size. | Skip — do more research first. |
| **25-40** | LEAPs okay if catalyst is strong. Size conservatively. | Prefer shares or DCA — not enough vol discount. | Skip. |
| **40-60** | **No LEAPs.** Buy shares or DCA instead. | No LEAPs. DCA or wait. | Skip entirely. |
| **> 60** | **Sell premium** (CSP) — don't buy it. | Sell premium or wait. | Do nothing. |

## Management Rules

| Situation | Action |
|-----------|--------|
| **100%+ gain** | Evaluate — don't auto-sell. See the decision matrix below. |
| **Thesis plays out** (catalyst hits, price target reached) | Close the position. Don't get greedy. |
| **90 DTE remaining** | Roll out 6-12 months. Never let a winning LEAP decay into expiry. |
| **Thesis breaks** (fundamental change, not just a red day) | Cut losses immediately. Defined risk only works if you respect it. |
| **Stock drops but thesis intact** | Hold or add if IV is still low. Don't panic — you bought time for a reason. |

### LEAP Profit-Taking Decision Matrix

LEAPs are **bought options** — you paid for time and directional upside. The 50-65% profit-taking rule is for **sold options** (CCs, CSPs) where you're harvesting theta decay. Different logic applies:

| Factor | Hold (let it run) | Take profit |
|--------|-------------------|-------------|
| Sector momentum | Accelerating / Steady Uptrend | Pulling Back / Downtrend |
| Time remaining | >120 DTE (plenty of time) | <90 DTE (theta accelerating) |
| Conviction | ≥7 and unchanged/rising | Dropped or thesis weakening |
| # Contracts | 1 (can't split) | 2+ (can sell half) |
| Gain | 100-200% (still has room) | 300%+ (extraordinary, lock some in) |
| Underlying trend | Above all SMAs, MACD bullish | Breaking below SMA50, MACD bearish |

**Default:** If sector is accelerating, conviction is high, and >120 DTE remains — **hold.** Set a trailing mental stop (e.g., close if profit drops below 50% of peak) instead of selling into strength.

**Exception:** At 300%+ gain or <90 DTE, take partial profit regardless of momentum — protect asymmetric wins.

## LEAPs vs. Shares — Capital Efficiency

Example: Bullish on $200 stock, $10K to deploy.

| | 100 Shares | 1 LEAP (0.70 delta, 18 mo) |
|-|-----------|----------------------|
| **Capital** | $20,000 (or $10K + margin) | ~$3,500 |
| **Notional exposure** | $20,000 | $20,000 |
| **Leverage** | 1x | ~5.7x |
| **Max loss** | Theoretically $20K | $3,500 (premium paid) |
| **Break-even** | $200 | ~$235 (strike + premium) |
| **Remaining capital** | $0 | $6,500 (deploy elsewhere) |

The LEAP lets you control the same 100 shares for 17% of the cost. The trade-off: you need the stock to move enough to cover the premium, and you're on a clock.

## Common Mistakes

1. **Buying OTM LEAPs on speculative stocks** — this is a lottery ticket, not a strategy. The stock needs to move 30-40%+ just to break even. Low probability.
2. **Buying when IV is high** — you're paying inflated prices AND exposed to IV crush. Wait for IV to contract.
3. **Not rolling before theta decay hits** — inside 90 DTE, your LEAP is bleeding daily. Roll out or close.
4. **Holding through thesis-breaking events** — defined risk means nothing if you redefine your thesis to avoid taking a loss.
5. **Oversizing** — leverage amplifies losses too. A 0.70 delta LEAP on a position-sized-for-shares is actually 5x the intended risk.
