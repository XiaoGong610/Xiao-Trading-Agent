#!/usr/bin/env python3
"""
whale-tracker.py — Track institutional activity, insider transactions, and unusual options.

Surfaces "smart money" signals: insider buying/selling clusters, institutional
holding changes, and unusual options volume that often precede significant moves.

Data sources (all free, no API keys required):
  - SEC EDGAR EFTS API (Form 4 insider filings)
  - Finviz (institutional holders)
  - Yahoo Finance via yfinance (options chain unusual activity)

Usage:
    .venv/bin/python3 scripts/whale-tracker.py AAPL                  # single ticker
    .venv/bin/python3 scripts/whale-tracker.py AAPL --days 90         # custom lookback
    .venv/bin/python3 scripts/whale-tracker.py AAPL TSLA NVDA         # multiple tickers
    .venv/bin/python3 scripts/whale-tracker.py --portfolio            # all held positions
    .venv/bin/python3 scripts/whale-tracker.py AAPL --json            # JSON output
    .venv/bin/python3 scripts/whale-tracker.py AAPL --insider-only    # just insider data
    .venv/bin/python3 scripts/whale-tracker.py AAPL --options-only    # just unusual options
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UA = "xiao-trading-agent/1.0 (personal research; contact@example.com)"
# SEC EDGAR requires specific User-Agent format (company/name + email)
SEC_UA = "xiao-trading-agent research@xiao-trading-agent.local"
ACCOUNTS_DIR = Path("portfolio/accounts")
CACHE_DIR = Path("/tmp/whale-tracker-cache")
CACHE_TTL = 3600  # 1 hour

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BOLD_GREEN = "\033[1;32m"
BOLD_YELLOW = "\033[1;33m"
BOLD_RED = "\033[1;31m"
BOLD_CYAN = "\033[1;36m"
BOLD_WHITE = "\033[1;37m"
BOLD_MAGENTA = "\033[1;35m"

USE_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

# Notable institutional investors to flag
NOTABLE_INSTITUTIONS = {
    "berkshire hathaway", "bridgewater associates", "renaissance technologies",
    "citadel", "two sigma", "de shaw", "millennium management",
    "ark invest", "ark investment", "soros fund management",
    "appaloosa management", "baupost group", "pershing square",
    "third point", "elliott management", "icahn enterprises",
    "tiger global", "coatue management", "dragoneer", "altimeter",
    "lone pine capital", "viking global", "durable capital",
}


def c(text: str, code: str) -> str:
    """Wrap text in ANSI color if terminal supports it."""
    if USE_COLOR:
        return f"{code}{text}{RESET}"
    return text


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def _cache_key(prefix: str, ticker: str, extra: str = "") -> Path:
    """Generate a cache file path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(f"{prefix}:{ticker}:{extra}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{prefix}_{ticker}_{h}.json"


def _cache_get(key: Path) -> dict | None:
    """Read from cache if fresh."""
    if not key.exists():
        return None
    try:
        mtime = key.stat().st_mtime
        if time.time() - mtime > CACHE_TTL:
            return None
        return json.loads(key.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(key: Path, data: dict) -> None:
    """Write to cache."""
    try:
        key.write_text(json.dumps(data, default=str))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_url(url: str, timeout: float = 15.0, accept: str = "application/json",
               user_agent: str | None = None) -> str | None:
    """Fetch URL with proper headers and error handling."""
    req = Request(url, headers={
        "User-Agent": user_agent or UA,
        "Accept": accept,
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, OSError) as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return None


def _fetch_json(url: str, timeout: float = 15.0,
                user_agent: str | None = None) -> dict | None:
    """Fetch URL and parse as JSON."""
    raw = _fetch_url(url, timeout=timeout, accept="application/json",
                     user_agent=user_agent)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed for %s", url)
        return None


# ---------------------------------------------------------------------------
# SEC EDGAR — Insider Transactions (Form 4)
# ---------------------------------------------------------------------------

# SEC EDGAR EFTS full-text search API
EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
# SEC EDGAR company tickers mapping
EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC EDGAR Form 4 filing detail
EDGAR_FILING_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

# Transaction codes from SEC Form 4
TRANSACTION_CODES = {
    "P": "Purchase",
    "S": "Sale",
    "A": "Grant/Award",
    "D": "Disposition (non-sale)",
    "F": "Tax withholding",
    "M": "Option exercise",
    "G": "Gift",
    "C": "Conversion",
    "J": "Other",
    "X": "Option exercise/expiry",
}


def _get_cik_for_ticker(ticker: str) -> str | None:
    """Look up SEC CIK number for a ticker symbol."""
    cache_key = _cache_key("cik", ticker)
    cached = _cache_get(cache_key)
    if cached:
        return cached.get("cik")

    data = _fetch_json(EDGAR_TICKERS_URL, user_agent=SEC_UA)
    if not data:
        return None

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry.get("cik_str", ""))
            _cache_set(cache_key, {"cik": cik})
            return cik

    return None


def _parse_form4_xml(xml_text: str) -> list[dict]:
    """Parse SEC Form 4 XML to extract transaction details."""
    transactions = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return transactions

    # Reporting owner info
    owner_el = root.find(".//reportingOwner")
    owner_name = ""
    owner_title = ""
    if owner_el is not None:
        name_el = owner_el.find(".//rptOwnerName")
        if name_el is not None and name_el.text:
            owner_name = name_el.text.strip()
        # Title can be in reportingOwnerRelationship/officerTitle
        title_el = owner_el.find(".//officerTitle")
        if title_el is not None and title_el.text:
            owner_title = title_el.text.strip()

    # Non-derivative transactions
    for txn in root.findall(".//nonDerivativeTransaction"):
        code_el = txn.find(".//transactionCoding/transactionCode")
        date_el = txn.find(".//transactionDate/value")
        shares_el = txn.find(".//transactionAmounts/transactionShares/value")
        price_el = txn.find(".//transactionAmounts/transactionPricePerShare/value")

        if code_el is None or code_el.text is None:
            continue

        code = code_el.text.strip()
        date = date_el.text.strip() if date_el is not None and date_el.text else ""
        shares = 0.0
        price = 0.0
        try:
            shares = float(shares_el.text) if shares_el is not None and shares_el.text else 0.0
        except ValueError:
            pass
        try:
            price = float(price_el.text) if price_el is not None and price_el.text else 0.0
        except ValueError:
            pass

        value = shares * price
        tx_type = TRANSACTION_CODES.get(code, code)

        transactions.append({
            "date": date,
            "insider": owner_name,
            "title": owner_title,
            "type": tx_type,
            "code": code,
            "shares": int(shares) if shares == int(shares) else shares,
            "price": round(price, 2),
            "value": round(value, 2),
        })

    return transactions


def fetch_insider_transactions(ticker: str, days: int = 30) -> dict:
    """Fetch insider transactions from SEC EDGAR for a ticker.

    Uses the EFTS full-text search API for Form 4 filings, then parses
    each filing's XML for transaction details.
    """
    cache_key = _cache_key("insider", ticker, str(days))
    cached = _cache_get(cache_key)
    if cached:
        return cached

    result = {
        "source": "sec_edgar",
        "available": False,
        "ticker": ticker.upper(),
        "lookback_days": days,
        "transactions": [],
        "summary": {},
        "signals": [],
    }

    cik = _get_cik_for_ticker(ticker)
    if not cik:
        result["error"] = f"CIK not found for {ticker}"
        return result

    # Pad CIK to 10 digits
    cik_padded = cik.zfill(10)

    # Search for Form 4 filings via EDGAR EFTS
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Use the EDGAR full-text search API
    params = urlencode({
        "q": f'"{ticker.upper()}"',
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
        "forms": "4",
    })
    search_url = f"https://efts.sec.gov/LATEST/search-index?{params}"

    time.sleep(0.15)  # SEC rate limit: 10 req/sec
    search_data = _fetch_json(search_url, user_agent=SEC_UA)

    # Fallback: use the EDGAR filing API with CIK directly
    if not search_data or not search_data.get("hits", {}).get("hits"):
        # Try the company filings endpoint
        filings_url = (
            f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        )
        time.sleep(0.15)
        filings_data = _fetch_json(filings_url, user_agent=SEC_UA)

        if filings_data:
            recent = filings_data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])

            all_transactions = []
            filing_count = 0

            for i, form in enumerate(forms):
                if form != "4":
                    continue
                filing_date = dates[i] if i < len(dates) else ""
                if filing_date < start_date:
                    continue
                if filing_date > end_date:
                    continue

                filing_count += 1
                if filing_count > 20:  # Limit to avoid too many requests
                    break

                # Fetch the actual Form 4 XML
                accession = accessions[i].replace("-", "") if i < len(accessions) else ""
                accession_dashed = accessions[i] if i < len(accessions) else ""
                primary_doc = primary_docs[i] if i < len(primary_docs) else ""

                if not accession or not primary_doc:
                    continue

                # Try XML version first
                xml_url = (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{cik}/{accession}/{primary_doc}"
                )
                time.sleep(0.15)
                xml_text = _fetch_url(xml_url, accept="application/xml",
                                     user_agent=SEC_UA)
                if xml_text:
                    txns = _parse_form4_xml(xml_text)
                    all_transactions.extend(txns)

            if all_transactions:
                result["available"] = True
                result["transactions"] = _deduplicate_transactions(all_transactions)
                result["summary"] = _summarize_transactions(result["transactions"])
                result["signals"] = _detect_insider_signals(result["transactions"], days)
                _cache_set(cache_key, result)
                return result

    # Parse EFTS search results if we got them
    if search_data and search_data.get("hits", {}).get("hits"):
        hits = search_data["hits"]["hits"]
        all_transactions = []

        for hit in hits[:20]:
            source = hit.get("_source", {})
            file_url = source.get("file_url", "")
            if not file_url:
                continue

            # Fetch XML of Form 4
            full_url = f"https://www.sec.gov{file_url}" if file_url.startswith("/") else file_url
            time.sleep(0.15)
            xml_text = _fetch_url(full_url, accept="application/xml",
                                 user_agent=SEC_UA)
            if xml_text:
                txns = _parse_form4_xml(xml_text)
                all_transactions.extend(txns)

        if all_transactions:
            result["available"] = True
            result["transactions"] = _deduplicate_transactions(all_transactions)

    # If no EDGAR data, try finviz as fallback
    if not result["available"]:
        finviz_txns = _fetch_finviz_insiders(ticker, days)
        if finviz_txns:
            result["available"] = True
            result["source"] = "finviz"
            result["transactions"] = finviz_txns

    if result["available"]:
        result["summary"] = _summarize_transactions(result["transactions"])
        result["signals"] = _detect_insider_signals(result["transactions"], days)

    _cache_set(cache_key, result)
    return result


