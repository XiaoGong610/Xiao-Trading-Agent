# Investment Influencers — X (Twitter)

High-signal accounts to check during weekly research sessions. Use X MCP tools to pull recent tweets directly (Step 4b of weekly workflow).

## Accounts

| Handle | Focus | Signal Quality | Best For | Notes |
|--------|-------|---------------|----------|-------|
| **@aleabitoreddit** (Serenity) | CPO / photonics / AI semi supply chain, neoclouds | Very High | Optical Track 3 (AXTI, AAOI, SIVE, COHR, LITE), neoclouds (NBIS), memory (MU) | Anonymous researcher. 4,500%+ returns in 2026. Bottleneck-first approach aligns with our AI capital flow framework. Portfolio tracked at serenitytrades.com. Concentrated bet on AI photonics + neocloud supercycle. **Also a public CRCL/stablecoin bull**: called CRCL at $54 (Feb 2026, "valuation reset to $12B"), flagged $109 a month later. Check him on CRCL too, not just semis. **Also covers packaging (AMKR: NVDA upstream capacity deals, Oct 2026) and legacy memory (ESMT, Sep 2026).** |
| **@maojietrading** (XTrader猫姐美股交易) | US stock technical analysis, swing trading | Medium | Short-term momentum plays, technical levels on major stocks | Chinese-language account. 16 years experience, 987% 5-year return. Posts in Chinese — focus on chart levels and entry/exit signals. YouTube: @catstocktrading. Website: xtradermaojie.com. Recently traded VRT post-earnings dip. |
| **@AlexMoonvestCN** (Alex G / Moonvest) | US stock investing, growth stocks | Medium | Growth stock picks, portfolio strategy | Co-founder of Moonvest App. Former Google Tech Lead Manager. Launched Moonvest ETF (MNVT) in 2026. 53% YTD vs QQQ 7%. Posts portfolio updates and stock analysis. Oct 2026: mostly Moonvest app promotion, "always all in". **Low stock-level signal lately.** |

## How to Use

**Via Claude in Chrome (preferred, local only):** no X API or MCP is set up. Use the user's logged-in Chrome session on x.com search, in Latest mode (`&f=live`):
- Ticker check: `from:HANDLE (TICKER OR CompanyName)`. For the Chinese accounts, add the Chinese term too (e.g. 稳定币).
- Weekly pass: `from:HANDLE since:YYYY-MM-DD`, then scroll and pull the article text via JS (`[data-testid="tweetText"]` + `time[datetime]`).
- X shows the Chinese accounts auto-translated, which is fine.
- If X redirects to login, ask the user to sign in. Never enter credentials.

**Fallback (if MCP unavailable):** Web search for recent posts:
```
"@aleabitoreddit" latest stock picks OR portfolio update 2026
"@maojietrading" stock analysis OR trading 2026
"@AlexMoonvestCN" investment OR stock 2026
```

**When to check (Step 4b of weekly workflow):**
- Every weekly session — pull all accounts before sector/stock research
- Influencer insights inform which sectors and stocks to prioritize
- When a watchlist stock has a big move — see if any influencer commented on it

**Coverage rule:** the Focus column says what an account *usually* posts about. It is not a filter. When researching any stock or sector, search every tracked account for it. Influencers add new names to their watchlists all the time. When one turns up covering something new, add it to their row.

**What to capture:**
- New stock mentions not on our watchlist → consider `/research-stock`
- Thesis changes on stocks we own → flag in next portfolio review
- Supply chain insights → update `knowledge/frameworks/ai-capital-flow.md`

## Quality Rules

- **High signal ≠ follow blindly.** Always validate with our own research funnel.
- **Track record matters.** Note when an influencer's calls work or fail over time.
- **Beware pump-and-dump.** Small-cap mentions from popular accounts can move prices. Don't chase the initial spike — wait for our own research to confirm.
