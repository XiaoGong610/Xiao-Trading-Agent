# Project Notes

A living document for brainstorming, discussions, decisions, and TODOs.

---

## Decisions Made

### Skill Naming Convention (2026-05-09)
- `research-*` — research skills
- `strategy-*` — strategy-specific skills
- `trade-*` — portfolio/trade management
- `plan-*` — orchestrator skills
- `util-*` — utility tools

### Research Funnel (2026-05-09)
Cost-aware top-down funnel:
1. `/research-market` (cheap) → many sectors
2. `/research-sector` (moderate) → 5-10 candidates per sector
3. `/research-stock` (moderate) → deep-dive on candidates worth investigating
4. `/research-stock-compare` (cheap) → narrow to top 2-3
5. `/plan-stock` (expensive) → only run on stocks you're seriously considering

### Folder Structure (2026-05-10)
- `research/stocks/` — one file per stock, accumulates research + plans
- `research/sectors/` — sector scans
- `research/comparisons/` — head-to-head comparisons
- `portfolio/` — active positions
- `trades/` — closed trade log
- Status lifecycle: `researched → watching → in-portfolio → removed`
- `0-WATCHLIST.md` groups stocks by actionability (Ready / Wait / Watching / Not Planned)

### Multi-Strategy Framework (2026-05-09)
Four strategies: Buy & Hold, DCA, LEAP Calls, Theta Gang. Research recommends strategy fit. Plan runs all applicable strategy skills and compares.

### DCA Preference (2026-05-10)
- Daily DCA by default
- Three approaches: Static Recurring, Limit Buys at Support, Hybrid Zone-Based
- For restricted stocks: plan per trading window, not per day

### AI Capital Flow Framework (2026-05-10)
Bottleneck progression: GPU → HBM → Cluster Scaling → Optical → next
Five tracks: Memory, I/O Interconnect, Optical, Power/Cooling, Custom ASIC
Key insight: "Don't chase hot spots — position ahead of the bottleneck shift."

### Sector Momentum Framework (2026-06-06)
Three-pillar quantitative momentum system: Mansfield Relative Strength (vs S&P 500), Weinstein Stage Analysis (30-week SMA), ROC momentum. Classifies sectors into: Accelerating Up, Steady Uptrend, Pulling Back in Uptrend, Sideways, Downtrend, Capitulation. Each maps to a strategy playbook. Sector momentum overrides stock-level RSI when they conflict. See `knowledge/frameworks/sector-momentum.md`.

### Regime-Aware Strategy Matrix (2026-06-06)
`/plan-stock` Phase 4a: sector momentum × stock RSI determines entry approach. Key insight: "Stock RSI 75" means momentum in an accelerating sector but overextension in a sideways sector. The sector context is the primary input for timing decisions.

### Crypto 4-Year Cycle Framework (2026-06-04)
BTC halving cycle analysis with on-chain indicators (MVRV, NUPL, Pi Cycle, Hash Ribbon, Puell Multiple). Current cycle peaked at $126K on Oct 6, 2025 (18 months post-halving — textbook). On-chain metrics suggest dampened drawdown with higher floor ($50-63K). Affects COIN/CRCL/MSTR position sizing. See `knowledge/frameworks/crypto-cycles.md`.

### Knowledge Base Wired Into All Skills (2026-06-14)
Full audit and update of all 14 skills. Every skill now consults relevant knowledge files instead of reinventing guidance inline. Key changes: added `--options` flag to technicals.py calls for IV data, added `dashboard.py` (later consolidated into `watchlist.py` — see 2026-07-18) to trade lifecycle skills, fixed naming bugs (`/plan` → `/plan-stock`, `/roll` → `/strategy-theta-gang roll`), added CAPE to market regime, added crypto-cycle.py trigger in scan-market.

### GICS Sector Misclassification (2026-06-06)
META, GOOG, and APP are classified as Communication Services by GICS but functionally behave as Technology/Ad-Tech. When using sector momentum framework, treat these as hybrid — check both Communication (GICS) and Technology (functional). Don't blindly apply Communication downtrend signals to these names.