def _deduplicate_transactions(txns: list[dict]) -> list[dict]:
    """Remove duplicate transactions based on date + insider + shares + code."""
    seen = set()
    unique = []
    for t in txns:
        key = (t.get("date"), t.get("insider"), t.get("shares"), t.get("code"))
        if key not in seen:
            seen.add(key)
            unique.append(t)
    # Sort by date descending
    unique.sort(key=lambda x: x.get("date", ""), reverse=True)
    return unique


def _summarize_transactions(txns: list[dict]) -> dict:
    """Summarize buy/sell activity."""
    buys = [t for t in txns if t.get("code") == "P"]
    sells = [t for t in txns if t.get("code") == "S"]
    exercises = [t for t in txns if t.get("code") in ("M", "X")]
    grants = [t for t in txns if t.get("code") == "A"]
    tax_with = [t for t in txns if t.get("code") == "F"]

    buy_value = sum(t.get("value", 0) for t in buys)
    sell_value = sum(t.get("value", 0) for t in sells)

    unique_buyers = set(t.get("insider", "") for t in buys if t.get("insider"))
    unique_sellers = set(t.get("insider", "") for t in sells if t.get("insider"))

    if buys and not sells:
        net_direction = "NET BUYING"
    elif sells and not buys:
        net_direction = "NET SELLING"
    elif buy_value > sell_value:
        net_direction = "NET BUYING"
    elif sell_value > buy_value:
        net_direction = "NET SELLING"
    else:
        net_direction = "NEUTRAL"

    return {
        "total_transactions": len(txns),
        "buys": len(buys),
        "sells": len(sells),
        "exercises": len(exercises),
        "grants": len(grants),
        "tax_withholding": len(tax_with),
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "unique_buyers": len(unique_buyers),
        "unique_sellers": len(unique_sellers),
        "net_direction": net_direction,
    }


