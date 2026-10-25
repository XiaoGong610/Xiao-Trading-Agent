# xiao-trading-agent

A personal portfolio advisor and trading research workspace powered by [Claude Code](https://claude.ai/code).

## What This Is

A set of Claude Code custom skills for stock research, portfolio management, and weekly trading plan generation. The agent advises — you execute. Three pillars:

1. **Research** — top-down market scan → sector analysis → stock deep-dives with conviction scoring
2. **Portfolio Review** — cross-account analysis, position management, tax-aware recommendations
3. **Trading Plans** — weekly DCA schedule, limit orders, CC/CSP setups, exit plans

## Weekly Workflow

All skills work independently. The weekly session below is the full end-to-end flow for a portfolio check-in.

```
1. Update accounts       → screenshots → portfolio/accounts/*.md
2. Add new picks         → watchlist.py --add TICKER
3. Triage                → watchlist.py --no-save (identify refresh queue, detect portfolio gaps)
4. Research              → /research-market (always) → /research-sector (batch stale) → /research-stock
5. Plan                  → /plan-stock on top 2-3 picks (user decides)
6. Portfolio review      → /portfolio-review (analysis: how am I doing?)
7. Trading plan          → /trading-plan (prescription: what should I do?)
8. Final dashboard       → watchlist.py (saves 0-WATCHLIST.md + unified HTML dashboard)
```

## Skills

### Research
| Command | Description |
|---------|-------------|
| `/research-market` | Broad market overview — regime, sector rotation, macro data, themes |
| `/research-sector software` | Deep-dive a sector or theme, rank 5-10 candidates |
| `/research-stock AAPL` | Full stock deep-dive — red flags, fundamentals, conviction score, market mislabeling |
| `/research-stock-compare AAPL, TSLA, NVDA` | Compare stocks head-to-head, rank by opportunity |

### Portfolio & Planning
| Command | Description |
|---------|-------------|
| `/portfolio-review` | Analysis — cross-account concentration, options intelligence, sector momentum, earnings risk, DCA review |
| `/trading-plan` | Prescription — DCA schedule, orders, position management, key dates, risk budget |
| `/plan-stock AAPL` | Orchestrator — context, research, strategy, execution plan with orders |

### Strategy
| Command | Description |
|---------|-------------|
| `/strategy-buy-and-hold AAPL` | Entry planning, position sizing, thesis tracking |
| `/strategy-dca AAPL` | DCA schedule, sizing, acceleration/pause rules |
| `/strategy-leaps AAPL` | LEAP calls — strike/expiry selection, IV gate, risk management |
| `/strategy-theta-gang analyze AAPL` | CC Sharpe check, CSP setup, recommended trades |
| `/strategy-theta-gang pick AAPL CSP` | Compare strike/expiry combos |
| `/strategy-theta-gang roll AAPL 170P 2026-05-16 CSP` | Analyze whether to roll a position |

### Watchlist
| Command | Description |
|---------|-------------|
| `/watchlist triage` | Tier stocks, show priority scores, identify refresh queue |
| `/watchlist add TICKER` | Quick-add a candidate from any source |
| `/watchlist refresh` | Auto-refresh top priority stocks |
| `/watchlist remove TICKER` | Remove a stock from the watchlist |

### Utility
| Command | Description |
|---------|-------------|
| `/util-chart AAPL 6mo buy=185 sell=220` | Interactive price chart with strategy overlays |

## Folder Structure

```
research/
  sectors/             # Sector-level scans (gitignored)
  stocks/              # Per-stock research & plans (gitignored)
    archive/           # Removed stocks (gitignored)
    0-WATCHLIST.md     # Auto-generated watchlist dashboard (priority scores, RSI, fwd P/E, earnings)
  comparisons/         # Head-to-head stock comparisons (gitignored)
knowledge/             # Decision-making reference docs (committed)
  signals/             # RSI, IV rank, volume, MA, MACD, breakout filter, market day types
  frameworks/          # Capital flow, valuation, sector momentum, crypto cycles, evidence ladder, tax rules
  sectors/             # Sector-specific metrics and cycle dynamics
  strategies/          # CSP, CC (Sharpe check), LEAPs, execution framework
  reference/           # Influencer tracking, ThetaGang leaders
portfolio/             # Multi-account portfolio management
  accounts/            # Per-account files: goals, positions, constraints (gitignored)
  plans/               # Weekly trading plans (gitignored)
  REVIEW-*.md          # Point-in-time portfolio reviews (gitignored)
# HTMLs are date-named in their source folders (not in a separate charts/ dir):
#   research/stocks/0-watchlist-dashboard-YYYY-MM-DD.html (unified 5-tab dashboard)
#   research/sectors/sector-heatmap-YYYY-MM-DD.html
scripts/               # Python scripts (committed)
  technicals.py        # Market data fetcher (price, technicals, options)
  watchlist.py         # Consolidated watchlist: triage, portfolio awareness, 0-WATCHLIST.md
  dashboard.py         # Unified 5-tab HTML dashboard (portfolio, RSI vs P/E, earnings, holdings, trading plan)
  app.py               # Streamlit interactive dashboard
  sector-momentum.py   # Mansfield RS + Weinstein Stage + ROC momentum
  sector-heatmap.py    # Interactive Plotly sector performance treemap
  crypto-cycle.py      # BTC on-chain cycle dashboard (MVRV, NUPL)
  sentiment.py         # StockTwits + Reddit retail sentiment
  macro.py             # FRED macro data + Polymarket predictions
  bottleneck-scorecard.py # Supply-chain stock scoring (0-100)
  cc-ladder-backtest.py # Backtest: uniform vs laddered covered calls
.claude/commands/      # Claude Code custom skills (committed)
NOTES.md               # Project decisions, discussions, and TODOs
```

## Knowledge Base

| File | Purpose |
|------|---------|
| `signals/rsi-guide.md` | RSI interpretation — sector beta, trend context, common mistakes |
| `signals/iv-rank-guide.md` | IV Rank × RSI decision matrix for strategy selection |
| `signals/volume-guide.md` | Volume confirmation — relative volume, capitulation signals |
| `signals/ma-guide.md` | SMA alignment, golden/death cross, entry level selection |
| `signals/macd-guide.md` | MACD crossovers, divergences, histogram momentum |
| `signals/breakout-filter.md` | True/false breakout 3-way filter (volume + ATR + IV) |
| `signals/market-day-types.md` | 5-type day classification: Trend/Range/Reversal/Munger/Event |
| `frameworks/ai-capital-flow.md` | 9-track AI supply chain bottleneck progression |
| `frameworks/valuation.md` | Forward P/E benchmarks by sector, CAPE/Shiller, PEG |
| `frameworks/sector-momentum.md` | Mansfield RS + Weinstein Stage + ROC momentum system |
| `frameworks/crypto-cycles.md` | BTC 4-year halving cycle, on-chain indicators |
| `frameworks/evidence-ladder.md` | Source grading, 12 red flags, evidence standards |
| `frameworks/tax-rules.md` | Multi-account tax optimization, wash sales, sell order, lot disposal method, straddle rules, RSUs & 10b5-1 plans |
| `sectors/semiconductors.md` | Semi cycles, Qual cycle, optical sub-layer, AI overlay |
| `strategies/when-to-csp.md` | **CSP Score** (6-component composite), Buffer %, graded Earnings Gate, IV×RSI matrix |
| `strategies/when-to-cc.md` | CC Sharpe 4-gate check, graded Earnings Gate, coverage rules, rolled CC handling, Ladder Rule, timing evidence |
| `strategies/when-to-leaps.md` | LEAP delta/expiry selection, IV<30 gate, vega risk |
| `strategies/execution-framework.md` | Order types, ATR-based stops, scaled exits, position sizing |
| `reference/influencers.md` | High-signal X/Twitter accounts for research |

## Setup

1. Clone this repo
2. Use with [Claude Code](https://claude.ai/code) — skills are automatically available as slash commands
3. Set up Python: `python3 -m venv .venv && pip install yfinance plotly matplotlib pandas numpy streamlit`
4. Optional: set `FRED_API_KEY` env var for macro data (free from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html))
5. Run the dashboard: `.venv/bin/python3 scripts/watchlist.py` (primary) or `.venv/bin/python3 -m streamlit run scripts/app.py` (full Streamlit)

Analysis files are gitignored since they contain personal trading data. Knowledge base and scripts are committed.