### Execution Framework (2026-06-18)
Investment strategies (DCA, B&H, LEAPs, Theta Gang) answer "what approach." The execution framework answers "what orders to place." Three phases: Entry (market/limit/scaled/DCA/CSP/breakout), Protection (stop/trailing/collar/put), Exit (target/scaled sells/trailing/time stop). Key tools: ATR for stop placement and order spacing, SMA for support levels, conviction for target allocation (% of portfolio, not $ amounts). Built into `/plan-stock` Phase 5 and documented in `knowledge/strategies/execution-framework.md`.

### Portfolio Review Workflow (2026-06-18)
Redesigned `/portfolio-review` to start with user-shared brokerage screenshots → update account files → cross-account analysis → recommendations. Removed dependency on nonexistent PROFILE.md/POSITIONS.md. Account files are the source of truth, refreshed from screenshots. Reviews saved to `portfolio/REVIEW-YYYY-MM-DD.md` as historical log.

### Pivot to Portfolio Advisor (2026-06-18)
CLAUDE.md updated to reflect the system as a research + portfolio management workspace, not a trading agent. Key changes: "Trading Strategies" → "Investment Strategies," added Execution Framework section with conviction-based allocation targets, updated skill diagram to `Research → Strategy → Execute → Manage`, documented 5-account structure. The agent advises; the user executes.