def _detect_insider_signals(txns: list[dict], days: int) -> list[str]:
    """Detect notable insider trading patterns."""
    signals = []
    buys = [t for t in txns if t.get("code") == "P"]
    sells = [t for t in txns if t.get("code") == "S"]

    # Cluster buying: 3+ distinct insiders buying in the lookback period
    unique_buyers = set(t.get("insider", "") for t in buys if t.get("insider"))
    if len(unique_buyers) >= 3:
        signals.append(
            f"CLUSTER BUYING: {len(unique_buyers)} insiders bought in {days} days (STRONG signal)"
        )
    elif len(unique_buyers) == 2:
        signals.append(
            f"NOTABLE: 2 insiders bought in {days} days (moderate signal)"
        )

    # Large single purchase (>$500K)
    for t in buys:
        if t.get("value", 0) >= 500_000:
            signals.append(
                f"LARGE BUY: {t['insider']} ({t.get('title', '?')}) bought "
                f"${t['value']:,.0f} worth"
            )

    # Large single sale (>$5M) — less meaningful but worth flagging
    # Cap at top 3 by value to avoid noise
    large_sells = sorted(
        [t for t in sells if t.get("value", 0) >= 5_000_000],
        key=lambda t: t.get("value", 0),
        reverse=True,
    )
    for t in large_sells[:3]:
        signals.append(
            f"LARGE SELL: {t['insider']} ({t.get('title', '?')}) sold "
            f"${t['value']:,.0f} worth"
        )
    if len(large_sells) > 3:
        total_large = sum(t.get("value", 0) for t in large_sells)
        signals.append(
            f"... and {len(large_sells) - 3} more large sells "
            f"(${total_large:,.0f} total across {len(large_sells)} transactions)"
        )

    # All selling, no buying
    if sells and not buys:
        total_sell = sum(t.get("value", 0) for t in sells)
        signals.append(f"ALL SELLING: {len(sells)} sells, 0 buys (${total_sell:,.0f} total)")

    # C-suite buying (CEO, CFO, COO, CTO)
    csuite_buys = [
        t for t in buys
        if any(role in (t.get("title", "") or "").upper()
               for role in ("CEO", "CFO", "COO", "CTO", "CHIEF"))
    ]
    if csuite_buys:
        names = ", ".join(set(t.get("insider", "?") for t in csuite_buys))
        signals.append(f"C-SUITE BUYING: {names}")

    return signals


def _fetch_finviz_insiders(ticker: str, days: int = 30) -> list[dict]:
    """Fallback: scrape insider transactions from Finviz."""
    if not HAS_BS4:
        return []

    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}&ty=i&p=d"
    raw = _fetch_url(url, accept="text/html")
    if not raw:
        return []

    try:
        soup = BeautifulSoup(raw, "html.parser")
    except Exception:
        return []

    transactions = []
    # Find the insider trading table
    tables = soup.find_all("table", class_="body-table")
    if not tables:
        return []

    cutoff_date = datetime.now() - timedelta(days=days)

    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header
            cells = row.find_all("td")
            if len(cells) < 6:
                continue
            try:
                insider = cells[0].get_text(strip=True)
                title = cells[1].get_text(strip=True)
                date_str = cells[2].get_text(strip=True)
                tx_type = cells[3].get_text(strip=True)
                price_str = cells[4].get_text(strip=True).replace(",", "")
                qty_str = cells[5].get_text(strip=True).replace(",", "")
                value_str = cells[6].get_text(strip=True).replace(",", "") if len(cells) > 6 else ""

                # Parse date — finviz uses various formats:
                # "Sep 08 '26", "Sep 08", "2026-09-08"
                date_formatted = date_str
                tx_date = None
                for fmt in ("%b %d '%y", "%b %d", "%Y-%m-%d"):
                    try:
                        tx_date = datetime.strptime(date_str, fmt)
                        if fmt == "%b %d":
                            tx_date = tx_date.replace(year=datetime.now().year)
                            if tx_date > datetime.now():
                                tx_date = tx_date.replace(year=tx_date.year - 1)
                        date_formatted = tx_date.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                if tx_date and tx_date < cutoff_date:
                    continue

                # Determine code
                tx_lower = tx_type.lower()
                if "buy" in tx_lower or "purchase" in tx_lower:
                    code = "P"
                elif "sale" in tx_lower or "sell" in tx_lower:
                    code = "S"
                elif "exercise" in tx_lower or "option" in tx_lower:
                    code = "M"
                else:
                    code = "J"

                price = float(price_str) if price_str else 0.0
                shares = float(qty_str) if qty_str else 0.0
                value = float(value_str) if value_str else shares * price

                transactions.append({
                    "date": date_formatted,
                    "insider": insider,
                    "title": title,
                    "type": TRANSACTION_CODES.get(code, tx_type),
                    "code": code,
                    "shares": int(shares) if shares == int(shares) else shares,
                    "price": round(price, 2),
                    "value": round(value, 2),
                })
            except (ValueError, IndexError):
                continue

    return transactions


