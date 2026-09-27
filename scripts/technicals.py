#!/usr/bin/env python3
"""
technicals.py — Fetch price, technical indicators, and options data for a ticker.

Usage:
    python3 scripts/technicals.py AAPL
    python3 scripts/technicals.py AAPL --period 6mo
    python3 scripts/technicals.py AAPL --options

Returns structured JSON to stdout.
"""

import sys
import json
import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


def calculate_rsi(series, window=14):
    # Wilder's smoothing (standard RSI, matches broker/charting platforms)
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram


def find_support_resistance(hist, window=20):
    """Find key support/resistance levels from recent pivot points."""
    highs = hist['High'].rolling(window=window, center=True).max()
    lows = hist['Low'].rolling(window=window, center=True).min()

    current_price = hist['Close'].iloc[-1]
    all_levels = []

    # Pivot highs (resistance candidates)
    for i in range(window, len(hist) - window):
        if hist['High'].iloc[i] == highs.iloc[i]:
            all_levels.append(('resistance', round(hist['High'].iloc[i], 2)))

    # Pivot lows (support candidates)
    for i in range(window, len(hist) - window):
        if hist['Low'].iloc[i] == lows.iloc[i]:
            all_levels.append(('support', round(hist['Low'].iloc[i], 2)))

    # Cluster nearby levels (within 1.5%)
    supports = sorted(set(p for t, p in all_levels if t == 'support'), reverse=True)
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


def get_options_summary(stock, current_price):
    """Get IV rank, put/call OI ratio, and nearest expiry chain summary."""
    try:
        expirations = stock.options
        if not expirations:
            return None

        # Use nearest expiry for quick snapshot
        nearest = expirations[0]
        chain = stock.option_chain(nearest)
        calls = chain.calls
        puts = chain.puts

        # Put/Call open interest ratio
        total_call_oi = calls['openInterest'].sum()
        total_put_oi = puts['openInterest'].sum()
        pc_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None

        # IV from ATM options (nearest strike to current price)
        atm_call_idx = (calls['strike'] - current_price).abs().idxmin()
        atm_put_idx = (puts['strike'] - current_price).abs().idxmin()
        atm_call_iv = calls.loc[atm_call_idx, 'impliedVolatility']
        atm_put_iv = puts.loc[atm_put_idx, 'impliedVolatility']
        current_iv = round((atm_call_iv + atm_put_iv) / 2 * 100, 1)

        # IV rank approximation using 52-week high/low from info
        info = stock.info or {}
        # yfinance doesn't give historical IV, so we report current IV
        # and note the 52w high/low for context
        iv_data = {
            "current_iv": current_iv,
            "put_call_oi_ratio": pc_ratio,
            "nearest_expiry": nearest,
            "expirations_available": expirations[:6],
        }

        # Find 30-45 DTE expiry (theta gang sweet spot)
        today = datetime.now().date()
        target_expiries = []
        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if 25 <= dte <= 50:
                target_expiries.append({"expiry": exp, "dte": dte})

        iv_data["theta_gang_expiries"] = target_expiries

        return iv_data

    except Exception as e:
        return {"error": str(e)}


def get_volume_profile(hist, bins=10):
    """Simple volume-by-price distribution over recent history."""
    price_range = hist['Close'].max() - hist['Close'].min()
    if price_range == 0:
        return None

    bin_edges = np.linspace(hist['Low'].min(), hist['High'].max(), bins + 1)
    volume_at_price = []

    for i in range(len(bin_edges) - 1):
        low = bin_edges[i]
        high = bin_edges[i + 1]
        mask = (hist['Close'] >= low) & (hist['Close'] < high)
        vol = hist.loc[mask, 'Volume'].sum()
        volume_at_price.append({
            "price_low": round(low, 2),
            "price_high": round(high, 2),
            "volume": int(vol)
        })

    # High volume node (HVN) = price level with most volume
    hvn = max(volume_at_price, key=lambda x: x['volume'])
    return {
        "high_volume_node": round((hvn['price_low'] + hvn['price_high']) / 2, 2),
        "distribution": volume_at_price
    }


