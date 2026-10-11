#!/usr/bin/env python3
"""
crypto-cycle.py — Bitcoin on-chain cycle dashboard.

Fetches on-chain metrics from BGeometrics free API and displays a cycle
dashboard with MVRV, NUPL, realized price, and composite cycle score.

Usage:
    python3 scripts/crypto-cycle.py              # terminal dashboard
    python3 scripts/crypto-cycle.py --json        # JSON output
    python3 scripts/crypto-cycle.py --save        # save to knowledge file

Data source: BGeometrics (https://bitcoin-data.com)
Free tier: 10 requests/hour, 15/day — no API key needed.

Note: The script batches all metrics into minimal API calls. If you hit
rate limits, wait an hour or register for a free API key at bitcoin-data.com
and set BGEOMETRICS_TOKEN env var.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = "https://api.bgeometrics.com/v1"
TIMEOUT = 15

# Cycle interpretation tables
MVRV_ZONES = [
    (7.0, float("inf"), "Extreme Overvaluation", "SELL — cycle top zone", "🔴"),
    (3.0, 7.0, "Overheated", "Distribution likely — trim positions", "🟠"),
    (1.0, 3.0, "Fair to Moderate", "Markup phase — hold/accumulate", "🟢"),
    (0.0, 1.0, "Fair Value", "Accumulation or early recovery", "🟡"),
    (float("-inf"), 0.0, "Undervalued", "Cycle bottom zone — BUY aggressively", "🔵"),
]

NUPL_ZONES = [
    (0.75, float("inf"), "Euphoria/Greed", "Cycle top — sell", "🔴"),
    (0.50, 0.75, "Belief/Optimism", "Bull run — hold", "🟢"),
    (0.25, 0.50, "Hope/Fear", "Early recovery or early decline", "🟡"),
    (0.0, 0.25, "Anxiety", "Bearish — approaching capitulation", "🟠"),
    (float("-inf"), 0.0, "Capitulation", "Cycle bottom — BUY", "🔵"),
]

CYCLE_SIGNALS = {
    "Extreme Opportunity": ("🔵", "Maximum buy zone — rare"),
    "Opportunity": ("🟢", "Good accumulation zone"),
    "Neutral": ("🟡", "Fair value — hold or small DCA"),
    "Caution": ("🟠", "Getting expensive — reduce buying"),
    "Danger": ("🔴", "Cycle top approaching — take profits"),
}


def fetch_metric(endpoint: str, token: str | None = None) -> list[dict]:
    """Fetch a metric from BGeometrics API."""
    url = f"{BASE_URL}/{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        if e.code == 429:
            print(f"⚠️  Rate limited on /{endpoint}. Free tier: 10 req/hour.")
            print("   Wait an hour or set BGEOMETRICS_TOKEN env var.")
            return []
        raise


def get_latest(data: list[dict]) -> dict | None:
    """Get the most recent entry from a list sorted by date."""
    if not data:
        return None
    # Data may be sorted ascending — get the last entry
    return data[-1]


def classify_mvrv(value: float) -> tuple[str, str, str]:
    """Classify MVRV into zone, action, and emoji."""
    for low, high, zone, action, emoji in MVRV_ZONES:
        if low <= value < high:
            return zone, action, emoji
    return "Unknown", "", "❓"


def classify_nupl(value: float) -> tuple[str, str, str]:
    """Classify NUPL into zone, action, and emoji."""
    for low, high, zone, action, emoji in NUPL_ZONES:
        if low <= value < high:
            return zone, action, emoji
    return "Unknown", "", "❓"


def format_dashboard(metrics: dict) -> str:
    """Format metrics into a readable terminal dashboard."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  BITCOIN ON-CHAIN CYCLE DASHBOARD — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("=" * 70)
    lines.append("")

    # BTC Price
    if metrics.get("price"):
        lines.append(f"  BTC Price:        ${metrics['price']:,.0f}")
        if metrics.get("realized_price"):
            lines.append(f"  Realized Price:   ${metrics['realized_price']:,.0f}")
            premium = ((metrics['price'] / metrics['realized_price']) - 1) * 100
            lines.append(f"  Premium/Discount: {premium:+.1f}% vs realized")
        else:
            lines.append("  Realized Price:   unavailable (API rate limit or missing data)")
        lines.append("")

    # MVRV
    if metrics.get("mvrv") is not None:
        zone, action, emoji = classify_mvrv(metrics["mvrv"])
        lines.append(f"  {emoji} MVRV Z-Score:   {metrics['mvrv']:.2f}  [{zone}]")
        lines.append(f"     → {action}")

    # NUPL
    if metrics.get("nupl") is not None:
        zone, action, emoji = classify_nupl(metrics["nupl"])
        lines.append(f"  {emoji} NUPL:           {metrics['nupl']:.4f}  [{zone}]")
        lines.append(f"     → {action}")

    # Composite Cycle Score
    if metrics.get("composite_score") is not None:
        signal = metrics.get("signal", "Unknown")
        sig_emoji, sig_desc = CYCLE_SIGNALS.get(signal, ("❓", ""))
        lines.append(f"  {sig_emoji} Cycle Score:    {metrics['composite_score']:.2f}/10  [{signal}]")
        lines.append(f"     → {sig_desc}")

    # Sub-scores
    if metrics.get("sub_scores"):
        lines.append("")
        lines.append("  Component Scores (0-10):")
        for name, score in metrics["sub_scores"].items():
            bar = "█" * int(score) + "░" * (10 - int(score))
            lines.append(f"    {name:<20s} {bar} {score:.1f}")

    lines.append("")

    # Cycle context
    lines.append("-" * 70)
    lines.append("  CYCLE CONTEXT")
    lines.append("-" * 70)
    lines.append(f"  Last halving:     April 2024 (4th)")
    lines.append(f"  Months since:     ~{((datetime.now() - datetime(2024, 4, 20)).days / 30):.0f} months")
    lines.append(f"  Cycle ATH:        $126,000 (Oct 6, 2025)")
    if metrics.get("price"):
        drawdown = ((metrics["price"] / 126000) - 1) * 100
        lines.append(f"  Drawdown from ATH: {drawdown:.1f}%")

    # Historical comparison
    lines.append("")
    lines.append("  Historical Cycle Peaks (MVRV at top):")
    lines.append("    2013: MVRV ~8.0  |  2017: MVRV ~5.0  |  2021: MVRV ~3.5")
    if metrics.get("mvrv") is not None:
        lines.append(f"    2025: MVRV peaked at ~2.5  |  Now: {metrics['mvrv']:.2f}")
        lines.append(f"    → Each cycle peaks at a LOWER MVRV — diminishing returns")

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  Data: {metrics.get('date', 'N/A')} | Source: BGeometrics (bitcoin-data.com)")
    lines.append("=" * 70)

    return "\n".join(lines)