# ---------------------------------------------------------------------------
# Institutional Holdings (Finviz + SEC)
# ---------------------------------------------------------------------------

def fetch_institutional_holders(ticker: str) -> dict:
    """Fetch institutional holder data for a ticker."""
    cache_key = _cache_key("inst", ticker)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    result = {
        "source": "yfinance",
        "available": False,
        "ticker": ticker.upper(),
        "top_holders": [],
        "recent_changes": [],
        "notable_holders": [],
    }

    # Try yfinance first — most reliable for institutional data
    if HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)

            # Major holders
            inst_holders = stock.institutional_holders
            if inst_holders is not None and not inst_holders.empty:
                result["available"] = True

                # Try to get shares outstanding for pct calculation fallback
                shares_outstanding = 0
                try:
                    info = stock.info or {}
                    shares_outstanding = info.get("sharesOutstanding", 0) or 0
                except Exception:
                    pass

                for _, row in inst_holders.head(15).iterrows():
                    holder_name = str(row.get("Holder", ""))
                    shares = int(row.get("Shares", 0)) if not pd.isna(row.get("Shares", 0)) else 0
                    pct = float(row.get("% Out", 0)) if not pd.isna(row.get("% Out", 0)) else 0.0
                    value = float(row.get("Value", 0)) if not pd.isna(row.get("Value", 0)) else 0.0
                    date_reported = str(row.get("Date Reported", ""))

                    # Convert pct: yfinance returns as decimal (0.08 = 8%) or 0
                    if pct > 0 and pct < 1:
                        pct_display = round(pct * 100, 2)
                    elif pct >= 1:
                        pct_display = round(pct, 2)
                    elif shares > 0 and shares_outstanding > 0:
                        # Compute from shares outstanding
                        pct_display = round(shares / shares_outstanding * 100, 2)
                    else:
                        pct_display = 0.0

                    holder_entry = {
                        "holder": holder_name,
                        "shares": shares,
                        "pct_out": pct_display,
                        "value": round(value, 2),
                        "date_reported": date_reported[:10] if date_reported else "",
                    }
                    result["top_holders"].append(holder_entry)

                    # Check if notable
                    holder_lower = holder_name.lower()
                    for notable in NOTABLE_INSTITUTIONS:
                        if notable in holder_lower:
                            result["notable_holders"].append(holder_entry)
                            break

            # Mutual fund holders for additional coverage
            mf_holders = stock.mutualfund_holders
            if mf_holders is not None and not mf_holders.empty:
                result["available"] = True
                fund_summary = []
                for _, row in mf_holders.head(5).iterrows():
                    holder_name = str(row.get("Holder", ""))
                    shares = int(row.get("Shares", 0)) if not pd.isna(row.get("Shares", 0)) else 0
                    pct = float(row.get("% Out", 0)) if not pd.isna(row.get("% Out", 0)) else 0.0
                    fund_summary.append({
                        "holder": holder_name,
                        "shares": shares,
                        "pct_out": round(pct * 100, 2) if pct < 1 else round(pct, 2),
                    })
                result["top_mutual_funds"] = fund_summary

        except Exception as exc:
            logger.warning("yfinance institutional data failed for %s: %s", ticker, exc)

    # Fallback: try finviz for institutional data
    if not result["available"] and HAS_BS4:
        finviz_inst = _fetch_finviz_institutional(ticker)
        if finviz_inst:
            result.update(finviz_inst)

    _cache_set(cache_key, result)
    return result


def _fetch_finviz_institutional(ticker: str) -> dict | None:
    """Scrape institutional ownership info from Finviz."""
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
    raw = _fetch_url(url, accept="text/html")
    if not raw or not HAS_BS4:
        return None

    try:
        soup = BeautifulSoup(raw, "html.parser")
    except Exception:
        return None

    result = {"available": False, "source": "finviz"}

    # Find institutional ownership percentage from snapshot table
    for row in soup.find_all("tr", class_="table-dark-row"):
        cells = row.find_all("td")
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            if text == "Inst Own":
                if i + 1 < len(cells):
                    pct = cells[i + 1].get_text(strip=True).replace("%", "")
                    try:
                        result["inst_ownership_pct"] = float(pct)
                        result["available"] = True
                    except ValueError:
                        pass
            elif text == "Inst Trans":
                if i + 1 < len(cells):
                    result["inst_transaction_pct"] = cells[i + 1].get_text(strip=True)
                    result["available"] = True

    return result if result["available"] else None


