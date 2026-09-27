#!/usr/bin/env python3
"""
Watchlist manager — single source of truth for watchlist status.

Consolidates: triage, priority refresh queue, live market data (price, RSI, fwd P/E),
sector momentum, earnings calendar, and generates 0-WATCHLIST.md.

Replaces: update-index.py (0-INDEX.md) and dashboard.py (1-DASHBOARD.md).

Usage:
    .venv/bin/python3 scripts/watchlist.py              # terminal dashboard + save 0-WATCHLIST.md
    .venv/bin/python3 scripts/watchlist.py --json        # JSON output
    .venv/bin/python3 scripts/watchlist.py --auto        # top N tickers only (for piping)
    .venv/bin/python3 scripts/watchlist.py --top 10      # show top 10 in refresh queue
    .venv/bin/python3 scripts/watchlist.py --update      # update tier field in frontmatter
    .venv/bin/python3 scripts/watchlist.py --add TICKER                    # quick-add a stock
    .venv/bin/python3 scripts/watchlist.py --add TICKER --sector Energy    # with sector
    .venv/bin/python3 scripts/watchlist.py --add TICKER --source "friend"  # with source
    .venv/bin/python3 scripts/watchlist.py --no-save     # skip writing 0-WATCHLIST.md
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

STOCKS_DIR = Path("research/stocks")
WATCHLIST_FILE = STOCKS_DIR / "0-WATCHLIST.md"
ACCOUNTS_DIR = Path("portfolio/accounts")

# Abbreviations for account names in compact displays
ACCOUNT_ABBREV = {
    'BROKERAGELINK': 'BL',
    'ROTH IRA': 'Roth',
    'HOLD': 'HOLD',
    'THETAGANG': 'TG',
    'GOBIG': 'GB',
}

# --- Tiered refresh cadence ---
REFRESH_CADENCE = {
    "high": 14,    # conviction 8+
    "medium": 28,  # conviction 6-7.9
    "low": 42,     # conviction 5-5.9
}

VERY_STALE_DAYS = 60

# --- Priority scoring constants ---
DEFAULT_TOP_N = 5
CANDIDATE_BONUS = 35          # new stocks get high priority
HELD_CANDIDATE_BONUS = 50     # held stocks with no thesis — always research
STALENESS_SCALE = 3           # +1 point per N days stale
STALENESS_CAP = 20            # max staleness bonus

MOMENTUM_BONUS = {
    "Accelerating Up": 15,
    "Steady Uptrend": 10,
    "Pulling Back in Uptrend": 8,
    "Pulling Back": 8,
    "Sideways": 0,
    "Mixed": 0,
    "Downtrend": -5,
    "Capitulation": -5,
}

# Map stock frontmatter sector names → GICS sector names from sector-momentum.py
SECTOR_TO_GICS = {
    "Semiconductors": "Technology",
    "Semiconductors / Memory": "Technology",
    "Semiconductors / Optical Communications": "Technology",
    "Semiconductor Equipment": "Technology",
    "Technology": "Technology",
    "Technology/Optical Communications": "Technology",
    "Technology/Optical Networking": "Technology",
    "Technology/Photonics": "Technology",
    "Software": "Technology",
    "Software - Infrastructure": "Technology",
    "Software/Gaming": "Technology",
    "Software (ETF)": "Technology",
    "Cybersecurity / Software": "Technology",
    "Communication Services": "Communication",
    "Healthcare": "Healthcare",
    "Financial Services": "Financials",
    "Crypto/Fintech": "Financials",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Industrials/Data Center Infrastructure": "Industrials",
    "Consumer Cyclical": "Consumer Disc.",
    "EVs/Autonomy": "Consumer Disc.",
    "Real Estate": "Real Estate",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Consumer Staples": "Consumer Staples",
    "Leveraged ETF / South Korea": None,  # no GICS mapping
    "Leveraged ETF / EVs & Autonomy": "Consumer Disc.",  # TSLL → same as TSLA
    "Technology/Semiconductors": "Technology",  # MPWR
    "Aerospace & Defense": "Industrials",  # SPCX
    "null": None,  # placeholder for stocks without sector data
}


def parse_frontmatter(filepath: Path) -> dict:
    content = filepath.read_text(encoding="utf-8")
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).strip().split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',')]
            fm[key] = value
    return fm


# --- Portfolio parsing helpers ---

def _parse_number(s: str) -> float | None:
    """Parse a number from a table cell, handling commas and tildes."""
    try:
        return float(s.strip().replace(',', '').replace('~', ''))
    except (ValueError, AttributeError):
        return None


def _parse_dollar(s: str) -> float | None:
    """Parse a dollar value like '$10,764' or '~$93'."""
    if '$' not in str(s):
        return None
    try:
        return float(str(s).strip().replace('$', '').replace(',', '').replace('~', '').strip())
    except (ValueError, AttributeError):
        return None


def _parse_pct(s: str) -> float | None:
    """Parse a percentage like '5.63%'."""
    m = re.search(r'([\d.]+)%', str(s))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def parse_portfolio_holdings() -> dict[str, list[dict]]:
    """Parse all portfolio account files and extract holdings.

    Returns: {TICKER: [{account, shares, value, pct_of_acct, is_option}, ...]}
    """
    if not ACCOUNTS_DIR.exists():
        return {}

    holdings: dict[str, list[dict]] = {}

    for filepath in ACCOUNTS_DIR.glob("*.md"):
        content = filepath.read_text(encoding="utf-8")
        fm = parse_frontmatter(filepath)
        account = fm.get('account_name', filepath.stem.upper())

        in_sold = False

        for line in content.split('\n'):
            # Track section headers — skip "Sold" sections
            if re.match(r'^#{1,4}\s+', line):
                in_sold = bool(re.search(r'[Ss]old', line))

                # Parse headers like "### AMZN — 801 shares ($219,858 — 97.26%)"
                hdr = re.match(
                    r'^#{1,4}\s+([A-Z]{1,5})\s+[—–-]\s+([\d,.]+)\s+shares?\s*\(\$([\d,.]+)',
                    line,
                )
                if hdr and not in_sold:
                    ticker = hdr.group(1)
                    shares = float(hdr.group(2).replace(',', ''))
                    value = float(hdr.group(3).replace(',', ''))
                    pct = _parse_pct(line)
                    existing = holdings.get(ticker, [])
                    if not any(h['account'] == account and not h.get('is_option')
                               for h in existing):
                        holdings.setdefault(ticker, []).append({
                            'account': account, 'shares': shares,
                            'value': value, 'pct_of_acct': pct,
                        })
                continue

            if in_sold:
                continue

            # Skip non-table rows and separators
            if not line.startswith('|') or '---' in line:
                continue

            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 3:
                continue

            first = cells[0].strip('*').strip()

            # Skip header rows
            if first.lower() in ('ticker', 'option', 'strike', 'trade',
                                  'acquired', '#', 'detail'):
                continue

            # Equity row: first cell is a valid ticker (1-5 uppercase letters)
            if re.match(r'^[A-Z]{1,5}$', first):
                ticker = first
                shares = _parse_number(cells[1]) if len(cells) > 1 else None
                value = _parse_dollar(cells[3]) if len(cells) > 3 else None
                pct = _parse_pct(cells[4]) if len(cells) > 4 else None

                existing = holdings.get(ticker, [])
                if not any(h['account'] == account and not h.get('is_option')
                           for h in existing):
                    holdings.setdefault(ticker, []).append({
                        'account': account, 'shares': shares,
                        'value': value, 'pct_of_acct': pct,
                    })
                continue

            # Option row: "TICKER $STRIKE Call/Put ..."
            opt_m = re.match(r'([A-Z]{1,5})\s+\$[\d.]+\s+(?:Call|Put)', first)
            if opt_m:
                ticker = opt_m.group(1)
                existing = holdings.get(ticker, [])
                if not any(h['account'] == account for h in existing):
                    value = _parse_dollar(cells[3]) if len(cells) > 3 else None
                    holdings.setdefault(ticker, []).append({
                        'account': account, 'shares': None,
                        'value': value, 'pct_of_acct': None,
                        'is_option': True,
                    })

    return holdings


def ensure_portfolio_coverage(holdings: dict[str, list[dict]]) -> list[str]:
    """Create candidate research stubs for held tickers missing research files.

    Returns list of newly created ticker symbols.
    """
    STOCKS_DIR.mkdir(parents=True, exist_ok=True)
    created = []

    for ticker in sorted(holdings.keys()):
        filepath = STOCKS_DIR / f"{ticker}.md"
        if filepath.exists():
            continue

        date_str = datetime.now().strftime("%Y-%m-%d")
        accounts = [h['account'] for h in holdings[ticker]]
        total_value = sum(h.get('value') or 0 for h in holdings[ticker])

        content = f"""---
