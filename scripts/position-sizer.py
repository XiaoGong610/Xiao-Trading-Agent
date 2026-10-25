#!/usr/bin/env python3
"""
position-sizer.py — Calculate target position size, max loss, and share/contract counts.

Automates the position sizing math done manually in every /plan-stock.

Usage:
    .venv/bin/python3 scripts/position-sizer.py ABBV --conviction 8.5
    .venv/bin/python3 scripts/position-sizer.py ABBV --conviction 8.5 --stop 238 --existing 0
    .venv/bin/python3 scripts/position-sizer.py ABBV --conviction 8.5 --portfolio 771428 --options
    .venv/bin/python3 scripts/position-sizer.py ABBV --conviction 8.5 --json
    .venv/bin/python3 scripts/position-sizer.py ABBV --conviction 8.5 --entry 256 --target 278
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

# --- Paths ---
ACCOUNTS_DIR = Path("portfolio/accounts")
STOCKS_DIR = Path("research/stocks")

# --- Conviction-to-allocation mapping ---
ALLOCATION_RANGES = [
    (9.0, 10.0, 0.05, 0.08),   # 9-10 → 5-8%
    (7.0,  8.99, 0.03, 0.05),  # 7-8  → 3-5%
    (5.0,  6.99, 0.01, 0.03),  # 5-6  → 1-3%
    (0.0,  4.99, 0.00, 0.01),  # <5   → 0-1%
]


def get_allocation_range(conviction: float) -> tuple[float, float]:
    """Return (low_pct, high_pct) for a conviction score."""
    for low, high, alloc_low, alloc_high in ALLOCATION_RANGES:
        if low <= conviction <= high:
            return alloc_low, alloc_high
    return 0.0, 0.01


def parse_frontmatter(filepath: Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
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
                value = [v.strip().strip('"').strip("'")
                         for v in value[1:-1].split(',')]
            fm[key] = value
    return fm


def get_portfolio_total() -> float | None:
    """Sum total_value from all account frontmatters."""
    if not ACCOUNTS_DIR.exists():
        return None

    total = 0.0
    found_any = False
    for filepath in ACCOUNTS_DIR.glob("*.md"):
        fm = parse_frontmatter(filepath)
        val = fm.get("total_value")
        if val:
            try:
                total += float(str(val).replace(",", ""))
                found_any = True
            except (ValueError, TypeError):
                pass
    return total if found_any else None


def get_existing_shares(ticker: str) -> tuple[float, list[dict]]:
    """Find existing shares from portfolio account files.

    Returns: (total_shares, [{account, shares, value}, ...])
    """
    if not ACCOUNTS_DIR.exists():
        return 0.0, []

    holdings = []
    ticker_upper = ticker.upper()

    for filepath in ACCOUNTS_DIR.glob("*.md"):
        fm = parse_frontmatter(filepath)
        account = fm.get("account_name", filepath.stem.upper())
        content = filepath.read_text(encoding="utf-8")
        in_sold = False

        for line in content.split('\n'):
            # Track section headers — skip "Sold" sections
            if re.match(r'^#{1,4}\s+', line):
                in_sold = bool(re.search(r'[Ss]old', line))

                # Parse headers like "### TICKER — 100 shares ($10,000 — 5.00%)"
                hdr = re.match(
                    r'^#{1,4}\s+([A-Z]{1,5})\s+[—–-]\s+([\d,.]+)\s+shares?\s*'
                    r'\(\$([\d,.]+)',
                    line,
                )
                if hdr and not in_sold and hdr.group(1) == ticker_upper:
                    shares = float(hdr.group(2).replace(',', ''))
                    value = float(hdr.group(3).replace(',', ''))
                    if not any(h['account'] == account for h in holdings):
                        holdings.append({
                            'account': account,
                            'shares': shares,
                            'value': value,
                        })
                continue

            if in_sold:
                continue
            if not line.startswith('|') or '---' in line:
                continue

            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 3:
                continue

            first = cells[0].strip('*').strip()
            if first.lower() in ('ticker', 'option', 'strike', 'trade',
                                 'acquired', '#', 'detail'):
                continue

            if re.match(r'^[A-Z]{1,5}$', first) and first == ticker_upper:
                shares_str = cells[1] if len(cells) > 1 else "0"
                value_str = cells[3] if len(cells) > 3 else "$0"
                try:
                    shares = float(shares_str.strip().replace(',', '')
                                   .replace('~', ''))
                except (ValueError, AttributeError):
                    shares = 0
                try:
                    value = float(value_str.strip().replace('$', '')
                                  .replace(',', '').replace('~', ''))
                except (ValueError, AttributeError):
                    value = 0
                if not any(h['account'] == account for h in holdings):
                    holdings.append({
                        'account': account,
                        'shares': shares,
                        'value': value,
                    })

    total_shares = sum(h['shares'] for h in holdings)
    return total_shares, holdings


def get_stock_research(ticker: str) -> dict:
    """Read entry_target and other fields from stock research file."""
    filepath = STOCKS_DIR / f"{ticker.upper()}.md"
    if not filepath.exists():
        return {}
    return parse_frontmatter(filepath)


def fetch_market_data(ticker: str) -> dict:
    """Fetch current price, ATR, SMAs, support/resistance via yfinance."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y", interval="1d", auto_adjust=True)

    if hist.empty:
        return {"error": f"No data found for '{ticker}'"}

    # SMAs
    hist['SMA_50'] = hist['Close'].rolling(50).mean()
    hist['SMA_200'] = hist['Close'].rolling(200).mean()

    # ATR (14-day)
    tr = pd.concat([
        hist['High'] - hist['Low'],
        (hist['High'] - hist['Close'].shift()).abs(),
        (hist['Low'] - hist['Close'].shift()).abs(),
    ], axis=1).max(axis=1)
    hist['ATR_14'] = tr.rolling(14).mean()

    last = hist.iloc[-1]
    current_price = float(last['Close'])

    # Support/resistance from pivot points
    supports, resistances = _find_support_resistance(hist)

    result = {
        "current_price": round(current_price, 2),
        "sma_50": round(float(last['SMA_50']), 2) if pd.notnull(last['SMA_50']) else None,
        "sma_200": round(float(last['SMA_200']), 2) if pd.notnull(last['SMA_200']) else None,
        "atr_14": round(float(last['ATR_14']), 2) if pd.notnull(last['ATR_14']) else None,
        "high_52w": round(float(hist['High'].tail(252).max()), 2),
        "low_52w": round(float(hist['Low'].tail(252).min()), 2),
        "support": supports,
        "resistance": resistances,
    }

    # Options data (if available)
    try:
        info = stock.info or {}
        result["sector"] = info.get("sector")
        result["industry"] = info.get("industry")
    except Exception:
        pass

    return result