# ---------------------------------------------------------------------------
# Unusual Options Activity (yfinance)
# ---------------------------------------------------------------------------

def fetch_unusual_options(ticker: str) -> dict:
    """Detect unusual options activity using yfinance options chain data.

    Flags strikes where volume/OI ratio exceeds 3x (unusual activity),
    and computes put/call skew.
    """
    cache_key = _cache_key("opts", ticker)
    cached = _cache_get(cache_key)
    if cached and cached.get("available"):
        return cached

    result = {
        "source": "yfinance",
        "available": False,
        "ticker": ticker.upper(),
        "unusual_strikes": [],
        "put_call_ratio": None,
        "total_call_volume": 0,
        "total_put_volume": 0,
        "largest_trades": [],
    }

    if not HAS_YFINANCE or not HAS_PANDAS:
        result["error"] = "yfinance or pandas not available"
        return result

    def _col_sum(df, col):
        """Sum a column, treating NaN as 0."""
        if col not in df.columns:
            return 0
        s = df[col].fillna(0).sum()
        try:
            return int(s) if not math.isnan(float(s)) else 0
        except (ValueError, TypeError):
            return 0

    def _safe_val(val, as_int=False):
        """Convert value, treating NaN/None as 0."""
        try:
            f = float(val) if val is not None else 0.0
            if math.isnan(f):
                return 0 if as_int else 0.0
            return int(f) if as_int else f
        except (ValueError, TypeError):
            return 0 if as_int else 0.0

    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            result["error"] = "No options data available"
            return result

        # Get current price — handle different yfinance versions
        current_price = 0
        try:
            fi = stock.fast_info
            current_price = getattr(fi, "last_price", 0) or 0
            if not current_price:
                current_price = fi.get("lastPrice", 0) if hasattr(fi, "get") else 0
        except Exception:
            pass
        if not current_price:
            try:
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])
            except Exception:
                pass

        all_unusual = []
        total_call_vol = 0
        total_put_vol = 0
        total_call_oi = 0
        total_put_oi = 0

        # Scan nearest 3 expiries for unusual activity
        for exp in expirations[:3]:
            try:
                chain = stock.option_chain(exp)
            except Exception:
                continue

            calls = chain.calls
            puts = chain.puts

            total_call_vol += _col_sum(calls, "volume")
            total_put_vol += _col_sum(puts, "volume")
            total_call_oi += _col_sum(calls, "openInterest")
            total_put_oi += _col_sum(puts, "openInterest")

            # Check each strike for unusual volume
            for opt_type, df in [("CALL", calls), ("PUT", puts)]:
                if df.empty:
                    continue
                for _, row in df.iterrows():
                    volume = _safe_val(row.get("volume", 0), as_int=True)
                    oi = _safe_val(row.get("openInterest", 0), as_int=True)
                    strike = _safe_val(row.get("strike", 0))
                    last_price = _safe_val(row.get("lastPrice", 0))
                    iv = _safe_val(row.get("impliedVolatility", 0))

                    if volume < 100 or oi < 10:
                        continue

                    v_oi_ratio = round(volume / oi, 1) if oi > 0 else 0.0

                    # Flag unusual: V/OI > 3x
                    if v_oi_ratio >= 3.0:
                        notional = round(volume * last_price * 100, 2)
                        all_unusual.append({
                            "strike": strike,
                            "expiry": exp,
                            "type": opt_type,
                            "volume": volume,
                            "open_interest": oi,
                            "v_oi_ratio": v_oi_ratio,
                            "last_price": round(last_price, 2),
                            "implied_vol": round(iv * 100, 1),
                            "notional": notional,
                            "signal": "UNUSUAL" if v_oi_ratio >= 5.0 else "ELEVATED",
                            "moneyness": _moneyness(strike, current_price, opt_type),
                        })

        # Sort by V/OI ratio descending
        all_unusual.sort(key=lambda x: x["v_oi_ratio"], reverse=True)

        # Put/Call ratio
        pc_ratio = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None
        pc_oi_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None

        # Largest trades by notional
        largest = sorted(all_unusual, key=lambda x: x["notional"], reverse=True)[:5]

        result["available"] = True
        result["unusual_strikes"] = all_unusual[:15]  # Top 15
        result["put_call_ratio"] = pc_ratio
        result["put_call_oi_ratio"] = pc_oi_ratio
        result["total_call_volume"] = total_call_vol
        result["total_put_volume"] = total_put_vol
        result["total_call_oi"] = total_call_oi
        result["total_put_oi"] = total_put_oi
        result["current_price"] = round(current_price, 2)
        result["largest_trades"] = largest
        result["expiries_scanned"] = list(expirations[:3])

        # Skew signals
        if pc_ratio is not None:
            if pc_ratio > 1.5:
                result["skew_signal"] = "BEARISH (heavy put buying)"
            elif pc_ratio < 0.5:
                result["skew_signal"] = "BULLISH (heavy call buying)"
            else:
                result["skew_signal"] = "NEUTRAL"

    except Exception as exc:
        result["error"] = str(exc)
        logger.warning("Options data failed for %s: %s", ticker, exc)

    if result.get("available"):
        _cache_set(cache_key, result)
    return result


