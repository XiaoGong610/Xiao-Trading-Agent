# Tax Rules for Multi-Account Portfolio

## Account Types & Tax Treatment

| Account | Tax on Gains | Tax on Losses | Rebalance Freely? |
|---------|-------------|---------------|-------------------|
| **Brokerage (HOLD, ThetaGang)** | Yes — short-term (ordinary income) or long-term (15-20%) | **Deductible** — offset gains, up to $3K/year against income | No — every sell triggers taxes |
| **Roth IRA** | **None** — tax-free growth | **Not deductible** — losses are wasted | Yes — no tax consequences |
| **401k / BrokerageLink** | **None** (tax-deferred, taxed on withdrawal) | **Not deductible** — losses are wasted | Yes — no tax consequences |

## The Core Rule: Which Account to Sell In

### Selling a LOSER (position is underwater)

```
SELL IN TAXABLE ACCOUNT FIRST

Taxable (HOLD, ThetaGang)  →  Loss is deductible. Harvest it.
Tax-free (Roth, 401k)      →  Loss is wasted. No benefit.
```

**Why:** A realized loss in a taxable account offsets capital gains dollar-for-dollar. In a tax-free account, the loss simply disappears — you can't deduct it anywhere.

### Selling a WINNER (position is profitable)

```
SELL IN TAX-FREE ACCOUNT FIRST

Tax-free (Roth, 401k)      →  No tax on gains. Pure profit.
Taxable (HOLD, ThetaGang)  →  Gains are taxed. Reduced profit.
```

**Why:** Gains in a Roth IRA are never taxed. The same gain in a taxable account loses 15-20% (LTCG) or up to 37% (STCG) to taxes.

### Summary Matrix

| | Position is a LOSER | Position is a WINNER |
|---|---|---|
| **Sell in taxable first** | ✅ **YES — harvest the tax loss** | ❌ No — you'll pay taxes on the gain |
| **Sell in tax-free first** | ❌ No — loss is wasted | ✅ **YES — gains are tax-free** |

## Holding Period Rules (Taxable Accounts Only)

| Holding Period | Tax Rate | Rule |
|---------------|----------|------|
| < 1 year | **Short-term** = ordinary income (up to 37%) | Avoid selling if you're close to 1 year |
| > 1 year | **Long-term** = 15-20% | Much better — wait for this if practical |

**Practical implication:** If a position in a taxable account is 10 months old with a big gain, wait 2 more months for long-term treatment. The tax savings on a $50K gain can be $5K-10K.

**Example:** a lot bought 11 months ago with a large gain → wait ~1 month for long-term treatment unless the thesis is breaking. Put the long-term date in the account file and flag it in reviews.

## Lot Disposal Method (Taxable Accounts)