ticker: {ticker}
status: candidate
added_date: {date_str}
sector: null
source: "portfolio-gap (held in {', '.join(accounts)}, ~${total_value:,.0f})"
---
"""
        filepath.write_text(content, encoding="utf-8")
        created.append(ticker)

    return created


# --- Display helpers for portfolio holdings ---

def _held_terminal(s: dict) -> str:
    """Format held indicator for terminal (5 chars wide)."""
    if not s.get('held_in'):
        return "    —"
    v = s.get('total_held_value', 0)
    if v >= 1000:
        return f"${v / 1000:.0f}K".rjust(5)
    return " held"


def _held_md(s: dict) -> str:
    """Format held indicator for markdown."""
    held_in = s.get('held_in', [])
    if not held_in:
        return "—"
    accounts = [ACCOUNT_ABBREV.get(h['account'], h['account']) for h in held_in]
    total = s.get('total_held_value', 0)
    if total >= 1000:
        return f"{','.join(accounts)} ${total / 1000:.0f}K"
    elif total > 0:
        return f"{','.join(accounts)} ${total:.0f}"
    return ','.join(accounts)


def find_last_update(filepath: Path) -> str | None:
    content = filepath.read_text(encoding="utf-8")
    dates = re.findall(r'\|\s*(\d{4}-\d{2}-\d{2})', content)
    if not dates:
        dates = re.findall(r'(\d{4}-\d{2}-\d{2})', content[:2000])
    return max(dates) if dates else None


def find_earnings_date(filepath: Path) -> tuple[str | None, int | None]:
    """Find earnings date and days until it."""
    content = filepath.read_text(encoding="utf-8")
    patterns = [
        r'[Ee]arnings\s*(?:\*\*)?(?:date)?:?\s*(?:\*\*)?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:,?\s*\d{4})?)',
        r'[Nn]ext\s+earnings[:\s]+(?:\*\*)?((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:,?\s*\d{4})?)',
    ]
    current_year = datetime.now().year
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            date_str = match.group(1).strip('*')
            for fmt in ['%B %d, %Y', '%B %d', '%b %d, %Y', '%b %d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if dt.year < current_year:
                        dt = dt.replace(year=current_year)
                    days_until = (dt - datetime.now()).days
                    return date_str, days_until
                except ValueError:
                    continue
    return None, None


def days_since(date_str: str) -> int:
    try:
        return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return 999


def compute_rsi(closes, period=14):
    """Compute RSI from a series of closing prices."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def get_market_data(tickers: list[str]) -> tuple[dict, dict, dict]:
    """Fetch current prices, RSI, and forward P/E for a list of tickers."""
    prices = {}
    rsi_values = {}
    fwd_pe = {}

    if not HAS_YFINANCE or not tickers:
        return prices, rsi_values, fwd_pe

    us_tickers = [t for t in tickers if not any(c in t for c in ['.', '/', 'IBDNF'])]
    if not us_tickers:
        return prices, rsi_values, fwd_pe

    try:
        # 6mo of history so Wilder's RSI smoothing converges (1mo gave distorted values)
        data = yf.download(us_tickers, period="6mo", progress=False)
        if len(us_tickers) == 1:
            try:
                closes = data['Close'].dropna().tolist()
                if closes:
                    prices[us_tickers[0]] = round(float(closes[-1]), 2)
                    rsi = compute_rsi(closes)
                    if rsi is not None:
                        rsi_values[us_tickers[0]] = rsi
            except (KeyError, IndexError):
                pass
        else:
            for t in us_tickers:
                try:
                    closes = data['Close'][t].dropna().tolist()
                    if closes:
                        prices[t] = round(float(closes[-1]), 2)
                        rsi = compute_rsi(closes)
                        if rsi is not None:
                            rsi_values[t] = rsi
                except (KeyError, IndexError):
                    pass

        # Fetch forward P/E for each ticker
        print("Fetching fundamentals...", file=sys.stderr)
        for t in us_tickers:
            try:
                info = yf.Ticker(t).info
                pe = info.get('forwardPE')
                if pe and pe > 0:
                    fwd_pe[t] = round(float(pe), 1)
            except Exception:
                pass

    except Exception:
        pass

    return prices, rsi_values, fwd_pe