### TradingAgents Framework Integration (2026-06-23)
Integrated data sources and patterns from [TradingAgents](https://github.com/TauricResearch/TradingAgents) (88K stars, multi-agent LLM trading framework). Five additions:
1. **`scripts/sentiment.py`** — StockTwits bull/bear ratio + Reddit posts (r/wsb, r/stocks, r/investing). No API keys. Flags >65% bull/bear divergence. Wired into `/research-stock`.
2. **`scripts/macro.py`** — FRED macro dashboard (fed funds, 10Y/2Y, yield curve, CPI, PCE, unemployment, VIX) + Polymarket prediction markets (rate cuts, recession, inflation, tariffs). FRED needs free API key, Polymarket is keyless. Wired into `/research-market`.
3. **Memory reflection loop** in `/plan-stock` Phase 0c — reads prior plans and portfolio reviews for the same ticker, extracts lessons to avoid repeating mistakes.
4. **Anti-hallucination prompt** in `/plan-stock` Phase 2 — "Treat technicals.py as source of truth. If sources conflict, flag the discrepancy."
5. **Data provenance rule** in `/research-market` — tag numbers as [FRED], [Polymarket], [web search]. Flag training memory with ⚠️.

Skipped: LangGraph orchestration, multi-agent debate, two-LLM architecture, structured output schemas, Alpha Vantage, five-tier rating.

### Stock-Skill Integration (2026-06-23)
Integrated execution and macro concepts from [stock-skill](https://gitee.com/destiny520537work/stock-skill) (3-trader distillation: Serenity × TraderS × 恨铁). Four additions:
1. **Crypto liquidity triangulation** in `/research-market` — BTC direction + ETF flows + stablecoin cap + 10Y yield as second-layer macro verification
2. **Market day classification** (`knowledge/signals/market-day-types.md`) — 5 types: Trend/Range/Reversal/Munger/Event. Event Day rules: wait for first shock wave, no counter-trend, must have stop
3. **True/false breakout filter** (`knowledge/signals/breakout-filter.md`) — Volume >1.5x + ATR >1x + moderate IV = confirmed breakout. Signal grades A-D.
4. **Fundamental due diligence items** in `/research-stock` — shareholder pledge ratio, core team turnover, related-party transactions, channel inventory truth

Skipped: Serenity persona (already have from serenity-skill), 3-phase entry (DCA/scaled limits cover this), debate mode, data provenance labeling, forced output templates.

### Serenity-Skill Integration (2026-06-23)
Integrated supply-chain bottleneck analysis from [serenity-skill](https://github.com/muxuuu/serenity-skill) (Serenity/@aleabitoreddit methodology). Three additions:
1. **`scripts/bottleneck-scorecard.py`** — 0-100 scoring for supply-chain stocks (8 weighted factors + 8 penalty modifiers). Supplemental to the general conviction score — only runs for hardware/manufacturing sectors.
2. **`knowledge/frameworks/evidence-ladder.md`** — Source grading (strong/medium/weak/needs-checking), 7 red flags, per-candidate evidence standard. Red flags run on ALL stocks, not just supply-chain.
3. **Value-chain layer ranking** in `/research-sector` — for supply-chain sectors, rank the constrained LAYERS before ranking companies. Prevents "popular ticker list" syndrome. Requires explicitly downgrading one popular area.

Key design decision: bottleneck scorecard is supplemental (not a replacement for conviction score) because it only applies to supply-chain-heavy sectors. Evidence ladder and red flags are universal.

### Portfolio Review Upgrade (2026-07-20)
Seven enhancements to `/portfolio-review`:
1. **Execution tracking (Step 0b)** — reads prior plan, shows done/not-done scorecard, flags carry-forward items. Caught TSLL/TSLA CCs/AMZN CC roll deferred 3 weeks (33% execution rate).
2. **Options intelligence (Step 3)** — CC Sharpe screen on uncovered shares, CSP Score gate before recommending CSPs, Buffer % monitoring on sold puts, earnings-through-DTE check on sold calls.
3. **Portfolio metrics (Step 2d)** — total value change, weighted avg conviction, cash runway, options notional exposure.
4. **Sector momentum overlay (Step 2e)** — maps positions to GICS sectors, flags overweight in downtrending sectors (caught 58.7% Consumer Disc. in Downtrend via TSLA+AMZN).
5. **Earnings risk dashboard (Step 3)** — all positions with earnings in 14 days + options exposure through earnings.
6. **Watchlist pipeline (Step 4)** — surfaces watchlist stocks below entry target not yet in portfolio.
7. **DCA optimization (Step 5)** — gap%, RSI, conviction columns + overpaying/missing accumulation/RSI pacing flags + DCA cash runway alert (< 4 weeks = LOW, < 3 weeks = CRITICAL).

Also added: plan-before-trade check in Step 7 (verify `/plan-stock` exists before recommending new trades), CSP capital feasibility check (strike × 100 vs account cash).

### HTML Rehoming & Date Naming (2026-07-20, updated 2026-08-15)
HTMLs date-named in their source folders to preserve history:
- Unified dashboard → `research/stocks/0-watchlist-dashboard-YYYY-MM-DD.html` (5 tabs: portfolio overview, RSI vs P/E, earnings, holdings, trading plan — generated by `scripts/dashboard.py`)
- Sector heatmap → `research/sectors/sector-heatmap-YYYY-MM-DD.html`
- Portfolio plan (markdown) → `portfolio/plans/PLAN-YYYY-MM-DD.md`

### CSP Score Framework & Graded Earnings Gate (2026-07-20)
Inspired by [PutFinder](https://putfinder.com) (a friend's rules-based CSP screening engine). Three additions:
1. **CSP Score** in `knowledge/strategies/when-to-csp.md` — 6-component composite score (0-100) as the CSP equivalent of CC Sharpe. Components: IV Rank (20%), VRP Edge (10%), AnnYield (25%), Buffer % (20%), Support (10%), Earnings Gate (15%). Verdicts: >65 = SELL, 45-65 = MARGINAL, <45 = SKIP.
2. **Buffer %** — `(stock - breakeven) / stock × 100`. Measures downside cushion more intuitively than delta alone. Thresholds: <5% thin, 5-8% moderate, 8-12% good, 12-18% strong, >18% very safe.
3. **Graded Earnings Gate** — replaces binary "earnings within DTE = skip" with 5-tier scoring: <7d before = 0 (disqualify), 7-14d before = 25, within 7d after = 50, 14+d after = 75, no earnings = 100. Applied to both CSP Score and CC Sharpe (replaces old Catalyst Clearance).

Updated `/strategy-theta-gang` skill to calculate and display CSP Score with component breakdown, Buffer % in trade tables, and PutFinder design credit.

First test on AMZN: CSP Score = 44.3 (SKIP) — correctly identified VRP Edge = 0 (options underpriced), Earnings Gate = 25 (all expiries hold through July 30), and thin Buffer % as disqualifying factors. The framework quantified what was previously a judgment call.

### Watchlist Consolidation (2026-07-18)
Consolidated 5 scripts into one unified `scripts/watchlist.py`:
- **Deleted:** `scripts/update-index.py`, `scripts/dashboard.py`, `scripts/chart-watchlist.py`, `scripts/chart-earnings.py`
- **Deleted outputs:** `research/stocks/0-INDEX.md`, `research/stocks/1-DASHBOARD.md`, `charts/watchlist-scatter.html`, `charts/earnings-calendar.html`
- **New outputs:** `research/stocks/0-WATCHLIST.md` (replaces both index and dashboard), `charts/watchlist-dashboard.html` (single tabbed HTML with RSI vs P/E scatter + earnings calendar)
- **New features:** tiered refresh cadence (conv 8+ = 14d, 6-7 = 28d, <6 = 42d), priority scoring (earnings > sector momentum > gap-to-target > staleness > conviction), `--add TICKER` for quick candidate pipeline, `--auto` for piping top N into scheduled agents, `--no-save` for terminal-only, `candidate` status with +35 priority bonus, sector momentum integration via parallel `sector-momentum.py --json` call
- **New skill:** `/watchlist` with actions: triage, add, refresh, remove
- **Rationale:** Five separate scripts with overlapping data fetches and inconsistent outputs. Single tool reduces token cost, simplifies workflow, and enables priority-based refresh instead of flat staleness checks.

---

## Discussions & Ideas

### ETF vs. Individual Stocks (2026-05-10)
- `/research-sector` includes relevant ETFs
- `/research-stock-compare` includes ETF alternative analysis
- ETFs win when: can't pick a winner, want diversification, limited capital
- Individual stocks win when: high conviction, want theta gang (need higher IV), ETF dilutes thesis

### Comparison Grouping (2026-05-10)
Comparisons can be within-sector or cross-sector. Saved to `research/comparisons/` with flexible naming.

### Knowledge Base — Hybrid Approach (2026-05-12)
Build a knowledge layer so the agent makes better decisions over time. Two components:

**1. Knowledge files** (start here) — human-readable reference docs that skills can consult:
```
knowledge/
  sectors/              — sector-specific logic (what metrics matter, cycle dynamics)
  strategies/           — when to use each strategy, edge cases, rules of thumb
  frameworks/           — reusable mental models (AI capital flow, valuation benchmarks)
  signals/              — how to interpret RSI, IV rank, P/E in different contexts
```

**2. Scoring scripts** (build later) — systematic ranking of stocks by composite signals:
- `scripts/screener.py` — input tickers, output ranked list by composite score
- Rules codified in Python, not prompt-dependent
- Consistent, fast, no token cost

**Why hybrid:** Knowledge files handle nuance and context (when does low P/E NOT mean cheap?). Scripts handle systematic scoring (rank 42 stocks). Skills reference both.

---

## TODOs

### 1. Portfolio Advisor Framework ✅ DONE (2026-06-14)
Multi-account portfolio advisor with per-account goals, constraints, and position tracking.

- [x] Build `/portfolio-review` skill — reads account files, fetches live data, recommends changes
- [x] Create per-account files in `portfolio/accounts/` (HOLD, BROKERAGELINK, ROTH IRA, THETAGANG)
- [x] Gitignore account files (contain sensitive data)
- [x] Remove trade lifecycle skills (`trade-open`, `trade-close`, `trade-review`, `trade-watch`, `trade-portfolio`) — agent advises, doesn't track transactions

### 2. Smart Watchlist ✅ DONE (updated 2026-08-15)
Enhance watchlist to bridge research → portfolio action.

- [x] Tiered refresh cadence with priority scoring (conv 8+ = 14d, 6-7 = 28d, <6 = 42d) — replaces simple stale flag
- [x] `--add TICKER` for candidate pipeline from any source (friend, news, sector scan)
- [x] Sector momentum integration in watchlist (reads `sector-momentum.py --json` in parallel)
- [x] Consolidated dashboard: `0-WATCHLIST.md` + `research/stocks/0-watchlist-dashboard-YYYY-MM-DD.html` (rehomed from charts/ with date naming, 2026-07-20)
- [x] Watchlist-to-portfolio pipeline — `/portfolio-review` Step 4 surfaces watchlist stocks below entry target not in portfolio (2026-07-20)
- [x] Portfolio awareness in watchlist (2026-08-15) — parses `portfolio/accounts/*.md`, auto-creates candidate stubs for held tickers missing research files, HELD column in all outputs (terminal, markdown, HTML hover + thicker scatter border), portfolio summary line
- [ ] Add `entry_trigger` field to research/stocks frontmatter (e.g., `"RSI < 35 or pullback to $380"`)
- [ ] Consider alert/notification when a watching stock hits its entry trigger
- ~~target_accounts field~~ — decided account-agnostic is better (2026-06-18)

### 3. Risk & Portfolio Management ✅ MOSTLY DONE (updated 2026-07-20)
Prevent overconcentration and size positions properly.

- [x] **Cross-account aggregation** — done in `/portfolio-review` (2026-06-18). Shows total exposure per ticker across all 5 accounts.
- [x] **Allocation framework** — conviction-based targets (9-10 → 5-8%, 7-8 → 3-5%, etc.) in execution framework
- [x] **Position sizing** — 2% risk rule in `knowledge/strategies/execution-framework.md`
- [x] **Max allocation enforcement** — `/portfolio-review` Step 4 compares conviction vs weight, flags misalignment. Plan-before-trade check prevents blind trades. (2026-07-20)
- [x] **Sector momentum overlay** — `/portfolio-review` Step 2e maps positions to sectors, flags overweight in downtrending sectors (2026-07-20)
- [x] **Execution tracking** — `/portfolio-review` Step 0b reads prior plan, shows done/not-done scorecard, flags carry-forwards (2026-07-20)
- [x] **DCA cash runway alerts** — flags when DCA account cash drops below 4 weeks (<3 wks = critical). Caught BL at 2.3 weeks. (2026-07-20)
- [x] **Options intelligence** — CC Sharpe on uncovered shares, CSP Score gate, Buffer % on sold puts, earnings-through-DTE check (2026-07-20)
- [x] **Earnings risk dashboard** — all held positions with earnings in 14 days + options exposure through earnings (2026-07-20)
- [x] **Correlation analysis** — `scripts/correlation.py` calculates pairwise correlation, detects clusters (TSLA/TSLL 1.00, crypto 0.75, AI semis 0.75+), scores diversification. Found portfolio has ~4 effective independent positions out of 27 held. (added 2026-09-09)
- [x] **Position sizing** — `scripts/position-sizer.py` automates conviction-based sizing, scaled entry math, and over-allocation detection. Correctly flags TSLA at 21.6% vs 2.0% target. (added 2026-09-09)
- [ ] **Portfolio performance tracking** — total P&L over time, benchmark comparison (needs trade history)

### CC Sharpe Framework & Tax Rules (2026-06-27)
Two additions to the knowledge base:
1. **`knowledge/strategies/when-to-cc.md`** — 4-gate CC Sharpe check before selling covered calls: IV Rank >50, premium yield >8% annualized, IV > realized vol, willing to sell at strike. Composite score 0-100 (>60 = sell, <40 = don't). Also covers: rolled CC management (don't apply profit rules to artificial P&L), coverage rules (never cover 100%), and common mistakes.
2. **`knowledge/frameworks/tax-rules.md`** — Multi-account tax optimization. Core rule: sell losers in taxable accounts first (harvest loss), sell winners in tax-free accounts first (no tax on gains). Covers wash sale rules across accounts, holding period awareness, and where-to-hold guide for tax efficiency. Wired into `/portfolio-review` sell recommendations.

### Weekly Trading Plan Output (2026-06-27)
Added Step 7 to `/portfolio-review` — every review now ends with a concrete weekly trading plan saved to `portfolio/plans/PLAN-YYYY-MM-DD.md`. Covers: DCA schedule with changes highlighted, one-time orders (limits, LEAPs, CCs), position management actions, key dates (earnings, expirations), and risk budget (capital deployment, cash runway).

### 4. Knowledge Base ✅ DONE (2026-06-14, updated 2026-06-27)
Build a knowledge layer for smarter decision-making. Start with knowledge files, add scoring scripts later.

**Phase 1 — Knowledge files (16/16 done):**
- [x] `knowledge/signals/rsi-guide.md`
- [x] `knowledge/signals/iv-rank-guide.md`
- [x] `knowledge/frameworks/ai-capital-flow.md`
- [x] `knowledge/frameworks/valuation.md` — includes CAPE/Shiller P/E (added 2026-05-26)
- [x] `knowledge/frameworks/crypto-cycles.md` — 4-year halving cycle + on-chain indicators (added 2026-06-04)
- [x] `knowledge/frameworks/sector-momentum.md` — Mansfield RS + Weinstein Stage + ROC (added 2026-06-06)
- [x] `knowledge/frameworks/macro-regimes.md` — now embedded in `/research-market` regime classification
- [x] `knowledge/sectors/semiconductors.md` — cycle dynamics, sub-sectors, HBM/NAND drivers, key metrics, AI overlay (added 2026-06-14)
- [x] `knowledge/strategies/when-to-csp.md` — **CSP Score** 6-component composite (IV Rank, VRP Edge, AnnYield, Buffer %, Support, Earnings Gate), delta/DTE rules, graded earnings gate, management rules (added 2026-06-14, CSP Score added 2026-07-20)
- [x] `knowledge/strategies/when-to-leaps.md` — IV environment, delta selection, vega risk, capital efficiency (added 2026-06-14)
- [x] `knowledge/strategies/execution-framework.md` — order types, stop placement, exits, position sizing, conviction-based allocation (added 2026-06-18)
- [x] `knowledge/frameworks/evidence-ladder.md` — source grading (strong/medium/weak), red flag checklist, per-candidate evidence standard (added 2026-06-23, adapted from serenity-skill)
- [x] `knowledge/signals/breakout-filter.md` — true/false breakout 3-way filter: volume >1.5x + ATR >1x + moderate IV (added 2026-06-23, adapted from stock-skill/恨铁)
- [x] `knowledge/signals/market-day-types.md` — 5-type market day classification: Trend/Range/Reversal/Munger/Event with Event Day discipline rules (added 2026-06-23, adapted from stock-skill/恨铁)
- [x] `knowledge/strategies/when-to-cc.md` — CC Sharpe 4-gate check (IV Rank, yield, IV vs RV, exit willingness), composite score, coverage rules, rolled CC note, graded Earnings Gate (added 2026-06-27, Earnings Gate upgraded 2026-07-20)
- [x] `knowledge/frameworks/tax-rules.md` — multi-account tax optimization: sell losers taxable first, winners tax-free first, wash sales, holding periods (added 2026-06-27)

**Phase 2 — Scoring scripts:**
- [x] `scripts/sector-momentum.py` — Mansfield RS + Weinstein Stage + ROC for all 11 GICS sectors
- [x] `scripts/sector-heatmap.py` — interactive Plotly treemap with period toggle
- [x] `scripts/crypto-cycle.py` — BTC on-chain cycle dashboard (MVRV, NUPL, cycle composite)
- [x] `scripts/bottleneck-scorecard.py` — supply-chain bottleneck scoring (8 weighted factors + 8 penalties → 0-100 score). Adapted from serenity-skill (added 2026-06-23)
- [x] `scripts/sentiment.py` — StockTwits bull/bear + Reddit posts, no API keys (added 2026-06-23, adapted from TradingAgents)
- [x] `scripts/macro.py` — FRED macro dashboard + Polymarket predictions (added 2026-06-23, adapted from TradingAgents)
- [x] `scripts/screener.py` — composite scoring (RSI + PEG + gap-to-target + conviction + sector momentum + staleness). Verdicts: STRONG BUY / BUY / HOLD / WATCH / AVOID. (added 2026-09-09)
- [x] `scripts/cash-check.py` — validates trading plan orders vs account cash balances, flags over-committed accounts (added 2026-09-06)
- [x] `scripts/correlation.py` — cross-position correlation matrix, cluster detection (TSLA/TSLL, crypto, AI semis), diversification scoring (added 2026-09-09)
- [x] `scripts/position-sizer.py` — conviction-based target allocation, scaled entry levels (40/30/30), over-allocation alerts (added 2026-09-09)
- [x] `scripts/execution-tracker.py` — auto-diff plan orders vs account state, carry-forward detection, execution rate scoring (added 2026-09-09)
- [ ] Wire screener into `/research-stock-compare` for systematic ranking
- [ ] Wire position-sizer into `/plan-stock` Phase 1
- [ ] Wire execution-tracker into `/portfolio-review` Step 0b

### 5. Macro Regime Detection ✅ DONE (2026-06-06)
~~Different market regimes favor different strategies.~~

Implemented via:
- `/research-market` — Market Regime table (S&P vs SMAs, VIX, Fear & Greed, yield curve, breadth) → 5 regime classifications with strategy implications
- `/research-sector` — Sector Momentum & Trend section with 6 momentum classifications
- `/plan-stock` Phase 4a — Regime-aware strategy matrix (sector momentum × stock RSI)
- `scripts/sector-momentum.py` — quantitative sector momentum with Mansfield RS, Weinstein Stage, ROC
- `knowledge/frameworks/sector-momentum.md` — documents the three-pillar methodology

### 6. Market Intelligence Skills 🔄 IN PROGRESS (2026-09-09)
Add continuous monitoring capabilities beyond point-in-time research snapshots.

- [x] **Social sentiment** — `scripts/sentiment.py` covers StockTwits bull/bear + Reddit posts (added 2026-06-23)
- [x] **Whale tracking** — `scripts/whale-tracker.py` (2026-09-09). SEC EDGAR Form 4 insider transactions, institutional 13F holdings (yfinance), unusual options activity. Multi-ticker + --portfolio mode. Cluster buying detection, C-suite signals, composite verdict.
- [ ] **News alerts** — breaking news, FDA decisions, earnings surprises, analyst upgrades/downgrades
- [ ] Consider using `/loop` for periodic monitoring

### 7. Scheduled Cloud Agents ➡️ MEDIUM
Set up Claude Code cloud triggers to run jobs on a recurring schedule.

- [ ] Daily: refresh technicals for all watching stocks
- [ ] Weekly: re-run `/research-market` for sector rotation updates
- [ ] Pre-earnings: auto-flag stocks in watchlist with earnings approaching within 7 days
- [ ] Explore Claude Code `/schedule` for cron-based remote agent triggers
- **Note (2026-07-18):** `watchlist.py --auto` outputs top N tickers for piping into scheduled agents. The infrastructure is built, just needs wiring to a cron trigger.
- **Note (2026-09-24):** Cloud infrastructure ready and tested. Research lives in private repo `Xiao-Trading-Research`; start cloud sessions/routines with **both repos attached**. The cloud environment's setup script runs `scripts/cloud-setup.sh` (links `research/`, builds `.venv`); network access is Custom with finance data domains allowlisted. Verified: research readable, yfinance works, pushes to the research repo work. Next: create the first routine.

### 8. Visual Dashboard & Charts ✅ DONE (2026-06-18, updated 2026-07-18)
Interactive visualizations to help interpret signals at a glance.

**Phase 1 — Plotly chart scripts (5/5 done, consolidated 2026-07-18):**
- [x] `scripts/sector-heatmap.py` — sector performance treemap (standalone, serves `/research-market`)
- [x] `scripts/sector-momentum.py` — terminal dashboard with MRS, Weinstein Stage, ROC (standalone, serves `/research-market`)
- [x] `scripts/crypto-cycle.py` — BTC on-chain cycle dashboard (standalone)
- [x] ~~`scripts/chart-watchlist.py`~~ — consolidated into `scripts/watchlist.py` (2026-07-18)
- [x] ~~`scripts/chart-earnings.py`~~ — consolidated into `scripts/watchlist.py` (2026-07-18)
- [x] `scripts/watchlist.py` — single tabbed `research/stocks/0-watchlist-dashboard-YYYY-MM-DD.html` with RSI vs P/E scatter + earnings calendar (2026-07-18, rehomed 2026-07-20)

**Phase 2 — Streamlit web app ✅ DONE (2026-06-18):**
- [x] `scripts/app.py` — local web dashboard at `localhost:8501`
- [x] Panels: Market Regime, Sector Momentum, Top Picks, RSI vs FwdPE Scatter, Conviction Scores, Earnings Calendar, Near Entry Target, Research Freshness
- [x] Research-focused (no portfolio data — that stays in `/portfolio-review`)

**Remaining:**
- [x] `scripts/dashboard.py` — unified 5-tab HTML dashboard (Portfolio Overview, RSI vs P/E, Earnings, Holdings, Trading Plan). Reads watchlist JSON from stdin + portfolio accounts + latest PLAN markdown. Replaces both the watchlist-only 2-tab dashboard and the LLM-generated 3-tab PLAN HTML. (2026-08-15)
- [ ] `scripts/chart-performance.py` — portfolio P&L over time (once we have trade history)

### 9. Multi-Timeframe Analysis ⬇️ LOW
Daily RSI tells one story; weekly/monthly tell another. Combining timeframes gives higher conviction signals.

- [ ] Add weekly and monthly RSI to dashboard alongside daily
- [ ] **Confluence signals** — daily oversold + weekly at support + monthly uptrend = highest conviction entry
- [ ] Update `scripts/watchlist.py` to fetch and display multi-timeframe RSI
- [ ] Add to knowledge base: `knowledge/signals/multi-timeframe.md`
- [ ] Consider adding weekly/monthly SMA alignment (e.g., price above monthly SMA 10 = long-term uptrend intact)

### 9. Leveraged ETF Strategy ❌ DECIDED AGAINST (2026-06-18)
~~Evaluate leveraged single-stock ETFs as alternative to options.~~

**Decision:** Leveraged ETFs (TSLL, CONL) are structurally bad for long-term holds due to daily-reset decay and path dependency. Portfolio review found $46K in TSLL across 3 accounts — recommended selling all. GoBig account learned the hard way: TSLL calls lost 73-96% even while TSLA was up. **Buy LEAPs on the underlying instead.** Not building a strategy skill for this.

### 10. Tax Optimization 🔄 PARTIALLY DONE (2026-06-27)
Maximize after-tax returns. Critical before year-end.

- [x] **Tax rules knowledge base** — `knowledge/frameworks/tax-rules.md` with multi-account sell order, wash sale rules, holding period awareness, where-to-hold guide
- [x] **Tax-aware sell recommendations** — `/portfolio-review` now checks account type before recommending sells (losers in taxable first, winners in tax-free first)
- [ ] **Wash sale tracking** — auto-flag if selling a stock at a loss and rebuying within 30 days across accounts
- [ ] **End-of-year review** — annual skill to scan portfolio for tax optimization before Dec 31

### 11. Harvest Decision Framework ✅ DONE (2026-09-09)

Unified logic for when to take profit, trim, or exit across all position types. Currently exit logic is scattered and inconsistent — the IGV LEAP incident (Aug 15) showed the system auto-recommended selling a +105% LEAP in an accelerating sector with 7 months left.

**Scope:**
- **Sold options (CCs/CSPs):** Close at 50-65% profit — this is fine (theta harvest)
- **Bought options (LEAPs):** Multi-factor matrix added to `when-to-leaps.md` (Aug 15). Sector momentum + time remaining + conviction + gain size
- **Shares (DCA'd):** When to trim overweight, when to pause DCA, when to accelerate. Gap-to-target + conviction-decay triggers
- **Shares (lump sum):** Scaled exit at targets (already in execution-framework.md) but needs conviction-decay logic
- **Leveraged ETFs:** Structural decay monitoring, bounce-and-sell triggers
- **Concentration management:** When a position grows to >15% from appreciation (AMZN 28%), systematic trim rules vs. intentional hold

**Key principle:** Different instruments have different exit logic. Don't apply theta-gang rules to directional bets.

**Deliverable:** `knowledge/strategies/when-to-harvest.md` ✅ — 6 position-type harvest matrices (sold options, LEAPs, DCA shares, lump sum shares, leveraged ETFs, concentration management) + cross-cutting rules (earnings, sector transitions, tax priority). Includes IGV LEAP case study. Integrated into `/portfolio-review` Step 3 and `/trading-plan` Step 5.