def format_markdown(metrics: dict) -> str:
    """Format metrics as markdown for the knowledge base."""
    date = metrics.get("date", datetime.now().strftime("%Y-%m-%d"))

    mvrv_zone = classify_mvrv(metrics.get("mvrv", 0))[0] if metrics.get("mvrv") is not None else "N/A"
    nupl_zone = classify_nupl(metrics.get("nupl", 0))[0] if metrics.get("nupl") is not None else "N/A"
    signal = metrics.get("signal", "N/A")

    lines = [
        f"## Current Cycle Dashboard (Updated {date})",
        "",
        "| Indicator | Reading | Zone | Signal |",
        "|-----------|---------|------|--------|",
    ]

    if metrics.get("mvrv") is not None:
        lines.append(f"| MVRV Z-Score | {metrics['mvrv']:.2f} | {mvrv_zone} | {classify_mvrv(metrics['mvrv'])[1]} |")
    if metrics.get("nupl") is not None:
        lines.append(f"| NUPL | {metrics['nupl']:.4f} | {nupl_zone} | {classify_nupl(metrics['nupl'])[1]} |")
    if metrics.get("composite_score") is not None:
        lines.append(f"| Cycle Composite | {metrics['composite_score']:.2f}/10 | {signal} | {CYCLE_SIGNALS.get(signal, ('', ''))[1]} |")
    if metrics.get("realized_price"):
        lines.append(f"| Realized Price | ${metrics['realized_price']:,.0f} | — | BTC cost basis of all holders |")
    if metrics.get("price"):
        premium = ((metrics['price'] / metrics['realized_price']) - 1) * 100
        lines.append(f"| BTC Price | ${metrics['price']:,.0f} | — | {premium:+.1f}% vs realized price |")

    if metrics.get("sub_scores"):
        lines.append("")
        lines.append("**Component Scores (0-10):**")
        lines.append("")
        lines.append("| Component | Score |")
        lines.append("|-----------|-------|")
        for name, score in metrics["sub_scores"].items():
            lines.append(f"| {name} | {score:.1f} |")

    lines.append("")
    lines.append(f"*Source: BGeometrics (bitcoin-data.com) | Updated: {date}*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Bitcoin on-chain cycle dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--save", action="store_true",
                        help="Update the cycle dashboard in knowledge/frameworks/crypto-cycles.md")
    args = parser.parse_args()

    token = os.environ.get("BGEOMETRICS_TOKEN")

    metrics = {"date": datetime.now().strftime("%Y-%m-%d")}

    # Fetch cycle-extreme first — it's the most data-rich endpoint (1 call)
    print("Fetching cycle composite...", file=sys.stderr)
    cycle_data = fetch_metric("cycle-extreme", token)
    if cycle_data:
        latest = get_latest(cycle_data)
        if latest:
            metrics["price"] = latest.get("priceUsd")
            metrics["composite_score"] = latest.get("compositeScore")
            metrics["signal"] = latest.get("signal")
            metrics["date"] = latest.get("d", metrics["date"])
            metrics["sub_scores"] = {
                "MVRV Z-Score": latest.get("scoreMvrvZscore", 0),
                "Puell Multiple": latest.get("scorePuell", 0),
                "Reserve Risk": latest.get("scoreReserveRisk", 0),
                "S2F Deviation": latest.get("scoreS2fDev", 0),
                "Power Law": latest.get("scorePowerLaw", 0),
                "Rainbow": latest.get("scoreRainbow", 0),
                "LTH MVRV": latest.get("scoreLthMvrv", 0),
            }

    # Fetch MVRV (1 call)
    print("Fetching MVRV...", file=sys.stderr)
    mvrv_data = fetch_metric("mvrv", token)
    if mvrv_data:
        latest = get_latest(mvrv_data)
        if latest:
            metrics["mvrv"] = latest.get("mvrv")

    # Fetch NUPL (1 call)
    print("Fetching NUPL...", file=sys.stderr)
    nupl_data = fetch_metric("nupl", token)
    if nupl_data:
        latest = get_latest(nupl_data)
        if latest:
            metrics["nupl"] = latest.get("nupl")

    # Fetch Realized Price (1 call)
    print("Fetching realized price...", file=sys.stderr)
    rp_data = fetch_metric("realized-price", token)
    if rp_data:
        latest = get_latest(rp_data)
        if latest:
            metrics["realized_price"] = latest.get("realizedPrice")

    # Total: 4 API calls (within free tier of 10/hour)

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    # Terminal dashboard
    print(format_dashboard(metrics))

    # Save to knowledge file
    if args.save:
        kb_path = Path(__file__).parent.parent / "knowledge" / "frameworks" / "crypto-cycles.md"
        if kb_path.exists():
            content = kb_path.read_text()
            md = format_markdown(metrics)

            # Replace existing dashboard section
            marker_start = "## Current Cycle Dashboard"
            marker_end = "\n## How to Use This Framework"

            if marker_start in content:
                start_idx = content.index(marker_start)
                end_idx = content.index(marker_end) if marker_end in content else len(content)
                updated = content[:start_idx] + md + "\n\n" + content[end_idx:]
                kb_path.write_text(updated)
                print(f"\nDashboard saved to {kb_path}", file=sys.stderr)
            else:
                print(f"\n⚠️  Could not find '{marker_start}' section in {kb_path}", file=sys.stderr)
        else:
            print(f"\n⚠️  Knowledge file not found: {kb_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