def _find_support_resistance(hist, window=20):
    """Find key support/resistance levels from recent pivot points."""
    highs = hist['High'].rolling(window=window, center=True).max()
    lows = hist['Low'].rolling(window=window, center=True).min()
    current_price = hist['Close'].iloc[-1]
    all_levels = []

    for i in range(window, len(hist) - window):
        if hist['High'].iloc[i] == highs.iloc[i]:
            all_levels.append(('resistance', round(float(hist['High'].iloc[i]), 2)))
        if hist['Low'].iloc[i] == lows.iloc[i]:
            all_levels.append(('support', round(float(hist['Low'].iloc[i]), 2)))

    supports = sorted(set(p for t, p in all_levels if t == 'support'),
                      reverse=True)
    resistances = sorted(set(p for t, p in all_levels if t == 'resistance'))

    def cluster(levels, threshold=0.015):
        clustered = []
        for level in levels:
            if not clustered or abs(level - clustered[-1]) / clustered[-1] > threshold:
                clustered.append(level)
        return clustered

    supports = [s for s in cluster(supports) if s < current_price][:3]
    resistances = [r for r in cluster(resistances) if r > current_price][:3]
    return supports, resistances


def fetch_options_data(ticker: str, current_price: float) -> dict | None:
    """Fetch options chain data for CSP/LEAP estimates."""
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return None

        # Current IV from nearest expiry ATM options
        nearest = expirations[0]
        chain = stock.option_chain(nearest)
        calls = chain.calls
        puts = chain.puts

        atm_call_idx = (calls['strike'] - current_price).abs().idxmin()
        atm_put_idx = (puts['strike'] - current_price).abs().idxmin()
        atm_call_iv = float(calls.loc[atm_call_idx, 'impliedVolatility'])
        atm_put_iv = float(puts.loc[atm_put_idx, 'impliedVolatility'])
        current_iv = (atm_call_iv + atm_put_iv) / 2

        # Find CSP premium for nearest strike at/below current price
        csp_candidates = puts[puts['strike'] <= current_price].copy()
        csp_info = None
        if not csp_candidates.empty:
            # Pick strike nearest to current price (ATM put)
            csp_idx = (csp_candidates['strike'] - current_price).abs().idxmin()
            csp_row = csp_candidates.loc[csp_idx]
            csp_info = {
                "strike": float(csp_row['strike']),
                "expiry": nearest,
                "bid": float(csp_row['bid']) if pd.notnull(csp_row['bid']) else None,
                "ask": float(csp_row['ask']) if pd.notnull(csp_row['ask']) else None,
                "mid": round((float(csp_row['bid']) + float(csp_row['ask'])) / 2, 2)
                       if pd.notnull(csp_row['bid']) and pd.notnull(csp_row['ask'])
                       else None,
                "collateral": float(csp_row['strike']) * 100,
            }

        # Find LEAP call (delta ~0.70 → typically 10-15% ITM)
        # Look for expiry 12+ months out
        today = datetime.now().date()
        leap_expiry = None
        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if dte >= 300:  # ~10 months minimum
                leap_expiry = exp
                break

        leap_info = None
        if leap_expiry:
            leap_chain = stock.option_chain(leap_expiry)
            leap_calls = leap_chain.calls
            # Target delta ~0.70 → strike roughly 10-15% below current price
            target_strike = current_price * 0.88  # ~12% ITM
            if not leap_calls.empty:
                leap_idx = (leap_calls['strike'] - target_strike).abs().idxmin()
                leap_row = leap_calls.loc[leap_idx]
                leap_mid = None
                if pd.notnull(leap_row['bid']) and pd.notnull(leap_row['ask']):
                    leap_mid = round(
                        (float(leap_row['bid']) + float(leap_row['ask'])) / 2, 2
                    )
                leap_info = {
                    "strike": float(leap_row['strike']),
                    "expiry": leap_expiry,
                    "bid": float(leap_row['bid']) if pd.notnull(leap_row['bid']) else None,
                    "ask": float(leap_row['ask']) if pd.notnull(leap_row['ask']) else None,
                    "mid": leap_mid,
                    "cost_per_contract": round(leap_mid * 100, 0) if leap_mid else None,
                    "leverage_ratio": round(current_price * 100 / (leap_mid * 100), 1)
                                      if leap_mid and leap_mid > 0 else None,
                }

        return {
            "current_iv": round(current_iv * 100, 1),
            "csp": csp_info,
            "leap": leap_info,
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_position(
    ticker: str,
    conviction: float,
    portfolio_size: float,
    market_data: dict,
    entry_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    existing_shares: float = 0,
    include_options: bool = False,
) -> dict:
    """Core position sizing calculation."""
    current_price = market_data["current_price"]
    atr = market_data.get("atr_14") or 0
    sma_200 = market_data.get("sma_200")
    supports = market_data.get("support", [])

    # Use entry_price if given, otherwise current price
    effective_entry = entry_price if entry_price else current_price

    # Allocation range
    alloc_low, alloc_high = get_allocation_range(conviction)
    alloc_mid = (alloc_low + alloc_high) / 2

    target_dollars = alloc_mid * portfolio_size
    target_shares = int(target_dollars / current_price)
    shares_to_add = max(0, target_shares - int(existing_shares))

    # Over-allocation detection
    current_value = existing_shares * current_price
    current_pct = current_value / portfolio_size * 100 if portfolio_size > 0 else 0
    over_target = int(existing_shares) > target_shares
    over_max = current_pct > alloc_high * 100

    result = {
        "ticker": ticker.upper(),
        "current_price": current_price,
        "conviction": conviction,
        "portfolio_size": portfolio_size,
        "allocation": {
            "range_low_pct": round(alloc_low * 100, 1),
            "range_high_pct": round(alloc_high * 100, 1),
            "midpoint_pct": round(alloc_mid * 100, 1),
            "midpoint_dollars": round(target_dollars, 0),
            "target_shares": target_shares,
            "existing_shares": int(existing_shares),
            "shares_to_add": shares_to_add,
            "current_value": round(current_value, 0),
            "current_pct": round(current_pct, 1),
            "over_target": over_target,
            "over_max": over_max,
        },
        "market_data": {
            "atr_14": atr,
            "sma_200": sma_200,
            "support": supports,
            "resistance": market_data.get("resistance", []),
            "high_52w": market_data.get("high_52w"),
            "low_52w": market_data.get("low_52w"),
        },
    }

    # Scaled entry (40/30/30 using ATR)
    if atr and atr > 0:
        t1_shares = int(round(shares_to_add * 0.40))
        t2_shares = int(round(shares_to_add * 0.30))
        t3_shares = shares_to_add - t1_shares - t2_shares  # remainder

        t1_price = round(effective_entry, 2)
        t2_price = round(effective_entry - atr, 2)
        t3_price = round(effective_entry - 2 * atr, 2)

        t1_cost = round(t1_shares * t1_price, 0)
        t2_cost = round(t2_shares * t2_price, 0)
        t3_cost = round(t3_shares * t3_price, 0)

        total_cost = t1_cost + t2_cost + t3_cost
        avg_price = round(total_cost / shares_to_add, 2) if shares_to_add > 0 else 0

        result["scaled_entry"] = {
            "atr": atr,
            "tranches": [
                {"pct": 40, "shares": t1_shares, "price": t1_price, "cost": t1_cost},
                {"pct": 30, "shares": t2_shares, "price": t2_price, "cost": t2_cost},
                {"pct": 30, "shares": t3_shares, "price": t3_price, "cost": t3_cost},
            ],
            "total_shares": shares_to_add,
            "total_cost": round(total_cost, 0),
            "avg_price": avg_price,
        }

    # Risk analysis
    # Suggest stop if not provided: nearest of SMA 200 or first support below entry
    suggested_stop = None
    stop_source = None
    if stop_price:
        suggested_stop = stop_price
        stop_source = "user-specified"
    elif sma_200 and sma_200 < effective_entry:
        suggested_stop = sma_200
        stop_source = "SMA 200"
    elif supports:
        # Pick the first support level below entry
        below = [s for s in supports if s < effective_entry]
        if below:
            suggested_stop = below[0]
            stop_source = "support level"

    if suggested_stop:
        # Use avg price from scaled entry if available, else effective_entry
        cost_basis = (result.get("scaled_entry", {}).get("avg_price")
                      or effective_entry)
        total_risk_shares = (shares_to_add + int(existing_shares)
                             if shares_to_add > 0 else int(existing_shares))
        if total_risk_shares == 0:
            total_risk_shares = target_shares

        max_loss = round(total_risk_shares * (cost_basis - suggested_stop), 0)
        max_loss_pct = round(max_loss / portfolio_size * 100, 2) if portfolio_size > 0 else 0
        stop_distance_pct = round(
            (effective_entry - suggested_stop) / effective_entry * 100, 1
        )

        risk_data = {
            "stop_price": round(suggested_stop, 2),
            "stop_source": stop_source,
            "stop_distance_pct": stop_distance_pct,
            "shares_at_risk": total_risk_shares,
            "cost_basis": round(cost_basis, 2),
            "max_loss_dollars": max_loss,
            "max_loss_pct_of_portfolio": max_loss_pct,
        }

        # Risk/reward if target given
        if target_price:
            reward = total_risk_shares * (target_price - cost_basis)
            risk = abs(max_loss) if max_loss != 0 else 1
            rr_ratio = round(reward / risk, 1) if risk > 0 else float('inf')
            risk_data["target_price"] = target_price
            risk_data["potential_gain"] = round(reward, 0)
            risk_data["risk_reward_ratio"] = rr_ratio

        result["risk"] = risk_data

    # Options sizing
    if include_options:
        opts = fetch_options_data(ticker, current_price)
        if opts and "error" not in opts:
            result["options"] = opts

    return result


def format_terminal(result: dict) -> str:
    """Format result as a readable terminal display."""
    lines = []
    w = 70  # width

    ticker = result["ticker"]
    lines.append("=" * w)
    lines.append(f"  POSITION SIZER — {ticker}".center(w))
    lines.append("=" * w)
    lines.append("")

    # Header info
    lines.append(f"  Current Price:           ${result['current_price']:,.2f}")
    lines.append(f"  Conviction:              {result['conviction']}")
    lines.append(f"  Portfolio Size:          ${result['portfolio_size']:,.0f}")
    lines.append("")

    # Allocation
    alloc = result["allocation"]
    lines.append("  TARGET ALLOCATION:")
    lines.append("  " + "-" * (w - 4))
    lines.append(f"    Range:                 {alloc['range_low_pct']}%"
                 f" - {alloc['range_high_pct']}%")
    lines.append(f"    Midpoint:              {alloc['midpoint_pct']}%"
                 f" = ${alloc['midpoint_dollars']:,.0f}")
    lines.append(f"    Shares needed:         {alloc['target_shares']} shares")
    lines.append(f"    Currently held:        {alloc['existing_shares']} shares")

    if alloc.get("over_target"):
        excess = alloc['existing_shares'] - alloc['target_shares']
        lines.append(
            f"    ** OVER-ALLOCATED **    {excess} shares over target"
            f" ({alloc['current_pct']}% vs {alloc['midpoint_pct']}% target)"
        )
        if alloc.get("over_max"):
            lines.append(
                f"    ** EXCEEDS MAX **       above {alloc['range_high_pct']}%"
                f" ceiling — consider trimming"
            )
        lines.append(f"    Shares to ADD:         0 shares (reduce, don't add)")
    else:
        lines.append(f"    Shares to ADD:         {alloc['shares_to_add']} shares")
    lines.append("")

    # Holdings breakdown (if existing shares across accounts)
    if hasattr(format_terminal, '_holdings') and format_terminal._holdings:
        for h in format_terminal._holdings:
            lines.append(f"      {h['account']}: {h['shares']:.0f} shares"
                         f" (${h['value']:,.0f})")
        lines.append("")

    # Scaled entry
    scaled = result.get("scaled_entry")
    if scaled and scaled["total_shares"] > 0:
        lines.append(f"  SCALED ENTRY (40/30/30, ATR = ${scaled['atr']:.2f}):")
        lines.append("  " + "-" * (w - 4))
        for t in scaled["tranches"]:
            lines.append(
                f"    Tranche {scaled['tranches'].index(t) + 1}"
                f" ({t['pct']}%):  {t['shares']} shares"
                f" @ ${t['price']:,.2f} = ${t['cost']:,.0f}"
            )
        lines.append(
            f"    Total if all fill: {scaled['total_shares']} shares,"
            f" ${scaled['total_cost']:,.0f} avg ${scaled['avg_price']:,.2f}"
        )
        lines.append("")

    # Risk analysis
    risk = result.get("risk")
    if risk:
        lines.append("  RISK ANALYSIS:")
        lines.append("  " + "-" * (w - 4))
        lines.append(
            f"    Mental stop:           ${risk['stop_price']:,.2f}"
            f" ({risk['stop_source']}, -{risk['stop_distance_pct']}%)"
        )
        lines.append(
            f"    Max loss at stop:      {risk['shares_at_risk']}"
            f" x (${risk['cost_basis']:,.2f} - ${risk['stop_price']:,.2f})"
            f" = ${risk['max_loss_dollars']:,.0f}"
        )
        lines.append(
            f"    Max loss % of portfolio: {risk['max_loss_pct_of_portfolio']:.2f}%"
        )
        if "target_price" in risk:
            lines.append(
                f"    Risk/reward to ${risk['target_price']:,.0f} PT:"
                f" {risk['risk_reward_ratio']}:1"
            )
        lines.append("")

    # Options
    opts = result.get("options")
    if opts and "error" not in opts:
        lines.append("  OPTIONS SIZING:")
        lines.append("  " + "-" * (w - 4))
        lines.append(f"    Current IV:            {opts['current_iv']}%")
        csp = opts.get("csp")
        if csp:
            premium_str = (f"~${csp['mid']:.2f}" if csp.get('mid')
                           else "check chain")
            lines.append(
                f"    CSP: 1x ${csp['strike']:.0f}P {csp['expiry']}"
                f" = ${csp['collateral']:,.0f} collateral,"
                f" {premium_str} premium"
            )
        leap = opts.get("leap")
        if leap:
            cost_str = (f"${leap['cost_per_contract']:,.0f}"
                        if leap.get('cost_per_contract') else "N/A")
            lev_str = (f"{leap['leverage_ratio']}x"
                       if leap.get('leverage_ratio') else "N/A")
            lines.append(
                f"    LEAP: 1x ${leap['strike']:.0f}C {leap['expiry']}"
                f" ~ {cost_str}, leverage {lev_str}"
            )
        lines.append("")

    lines.append("=" * w)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Position sizer — target allocation, shares, risk metrics"
    )
    parser.add_argument("ticker", help="Stock ticker (e.g., ABBV, TSLA)")
    parser.add_argument(
        "--conviction", "-c", type=float, required=True,
        help="Conviction score (1-10)"
    )
    parser.add_argument(
        "--portfolio", "-p", type=float, default=None,
        help="Total portfolio size in dollars (default: sum from account files)"
    )
    parser.add_argument(
        "--entry", "-e", type=float, default=None,
        help="Entry price (default: current market price)"
    )
    parser.add_argument(
        "--stop", "-s", type=float, default=None,
        help="Stop loss price (default: SMA 200 or nearest support)"
    )
    parser.add_argument(
        "--target", "-t", type=float, default=None,
        help="Price target for risk/reward calculation"
    )
    parser.add_argument(
        "--existing", type=float, default=None,
        help="Existing shares held (default: read from account files)"
    )
    parser.add_argument(
        "--options", action="store_true",
        help="Include CSP/LEAP sizing estimates"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of terminal display"
    )

    args = parser.parse_args()
    ticker = args.ticker.upper()

    # --- Portfolio size ---
    portfolio_size = args.portfolio
    if portfolio_size is None:
        portfolio_size = get_portfolio_total()
        if portfolio_size is None:
            print("Error: Could not read portfolio size from account files."
                  " Use --portfolio flag.", file=sys.stderr)
            sys.exit(1)

    # --- Existing shares ---
    existing_shares = args.existing
    holdings_detail = []
    if existing_shares is None:
        existing_shares, holdings_detail = get_existing_shares(ticker)

    # --- Fetch market data ---
    print(f"Fetching market data for {ticker}...", file=sys.stderr)
    market_data = fetch_market_data(ticker)
    if "error" in market_data:
        print(f"Error: {market_data['error']}", file=sys.stderr)
        sys.exit(1)

    # --- Read research file for entry target / price target ---
    research = get_stock_research(ticker)
    entry_price = args.entry
    target_price = args.target
    if target_price is None and research.get("entry_target"):
        # entry_target from research can serve as a reference but
        # we don't auto-use it as the target_price (that's the sell target)
        pass

    # --- Calculate ---
    result = calculate_position(
        ticker=ticker,
        conviction=args.conviction,
        portfolio_size=portfolio_size,
        market_data=market_data,
        entry_price=entry_price,
        stop_price=args.stop,
        target_price=target_price,
        existing_shares=existing_shares,
        include_options=args.options,
    )

    # Add holdings detail for display
    if holdings_detail:
        result["holdings_detail"] = holdings_detail

    # --- Output ---
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Pass holdings detail to formatter
        format_terminal._holdings = holdings_detail
        print(format_terminal(result))


if __name__ == "__main__":
    main()