def _moneyness(strike: float, current: float, opt_type: str) -> str:
    """Classify option moneyness."""
    if current == 0:
        return "?"
    pct = (strike - current) / current * 100
    if opt_type == "CALL":
        if pct < -5:
            return "Deep ITM"
        elif pct < 0:
            return "ITM"
        elif pct < 2:
            return "ATM"
        elif pct < 10:
            return "OTM"
        else:
            return "Deep OTM"
    else:  # PUT
        if pct > 5:
            return "Deep ITM"
        elif pct > 0:
            return "ITM"
        elif pct > -2:
            return "ATM"
        elif pct > -10:
            return "OTM"
        else:
            return "Deep OTM"


# ---------------------------------------------------------------------------
# Portfolio reader
# ---------------------------------------------------------------------------

def get_portfolio_tickers() -> list[str]:
    """Read ticker symbols from portfolio account files."""
    if not ACCOUNTS_DIR.exists():
        return []

    tickers = set()
    for filepath in ACCOUNTS_DIR.glob("*.md"):
        content = filepath.read_text(encoding="utf-8")
        in_sold = False
        for line in content.split("\n"):
            # Track section headers — skip "Sold" sections
            if re.match(r"^#{1,4}\s+", line):
                in_sold = bool(re.search(r"[Ss]old", line))
                # Parse: ### TICKER — 100 shares ...
                hdr = re.match(
                    r"^#{1,4}\s+([A-Z]{1,5})\s+[—–-]\s+\d", line
                )
                if hdr and not in_sold:
                    tickers.add(hdr.group(1))
                continue

            if in_sold:
                continue

            # Table rows with ticker as first cell
            if line.startswith("|") and "---" not in line:
                cells = [cl.strip() for cl in line.split("|")[1:-1]]
                if cells and re.match(r"^[A-Z]{1,5}$", cells[0].strip("*").strip()):
                    first = cells[0].strip("*").strip()
                    if first.lower() not in (
                        "ticker", "option", "strike", "trade", "acquired",
                        "#", "detail",
                    ):
                        tickers.add(first)

    return sorted(tickers)


# ---------------------------------------------------------------------------
# Combined result + verdict
# ---------------------------------------------------------------------------

def generate_verdict(insider: dict, institutional: dict, options: dict) -> str:
    """Generate a summary verdict from all three data sources."""
    signals = []
    bullish = 0
    bearish = 0

    # Insider signals
    if insider.get("available"):
        summary = insider.get("summary", {})
        direction = summary.get("net_direction", "")
        if direction == "NET BUYING":
            bullish += 2
            signals.append("insider buying")
        elif direction == "NET SELLING":
            bearish += 1  # Selling less meaningful (could be planned)
            signals.append("insider selling")

        # Cluster buying is a strong signal
        for sig in insider.get("signals", []):
            if "CLUSTER BUYING" in sig:
                bullish += 3
            elif "C-SUITE BUYING" in sig:
                bullish += 2
            elif "LARGE BUY" in sig:
                bullish += 1
            elif "ALL SELLING" in sig:
                bearish += 1

    # Institutional signals
    if institutional.get("available"):
        if institutional.get("notable_holders"):
            bullish += 1
            signals.append("notable fund holders")
        inst_trans = institutional.get("inst_transaction_pct", "")
        if inst_trans:
            try:
                pct = float(inst_trans.replace("%", ""))
                if pct > 5:
                    bullish += 1
                    signals.append("institutional adding")
                elif pct < -5:
                    bearish += 1
                    signals.append("institutional reducing")
            except ValueError:
                pass

    # Options signals
    if options.get("available"):
        unusual = options.get("unusual_strikes", [])
        if unusual:
            calls_unusual = [u for u in unusual if u["type"] == "CALL"]
            puts_unusual = [u for u in unusual if u["type"] == "PUT"]
            if len(calls_unusual) > len(puts_unusual) * 2:
                bullish += 1
                signals.append("unusual call activity")
            elif len(puts_unusual) > len(calls_unusual) * 2:
                bearish += 1
                signals.append("unusual put activity")
            else:
                signals.append("unusual options activity (mixed)")

        skew = options.get("skew_signal", "")
        if "BULLISH" in skew:
            bullish += 1
        elif "BEARISH" in skew:
            bearish += 1

    # Generate verdict
    if bullish >= 4 and bearish <= 1:
        emoji = "🟢"
        label = "BULLISH"
        desc = "Strong smart money accumulation"
    elif bullish >= 2 and bearish <= 1:
        emoji = "🟢"
        label = "LEANING BULLISH"
        desc = ", ".join(signals) if signals else "Mild positive signals"
    elif bearish >= 3 and bullish <= 1:
        emoji = "🔴"
        label = "BEARISH"
        desc = "Smart money distribution"
    elif bearish >= 2 and bullish <= 1:
        emoji = "🔴"
        label = "LEANING BEARISH"
        desc = ", ".join(signals) if signals else "Mild negative signals"
    elif bullish > 0 or bearish > 0:
        emoji = "⚠️"
        label = "MIXED"
        desc = ", ".join(signals) if signals else "Conflicting signals"
    else:
        emoji = "⬜"
        label = "NO SIGNAL"
        desc = "Insufficient data"

    return f"{emoji} {label} — {desc}"


# ---------------------------------------------------------------------------
# Terminal formatting
# ---------------------------------------------------------------------------

def _fmt_value(val: float) -> str:
    """Format dollar value compactly."""
    if val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:,.0f}"