def fetch_sector_momentum() -> dict[str, str]:
    """Run sector-momentum.py --json and return {gics_sector: momentum_classification}."""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/sector-momentum.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print("  ⚠ sector-momentum.py failed, skipping sector bonus", file=sys.stderr)
            return {}
        data = json.loads(result.stdout)
        return {entry["sector"]: entry["momentum"] for entry in data}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, Exception) as e:
        print(f"  ⚠ sector momentum unavailable: {e}", file=sys.stderr)
        return {}


def get_refresh_cadence(conv_f: float | None) -> int:
    """Return stale threshold in days based on conviction tier."""
    if conv_f is not None and conv_f >= 8:
        return REFRESH_CADENCE["high"]     # 14 days
    elif conv_f is not None and conv_f >= 6:
        return REFRESH_CADENCE["medium"]   # 28 days
    else:
        return REFRESH_CADENCE["low"]      # 42 days


def compute_priority_score(stock: dict, gap_pct: float | None,
                           sector_momentum: str | None,
                           is_candidate: bool = False) -> tuple[int, list[str]]:
    """Compute numeric priority score and breakdown for refresh ordering."""
    score = 0
    breakdown = []

    # Candidate bonus — new stocks need first research
    if is_candidate:
        score += CANDIDATE_BONUS
        breakdown.append(f"NEW candidate (+{CANDIDATE_BONUS})")

    # Earnings proximity (highest weight)
    earnings_days = stock.get('earnings_days')
    if earnings_days is not None and earnings_days > 0:
        if earnings_days < 7:
            score += 40
            breakdown.append(f"earnings <7d (+40)")
        elif earnings_days < 14:
            score += 25
            breakdown.append(f"earnings <14d (+25)")
        elif earnings_days < 30:
            score += 10
            breakdown.append(f"earnings <30d (+10)")

    # Sector momentum bonus
    if sector_momentum:
        bonus = MOMENTUM_BONUS.get(sector_momentum, 0)
        if bonus != 0:
            score += bonus
            breakdown.append(f"sector {sector_momentum} ({bonus:+d})")

    # Gap to target
    if gap_pct is not None:
        if abs(gap_pct) <= 5:
            score += 25
            breakdown.append(f"within 5% of target (+25)")
        elif abs(gap_pct) <= 10:
            score += 15
            breakdown.append(f"within 10% of target (+15)")
        elif abs(gap_pct) <= 15:
            score += 5
            breakdown.append(f"within 15% of target (+5)")

    # Staleness
    stale_days = stock.get('stale_days', 0)
    if stale_days > 0 and not is_candidate:
        stale_pts = min(stale_days // STALENESS_SCALE, STALENESS_CAP)
        if stale_pts > 0:
            score += stale_pts
            breakdown.append(f"stale {stale_days}d (+{stale_pts})")

    # Conviction (lighter weight — may be stale)
    conviction = stock.get('conviction')
    if conviction:
        try:
            conv_f = float(conviction)
            conv_pts = round(conv_f * 2)
            score += conv_pts
            breakdown.append(f"conv {conv_f} (+{conv_pts})")
        except (ValueError, TypeError):
            pass

    return score, breakdown


def classify_stock(stock: dict, price: float | None, sector_momentum: str | None,
                   rsi: float | None = None, fwd_pe: float | None = None) -> dict:
    """Classify a stock into a tier with reasons and priority score."""
    ticker = stock['ticker']
    conviction = stock.get('conviction')
    conv_f = None
    if conviction:
        try:
            conv_f = float(conviction)
        except (ValueError, TypeError):
            pass

    stale_days = stock['stale_days']
    earnings_date = stock.get('earnings_date')
    earnings_days = stock.get('earnings_days')
    entry_target = stock.get('entry_target')
    is_candidate = stock.get('status') == 'candidate'

    # Calculate gap to target
    gap_pct = None
    if price and entry_target:
        try:
            target_f = float(entry_target)
            if target_f > 0:
                gap_pct = ((price / target_f) - 1) * 100
        except (ValueError, TypeError):
            pass

    reasons = []

    # --- CANDIDATE: always needs research ---
    if is_candidate:
        tier = 'candidate'
        reasons.append("new — needs first research")
        priority_score, score_breakdown = compute_priority_score(
            stock, gap_pct, sector_momentum, is_candidate=True)
        return {
            'ticker': ticker,
            'tier': tier,
            'conviction': conv_f,
            'sector': stock.get('sector', ''),
            'thesis': stock.get('thesis', ''),
            'strategies': stock.get('strategies', []),
            'stale_days': stale_days,
            'gap_pct': gap_pct,
            'price': price,
            'rsi': rsi,
            'fwd_pe': fwd_pe,
            'entry_target': entry_target,
            'earnings': earnings_date,
            'earnings_days': earnings_days,
            'reasons': reasons,
            'priority_score': priority_score,
            'score_breakdown': score_breakdown,
            'sector_momentum': sector_momentum,
            'needs_refresh': True,
        }

    tier = 'passive'

    # --- ACTIVE triggers ---
    if conv_f and conv_f >= 7:
        tier = 'active'
        reasons.append(f"conviction {conv_f}")

    if gap_pct is not None and -15 < gap_pct < 5:
        tier = 'active'
        reasons.append(f"near target ({gap_pct:+.1f}%)")

    if earnings_days is not None and 0 < earnings_days <= 30:
        tier = 'active'
        reasons.append(f"earnings in {earnings_days}d")

    # --- REMOVE triggers (override to remove if no active reasons) ---
    if tier != 'active':
        remove_reasons = []
        if conv_f is not None and conv_f < 5:
            remove_reasons.append(f"low conviction ({conv_f})")
        if conv_f is None and stale_days > VERY_STALE_DAYS:
            remove_reasons.append(f"no conviction + stale {stale_days}d")
        if stale_days > 90:
            remove_reasons.append(f"very stale ({stale_days}d)")
        if gap_pct is not None and gap_pct > 50:
            remove_reasons.append(f"far above target ({gap_pct:+.0f}%)")

        if remove_reasons:
            tier = 'remove'
            reasons = remove_reasons
        elif not reasons:
            reasons.append("no active triggers")

    # --- Tiered refresh check ---
    cadence = get_refresh_cadence(conv_f)
    needs_refresh = tier == 'active' and stale_days > cadence

    if needs_refresh and stale_days > cadence:
        reasons.append(f"stale {stale_days}d (cadence {cadence}d)")

    # --- Priority scoring ---
    priority_score, score_breakdown = compute_priority_score(
        stock, gap_pct, sector_momentum)

    return {
        'ticker': ticker,
        'tier': tier,
        'conviction': conv_f,
        'sector': stock.get('sector', ''),
        'thesis': stock.get('thesis', ''),
        'strategies': stock.get('strategies', []),
        'stale_days': stale_days,
        'gap_pct': gap_pct,
        'price': price,
        'rsi': rsi,
        'fwd_pe': fwd_pe,
        'entry_target': entry_target,
        'earnings': earnings_date,
        'earnings_days': earnings_days,
        'reasons': reasons,
        'priority_score': priority_score,
        'score_breakdown': score_breakdown,
        'sector_momentum': sector_momentum,
        'needs_refresh': needs_refresh,
    }


def load_and_classify() -> list[dict]:
    """Load all watching/candidate stocks and classify them."""
    # Scan portfolio and create candidate stubs for held-but-untracked tickers
    print("Scanning portfolio...", file=sys.stderr)
    holdings = parse_portfolio_holdings()
    if holdings:
        created = ensure_portfolio_coverage(holdings)
        if created:
            print(f"  Created {len(created)} research stubs: {', '.join(created)}",
                  file=sys.stderr)
        print(f"  {len(holdings)} tickers held across portfolio", file=sys.stderr)

    if not STOCKS_DIR.exists():
        return []

    # Start sector momentum fetch early (runs in parallel with market data fetch)
    momentum_proc = None
    try:
        momentum_proc = subprocess.Popen(
            [sys.executable, "scripts/sector-momentum.py", "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except Exception:
        pass

    stocks_raw = []
    for f in STOCKS_DIR.glob("*.md"):
        if f.name.startswith(('0-', '1-')):
            continue
        fm = parse_frontmatter(f)
        if not fm.get('ticker') or fm.get('status') not in ('watching', 'candidate'):
            continue

        last_update = find_last_update(f)
        earnings_date, earnings_days = find_earnings_date(f)

        stocks_raw.append({
            'ticker': fm['ticker'],
            'status': fm.get('status', ''),
            'sector': fm.get('sector', ''),
            'thesis': fm.get('thesis', ''),
            'conviction': fm.get('conviction'),
            'entry_target': fm.get('entry_target'),
            'strategies': fm.get('strategies', []),
            'stale_days': days_since(last_update) if last_update else 999,
            'last_update': last_update,
            'earnings_date': earnings_date,
            'earnings_days': earnings_days,
            'filepath': f,
        })

    # Fetch market data (prices, RSI, fwd P/E)
    tickers = [s['ticker'] for s in stocks_raw]
    print("Fetching market data...", file=sys.stderr)
    prices, rsi_values, fwd_pe_values = get_market_data(tickers)

    # Collect sector momentum (should be done by now)
    sector_momentum_map = {}
    if momentum_proc:
        try:
            stdout, _ = momentum_proc.communicate(timeout=45)
            if momentum_proc.returncode == 0:
                data = json.loads(stdout)
                sector_momentum_map = {entry["sector"]: entry["momentum"] for entry in data}
            else:
                print("  ⚠ sector-momentum.py failed, skipping sector bonus", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ sector momentum unavailable: {e}", file=sys.stderr)
            if momentum_proc.poll() is None:
                momentum_proc.kill()

    # Classify
    classified = []
    for s in stocks_raw:
        ticker = s['ticker']
        price = prices.get(ticker)
        rsi = rsi_values.get(ticker)
        pe = fwd_pe_values.get(ticker)
        # Map stock sector → GICS sector → momentum
        gics_sector = SECTOR_TO_GICS.get(s.get('sector', ''))
        momentum = sector_momentum_map.get(gics_sector) if gics_sector else None
        # Warn on unmapped sectors (for maintenance)
        if s.get('sector') and s['sector'] not in SECTOR_TO_GICS:
            print(f"  ⚠ unmapped sector '{s['sector']}' for {ticker}", file=sys.stderr)
        result = classify_stock(s, price, momentum, rsi=rsi, fwd_pe=pe)
        result['filepath'] = s.get('filepath')
        result['last_update'] = s.get('last_update')
        classified.append(result)

    # Enrich with portfolio holdings data
    for s in classified:
        ticker = s['ticker']
        if ticker in holdings:
            s['held_in'] = holdings[ticker]
            s['total_held_value'] = sum(h.get('value') or 0 for h in holdings[ticker])
            # Held candidates get boosted score — no holding without thesis
            if s['tier'] == 'candidate':
                boost = HELD_CANDIDATE_BONUS - CANDIDATE_BONUS  # +15 on top
                s['priority_score'] += boost
                s['score_breakdown'].insert(0, f"HELD no thesis (+{HELD_CANDIDATE_BONUS})")
                s['needs_refresh'] = True
        else:
            s['held_in'] = []
            s['total_held_value'] = 0

    return classified


def update_frontmatter_tier(filepath: Path, tier: str):
    """Update or add tier field in frontmatter."""
    content = filepath.read_text(encoding="utf-8")
    match = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
    if not match:
        return

    fm_block = match.group(2)

    # Update or add tier
    if re.search(r'^tier:', fm_block, re.MULTILINE):
        fm_block = re.sub(r'^tier:.*$', f'tier: {tier}', fm_block, flags=re.MULTILINE)
    else:
        fm_block += f'\ntier: {tier}'

    new_content = match.group(1) + fm_block + match.group(3) + content[match.end():]
    filepath.write_text(new_content, encoding="utf-8")


def add_stock(ticker: str, sector: str | None = None, source: str | None = None):
    """Create a candidate stub file for a new stock."""
    ticker = ticker.upper()
    filepath = STOCKS_DIR / f"{ticker}.md"

    if filepath.exists():
        fm = parse_frontmatter(filepath)
        print(f"  {ticker} already exists (status: {fm.get('status', 'unknown')})")
        return

    STOCKS_DIR.mkdir(parents=True, exist_ok=True)

    # Try to look up sector from yfinance if not provided
    if not sector and HAS_YFINANCE:
        try:
            info = yf.Ticker(ticker).info
            sector = info.get('sector', None)
        except Exception:
            pass

    date_str = datetime.now().strftime("%Y-%m-%d")
    source_line = f'\nsource: "{source}"' if source else ""

    content = f"""---
ticker: {ticker}
status: candidate
added_date: {date_str}
sector: {sector or "null"}{source_line}
---
"""
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ Added {ticker} as candidate → research/stocks/{ticker}.md")
    if sector:
        print(f"     Sector: {sector}")
    if source:
        print(f"     Source: {source}")
    print(f"     Run /research-stock {ticker} to complete the profile.")


# --- Terminal dashboard ---

def rsi_flag(rsi_val):
    if rsi_val is None:
        return "  —"
    if rsi_val < 30:
        return f"{rsi_val:4.0f} OS"
    elif rsi_val > 70:
        return f"{rsi_val:4.0f} OB"
    return f"{rsi_val:4.0f}   "


def pe_flag(pe_val):
    if pe_val is None:
        return "     —"
    if pe_val < 15:
        return f"{pe_val:5.1f}x$"
    elif pe_val > 100:
        return f"{pe_val:5.0f}x!"
    return f"{pe_val:5.1f}x "


def print_dashboard(classified: list[dict], top_n: int = DEFAULT_TOP_N):
    """Print tiered watchlist to terminal."""
    candidates = sorted(
        [s for s in classified if s['tier'] == 'candidate'],
        key=lambda s: -s['priority_score'],
    )
    active = sorted(
        [s for s in classified if s['tier'] == 'active'],
        key=lambda s: (-s['priority_score'], -(s['conviction'] or 0)),
    )
    passive = sorted(
        [s for s in classified if s['tier'] == 'passive'],
        key=lambda s: s['ticker'],
    )
    remove = sorted(
        [s for s in classified if s['tier'] == 'remove'],
        key=lambda s: s['ticker'],
    )

    needs_refresh = sorted(
        [s for s in classified if s['needs_refresh']],
        key=lambda s: -s['priority_score'],
    )

    width = 120
    print("=" * width)
    print(f"  WATCHLIST — {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * width)

    # Summary
    n_active = len(active)
    n_cand = len(candidates)
    n_passive = len(passive)
    n_remove = len(remove)
    n_refresh = len(needs_refresh)
    n_held = sum(1 for s in classified if s.get('held_in'))
    total_held_val = sum(s.get('total_held_value', 0) for s in classified if s.get('held_in'))
    print(f"\n  {n_active} active | {n_cand} candidate | {n_passive} passive | {n_remove} remove | {n_refresh} need refresh")
    if n_held:
        print(f"  Portfolio: {n_held} held stocks tracked (${total_held_val / 1000:.0f}K)")
    print()

    # Candidates
    if candidates:
        print(f"  CANDIDATES ({len(candidates)} — need first /research-stock)")
        print(f"  {'-' * (width - 4)}")
        for s in candidates:
            sector_str = s['sector'] or '?'
            mom = f" [{s['sector_momentum']}]" if s.get('sector_momentum') else ""
            price_str = f"${s['price']:.2f}" if s['price'] else "—"
            rsi_str = rsi_flag(s.get('rsi'))
            pe_str = pe_flag(s.get('fwd_pe'))
            held_str = _held_terminal(s)
            print(f"    {s['ticker']:6s} | score {s['priority_score']:3d} | {price_str:>9s} | RSI {rsi_str} | PE {pe_str} | {held_str} | {sector_str}{mom}")
        print()

    # Active — full table with market data
    cadence_note = "conv 8+: 14d, 6-7: 28d, <6: 42d"
    print(f"  ACTIVE ({len(active)} — cadence: {cadence_note})")
    print(f"  {'-' * (width - 4)}")
    print(f"    {'TICKER':6s} | {'CONV':>4s} | {'PRICE':>9s} | {'RSI':>6s} | {'FwdPE':>6s} | {'GAP':>7s} | {'EARN':>5s} | {'HELD':>5s} | {'STATUS':8s} | REASONS")
    print(f"    {'-'*6} | {'-'*4} | {'-'*9} | {'-'*6} | {'-'*6} | {'-'*7} | {'-'*5} | {'-'*5} | {'-'*8} | {'-'*20}")
    for s in active:
        conv = f"{s['conviction']:.1f}" if s['conviction'] else "  ?"
        price_str = f"${s['price']:.2f}" if s['price'] else "      —"
        rsi_str = rsi_flag(s.get('rsi'))
        pe_str = pe_flag(s.get('fwd_pe'))
        gap = f"{s['gap_pct']:+.1f}%" if s['gap_pct'] is not None else "    —"
        earn = f"{s['earnings_days']:3d}d" if s.get('earnings_days') and s['earnings_days'] > 0 else "   —"
        if s['needs_refresh']:
            status = f"🔄 {s['priority_score']:3d}"
        else:
            status = "  ✅    "
        held_str = _held_terminal(s)
        reasons_str = ", ".join(s['reasons'][:2])
        print(f"    {s['ticker']:6s} | {conv:>4s} | {price_str:>9s} | {rsi_str} | {pe_str} | {gap:>7s} | {earn:>5s} | {held_str} | {status} | {reasons_str}")

    print()

    # Passive
    if passive:
        print(f"  PASSIVE ({len(passive)} — check monthly)")
        print(f"  {'-' * (width - 4)}")
        for s in passive:
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "  ?"
            price_str = f"${s['price']:.2f}" if s['price'] else "—"
            rsi_str = rsi_flag(s.get('rsi'))
            pe_str = pe_flag(s.get('fwd_pe'))
            stale = f"{s['stale_days']}d" if s['stale_days'] < 999 else "never"
            held_str = _held_terminal(s)
            reasons_str = ", ".join(s['reasons'][:2])
            print(f"    {s['ticker']:6s} | conv {conv} | {price_str:>9s} | RSI {rsi_str} | PE {pe_str} | {held_str} | stale {stale:>5s} | {reasons_str}")
        print()

    # Remove candidates
    if remove:
        print(f"  REMOVE? ({len(remove)} — review for removal)")
        print(f"  {'-' * (width - 4)}")
        for s in remove:
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "  ?"
            reasons_str = ", ".join(s['reasons'][:2])
            print(f"    {s['ticker']:6s} | conv {conv} | {reasons_str}")
        print()

    # Priority refresh queue
    print(f"  REFRESH QUEUE — top {min(top_n, len(needs_refresh))} of {len(needs_refresh)}:")
    print(f"  {'-' * (width - 4)}")
    if needs_refresh:
        for i, s in enumerate(needs_refresh[:top_n], 1):
            conv = f"{s['conviction']:.1f}" if s['conviction'] else " ?"
            top_reasons = " | ".join(s['score_breakdown'][:3])
            print(f"    {i:2d}. {s['ticker']:6s}  score {s['priority_score']:3d}  conv {conv}  — {top_reasons}")
        if len(needs_refresh) > top_n:
            print(f"\n    ... and {len(needs_refresh) - top_n} more (use --top N to see more)")
    else:
        print(f"    All stocks are fresh!")

    print()
    print("=" * width)


# --- Markdown generation for 0-WATCHLIST.md ---

def rsi_md(rsi_val):
    if rsi_val is None:
        return "—"
    if rsi_val < 30:
        return f"**{rsi_val:.0f}** 🔻"
    elif rsi_val > 70:
        return f"**{rsi_val:.0f}** 🔺"
    return f"{rsi_val:.0f}"


def pe_md(pe_val):
    if pe_val is None:
        return "—"
    if pe_val < 15:
        return f"**{pe_val:.1f}x** 💰"
    elif pe_val > 100:
        return f"**{pe_val:.0f}x** ⚠️"
    return f"{pe_val:.1f}x"


def generate_watchlist_md(classified: list[dict], top_n: int = DEFAULT_TOP_N) -> str:
    """Generate 0-WATCHLIST.md content."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []

    lines.append(f"# Watchlist")
    lines.append(f"")
    lines.append(f"*Auto-generated on {today} by `scripts/watchlist.py`*")
    lines.append(f"")

    # Separate by tier
    candidates = sorted(
        [s for s in classified if s['tier'] == 'candidate'],
        key=lambda s: -s['priority_score'],
    )
    active = sorted(
        [s for s in classified if s['tier'] == 'active'],
        key=lambda s: (-s['priority_score'], -(s['conviction'] or 0)),
    )
    passive = sorted(
        [s for s in classified if s['tier'] == 'passive'],
        key=lambda s: s['ticker'],
    )
    remove = sorted(
        [s for s in classified if s['tier'] == 'remove'],
        key=lambda s: s['ticker'],
    )
    needs_refresh = sorted(
        [s for s in classified if s['needs_refresh']],
        key=lambda s: -s['priority_score'],
    )

    n_active = len(active)
    n_cand = len(candidates)
    n_passive = len(passive)
    n_remove = len(remove)
    n_refresh = len(needs_refresh)

    n_held = sum(1 for s in classified if s.get('held_in'))
    total_held_val = sum(s.get('total_held_value', 0) for s in classified if s.get('held_in'))
    lines.append(f"**{n_active}** active | **{n_cand}** candidate | **{n_passive}** passive | **{n_remove}** remove | **{n_refresh}** need refresh")
    if n_held:
        lines.append(f"")
        lines.append(f"Portfolio: **{n_held}** held stocks tracked (${total_held_val / 1000:.0f}K)")
    lines.append(f"")

    # Refresh queue
    lines.append(f"## Refresh Queue (top {min(top_n, len(needs_refresh))} of {len(needs_refresh)})")
    lines.append(f"")
    if needs_refresh:
        lines.append(f"| # | Ticker | Score | Conv | Why |")
        lines.append(f"|---|--------|-------|------|-----|")
        for i, s in enumerate(needs_refresh[:top_n], 1):
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "?"
            why = ", ".join(s['score_breakdown'][:3])
            lines.append(f"| {i} | [{s['ticker']}]({s['ticker']}.md) | {s['priority_score']} | {conv} | {why} |")
    else:
        lines.append(f"All stocks are fresh!")
    lines.append(f"")

    # Candidates
    if candidates:
        lines.append(f"## Candidates ({len(candidates)} — need /research-stock)")
        lines.append(f"")
        lines.append(f"| Ticker | Score | Price | RSI | Fwd P/E | Held | Sector | Momentum |")
        lines.append(f"|--------|-------|-------|-----|---------|------|--------|----------|")
        for s in candidates:
            price_str = f"${s['price']:.2f}" if s['price'] else "—"
            mom = s.get('sector_momentum', '—') or '—'
            held = _held_md(s)
            lines.append(f"| [{s['ticker']}]({s['ticker']}.md) | {s['priority_score']} | {price_str} | {rsi_md(s.get('rsi'))} | {pe_md(s.get('fwd_pe'))} | {held} | {s['sector'] or '?'} | {mom} |")
        lines.append(f"")

    # Active — grouped by sector
    lines.append(f"## Active ({len(active)} stocks)")
    lines.append(f"")
    lines.append(f"*Refresh cadence: conv 8+ = 14d, conv 6-7 = 28d, conv <6 = 42d*")
    lines.append(f"")

    # Group by sector
    sectors = {}
    for s in active:
        sector = s['sector'] or 'Other'
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(s)

    for sector in sorted(sectors.keys()):
        lines.append(f"### {sector}")
        lines.append(f"")
        lines.append(f"| Ticker | Conv | Price | RSI | Fwd P/E | Target | Gap | Earn | Held | Status | Thesis |")
        lines.append(f"|--------|------|-------|-----|---------|--------|-----|------|------|--------|--------|")
        for s in sectors[sector]:
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "?"
            price_str = f"${s['price']:.2f}" if s['price'] else "—"
            target_str = f"${s['entry_target']}" if s['entry_target'] else "—"
            gap_str = f"{s['gap_pct']:+.1f}%" if s['gap_pct'] is not None else "—"
            earn_str = f"{s['earnings_days']}d" if s.get('earnings_days') and s['earnings_days'] > 0 else "—"
            status = f"🔄 {s['priority_score']}" if s['needs_refresh'] else "✅"
            thesis = s.get('thesis', '')[:80]
            held = _held_md(s)
            lines.append(f"| [{s['ticker']}]({s['ticker']}.md) | {conv} | {price_str} | {rsi_md(s.get('rsi'))} | {pe_md(s.get('fwd_pe'))} | {target_str} | {gap_str} | {earn_str} | {held} | {status} | {thesis} |")
        lines.append(f"")

    # Passive
    if passive:
        lines.append(f"## Passive ({len(passive)} stocks)")
        lines.append(f"")
        lines.append(f"| Ticker | Conv | Price | RSI | Fwd P/E | Held | Sector | Reason |")
        lines.append(f"|--------|------|-------|-----|---------|------|--------|--------|")
        for s in passive:
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "?"
            price_str = f"${s['price']:.2f}" if s['price'] else "—"
            held = _held_md(s)
            reasons_str = ", ".join(s['reasons'][:2])
            lines.append(f"| [{s['ticker']}]({s['ticker']}.md) | {conv} | {price_str} | {rsi_md(s.get('rsi'))} | {pe_md(s.get('fwd_pe'))} | {held} | {s['sector'] or '?'} | {reasons_str} |")
        lines.append(f"")

    # Remove
    if remove:
        lines.append(f"## Remove Candidates ({len(remove)} stocks)")
        lines.append(f"")
        lines.append(f"| Ticker | Conv | Reason |")
        lines.append(f"|--------|------|--------|")
        for s in remove:
            conv = f"{s['conviction']:.1f}" if s['conviction'] else "?"
            reasons_str = ", ".join(s['reasons'][:2])
            lines.append(f"| [{s['ticker']}]({s['ticker']}.md) | {conv} | {reasons_str} |")
        lines.append(f"")

    # Earnings calendar
    earnings_stocks = [(s['ticker'], s['earnings'], s['earnings_days'])
                       for s in classified
                       if s.get('earnings_days') and s['earnings_days'] > 0]
    if earnings_stocks:
        earnings_stocks.sort(key=lambda x: x[2])
        lines.append(f"## Earnings Calendar")
        lines.append(f"")
        lines.append(f"| Ticker | Earnings | Days |")
        lines.append(f"|--------|----------|------|")
        for ticker, date, days in earnings_stocks:
            urgency = " ⚡" if days < 7 else ""
            lines.append(f"| [{ticker}]({ticker}.md) | {date} | {days}d{urgency} |")
        lines.append(f"")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Watchlist manager")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--update", action="store_true", help="Update tier in frontmatter")
    parser.add_argument("--auto", action="store_true", help="Output top N tickers only, one per line")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N, help=f"Number of stocks in refresh queue (default {DEFAULT_TOP_N})")
    parser.add_argument("--add", metavar="TICKER", help="Quick-add a stock as candidate")
    parser.add_argument("--sector", help="Sector for --add (auto-detected if omitted)")
    parser.add_argument("--source", help="Source for --add (e.g., 'sector-scan', 'friend', 'news')")
    parser.add_argument("--no-save", action="store_true", help="Skip writing 0-WATCHLIST.md")
    args = parser.parse_args()

    # Quick-add mode
    if args.add:
        add_stock(args.add, sector=args.sector, source=args.source)
        return

    classified = load_and_classify()

    if args.update:
        for s in classified:
            if s.get('filepath'):
                update_frontmatter_tier(s['filepath'], s['tier'])
        print(f"Updated tier for {len(classified)} stocks.")
        return

    if args.auto:
        needs_refresh = sorted(
            [s for s in classified if s['needs_refresh']],
            key=lambda s: -s['priority_score'],
        )
        for s in needs_refresh[:args.top]:
            print(s['ticker'])
        return

    if args.json:
        output = []
        for s in classified:
            entry = {k: v for k, v in s.items() if k != 'filepath'}
            output.append(entry)
        print(json.dumps(output, indent=2))
        return

    # Terminal dashboard
    print_dashboard(classified, top_n=args.top)

    # Save 0-WATCHLIST.md and generate unified dashboard
    if not args.no_save:
        md = generate_watchlist_md(classified, top_n=max(args.top, 10))
        WATCHLIST_FILE.write_text(md, encoding="utf-8")
        print(f"\nSaved to {WATCHLIST_FILE}")

        # Pipe classified JSON to dashboard.py for unified HTML
        dashboard_json = json.dumps(
            [{k: v for k, v in s.items() if k != 'filepath'} for s in classified])
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/dashboard.py", "--no-open"],
                input=dashboard_json, capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                for line in proc.stdout.strip().split('\n'):
                    if line:
                        print(line)
            else:
                print(f"  Dashboard failed: {proc.stderr[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"  Dashboard failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