def analyze(ticker, period="6mo", include_options=False):
    stock = yf.Ticker(ticker)

    # Fetch enough history for 200 SMA
    fetch_period = "2y" if period in ["1y", "2y", "max"] else "1y"
    hist = stock.history(period=fetch_period, interval="1d", auto_adjust=True)

    if hist.empty:
        return {"error": f"No data found for '{ticker}'"}

    # Calculate indicators
    hist['SMA_20'] = hist['Close'].rolling(20).mean()
    hist['SMA_50'] = hist['Close'].rolling(50).mean()
    hist['SMA_200'] = hist['Close'].rolling(200).mean()
    hist['RSI_14'] = calculate_rsi(hist['Close'])
    hist['MACD'], hist['MACD_Signal'], hist['MACD_Hist'] = calculate_macd(hist['Close'])

    # Bollinger Bands
    bb_mid = hist['Close'].rolling(20).mean()
    bb_std = hist['Close'].rolling(20).std()
    hist['BB_Upper'] = bb_mid + 2 * bb_std
    hist['BB_Lower'] = bb_mid - 2 * bb_std

    # ATR (14-day)
    tr = pd.concat([
        hist['High'] - hist['Low'],
        (hist['High'] - hist['Close'].shift()).abs(),
        (hist['Low'] - hist['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    hist['ATR_14'] = tr.rolling(14).mean()

    last = hist.iloc[-1]
    prev = hist.iloc[-2]
    current_price = round(last['Close'], 2)

    # Price data
    price = {
        "current": current_price,
        "prev_close": round(prev['Close'], 2),
        "change": round(last['Close'] - prev['Close'], 2),
        "change_pct": round((last['Close'] - prev['Close']) / prev['Close'] * 100, 2),
        "high_52w": round(hist['High'].tail(252).max(), 2),
        "low_52w": round(hist['Low'].tail(252).min(), 2),
        "avg_volume_20d": int(hist['Volume'].tail(20).mean()),
        "last_volume": int(last['Volume']),
    }

    # Technical snapshot
    technicals = {
        "rsi_14": round(last['RSI_14'], 1) if pd.notnull(last['RSI_14']) else None,
        "macd": {
            "value": round(last['MACD'], 3) if pd.notnull(last['MACD']) else None,
            "signal": round(last['MACD_Signal'], 3) if pd.notnull(last['MACD_Signal']) else None,
            "histogram": round(last['MACD_Hist'], 3) if pd.notnull(last['MACD_Hist']) else None,
        },
        "sma_20": round(last['SMA_20'], 2) if pd.notnull(last['SMA_20']) else None,
        "sma_50": round(last['SMA_50'], 2) if pd.notnull(last['SMA_50']) else None,
        "sma_200": round(last['SMA_200'], 2) if pd.notnull(last['SMA_200']) else None,
        "bollinger": {
            "upper": round(last['BB_Upper'], 2) if pd.notnull(last['BB_Upper']) else None,
            "lower": round(last['BB_Lower'], 2) if pd.notnull(last['BB_Lower']) else None,
        },
        "atr_14": round(last['ATR_14'], 2) if pd.notnull(last['ATR_14']) else None,
    }

    # Support/Resistance
    supports, resistances = find_support_resistance(hist)

    # Volume profile (last 3 months)
    vol_profile = get_volume_profile(hist.tail(66))

    # Trend context
    trend = {
        "above_sma_20": bool(current_price > (technicals['sma_20'] or 0)),
        "above_sma_50": bool(current_price > (technicals['sma_50'] or 0)),
        "above_sma_200": bool(current_price > (technicals['sma_200'] or 0)),
        "distance_from_52w_high_pct": round((current_price - price['high_52w']) / price['high_52w'] * 100, 1),
        "distance_from_52w_low_pct": round((current_price - price['low_52w']) / price['low_52w'] * 100, 1),
    }

    result = {
        "ticker": ticker.upper(),
        "timestamp": datetime.now().isoformat(),
        "price": price,
        "technicals": technicals,
        "trend": trend,
        "support": supports,
        "resistance": resistances,
        "volume_profile_hvn": vol_profile['high_volume_node'] if vol_profile else None,
    }

    # Options data (heavier call, opt-in)
    if include_options:
        options = get_options_summary(stock, current_price)
        if options:
            result["options"] = options

    # Fundamentals snapshot
    info = stock.info or {}
    result["fundamentals"] = {
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margin": info.get("profitMargins"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "next_earnings": info.get("earningsTimestamp"),
        "dividend_yield": info.get("dividendYield"),
        "ex_dividend_date": info.get("exDividendDate"),
    }

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch stock technicals as JSON")
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL, 0700.HK)")
    parser.add_argument("--period", default="6mo", help="History period: 3mo, 6mo, 1y, 2y (default: 6mo)")
    parser.add_argument("--options", action="store_true", help="Include options chain data (IV, P/C ratio, expiries)")

    args = parser.parse_args()
    result = analyze(args.ticker, period=args.period, include_options=args.options)
    print(json.dumps(result, indent=2, default=str))