def _fmt_shares(shares: int | float) -> str:
    """Format share count with commas."""
    if isinstance(shares, float) and shares != int(shares):
        return f"{shares:,.1f}"
    return f"{int(shares):,}"


def format_terminal(ticker: str, insider: dict, institutional: dict,
                    options: dict, days: int) -> str:
    """Format all whale tracker data for terminal display."""
    width = 70
    lines = []

    lines.append("")
    lines.append(c("=" * width, BOLD))
    lines.append(c(f"  WHALE TRACKER — {ticker.upper()} ({days}-day lookback)", BOLD_CYAN))
    lines.append(c("=" * width, BOLD))

    # --- Insider Transactions ---
    lines.append("")
    lines.append(c("  INSIDER TRANSACTIONS:", BOLD_WHITE))
    lines.append(c("  " + "-" * (width - 4), DIM))

    if insider.get("available"):
        txns = insider.get("transactions", [])
        # Show open-market buys and sells (not exercises, grants, tax withholding)
        market_txns = [t for t in txns if t.get("code") in ("P", "S")]

        if market_txns:
            # Header
            lines.append(c(
                f"    {'Date':<12}{'Insider':<22}{'Title':<8}{'Type':<6}"
                f"{'Shares':>10}{'Value':>12}",
                DIM,
            ))
            for t in market_txns[:10]:
                date = t.get("date", "")[:10]
                name = (t.get("insider", "?"))[:20]
                title = (t.get("title", "?"))[:6]
                tx_type = "BUY" if t.get("code") == "P" else "SELL"
                shares = _fmt_shares(t.get("shares", 0))
                value = _fmt_value(t.get("value", 0))

                color = GREEN if t.get("code") == "P" else RED
                lines.append(c(
                    f"    {date:<12}{name:<22}{title:<8}{tx_type:<6}"
                    f"{shares:>10}{value:>12}",
                    color,
                ))
        else:
            lines.append(f"    No open-market buys or sells in {days} days.")
            other = [t for t in txns if t.get("code") not in ("P", "S")]
            if other:
                codes = {}
                for t in other:
                    code_name = t.get("type", t.get("code", "?"))
                    codes[code_name] = codes.get(code_name, 0) + 1
                detail = ", ".join(f"{v}x {k}" for k, v in codes.items())
                lines.append(c(f"    Other activity: {detail}", DIM))

        # Summary
        summary = insider.get("summary", {})
        buy_count = summary.get("buys", 0)
        sell_count = summary.get("sells", 0)
        buy_val = summary.get("buy_value", 0)
        sell_val = summary.get("sell_value", 0)
        direction = summary.get("net_direction", "?")

        lines.append("")
        summary_line = (
            f"    Summary: {buy_count} buys ({_fmt_value(buy_val)}), "
            f"{sell_count} sells ({_fmt_value(sell_val)})"
        )
        if direction in ("NET BUYING",):
            lines.append(c(f"{summary_line}. {direction}", BOLD_GREEN))
        elif direction in ("NET SELLING",):
            lines.append(c(f"{summary_line}. ⚠️ {direction}", BOLD_YELLOW))
        else:
            lines.append(f"{summary_line}. {direction}")

        # Signals
        for sig in insider.get("signals", []):
            if "CLUSTER" in sig or "C-SUITE" in sig:
                lines.append(c(f"    🟢 {sig}", BOLD_GREEN))
            elif "LARGE BUY" in sig:
                lines.append(c(f"    🟢 {sig}", GREEN))
            elif "ALL SELLING" in sig:
                lines.append(c(f"    🔴 {sig}", BOLD_RED))
            else:
                lines.append(c(f"    ⚠️ {sig}", YELLOW))
    else:
        error = insider.get("error", "Data unavailable")
        lines.append(c(f"    {error}", DIM))

    # --- Institutional Activity ---
    lines.append("")
    lines.append(c("  INSTITUTIONAL ACTIVITY:", BOLD_WHITE))
    lines.append(c("  " + "-" * (width - 4), DIM))

    if institutional.get("available"):
        top_holders = institutional.get("top_holders", [])
        if top_holders:
            # Top 5 holders
            top_line = "    Top Holders: " + ", ".join(
                f"{h['holder'][:25]} ({h['pct_out']:.1f}%)"
                for h in top_holders[:5]
            )
            lines.append(top_line)

        notable = institutional.get("notable_holders", [])
        if notable:
            notable_names = ", ".join(h["holder"][:25] for h in notable)
            lines.append(c(f"    Notable: {notable_names}", BOLD_GREEN))

        # Top mutual fund holders
        mf = institutional.get("top_mutual_funds", [])
        if mf:
            lines.append(c("    Top Fund Holders:", DIM))
            for fund in mf[:3]:
                lines.append(c(
                    f"      {fund['holder'][:40]} ({fund['pct_out']:.1f}%)",
                    DIM,
                ))

        inst_pct = institutional.get("inst_ownership_pct")
        if inst_pct is not None:
            lines.append(f"    Institutional Ownership: {inst_pct:.1f}%")

        inst_trans = institutional.get("inst_transaction_pct", "")
        if inst_trans:
            lines.append(f"    Institutional Net Transaction: {inst_trans}")
    else:
        error = institutional.get("error", "Data unavailable")
        lines.append(c(f"    {error}", DIM))

    # --- Unusual Options ---
    lines.append("")
    lines.append(c("  UNUSUAL OPTIONS:", BOLD_WHITE))
    lines.append(c("  " + "-" * (width - 4), DIM))

    if options.get("available"):
        unusual = options.get("unusual_strikes", [])
        if unusual:
            lines.append(c(
                f"    {'Strike':>8}  {'Expiry':<12}{'Type':<6}"
                f"{'Volume':>8}{'OI':>8}{'V/OI':>7}  {'Signal':<10}{'Moneyness':<12}",
                DIM,
            ))
            for u in unusual[:10]:
                strike = f"${u['strike']:.0f}" if u['strike'] >= 10 else f"${u['strike']:.1f}"
                vol = f"{u['volume']:,}"
                oi = f"{u['open_interest']:,}"
                v_oi = f"{u['v_oi_ratio']:.1f}x"
                signal = u["signal"]
                moneyness = u.get("moneyness", "")

                sig_color = BOLD_RED if signal == "UNUSUAL" else YELLOW
                type_color = GREEN if u["type"] == "CALL" else RED

                # Build line without ANSI-inside-format-spec (ANSI codes break width)
                type_str = c(f"{u['type']:<6}", type_color)
                signal_str = c(f"{signal:<10}", sig_color)
                moneyness_str = c(moneyness, DIM)

                lines.append(
                    f"    {strike:>8}  {u['expiry']:<12}{type_str}"
                    f"{vol:>8}{oi:>8}{v_oi:>7}  {signal_str}{moneyness_str}"
                )
        else:
            lines.append("    No unusual volume/OI detected in nearest 3 expiries.")

        # Put/Call ratio
        pc = options.get("put_call_ratio")
        if pc is not None:
            if pc > 1.5:
                pc_label = c(f"{pc:.2f} (bearish skew)", BOLD_RED)
            elif pc < 0.5:
                pc_label = c(f"{pc:.2f} (bullish skew)", BOLD_GREEN)
            else:
                pc_label = f"{pc:.2f} (neutral)"
            lines.append(f"    Put/Call volume ratio: {pc_label}")

        pc_oi = options.get("put_call_oi_ratio")
        if pc_oi is not None:
            lines.append(c(f"    Put/Call OI ratio: {pc_oi:.2f}", DIM))

        # Largest trade
        largest = options.get("largest_trades", [])
        if largest:
            big = largest[0]
            lines.append(
                f"    Largest: {big['volume']:,}x ${big['strike']:.0f}"
                f"{big['type'][0]} {big['expiry']} "
                f"@ ${big['last_price']:.2f} ({_fmt_value(big['notional'])} notional)"
            )

        skew = options.get("skew_signal", "")
        if skew:
            skew_color = BOLD_GREEN if "BULLISH" in skew else BOLD_RED if "BEARISH" in skew else DIM
            lines.append(f"    Skew signal: {c(skew, skew_color)}")
    else:
        error = options.get("error", "Data unavailable")
        lines.append(c(f"    {error}", DIM))

    # --- Verdict ---
    verdict = generate_verdict(insider, institutional, options)
    lines.append("")
    lines.append(c(f"  VERDICT: {verdict}", BOLD))
    lines.append(c("=" * width, BOLD))
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_ticker(ticker: str, days: int = 30,
               insider_only: bool = False,
               options_only: bool = False) -> dict:
    """Run whale tracker for a single ticker. Returns combined result dict."""
    ticker = ticker.upper()

    insider = {}
    institutional = {}
    options = {}

    fetch_all = not insider_only and not options_only

    if fetch_all or insider_only:
        insider = fetch_insider_transactions(ticker, days=days)
        time.sleep(0.2)  # Rate limit between sources

    if fetch_all:
        institutional = fetch_institutional_holders(ticker)
        time.sleep(0.2)

    if fetch_all or options_only:
        options = fetch_unusual_options(ticker)

    verdict = generate_verdict(insider, institutional, options)

    return {
        "ticker": ticker,
        "lookback_days": days,
        "timestamp": datetime.now().isoformat(),
        "insider": insider,
        "institutional": institutional,
        "options": options,
        "verdict": verdict,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Track institutional activity, insider transactions, and unusual options"
    )
    parser.add_argument(
        "tickers", nargs="*",
        help="Ticker symbol(s) to track",
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Lookback period in days (default: 30)",
    )
    parser.add_argument(
        "--portfolio", action="store_true",
        help="Track all held positions from portfolio accounts",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--insider-only", action="store_true",
        help="Only fetch insider transaction data",
    )
    parser.add_argument(
        "--options-only", action="store_true",
        help="Only fetch unusual options data",
    )
    args = parser.parse_args()

    tickers = list(args.tickers) if args.tickers else []

    if args.portfolio:
        portfolio_tickers = get_portfolio_tickers()
        if not portfolio_tickers:
            print("No portfolio tickers found. Check portfolio/accounts/ files.", file=sys.stderr)
            sys.exit(1)
        tickers.extend(portfolio_tickers)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tickers:
            t_upper = t.upper()
            if t_upper not in seen:
                seen.add(t_upper)
                unique.append(t_upper)
        tickers = unique

    if not tickers:
        parser.print_help()
        sys.exit(1)

    results = []
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(0.5)  # Rate limit between tickers
        result = run_ticker(
            ticker,
            days=args.days,
            insider_only=args.insider_only,
            options_only=args.options_only,
        )
        results.append(result)

    if args.json:
        output = results if len(results) > 1 else results[0]
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    else:
        for result in results:
            print(format_terminal(
                result["ticker"],
                result.get("insider", {}),
                result.get("institutional", {}),
                result.get("options", {}),
                args.days,
            ))


if __name__ == "__main__":
    main()