The account's default disposal method decides which lots leave on **any sale you don't hand-pick, including option assignments** (called-away CCs can't use Specific Shares). Set it per account in Fidelity: Accounts & Trade → Account Features → Cost basis tracking.

| Method | Use? | Why |
|--------|------|-----|
| **High-cost long-term** | ✅ **Default for taxable accounts** | Sells long-term lots first (15–20% rate), highest cost first (smallest gain). Only touches short-term lots once long-term is exhausted |
| High cost | ⚠️ OK only if every lot is long-term | Ignores holding period — can sell a new short-term lot at ordinary-income rates ahead of a long-term lot |
| FIFO (Fidelity's default) | ❌ | Sells the oldest (usually lowest-cost) lot → biggest gain |
| Specific Shares | Per-trade only | Pick lots on manual sell orders; doesn't help on assignment |

**Rules:**
- Check the method **before** selling CCs on a position with mixed lots. If an assignment already went through on the wrong lots, call Fidelity before settlement (T+1); after that it's locked.
- Not relevant for Roth IRA / 401k (BrokerageLink): no capital-gains tax.

**Example:** lots at $180, $186 and $216, stock called away at $280. FIFO delivers the $180 lot ($100/sh gain). High-cost long-term delivers the $216 lot ($64/sh gain). On 300 shares that's ~$10.8K less gain, or ~$2K less tax at the long-term rate. Record each account's method in its account file.

## Hedging Short-Term Shares (Straddle Rules)

In a taxable account, **buying a put (or a collar) on shares held ≤ 1 year resets their holding period**: the 1-year clock restarts when the put is closed, exercised or expires (IRC §1233(b), §1092). A deep-ITM short call can do the same.

| Hedge on short-term shares | Holding period |
|---|---|
| Protective put / collar | ❌ **Reset** |
| Covered call, OTM ("qualified CC") | ✅ Keeps running |
| Deep-ITM covered call | ❌ Suspended |
| Shares already long-term | ✅ Unaffected by any of these |

**Rule:** to hedge short-term shares in a taxable account, use far-OTM covered calls. Only use puts or collars on long-term lots, or in Roth/401k.
**Example:** a volatile stock bought within the last year, hedged into earnings. Choose a ladder of far-OTM covered calls (+20–35%) over a protective-put collar, so the holding-period clock keeps running.

## Tax-Loss Harvesting

**What:** Sell a losing position to realize the loss, then use it to offset gains elsewhere.

**Rules:**
1. Losses offset gains dollar-for-dollar (no limit)
2. Excess losses offset up to $3,000/year of ordinary income
3. Remaining losses carry forward to future years
4. **Wash sale rule:** If you buy the same or "substantially identical" security within 30 days (before or after the sale), the loss is disallowed

**Wash sale across accounts:** The wash sale rule applies ACROSS ALL your accounts. If you sell TSLL at a loss in ThetaGang and buy TSLL in your Roth IRA within 30 days, the loss is disallowed. Be careful when the same stock is held in multiple accounts.

**Options count as buys:** Buying a *call* (an option to acquire) on the same security within the 61-day window also triggers a wash sale. So does selling a deep-ITM put. Example: one account buys 8 calls on a stock while another account plans a tax-loss sale of 992 shares, so up to 800 of those shares' loss gets disallowed. In a taxable account the disallowed loss isn't lost: it's **added to the calls' cost basis** and recognized when the calls are sold or expire. It's deferred, not destroyed. In an IRA the loss is lost permanently. Check every account's *option* buys, not just share buys, before a tax-loss sale.

**Safe alternatives during the 30-day window:**
- Sell TSLL, buy TSLA shares instead (not substantially identical — different security)
- Sell one semi ETF, buy a different semi ETF (different fund, different index)
- Wait 31 days, then rebuy if you still want the position

## Where to Hold What (Tax Efficiency)

| Asset Type | Best Account | Why |
|-----------|-------------|-----|
| High-growth stocks (NVDA, MU) | **Roth IRA** | Gains compound tax-free. Max growth = max tax savings. |
| Dividend stocks | **Roth IRA or 401k** | Dividends are taxed annually in brokerage. Tax-free in Roth. |
| Theta gang (CSPs, CCs) | **Roth IRA** | Premium income is short-term gains in brokerage. Tax-free in Roth. |
| Buy & Hold (AMZN, GOOG) | **Either** — brokerage is fine if holding >1 year | Long-term cap gains rate is manageable (15-20%). |
| Speculative / high-turnover | **Roth IRA** | Frequent trading = all short-term gains. Tax-free in Roth avoids the penalty. |
| Positions you might tax-loss harvest | **Brokerage** | You need it in a taxable account to harvest the loss. |

## Multi-Account Concentration & Tax Implications

When the same stock is held across multiple accounts, selling in one account requires checking:

1. **Wash sale risk** — are you buying in another account within 30 days?
2. **Which account gives the best tax treatment** for this specific sale? (loser → taxable, winner → tax-free)
3. **Holding period** — in the taxable account, is it short-term or long-term?

## Employer Stock: RSUs, Trading Windows & 10b5-1 Plans

### How RSUs are taxed
| Event | Tax |
|---|---|
| **Vest** | Full FMV at vest = **ordinary income** (W-2): federal + state + FICA. Taxed whether or not you sell |
| **Cost basis** | **= FMV on the vest date.** Already taxed once |
| **Sell later** | Only the move *since vest* is a capital gain or loss. Short-term if sold ≤ 1 year after vest, long-term after |

**Key implications:**
- **Selling right after vest is ~tax-free.** Gain ≈ 0 because basis = vest price. Holding vested RSUs is financially the same as buying that much employer stock with cash on vest day. Ask: "Would I buy this much today?"
- **Sell the new RSU lots first, not older appreciated lots.** Old open-market shares with a low basis realize real gains. Newly vested shares realize ~nothing. Use Specific Shares on the sale.
- **Under-withholding.** Employers withhold federal at the flat **22% supplemental rate** (37% only above $1M of supplemental wages in a year). If your marginal bracket is 32–37%, you'll owe the difference at filing, possibly with an underpayment penalty. Set aside **~10–15% of the vest value** extra, or make an estimated payment (Q4 due **Jan 15**). Safe harbor: pay ≥ 110% of last year's tax via withholding plus estimates if AGI > $150K.
- **1099-B basis trap.** Stock-plan brokers often report RSU sales with **$0 or missing basis**. Use the supplemental statement and adjust on **Form 8949**, or the vest income gets taxed twice.
- **Wash sales apply.** Selling employer stock at a loss within 30 days of a vest (a vest counts as an acquisition) can disallow the loss.

### Trading windows
- Insiders can only trade in **open windows**, typically opening 1–2 trading days after earnings and closing ~2–4 weeks before quarter-end (check your company's policy for exact dates). **Pre-clearance** is often required.
- Most policies **ban options, shorting and hedging** on employer stock. Shares only.
- Never trade on material non-public information, even inside an open window.
- **If a vest lands near the window close,** settlement can push shares past the window, and they're stuck until the next one (~3 months of price risk). That's the main case for a 10b5-1 plan.

### Rule 10b5-1 trading plans
A pre-scheduled, written plan to buy or sell that lets trades execute **even when the window is closed or you hold MNPI**. It's an affirmative defense against insider-trading claims. Rules after the SEC's 2023 amendments, still in force in 2026 ([NASPP](https://www.naspp.com/blog/rule-10b5-1-trading-plans-explained), [Mondaq](https://www.mondaq.com/unitedstates/securities/1799304/rule-10b51-trading-plans-a-practical-overview-for-companies-and-corporate-insiders)):

| Rule | Requirement |
|---|---|
| **Adopt only in an open window**, without MNPI | The plan must be set up when you could legally trade anyway |
| **Cooling-off period** | **Employees: 30 days** from adoption or modification before the first trade. Directors/officers: later of 90 days or 2 business days after the 10-Q, max 120 days |
| **Good faith** | Must be entered and operated in good faith. No influencing the plan afterwards |
| **No overlapping plans** | Only one active plan for open-market trades at a time |
| **Single-trade plans** | Max **one per 12 months** |
| **Modification = new plan** | Changing price, amount or timing restarts the cooling-off. Terminating early hurts the plan's credibility and good-faith defense |
| **Sell-to-cover exemption** | Automatic sales just to cover RSU tax withholding are exempt from the overlap and single-trade limits |
| **Company approval** | The plan usually goes through the company's legal team and is executed by the stock-plan broker |

**Typical plan design for RSU diversification:**
- **"Sell X% of each vest at market within N days of vest."** It runs automatically every quarter, so trapped vests and timing decisions go away.
- Add an optional **price floor**: "only sell if ≥ $Y." Each extra condition can leave shares unsold, though, so keep it simple.
- Adopt it at least **30 days before the first vest** it should cover, in an open window.

**Rule for `/portfolio-review` and `/trading-plan`:** when an RSU vest is expected, plan the sale before the vest. Steps: check the window dates, size the sale so total employer stock stays ≤ ~5% of the portfolio (the job is already exposure), sell the new lots first, reserve cash for under-withholding, and recommend a 10b5-1 plan if vests keep landing outside windows. Concentration takes priority over conviction for employer stock.

## Rules for `/portfolio-review`

When recommending sells across accounts, always specify the account order and tax rationale:

```
Selling a LOSER:
  1st: Taxable account (harvest loss)
  2nd: Tax-free accounts (no benefit, just cleaning up)

Selling a WINNER:
  1st: Tax-free account (no tax on gains)
  2nd: Taxable account, ONLY if long-term (>1 year)
  3rd: Taxable account, short-term — AVOID unless necessary
```

Flag any position approaching the 1-year holding mark — waiting 2-4 weeks can save thousands in taxes.
