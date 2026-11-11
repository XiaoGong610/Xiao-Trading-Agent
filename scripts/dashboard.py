#!/usr/bin/env python3
"""
Unified dashboard — portfolio + watchlist in one interactive HTML.

Combines portfolio account data with watchlist classified stock data to generate
a multi-tab HTML dashboard with: Portfolio Overview, RSI vs P/E, Earnings Calendar,
and cross-account Holdings table.

Usage:
    .venv/bin/python3 scripts/dashboard.py                    # auto-runs watchlist.py
    .venv/bin/python3 scripts/watchlist.py --json | .venv/bin/python3 scripts/dashboard.py
    .venv/bin/python3 scripts/dashboard.py --no-open          # don't open browser

Output: research/stocks/0-watchlist-dashboard-YYYY-MM-DD.html
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# Import shared functions from watchlist.py
sys.path.insert(0, str(Path(__file__).parent))
from watchlist import (
    parse_frontmatter,
    parse_portfolio_holdings,
    ACCOUNT_ABBREV,
    ACCOUNTS_DIR,
    SECTOR_TO_GICS,
)

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# --- Paths ---
OUTPUT_PATH = Path("research/stocks") / f"0-watchlist-dashboard-{date.today().isoformat()}.html"

# --- Colors ---
SECTOR_COLORS = {
    "Technology": "#1f77b4",
    "Healthcare": "#2ca02c",
    "Financials": "#ff7f0e",
    "Consumer Disc.": "#d62728",
    "Consumer Staples": "#9467bd",
    "Energy": "#8c564b",
    "Industrials": "#e377c2",
    "Materials": "#7f7f7f",
    "Real Estate": "#bcbd22",
    "Utilities": "#17becf",
    "Communication": "#aec7e8",
    "Other": "#888888",
}

ACCOUNT_COLORS = {
    "BROKERAGELINK": "#58a6ff",
    "ROTH IRA": "#3fb950",
    "HOLD": "#d29922",
    "THETAGANG": "#bc8cff",
    "GOBIG": "#f85149",
}

# Full display names for portfolio overview
ACCOUNT_DISPLAY = {
    'BROKERAGELINK': 'BrokerageLink (401k)',
    'ROTH IRA': 'Roth IRA',
    'HOLD': 'Hold (Covered Calls)',
    'THETAGANG': 'ThetaGang',
    'GOBIG': 'GoBig (LEAPs)',
}


# --- Data loading ---

def load_watchlist_json() -> list[dict]:
    """Load watchlist data from stdin or by running watchlist.py --json."""
    # Try stdin first (when piped from watchlist.py)
    if not sys.stdin.isatty():
        try:
            data = sys.stdin.read()
            if data.strip():
                return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # Fall back to running watchlist.py --json
    print("Running watchlist.py --json...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "watchlist.py"),
         "--json", "--no-save"],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        print(f"  watchlist.py failed: {result.stderr[:200]}", file=sys.stderr)
        return []
    return json.loads(result.stdout)


def load_account_summaries() -> list[dict]:
    """Load account-level summaries from frontmatter."""
    if not ACCOUNTS_DIR.exists():
        return []
    accounts = []
    for f in sorted(ACCOUNTS_DIR.glob("*.md")):
        fm = parse_frontmatter(f)
        if fm.get('account_name'):
            accounts.append({
                'name': fm['account_name'],
                'total_value': float(fm.get('total_value', 0)),
                'cash': float(fm.get('cash', 0)),
                'strategy': fm.get('strategy', ''),
                'last_updated': fm.get('last_updated', ''),
            })
    return accounts


def build_sector_map(watchlist: list[dict]) -> dict[str, str]:
    """Build {TICKER: GICS_sector} from watchlist data + research files."""
    sector_map: dict[str, str] = {}

    for s in watchlist:
        ticker = s.get('ticker')
        sector = s.get('sector', '')
        if ticker and sector:
            gics = SECTOR_TO_GICS.get(sector)
            if gics:
                sector_map[ticker] = gics

    stocks_dir = Path("research/stocks")
    if stocks_dir.exists():
        for f in stocks_dir.glob("*.md"):
            if f.name.startswith(('0-', '1-')):
                continue
            fm = parse_frontmatter(f)
            ticker = fm.get('ticker')
            if ticker and ticker not in sector_map:
                gics = SECTOR_TO_GICS.get(fm.get('sector', ''))
                if gics:
                    sector_map[ticker] = gics

    return sector_map


# --- Tab 1: Portfolio Overview ---

def _build_overview(accounts, holdings, sector_map, date_str):
    """Portfolio Overview — donut charts, metric cards, account bars."""
    total_value = sum(a['total_value'] for a in accounts)
    total_cash = sum(a['cash'] for a in accounts)

    # Aggregate position values by ticker
    stock_values: dict[str, float] = {}
    for ticker, positions in holdings.items():
        total = sum(p.get('value') or 0 for p in positions)
        if total > 0:
            stock_values[ticker] = total

    # --- Donut by stock ---
    sorted_stocks = sorted(stock_values.items(), key=lambda x: -x[1])
    top_n = 12
    top_stocks = sorted_stocks[:top_n]
    other_value = sum(v for _, v in sorted_stocks[top_n:])

    stock_labels = [t for t, _ in top_stocks]
    stock_vals = [v for _, v in top_stocks]
    if other_value > 0:
        stock_labels.append("Other")
        stock_vals.append(other_value)
    if total_cash > 0:
        stock_labels.append("Cash")
        stock_vals.append(total_cash)
    # Reconcile to the account totals: pending settlements, short options and option
    # rows not parsed as positions. Keeps the pies on the same base as the topline.
    unparsed = total_value - sum(stock_values.values()) - total_cash
    if unparsed > 0:
        stock_labels.append("Pending & options")
        stock_vals.append(unparsed)

    stock_fig = go.Figure(data=[go.Pie(
        labels=stock_labels, values=stock_vals,
        hole=0.45, textinfo='label+percent', textposition='inside',
        hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>',
        sort=False,
        marker=dict(line=dict(color='#0d1117', width=2)),
    )])
    stock_fig.update_layout(
        title=dict(text="By Stock", font=dict(size=16, color='#e6edf3')),
        height=400, margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor='#161b22', font=dict(color='#e6edf3'),
        legend=dict(font=dict(size=11, color='#8b949e'), bgcolor='rgba(0,0,0,0)'),
    )

    # --- Donut by sector ---
    sector_values: dict[str, float] = {}
    for ticker, value in stock_values.items():
        sector = sector_map.get(ticker, 'Other')
        sector_values[sector] = sector_values.get(sector, 0) + value
    if total_cash > 0:
        sector_values['Cash'] = total_cash
    if unparsed > 0:
        sector_values['Pending & options'] = unparsed

    sorted_sectors = sorted(sector_values.items(), key=lambda x: -x[1])
    sector_labels = [s for s, _ in sorted_sectors]
    sector_vals = [v for _, v in sorted_sectors]
    sector_colors = [SECTOR_COLORS.get(s, '#888') if s not in ('Cash', 'Pending & options') else '#4a4a4a'
                     for s in sector_labels]

    sector_fig = go.Figure(data=[go.Pie(
        labels=sector_labels, values=sector_vals,
        hole=0.45, textinfo='label+percent', textposition='inside',
        hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>',
        sort=False,
        marker=dict(colors=sector_colors, line=dict(color='#0d1117', width=2)),
    )])
    sector_fig.update_layout(
        title=dict(text="By Sector", font=dict(size=16, color='#e6edf3')),
        height=400, margin=dict(t=50, b=20, l=20, r=20),
        paper_bgcolor='#161b22', font=dict(color='#e6edf3'),
        legend=dict(font=dict(size=11, color='#8b949e'), bgcolor='rgba(0,0,0,0)'),
    )

    stock_html = stock_fig.to_html(include_plotlyjs=False, full_html=False, div_id="pie-stock")
    sector_html = sector_fig.to_html(include_plotlyjs=False, full_html=False, div_id="pie-sector")

    # --- Account bars ---
    max_account = max((acc['total_value'] for acc in accounts), default=0)
    account_bars = ""
    for a in sorted(accounts, key=lambda x: -x['total_value']):
        pct = (a['total_value'] / total_value * 100) if total_value > 0 else 0
        display_name = ACCOUNT_DISPLAY.get(a['name'], a['name'])
        color = ACCOUNT_COLORS.get(a['name'], '#888')
        cash_pct = (a['cash'] / a['total_value'] * 100) if a['total_value'] > 0 else 0
        # Bar length = account value relative to the largest account (largest = full width),
        # split into invested (solid) and cash (light) segments
        scale = a['total_value'] / max_account * 100 if max_account > 0 else 0
        cash_w = scale * cash_pct / 100
        account_bars += (
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">'
            f'<div style="width:160px;color:#8b949e;font-size:13px;text-align:right;">{display_name}</div>'
            f'<div style="flex:1;height:28px;position:relative;display:flex;">'
            f'<div style="width:{scale - cash_w}%;background:{color};height:100%;'
            f'border-radius:4px 0 0 4px;opacity:0.85;"></div>'
            f'<div style="width:{cash_w}%;background:{color};height:100%;'
            f'border-radius:0 4px 4px 0;opacity:0.3;"></div>'
            f'<div style="position:absolute;top:5px;left:8px;font-size:12px;font-weight:600;">'
            f'${a["total_value"]/1000:.0f}K · {pct:.1f}% of total</div>'
            f'</div>'
            f'<div style="width:80px;color:#8b949e;font-size:12px;">cash {cash_pct:.0f}%</div>'
            f'</div>'
        )

    n_positions = len(stock_values)
    last_updated = max((a['last_updated'] for a in accounts if a['last_updated']), default='—')

    return f"""
    <div class="metrics">
      <div class="metric">
        <div class="label">Total Portfolio</div>
        <div class="value" style="color:#3fb950">${total_value/1000:.0f}K</div>
      </div>
      <div class="metric">
        <div class="label">Total Cash</div>
        <div class="value">${total_cash/1000:.0f}K <span style="font-size:14px;color:#8b949e">({total_cash/total_value*100:.1f}%)</span></div>
      </div>
      <div class="metric">
        <div class="label">Positions</div>
        <div class="value">{n_positions}</div>
      </div>
      <div class="metric">
        <div class="label">Last Updated</div>
        <div class="value" style="font-size:18px;">{last_updated}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
      <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px;">
        {stock_html}
      </div>
      <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px;">
        {sector_html}
      </div>
    </div>
    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;">
      <div style="font-size:14px;font-weight:600;margin-bottom:4px;">Account Breakdown</div>
      <div style="font-size:11px;color:#8b949e;margin-bottom:12px;">Bar length = account value (largest account = full width) · solid = invested · light = cash</div>
      {account_bars}
    </div>
    """


# --- Tab 2: RSI vs P/E Scatter ---

# --- Opportunity Map (replaces the old RSI vs P/E scatter) ---

_SECTOR_ALIASES = {'Consumer Disc.': 'Consumer Discretionary', 'Communication': 'Communication Services'}


def _trend_svg(px, sma, hi_idx, above_200, w=250, h=60):
    """Larger 1-year trend chart for the opportunity card."""
    if not px or len(px) < 2:
        return '<div style="color:#484f58;font-size:12px;">No price history</div>'
    vals = px + [v for v in (sma or []) if v is not None]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    n = len(px)
    X = lambda i: i * w / (n - 1)
    Y = lambda v: h - 2 - (v - lo) / span * (h - 4)
    color = '#3fb950' if above_200 else '#f85149' if above_200 is False else '#8b949e'
    price = ' '.join(f'{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(px))
    sma_pts = ' '.join(f'{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(sma or []) if v is not None)
    dot = (f'<circle cx="{X(hi_idx):.1f}" cy="{Y(px[hi_idx]):.1f}" r="3" fill="#e6edf3"/>'
           if hi_idx is not None and 0 <= hi_idx < n else '')
    return (f'<svg width="{w}" height="{h}">'
            f'<polyline fill="none" stroke="#8b949e" stroke-width="1" stroke-dasharray="4,3" points="{sma_pts}"/>'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{price}"/>{dot}</svg>')


def _build_opportunity_map(stocks, sector_map, date_str):
    """RSI (x) vs valuation relative to the sector band (y); color = trend, shape = held/watchlist,
    size = conviction. Hover or click a point to see its card with the 1-year trend chart."""
    import json as _json
    import math
    pts = []
    placed = []   # (x, y) of labels already placed, to avoid overlaps

    def _label_pos(x, y):
        options = ['top center', 'bottom center', 'middle right', 'middle left']
        crowd = sum(1 for px, py in placed if abs(px - x) < 4 and abs(py - y) < 0.18)
        placed.append((x, y))
        return options[crowd % len(options)]
    for st in stocks:
        rsi, pe = st.get('rsi'), st.get('fwd_pe')
        if rsi is None or pe is None:
            continue
        sector = sector_map.get(st['ticker'], 'Other')
        cheap, rich = PE_BANDS.get(_SECTOR_ALIASES.get(sector, sector), (15, 35))
        val = (pe - cheap) / ((rich - cheap) or 1)          # 0 = cheap line, 1 = rich line
        y = val if val <= 1.5 else 1.5 + math.log1p(val - 1.5) * 0.5   # compress the rich tail
        pts.append((st, max(-0.6, y), val, cheap, rich, sector))

    held_pts = [p for p in pts if p[0].get('held_in')]
    watch_pts = [p for p in pts if not p[0].get('held_in')]
    cards = []

    def _trace(group, name, symbol):
        xs, ys, colors, sizes, texts, idx, tpos = [], [], [], [], [], [], []
        for st, y, val, cheap, rich, sector in group:
            above = st.get('above_sma200')
            conv = st.get('conviction')
            xs.append(st['rsi']); ys.append(y); texts.append(st['ticker'])
            tpos.append(_label_pos(st['rsi'], y))
            colors.append('#3fb950' if above else '#f85149' if above is False else '#8b949e')
            sizes.append(8 + 2.2 * float(conv or 4))
            label = 'cheap' if val < 0 else 'rich' if val > 1 else 'fair'
            v200 = st.get('pct_vs_sma200'); off = st.get('pct_off_high')
            ed = st.get('earnings_days')
            earn_txt = (f' · <b style="color:#d29922">earnings in {ed}d</b>'
                        if ed is not None and 0 <= ed <= 14 else '')
            card = (
                f'<div style="font-size:18px;font-weight:700;color:#e6edf3;">{st["ticker"]} '
                f'<span style="font-size:12px;font-weight:400;color:#8b949e;">{sector} · {"held" if st.get("held_in") else "watchlist"}</span></div>'
                f'<div style="margin:6px 0 10px;font-size:13px;color:#c9d1d9;">'
                f'Price <b>${(st.get("price") or 0):,.2f}</b> · Conv <b>{conv if conv is not None else "—"}</b> · '
                f'RSI <b>{st["rsi"]:.0f}</b><br>'
                f'Fwd P/E <b>{st["fwd_pe"]:.1f}x</b> ({label}; sector band {cheap}–{rich}x)<br>'
                f'vs 200D <b>{"—" if v200 is None else f"{v200:+.0f}%"}</b> · Off high <b>{"—" if off is None else f"{off:+.0f}%"}</b>'
                f'{earn_txt}'
                f'</div>{_trend_svg(st.get("trend_px"), st.get("trend_sma"), st.get("trend_hi_idx"), above)}'
                f'<div style="font-size:11px;color:#8b949e;margin-top:4px;">1-year price · dashed = 200-day avg · dot = 52-week high</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:8px;">{(st.get("thesis") or "")[:260]}</div>')
            idx.append(len(cards)); cards.append(card)
        return go.Scatter(
            x=xs, y=ys, mode='markers+text', name=name, text=texts, textposition=tpos,
            textfont=dict(size=10, color='#c9d1d9'), customdata=idx,
            marker=dict(symbol=symbol, size=sizes, color=colors, opacity=0.85,
                        line=dict(width=1.5 if symbol == 'circle' else 1, color='#e6edf3')),
            hovertemplate='<b>%{text}</b><extra></extra>')

    fig = go.Figure([_trace(held_pts, 'Held', 'circle'), _trace(watch_pts, 'Watchlist', 'diamond')])
    for y, lbl in ((0, 'cheap line'), (1, 'rich line')):
        fig.add_hline(y=y, line_dash='dash', line_color='#484f58', annotation_text=lbl,
                      annotation_position='right', annotation_font=dict(color='#8b949e', size=10))
    for x in (30, 70):
        fig.add_vline(x=x, line_dash='dot', line_color='#484f58')
    fig.add_annotation(x=11, y=-0.72, text='CHEAP + OVERSOLD → buy candidates if green', showarrow=False,
                       font=dict(color='#3fb950', size=10), xanchor='left', yanchor='bottom')
    fig.add_annotation(x=84, y=max([2.0] + [p[1] for p in pts]) + 0.2, text='RICH + OVERBOUGHT → trim / avoid', showarrow=False,
                       font=dict(color='#f85149', size=10), xanchor='right', yanchor='top')
    fig.update_layout(
        title=None,
        xaxis=dict(title='RSI (14) — oversold ← → overbought', range=[10, 85], gridcolor='#21262d'),
        yaxis=dict(title='Valuation vs sector (0 = cheap line, 1 = rich line; top compressed)',
                   range=[-0.75, max([2.0] + [p[1] for p in pts]) + 0.25],
                   gridcolor='#21262d', zeroline=False),
        height=660, margin=dict(t=60, l=60, r=20, b=60),
        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117', font=dict(color='white'),
        legend=dict(orientation='h', y=1.06, x=1, xanchor='right', yanchor='bottom'),
        updatemenus=[dict(type='buttons', direction='right', x=0, y=1.06, xanchor='left', yanchor='bottom',
                          bgcolor='#21262d', font=dict(color='#c9d1d9', size=11),
                          buttons=[dict(label='All', method='restyle', args=['visible', [True, True]]),
                                   dict(label='Watchlist only', method='restyle', args=['visible', [False, True]]),
                                   dict(label='Held only', method='restyle', args=['visible', [True, False]])])])
    plot = fig.to_html(include_plotlyjs=False, full_html=False, div_id='oppmap')
    return (
        '<div style="font-size:12px;color:#8b949e;margin-bottom:6px;">'
        f'<b style="color:#e6edf3;">Opportunity Map · {date_str}</b> &nbsp;·&nbsp; '
        '<b style="color:#e6edf3;">Color = trend:</b> '
        '<span style="color:#3fb950;">● above 200-day (uptrend)</span> &nbsp; '
        '<span style="color:#f85149;">● below 200-day (downtrend)</span> &nbsp; '
        '<span style="color:#8b949e;">● no data</span> &nbsp;·&nbsp; '
        '<b style="color:#e6edf3;">Shape:</b> ● held &nbsp;◆ watchlist &nbsp;·&nbsp; '
        '<b style="color:#e6edf3;">Size:</b> conviction</div>'
        '<div style="display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px;align-items:start;">'
        f'<div>{plot}</div>'
        '<div id="opp-card" style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;'
        'position:sticky;top:12px;min-height:200px;color:#8b949e;font-size:13px;box-sizing:border-box;'
        'width:280px;overflow-wrap:anywhere;overflow:hidden;">'
        'Hover or click a stock to see its card and 1-year trend.</div></div>'
        f'<script>(function(){{var cards={_json.dumps(cards)};'
        'function bind(){var gd=document.getElementById("oppmap");'
        'if(!gd||!gd.on){return setTimeout(bind,200);}'
        'var show=function(ev){var p=ev.points[0];if(p&&p.customdata!==undefined)'
        '{document.getElementById("opp-card").innerHTML=cards[p.customdata];}};'
        'gd.on("plotly_hover",show);gd.on("plotly_click",show);}'
        'bind();})();</script>')


def _build_scatter(stocks, date_str):
    """RSI vs Forward P/E scatter plot with held stock markers."""
    plottable = [s for s in stocks
                 if s.get('rsi') is not None and s.get('fwd_pe') is not None]

    fig = go.Figure()

    # Group by GICS sector
    sector_groups: dict[str, list] = {}
    for s in plottable:
        gics = SECTOR_TO_GICS.get(s.get('sector', ''), 'Other') or 'Other'
        sector_groups.setdefault(gics, []).append(s)

    for sector in sorted(sector_groups.keys()):
        ss = sector_groups[sector]
        color = SECTOR_COLORS.get(sector, "#888888")

        sizes = []
        for s in ss:
            gap = s.get('gap_pct')
            sizes.append(max(8, min(22, 22 - abs(gap) * 0.5)) if gap is not None else 12)

        hover_texts = []
        for s in ss:
            target = f"${s['entry_target']}" if s.get('entry_target') else "—"
            gap = f"{s['gap_pct']:+.1f}%" if s.get('gap_pct') is not None else "—"
            price = f"${s['price']:.2f}" if s.get('price') else "—"
            conv = f"{s['conviction']:.1f}" if s.get('conviction') else "?"
            earn = f"{s['earnings_days']}d" if s.get('earnings_days') and s['earnings_days'] > 0 else "—"
            held_line = ""
            if s.get('held_in'):
                accts = [ACCOUNT_ABBREV.get(h['account'], h['account'])
                         for h in s['held_in']]
                hv = s.get('total_held_value', 0)
                held_line = (f"<br><b>Held:</b> {', '.join(accts)}"
                             + (f" (${hv/1000:.0f}K)" if hv >= 1000 else ""))
            hover_texts.append(
                f"<b>{s['ticker']}</b><br>Price: {price}<br>"
                f"RSI: {s['rsi']}<br>Fwd P/E: {s['fwd_pe']:.1f}x<br>"
                f"Sector: {s.get('sector', '')}<br>"
                f"Conv: {conv} | Target: {target} | Gap: {gap}<br>"
                f"Earnings: {earn}{held_line}"
            )

        line_widths = [2.5 if s.get('held_in') else 1 for s in ss]

        fig.add_trace(go.Scatter(
            x=[s['rsi'] for s in ss],
            y=[s['fwd_pe'] for s in ss],
            mode="markers+text", name=sector,
            text=[s['ticker'] for s in ss],
            textposition="top center",
            textfont=dict(size=11, color="#cccccc"),
            hovertext=hover_texts, hoverinfo="text",
            marker=dict(size=sizes, color=color, opacity=0.85,
                        line=dict(width=line_widths, color="#ffffff")),
        ))

    fig.add_vline(x=30, line_dash="dash", line_color="#66bb6a", line_width=1)
    fig.add_vline(x=70, line_dash="dash", line_color="#ef5350", line_width=1)
    fig.add_hline(y=25, line_dash="dash", line_color="#888888", line_width=1)
    fig.add_annotation(x=15, y=6, text="OVERSOLD + CHEAP", showarrow=False,
                       font=dict(size=13, color="#66bb6a", family="Arial Black"), opacity=0.4)
    fig.add_annotation(x=80, y=200, text="OVERBOUGHT + EXPENSIVE", showarrow=False,
                       font=dict(size=13, color="#ef5350", family="Arial Black"), opacity=0.4)

    fig.update_layout(
        title=dict(text=f"RSI vs Forward P/E | {date_str}", font=dict(size=18)),
        xaxis=dict(title="RSI (14-period)", gridcolor="#333333", zeroline=False),
        yaxis=dict(title="Forward P/E (log scale)", type="log",
                   range=[0.6, 3.0], gridcolor="#333333", zeroline=False,
                   tickvals=[5, 10, 15, 25, 50, 100, 200, 500],
                   ticktext=["5x", "10x", "15x", "25x", "50x", "100x", "200x", "500x"]),
        legend=dict(title="Sector", bgcolor="rgba(30,30,30,0.8)",
                    bordercolor="#555555", borderwidth=1, font=dict(color="white")),
        height=650, margin=dict(t=60, l=60, r=30, b=60),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="white"),
        hoverlabel=dict(bgcolor="#2a2a2a", bordercolor="#555555",
                        font_size=13, font_color="white"),
    )
    return fig


# --- Tab 3: Earnings Calendar ---

def _build_earnings(stocks, date_str):
    """Earnings calendar horizontal bar chart."""
    today = datetime.now().date()
    current_year = datetime.now().year

    entries = []
    for s in stocks:
        days = s.get('earnings_days')
        earn_str = s.get('earnings')
        if days is None or days <= 0 or earn_str is None:
            continue
        if s.get('earnings_iso'):   # live date from Yahoo, with timing
            entries.append({
                'ticker': s['ticker'], 'earnings_date': date.fromisoformat(s['earnings_iso']),
                'days_until': days, 'sector': s.get('sector', ''),
                'conviction': s.get('conviction'), 'held': bool(s.get('held_in')),
                'timing': s.get('earnings_time'), 'estimate': s.get('earnings_est'),
            })
            continue
        for fmt in ['%B %d, %Y', '%B %d', '%b %d, %Y', '%b %d']:
            try:
                dt = datetime.strptime(earn_str.strip('*'), fmt)
                if dt.year < current_year:
                    dt = dt.replace(year=current_year)
                entries.append({
                    'ticker': s['ticker'], 'earnings_date': dt.date(),
                    'days_until': days, 'sector': s.get('sector', ''),
                    'conviction': s.get('conviction'),
                    'held': bool(s.get('held_in')),
                })
                break
            except ValueError:
                continue

    if not entries:
        return None

    entries.sort(key=lambda e: e['days_until'])
    fig = go.Figure()

    def urgency_color(d):
        if d < 7: return "#ef5350"
        if d < 14: return "#ffa726"
        if d < 30: return "#ffee58"
        return "#66bb6a"

    def urgency_label(d):
        if d < 7: return "IMMINENT"
        if d < 14: return "SOON"
        if d < 30: return "UPCOMING"
        return "SAFE"

    # Held positions are marked with ● so your own names stand out
    tickers = [('● ' if e['held'] else '') + e['ticker'] for e in entries]
    days = [e['days_until'] for e in entries]
    colors = [urgency_color(d) for d in days]
    dates = [e['earnings_date'].strftime('%a %b %d')
             + (f" · {e['timing']}" if e.get('timing') else '')
             + (' (est.)' if e.get('estimate') else '') for e in entries]

    hover_texts = []
    for e in entries:
        conv = f"{e['conviction']:.1f}" if e.get('conviction') else "?"
        held = "Yes" if e['held'] else "No"
        hover_texts.append(
            f"<b>{e['ticker']}</b><br>"
            f"Earnings: {e['earnings_date'].strftime('%a %b %d, %Y')}"
            f"{' · ' + {'BMO': 'before market open', 'AMC': 'after market close'}.get(e.get('timing'), e.get('timing') or '') if e.get('timing') else ''}"
            f"{' (estimated)' if e.get('estimate') else ''}<br>"
            f"Days: {e['days_until']}<br>"
            f"Sector: {e['sector']}<br>"
            f"Conv: {conv}<br>"
            f"Held: {held}<br>"
            f"Urgency: {urgency_label(e['days_until'])}"
        )

    fig.add_trace(go.Bar(
        y=tickers, x=days, orientation="h",
        marker=dict(color=colors, opacity=0.9,
                    line=dict(width=1, color="#0d1117")),
        text=[f"  {d}d — {dt}" for d, dt in zip(days, dates)],
        textposition="outside",
        textfont=dict(color="#e6edf3", size=12),
        hovertext=hover_texts, hoverinfo="text",
        showlegend=False,
    ))

    # Reference lines at 7 and 14 days
    fig.add_vline(x=7, line_dash="dash", line_color="#ef5350", line_width=1,
                  annotation_text="7d", annotation_position="top",
                  annotation_font=dict(color="#ef5350", size=10))
    fig.add_vline(x=14, line_dash="dash", line_color="#ffa726", line_width=1,
                  annotation_text="14d", annotation_position="top",
                  annotation_font=dict(color="#ffa726", size=10))
    fig.add_vline(x=30, line_dash="dash", line_color="#ffee58", line_width=1,
                  annotation_text="30d", annotation_position="top",
                  annotation_font=dict(color="#ffee58", size=10))

    chart_height = max(350, len(entries) * 40 + 100)

    fig.update_layout(
        title=dict(text=f"Earnings Calendar | {date_str}", font=dict(size=18)),
        xaxis=dict(title="Days Until Earnings", gridcolor="#333333",
                   tickfont=dict(color="#cccccc"), zeroline=False),
        yaxis=dict(title="", tickfont=dict(color="#cccccc", size=13),
                   # Horizontal bars stack bottom-up: descending puts the soonest on top
                   automargin=True, categoryorder="total descending"),
        height=chart_height,
        margin=dict(t=60, l=10, r=140, b=60),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", font=dict(color="white"),
    )
    return fig


# --- Tab 4: Holdings Table ---

# Local, gitignored overrides for intentional exceptions (long holds, employer caps).
# Format: markdown table rows "| TICKER | min% | max% | note |".
OVERRIDES_PATH = Path("portfolio/allocation-overrides.md")


def _load_allocation_overrides() -> dict:
    overrides = {}
    if not OVERRIDES_PATH.exists():
        return overrides
    for line in OVERRIDES_PATH.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3 or not cells[0].isupper() or not cells[0].isalpha():
            continue
        try:
            overrides[cells[0]] = (float(cells[1]), float(cells[2]),
                                   cells[3] if len(cells) > 3 else '')
        except ValueError:
            continue
    return overrides


# Position-sizing framework: knowledge/frameworks/position-sizing.md
CONVICTION_BASE = [(9, 6.5), (8, 4.5), (7, 3.5), (6, 2.0), (5, 1.0)]
# Forward P/E (cheap below, rich above) by GICS sector, simplified from valuation.md
PE_BANDS = {
    'Technology': (20, 40), 'Communication Services': (18, 35),
    'Consumer Discretionary': (18, 40), 'Consumer Staples': (16, 28),
    'Healthcare': (15, 30), 'Financials': (12, 25), 'Energy': (10, 20),
    'Industrials': (18, 35), 'Utilities': (14, 22), 'Materials': (12, 25),
    'Real Estate': (15, 35),
}
MOMENTUM_MULT = {'Accelerating Up': 1.1, 'Downtrend': 0.8, 'Capitulation': 0.8}
CLUSTER_CAP_PCT = 25.0
TOLERANCE = 0.25  # within ±25% of target = on target


def _base_target(conviction):
    if conviction is None:
        return None
    c = float(conviction)
    for floor, pct in CONVICTION_BASE:
        if c >= floor:
            return pct
    return 0.0


def _target_weight(d, sector):
    """Conviction base x valuation x volatility x sector momentum. Returns (pct, factors)."""
    base = _base_target(d.get('conviction'))
    if base is None:
        return None, []
    pct, notes = base, [f"conv {base:.1f}%"]
    pe, band = d.get('fwd_pe'), PE_BANDS.get(sector, (15, 35))
    if pe:
        if pe < band[0]:
            pct *= 1.2; notes.append("cheap ×1.2")
        elif pe > band[1]:
            pct *= 0.8; notes.append("rich ×0.8")
    atr = d.get('atr_pct')
    if atr:
        if atr < 3:
            pct *= 1.1; notes.append("low vol ×1.1")
        elif atr > 6:
            pct *= 0.75; notes.append("high vol ×0.75")
    mult = MOMENTUM_MULT.get(d.get('sector_momentum') or '')
    if mult:
        pct *= mult; notes.append(f"sector ×{mult}")
    return pct, notes


def _load_clusters() -> list[dict]:
    """Correlated clusters of held positions (scripts/correlation.py --json)."""
    try:
        out = subprocess.run([sys.executable, str(Path(__file__).parent / 'correlation.py'), '--json'],
                             capture_output=True, text=True, timeout=180)
        return json.loads(out.stdout).get('clusters', []) if out.returncode == 0 else []
    except Exception:
        return []


def _action_hint(status, d):
    """Allocation status x timing signals -> what to do next."""
    if d.get('earnings_days') is not None and 0 <= d['earnings_days'] <= 7 and status != 'on':
        return 'Wait: earnings'
    if status == 'on':
        return 'Hold'
    rsi = float(d['rsi']) if d.get('rsi') is not None else 50.0
    stretch = d.get('pct_vs_sma20') or 0
    good = rsi < 40 or stretch < -8
    poor = rsi > 65 or stretch > 10
    if status == 'under':
        if poor: return 'Wait for pullback'
        hint = 'Add zone' if good else 'DCA'
        if hint == 'Add zone' and d.get('above_sma200') is False and d.get('sector_momentum') in ('Downtrend', 'Capitulation'):
            hint = 'DCA slowly'
        return hint
    if good: return 'Trim on bounce'
    if poor: return 'Trim into strength'
    return 'Trim on strength'


def _build_holdings_table(holdings, watchlist, sector_map, portfolio_total=None, portfolio_cash=0.0):
    """Cross-account holdings table grouped by GICS sector."""
    wl_lookup = {s['ticker']: s for s in watchlist}

    # Aggregate per ticker
    ticker_data = {}
    for ticker, positions in holdings.items():
        total_shares = sum(p.get('shares') or 0 for p in positions)
        total_value = sum(p.get('value') or 0 for p in positions)
        accounts = sorted(set(
            ACCOUNT_ABBREV.get(p['account'], p['account']) for p in positions
        ))
        is_option_only = all(p.get('is_option') for p in positions)
        wl = wl_lookup.get(ticker, {})

        ticker_data[ticker] = {
            'ticker': ticker,
            'sector': sector_map.get(ticker, 'Other'),
            'accounts': ', '.join(accounts),
            'shares': total_shares if not is_option_only else None,
            'value': total_value,
            'conviction': wl.get('conviction'),
            'rsi': wl.get('rsi'),
            'fwd_pe': wl.get('fwd_pe'),
            'atr_pct': wl.get('atr_pct'),
            'pct_vs_sma20': wl.get('pct_vs_sma20'),
            'above_sma200': wl.get('above_sma200'),
            'spark': wl.get('spark'),
            'pe_trailing': wl.get('pe_trailing'),
            'is_etf': wl.get('is_etf'),
            'price': wl.get('price'),
            'trend_px': wl.get('trend_px'), 'trend_sma': wl.get('trend_sma'),
            'trend_hi_idx': wl.get('trend_hi_idx'), 'rsi_spark': wl.get('rsi_spark'),
            'pct_vs_sma200': wl.get('pct_vs_sma200'),
            'pct_off_high': wl.get('pct_off_high'),
            'rs_1m': wl.get('rs_1m'),
            'rs_etf': wl.get('rs_etf'),
            'sector_momentum': wl.get('sector_momentum'),
            'earnings_days': wl.get('earnings_days'),
        }

    # % of the TOTAL portfolio (account totals incl. cash), same base as the topline and pies
    total_portfolio = portfolio_total or sum(d['value'] for d in ticker_data.values()) or 1
    overrides = _load_allocation_overrides()

    # Multi-factor targets, then scale down correlated clusters above the cap
    for d in ticker_data.values():
        ov = overrides.get(d['ticker'])
        if ov:
            d['target'], d['factors'], d['override'] = (ov[0] + ov[1]) / 2, [], ov
        else:
            d['target'], d['factors'] = _target_weight(d, d['sector'])
            d['override'] = None
    # Clusters that share a theme label (e.g. several "AI Semis" groups) are one bet
    themes: dict[str, set] = {}
    for i, cl in enumerate(_load_clusters()):
        label = cl.get('label') or 'Correlated Group'
        key = f'{label}#{i}' if label == 'Correlated Group' else label
        themes.setdefault(key, set()).update(cl.get('members', []))
    for key, tickers in themes.items():
        cl = {'label': key.split('#')[0], 'members': sorted(tickers)}
        members = [ticker_data[t] for t in cl.get('members', [])
                   if t in ticker_data and ticker_data[t]['target'] and not ticker_data[t]['override']]
        total = sum(m['target'] for m in members)
        if total > CLUSTER_CAP_PCT:
            scale = CLUSTER_CAP_PCT / total
            for m in members:
                m['target'] *= scale
                m['factors'].append(f"cluster cap ×{scale:.2f} ({cl.get('label', 'cluster')})")

    # Group by sector
    sectors: dict[str, list] = {}
    for d in ticker_data.values():
        sectors.setdefault(d['sector'], []).append(d)
    for sector in sectors:
        sectors[sector].sort(key=lambda x: -x['value'])

    def _conv_badge(c):
        if c is None: return '<span style="color:#484f58">—</span>'
        v = float(c)
        if v >= 8: cls, bg = '#3fb950', '#3fb95022'
        elif v >= 7: cls, bg = '#58a6ff', '#58a6ff22'
        elif v >= 6: cls, bg = '#d29922', '#d2992222'
        else: cls, bg = '#8b949e', '#8b949e22'
        return (f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                f'font-size:12px;font-weight:600;background:{bg};color:{cls};">{v:.1f}</span>')

    def _sparkline(closes, above_200):
        """Tiny 60-day price line; green = above 200-day (uptrend), red = below."""
        if not closes or len(closes) < 2:
            return ''
        lo, hi = min(closes), max(closes)
        span = (hi - lo) or 1
        w, h = 56, 16
        pts = ' '.join(f'{i * w / (len(closes) - 1):.1f},{h - (c - lo) / span * h:.1f}'
                       for i, c in enumerate(closes))
        color = '#3fb950' if above_200 else '#f85149' if above_200 is False else '#8b949e'
        trend = 'above' if above_200 else 'below' if above_200 is False else 'n/a vs'
        return (f'<svg width="{w}" height="{h}" style="vertical-align:middle;margin-right:6px;">'
                f'<title>60-day price; {trend} 200-day average</title>'
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/></svg>')

    def _pct_cell(v, good_above=0.0):
        if v is None: return '<span style="color:#484f58">—</span>'
        color = '#3fb950' if v >= good_above else '#f85149' if v <= -20 else '#d29922'
        return f'<span style="color:{color}">{v:+.0f}%</span>'

    def _rs_arrow(rs, etf):
        if rs is None: return ''
        if rs >= 15: a, c = '↑↑', '#3fb950'
        elif rs >= 5: a, c = '↑', '#3fb950'
        elif rs <= -15: a, c = '↓↓', '#f85149'
        elif rs <= -5: a, c = '↓', '#f85149'
        else: a, c = '→', '#8b949e'
        return (f'<span title="1-month return vs {etf}: {rs:+.1f} pts" '
                f'style="color:{c};font-size:11px;margin-left:4px;cursor:help;">{a}</span>')

    def _price_cell(price, spark):
        if not price: return '<span style="color:#484f58">—</span>'
        chg = ''
        if spark and len(spark) >= 2 and spark[-2]:
            pct = (spark[-1] / spark[-2] - 1) * 100
            c = '#3fb950' if pct > 0 else '#f85149' if pct < 0 else '#8b949e'
            chg = (f'<br><span title="Change vs the previous trading day\'s close" '
                   f'style="color:{c};font-size:11px;cursor:help;">{pct:+.1f}%</span>')
        return f'${price:,.2f}{chg}'

    def _etf_badge(is_etf):
        if not is_etf: return ''
        return (' <span title="Exchange-traded fund (basket of stocks)" style="display:inline-block;'
                'padding:0 5px;border-radius:8px;font-size:10px;font-weight:600;'
                'background:#58a6ff22;color:#58a6ff;cursor:help;">ETF</span>')

    def _earn_badge(days):
        if days is None or not (0 <= days <= 14): return ''
        c = '#f85149' if days <= 7 else '#d29922'
        return (f' <span title="Earnings in {days} days" style="display:inline-block;padding:0 5px;'
                f'border-radius:8px;font-size:10px;font-weight:600;background:{c}33;color:{c};">'
                f'E {days}d</span>')

    def _trend_chart(px, sma, hi_idx, above_200):
        """1-year price (solid), 200-day average (dashed), dot at the 52-week high."""
        if not px or len(px) < 2:
            return ''
        vals = px + [v for v in (sma or []) if v is not None]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1
        w, h = 84, 22
        n = len(px)
        X = lambda i: i * w / (n - 1)
        Y = lambda v: h - 1 - (v - lo) / span * (h - 2)
        color = '#3fb950' if above_200 else '#f85149' if above_200 is False else '#8b949e'
        price = ' '.join(f'{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(px))
        sma_pts = ' '.join(f'{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(sma or []) if v is not None)
        dot = ''
        if hi_idx is not None and 0 <= hi_idx < n:
            dot = f'<circle cx="{X(hi_idx):.1f}" cy="{Y(px[hi_idx]):.1f}" r="2" fill="#e6edf3"/>'
        return (f'<svg width="{w}" height="{h}" style="vertical-align:middle;">'
                f'<title>1-year price (line), 200-day average (dashed), dot = 52-week high</title>'
                f'<polyline fill="none" stroke="#8b949e" stroke-width="1" stroke-dasharray="3,2" points="{sma_pts}"/>'
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{price}"/>{dot}</svg>')

    def _rsi_chart(vals):
        """60-day RSI line with faint 30/70 bands."""
        if not vals or len(vals) < 2:
            return ''
        # Same size as the trend chart; scale 15–85 (where RSI lives) so moves are visible
        w, h, lo, hi = 84, 22, 15.0, 85.0
        Y = lambda v: h - 1 - (min(max(v, lo), hi) - lo) / (hi - lo) * (h - 2)
        pts = ' '.join(f'{i * w / (len(vals) - 1):.1f},{Y(v):.1f}' for i, v in enumerate(vals))
        last = vals[-1]
        c = '#3fb950' if last < 30 else '#f85149' if last > 70 else '#58a6ff'
        return (f'<svg width="{w}" height="{h}" style="vertical-align:middle;margin-right:6px;">'
                f'<title>60-day RSI; bands at 30 and 70</title>'
                f'<rect x="0" y="{Y(70):.1f}" width="{w}" height="{Y(30) - Y(70):.1f}" fill="#30363d" opacity="0.5"/>'
                f'<polyline fill="none" stroke="{c}" stroke-width="1.5" points="{pts}"/></svg>')

    def _rsi_cell(r):
        if r is None: return '<span style="color:#484f58">—</span>'
        v = float(r)
        if v < 30: color = '#3fb950'    # oversold — bullish
        elif v > 70: color = '#f85149'  # overbought — bearish
        elif v < 40: color = '#66bb6a'
        elif v > 60: color = '#ffa726'
        else: color = '#8b949e'
        return f'<span style="color:{color};font-weight:500">{v:.0f}</span>'

    def _pe_cell(p, trailing=False):
        if p is None: return '<span style="color:#484f58">—</span>'
        v = float(p)
        if v < 15: color = '#3fb950'     # cheap
        elif v > 50: color = '#f85149'   # expensive
        elif v > 30: color = '#d29922'
        else: color = '#8b949e'
        if trailing:
            return (f'<span style="color:{color}" title="Trailing P/E (ETF: no forward estimate available)">'
                    f'{v:.1f}x <span style="font-size:10px;color:#8b949e;cursor:help;">T</span></span>')
        return f'<span style="color:{color}">{v:.1f}x</span>'

    def _alloc_bar(pct):
        """Mini inline allocation bar."""
        width = min(pct * 3, 100)  # scale: 33% = full bar
        if pct > 15: color = '#f85149'
        elif pct > 5: color = '#58a6ff'
        else: color = '#30363d'
        return (f'<div style="display:flex;align-items:center;gap:6px;">'
                f'<div style="flex:1;background:#21262d;border-radius:3px;height:6px;'
                f'min-width:60px;overflow:hidden;">'
                f'<div style="width:{width}%;background:{color};height:100%;'
                f'border-radius:3px;"></div></div>'
                f'<span style="font-size:12px;min-width:40px;text-align:right;">'
                f'{pct:.1f}%</span></div>')

    def _alloc_cells(d, pct):
        dash = '<span style="color:#484f58">—</span>'
        if d['target'] is None:
            return dash, dash, dash
        ov = d['override']
        if ov:
            lo, hi = ov[0], ov[1]
            target_txt = f'{lo:.0f}–{hi:.0f}%'
        else:
            lo, hi = d['target'] * (1 - TOLERANCE), d['target'] * (1 + TOLERANCE)
            target_txt = f'{d["target"]:.1f}%'
        status = 'under' if pct < lo else 'over' if pct > hi else 'on'
        # Gap to the target itself (overrides: to the nearest band edge)
        if ov:
            gap = pct - lo if status == 'under' else pct - hi if status == 'over' else 0.0
        else:
            gap = pct - d['target']
        far = abs(gap) >= max(2.0, d['target'] * 0.5)
        dollars = abs(gap) / 100 * total_portfolio
        if status == 'on':
            badge = '<span style="color:#3fb950">On target</span>'
        else:
            color = '#f85149' if far else '#d29922'
            label = ('Far ' if far else '') + status
            badge = (f'<span style="color:{color};font-weight:600;white-space:nowrap;">{label} {gap:+.1f}pt</span>'
                     f'<br><span style="color:#8b949e;font-size:11px;">~${dollars/1000:.1f}K</span>')
        title = ' · '.join(d['factors']) if d['factors'] else (ov[2] if ov else '')
        target_cell = f'<span style="color:#8b949e;cursor:help;" title="{title}">{target_txt}</span>'
        if ov:
            note = (ov[2] or 'set locally').replace('"', "'")
            hint = (f'<span title="{note}" style="display:inline-block;padding:1px 8px;border-radius:10px;'
                    f'background:#8b949e22;color:#8b949e;font-size:11px;cursor:help;white-space:nowrap;">'
                    f'Exception &#9432;</span>')
        else:
            hint = _action_hint(status, d)
        return target_cell, badge, hint

    rows = []
    row_idx = 0
    for sector in sorted(sectors.keys(),
                         key=lambda s: -sum(d['value'] for d in sectors[s])):
        sector_total = sum(d['value'] for d in sectors[sector])
        sector_pct = sector_total / total_portfolio * 100
        color = SECTOR_COLORS.get(sector, '#888')
        n_stocks = len(sectors[sector])

        rows.append(
            f'<tr style="background:#161b22;font-weight:600;border-top:2px solid #30363d;">'
            f'<td style="border-left:4px solid {color};padding-left:12px;">'
            f'{sector} <span style="color:#484f58;font-weight:400;font-size:12px;">'
            f'({n_stocks})</span></td>'
            f'<td></td><td></td><td></td>'
            f'<td style="text-align:right;font-size:15px;">${sector_total/1000:.0f}K</td>'
            f'<td>{_alloc_bar(sector_pct)}</td>'
            f'<td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>'
        )

        for d in sectors[sector]:
            pct = d['value'] / total_portfolio * 100
            shares = f"{d['shares']:,.1f}" if d['shares'] else '<span style="color:#484f58">opts</span>'
            value = f"${d['value']:,.0f}" if d['value'] > 0 else "—"
            bg = '#161b2280' if row_idx % 2 == 0 else 'transparent'
            row_idx += 1
            target, status, hint = _alloc_cells(d, pct)

            rows.append(
                f'<tr style="background:{bg};">'
                f'<td style="padding-left:28px;font-weight:500;white-space:nowrap;">{d["ticker"]}{_etf_badge(d.get("is_etf"))}{_earn_badge(d.get("earnings_days"))}</td>'
                f'<td style="color:#8b949e;font-size:12px;">{d["accounts"]}</td>'
                f'<td style="text-align:right;color:#8b949e;">{shares}</td>'
                f'<td style="text-align:right;white-space:nowrap;">{_price_cell(d.get("price"), d.get("spark"))}</td>'
                f'<td style="text-align:right;">{value}</td>'
                f'<td>{_alloc_bar(pct)}</td>'
                f'<td style="text-align:center;">{_trend_chart(d.get("trend_px"), d.get("trend_sma"), d.get("trend_hi_idx"), d.get("above_sma200"))}</td>'
                f'<td style="text-align:center;">{_pct_cell(d.get("pct_vs_sma200"))}</td>'
                f'<td style="text-align:center;">{_pct_cell(d.get("pct_off_high"), good_above=-5.0)}</td>'
                f'<td style="text-align:center;white-space:nowrap;">{_rsi_chart(d.get("rsi_spark"))}{_rsi_cell(d["rsi"])}{_rs_arrow(d.get("rs_1m"), d.get("rs_etf"))}</td>'
                f'<td style="text-align:center;">{_pe_cell(d["fwd_pe"], d.get("pe_trailing"))}</td>'
                f'<td style="text-align:center;">{_conv_badge(d["conviction"])}</td>'
                f'<td style="text-align:center;">{target}</td>'
                f'<td>{status}</td>'
                f'<td style="font-size:12px;white-space:nowrap;">{hint}</td></tr>'
            )

    # Footer: what the portfolio would look like if every target were met
    actual_sum = target_sum = 0.0
    for d in ticker_data.values():
        pct = d['value'] / total_portfolio * 100
        actual_sum += pct
        if d.get('override'):
            lo, hi = d['override'][0], d['override'][1]
            target_sum += min(max(pct, lo), hi)   # exceptions: current, clamped into their band
        elif d.get('target') is not None:
            target_sum += d['target']
        else:
            target_sum += pct                     # no conviction: assume unchanged
    cash_pct = portfolio_cash / total_portfolio * 100           # settled cash (same as topline)
    pending_pct = max(0.0, 100 - actual_sum - cash_pct)          # pending settlements & options
    need = target_sum - actual_sum
    total_if = target_sum + cash_pct + pending_pct
    color = '#f85149' if total_if > 100.5 else '#3fb950'
    verdict = (f'over-allocated by {total_if - 100:.1f} pts: would need ~${need / 100 * total_portfolio / 1000:.0f}K '
               f'of new money or trims' if total_if > 100.5 else 'fits within the portfolio')
    rows.append(
        f'<tr style="background:#161b22;border-top:2px solid #30363d;font-weight:600;">'
        f'<td colspan="5" style="padding-left:12px;">If all targets were met '
        f'<span class="tip" title="Formula names at their target; exceptions at their current weight clamped into their band; '
        f'names without conviction unchanged; cash kept at today\'s level">&#9432;</span></td>'
        f'<td colspan="11" style="white-space:nowrap;">Holdings <b>{target_sum:.1f}%</b> '
        f'<span style="color:#8b949e;font-weight:400;">(today {actual_sum:.1f}%)</span> + cash {cash_pct:.1f}% '
        f'+ pending {pending_pct:.1f}% = '
        f'<span style="color:{color};">{total_if:.1f}%</span> '
        f'<span style="color:#8b949e;font-weight:400;">· {verdict}</span></td></tr>'
    )

    return (
        '<table style="font-size:13px;"><thead><tr>'
        '<th style="min-width:140px;">Sector / Ticker</th>'
        '<th>Accounts</th>'
        '<th style="text-align:right;">Shares</th>'
        '<th style="text-align:right;"><span style="white-space:nowrap;">Price&nbsp;<span class="tip" title="Latest price (live during market hours, else the last close). % = change vs the previous trading day\'s close">&#9432;</span></span></th>'
        '<th style="text-align:right;min-width:90px;">Value</th>'
        '<th style="min-width:130px;">% Portfolio</th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">Trend 1Y&nbsp;<span class="tip" title="1-year price (green above / red below the 200-day average), dashed line = 200-day average, dot = 52-week high">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">vs 200D&nbsp;<span class="tip" title="% above/below the 200-day average. Positive = long-term uptrend; below −20% = deep downtrend">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">Off High&nbsp;<span class="tip" title="% below the 52-week high: how much has been given back. Use with RSI to judge dip vs breakdown">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">RSI&nbsp;<span class="tip" title="14-day RSI: &lt;30 oversold, &gt;70 overbought. Read with the trend: oversold in a downtrend can keep falling. Chart = 60-day RSI with the 30–70 band shaded; arrow = 1-month strength vs sector ETF">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">Fwd P/E&nbsp;<span class="tip" title="Price / next-12-month expected EPS. Green &lt;15x cheap, amber &gt;30x, red &gt;50x (compare within sector)">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">Conv&nbsp;<span class="tip" title="Research conviction 1–10 (business quality, growth, valuation, technicals, catalyst, institutional)">&#9432;</span></span></th>'
        '<th style="text-align:center;"><span style="white-space:nowrap;">Target&nbsp;<span class="tip" title="Target weight = conviction base × valuation × volatility × sector momentum, cluster-capped (hover a value for its math). Ranges = local overrides">&#9432;</span></span></th>'
        '<th><span style="white-space:nowrap;">Status&nbsp;<span class="tip" title="Actual vs target: on target within ±25%; gap shown in points and dollars to reach target">&#9432;</span></span></th>'
        '<th><span style="white-space:nowrap;">Action&nbsp;<span class="tip" title="Status × timing (RSI, distance from 20-day average); earnings within 7 days → wait. Guidance, not orders">&#9432;</span></span></th>'
        '</tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table>'
    )


# --- Tab 5: Trading Plan (from latest PLAN markdown) ---

def _load_latest_plan() -> tuple[str, str]:
    """Find and render the most recent PLAN markdown as HTML.

    Returns (plan_html, plan_date) or ('', '') if no plan found.
    """
    plans_dir = Path("portfolio/plans")
    if not plans_dir.exists():
        return '', ''

    plan_files = sorted(plans_dir.glob("PLAN-*.md"), reverse=True)
    if not plan_files:
        return '', ''

    plan_path = plan_files[0]
    # Extract date from filename: PLAN-2026-08-08.md → 2026-08-08
    plan_date = plan_path.stem.replace('PLAN-', '')
    content = plan_path.read_text(encoding="utf-8")

    # Show the "At a Glance" section up front; collapse the full plan below it
    import re
    m = re.search(r'^## At a Glance.*?(?=^## |^---\s*$|\Z)', content, re.M | re.S)
    if not m:
        return _render_plan_md(content), plan_date
    glance = m.group(0)
    rest = content[:m.start()] + content[m.end():]
    return (_render_plan_md(glance)
            + '<details style="margin-top:20px;"><summary style="cursor:pointer;color:#58a6ff;'
              'font-size:14px;font-weight:600;padding:8px 0;">Show full plan ▸</summary>'
            + _render_plan_md(rest) + '</details>'), plan_date


def _md_inline(text: str) -> str:
    """Process inline markdown: **bold**, ~~strikethrough~~, `code`."""
    import re
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Strikethrough
    text = re.sub(r'~~(.+?)~~', r'<s style="color:#8b949e">\1</s>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code style="background:#21262d;padding:1px 5px;'
                  r'border-radius:3px;font-size:12px;">\1</code>', text)
    return text


def _action_badge(text: str) -> str:
    """Detect action keywords and return a colored badge."""
    t = text.upper().strip('* ')
    badge = '<span class="badge badge-{cls}">{label}</span>'
    if any(k in t for k in ['SELL CC', 'SELL TO OPEN']):
        return badge.format(cls='red', label='SELL CC')
    if 'SELL HALF' in t or 'TAKE PROFIT' in t:
        return badge.format(cls='orange', label='TAKE PROFIT')
    if t.startswith('SELL') or 'CLOSE' in t:
        return badge.format(cls='red', label=t.split()[0])
    if t.startswith('BUY') or 'RESUME' in t:
        return badge.format(cls='green', label=t.split()[0])
    if t.startswith('ROLL'):
        return badge.format(cls='orange', label='ROLL')
    if 'MONITOR' in t:
        return badge.format(cls='orange', label='MONITOR')
    if 'HOLD' in t or 'DELIBERATE' in t:
        return badge.format(cls='blue', label='HOLD')
    if 'LET EXPIRE' in t or 'EXPIRE' in t:
        return badge.format(cls='gray', label='EXPIRE')
    if 'PAUSED' in t or 'Paused' in text:
        return badge.format(cls='gray', label='PAUSED')
    if 'RESUMED' in t:
        return badge.format(cls='green', label='RESUMED')
    return ''


def _style_plan_cell(text: str, header: str) -> str:
    """Apply smart styling to plan table cells based on column header and content."""
    import re
    clean = text.strip().strip('*')

    # Conviction column — colored badges
    if header.lower() in ('conv', 'conviction'):
        try:
            v = float(clean)
            if v >= 8: cls, bg = '#3fb950', '#3fb95022'
            elif v >= 7: cls, bg = '#58a6ff', '#58a6ff22'
            elif v >= 6: cls, bg = '#d29922', '#d2992222'
            else: cls, bg = '#8b949e', '#8b949e22'
            return (f'<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                    f'font-size:12px;font-weight:600;background:{bg};color:{cls};">{v}</span>')
        except ValueError:
            pass

    # RSI column — color-coded
    if header.lower() == 'rsi':
        try:
            v = float(clean)
            if v < 30: color = '#3fb950'
            elif v > 70: color = '#f85149'
            elif v < 40: color = '#66bb6a'
            elif v > 60: color = '#ffa726'
            else: color = '#8b949e'
            return f'<span style="color:{color};font-weight:500">{v:.0f}</span>'
        except ValueError:
            pass

    # Gap% column — green negative (below target), red positive (above)
    if header.lower() in ('gap%', 'gap'):
        m = re.match(r'([+-]?[\d.]+)%', clean)
        if m:
            v = float(m.group(1))
            color = '#3fb950' if v < 0 else '#d29922' if v < 20 else '#f85149'
            return f'<span style="color:{color}">{v:+.1f}%</span>'

    # Change column — badges for changes
    if header.lower() == 'change':
        if 'PAUSED' in text.upper():
            return '<span class="badge badge-gray">PAUSED</span>'
        if 'RESUMED' in text.upper():
            return '<span class="badge badge-green">RESUMED</span>'
        m = re.match(r'([+-]\$[\d,]+)', clean)
        if m:
            val = m.group(1)
            cls = 'badge-red' if val.startswith('-') else 'badge-green'
            return f'<span class="badge {cls}">{val}</span>'

    return None  # no special styling


def _render_plan_md(md: str) -> str:
    """Convert plan markdown to richly styled HTML matching the old PLAN dashboard."""
    import re

    # Badge CSS (injected once at the top)
    badge_css = """<style>
    .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
    .badge-red{background:#f8514933;color:#f85149}
    .badge-green{background:#3fb95033;color:#3fb950}
    .badge-orange{background:#d2992233;color:#d29922}
    .badge-blue{background:#58a6ff33;color:#58a6ff}
    .badge-gray{background:#8b949e33;color:#8b949e}
    .priority{display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;
              padding:14px 18px;background:#161b22;border-radius:8px;border-left:4px solid;line-height:1.5}
    .priority .num{font-size:22px;font-weight:700;min-width:28px}
    .plan-table{border-spacing:0}
    .plan-table tr.paused{color:#8b949e;text-decoration:line-through}
    .plan-table tr.paused .badge{opacity:0.6}
    .plan-table td{vertical-align:top}
    .plan-table tr:nth-child(even){background:#161b2260}
    .plan-metric{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:8px;
                 padding:10px 16px;margin:4px 8px 4px 0}
    .plan-metric .label{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
    .plan-metric .val{font-size:18px;font-weight:700;margin-top:2px}
    .section-box{background:#161b22;border:1px solid #30363d;border-radius:8px;
                 padding:14px 18px;margin:12px 0}
    </style>"""

    lines = md.split('\n')
    html_parts = [badge_css]
    in_table = False
    table_rows: list = []
    table_headers_raw: list = []
    current_section = ''
    in_summary = False
    summary_count = 0
    priority_colors = ['#f85149', '#d29922', '#58a6ff', '#bc8cff', '#8b949e']

    def _is_paused_row(cells):
        return any('~~' in c or 'Paused' in c or 'paused' in c for c in cells)

    def flush_table():
        nonlocal in_table, table_rows, table_headers_raw
        if not table_rows:
            return
        header = table_rows[0]
        data_rows = table_rows[1:]
        cols = [_md_inline(c.strip()) for c in header]
        raw_headers = [c.strip().strip('*') for c in header]

        thead = '<tr>' + ''.join(f'<th>{c}</th>' for c in cols) + '</tr>'
        tbody_rows = []

        for row in data_rows:
            cells = [c.strip() for c in row]
            while len(cells) < len(cols):
                cells.append('')

            paused = _is_paused_row(cells)
            row_class = ' class="paused"' if paused else ''

            # Color-code left border based on action column
            style = ''
            all_cells_text = ' '.join(cells)
            if any(k in all_cells_text for k in ['SELL', 'TAKE PROFIT', 'CLOSE', 'SKIP']):
                style = ' style="border-left:3px solid #f85149;"'
            elif any(k in all_cells_text for k in ['BUY', 'RESUME', 'RESUMED', 'ACCEPT']):
                style = ' style="border-left:3px solid #3fb950;"'
            elif any(k in all_cells_text for k in ['ROLL', 'MONITOR']):
                style = ' style="border-left:3px solid #d29922;"'
            elif any(k in all_cells_text for k in ['HOLD', 'DELIBERATE', 'WAIT']):
                style = ' style="border-left:3px solid #58a6ff;"'
            elif any(k in all_cells_text for k in ['LET EXPIRE']):
                style = ' style="border-left:3px solid #8b949e;"'

            # Total/summary rows
            if cells[0].strip('* ').upper() == 'TOTAL':
                style = ' style="border-top:2px solid #30363d;font-weight:600;"'

            # Process each cell
            rendered = []
            for i, cell in enumerate(cells):
                hdr = raw_headers[i] if i < len(raw_headers) else ''
                # Try smart styling first
                styled = _style_plan_cell(cell, hdr)
                if styled:
                    rendered.append(f'<td>{styled}</td>')
                    continue
                processed = _md_inline(cell)
                # Try action badge for Type/Change/Action columns
                if hdr.lower() in ('type', 'change', 'action'):
                    badge = _action_badge(cell)
                    if badge:
                        processed = badge
                rendered.append(f'<td>{processed}</td>')

            tbody_rows.append(f'<tr{row_class}{style}>{"".join(rendered)}</tr>')

        html_parts.append(
            f'<table class="plan-table"><thead>{thead}</thead>'
            f'<tbody>{"".join(tbody_rows)}</tbody></table>'
        )
        table_rows.clear()
        in_table = False

    for line in lines:
        stripped = line.strip()

        # Table rows
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = stripped.split('|')[1:-1]
            if all(c.strip().replace('-', '').replace(':', '') == '' for c in cells):
                if not in_table:
                    in_table = True
                continue
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            continue
        elif in_table:
            flush_table()

        # Track summary section for priority cards
        if '3 Things That Matter' in stripped or 'Summary' in stripped and '#' in stripped:
            in_summary = True
            summary_count = 0

        # Detect header metric lines: **Regime:**, **Portfolio:**, **Execution rate**
        if stripped.startswith('**Regime:'):
            html_parts.append(
                f'<div class="plan-metric"><div class="label">Regime</div>'
                f'<div class="val" style="font-size:14px;">{_md_inline(stripped)}</div></div>')
            continue
        if stripped.startswith('**Portfolio:') or stripped.startswith('**Portfolio '):
            html_parts.append(
                f'<div class="plan-metric" style="border-left:3px solid #3fb950;">'
                f'<div class="label">Portfolio</div>'
                f'<div class="val" style="font-size:14px;">{_md_inline(stripped)}</div></div>')
            continue
        if stripped.startswith('**Execution rate'):
            # Color based on rate
            color = '#f85149' if '25%' in stripped or '< 50%' in stripped else '#d29922'
            html_parts.append(
                f'<div class="plan-metric" style="border-left:3px solid {color};">'
                f'<div class="label">Execution</div>'
                f'<div class="val" style="font-size:14px;">{_md_inline(stripped)}</div></div>')
            continue

        # Headers
        if stripped.startswith('# ') and not stripped.startswith('## '):
            html_parts.append(
                f'<h2 style="margin:24px 0 8px;font-size:20px;color:#e6edf3;">'
                f'{_md_inline(stripped[2:])}</h2>')
            current_section = stripped[2:]
        elif stripped.startswith('## '):
            in_summary = 'summary' in stripped.lower() or '3 things' in stripped.lower()
            summary_count = 0
            html_parts.append(
                f'<h3 style="margin:20px 0 8px;font-size:16px;color:#e6edf3;'
                f'border-bottom:1px solid #30363d;padding-bottom:6px;">'
                f'{_md_inline(stripped[3:])}</h3>')
            current_section = stripped[3:]
        elif stripped.startswith('### '):
            html_parts.append(
                f'<h4 style="margin:16px 0 6px;font-size:14px;color:#8b949e;">'
                f'{_md_inline(stripped[4:])}</h4>')
        elif stripped == '---':
            in_summary = False
            html_parts.append(
                '<hr style="border:none;border-top:1px solid #30363d;margin:16px 0;">')
        elif stripped.startswith('**') and stripped.endswith('**') and len(stripped) > 4:
            html_parts.append(
                f'<div class="section-box" style="border-left:3px solid #d29922;">'
                f'{_md_inline(stripped)}</div>')
        elif stripped:
            m = re.match(r'^(\d+)\.\s+(.+)', stripped)
            if m and in_summary:
                # Priority cards with numbered badges
                idx = summary_count
                color = priority_colors[idx] if idx < len(priority_colors) else '#8b949e'
                summary_count += 1
                html_parts.append(
                    f'<div class="priority" style="border-left-color:{color};">'
                    f'<div class="num" style="color:{color};">{m.group(1)}</div>'
                    f'<div style="flex:1;font-size:13px;">{_md_inline(m.group(2))}</div>'
                    f'</div>')
            elif m:
                html_parts.append(
                    f'<div style="margin:6px 0;padding:10px 14px;background:#161b22;'
                    f'border:1px solid #30363d;border-radius:6px;line-height:1.5;">'
                    f'<span style="color:#58a6ff;font-weight:700;margin-right:8px;">'
                    f'{m.group(1)}.</span>{_md_inline(m.group(2))}</div>')
            else:
                html_parts.append(
                    f'<p style="margin:6px 0;line-height:1.5;">{_md_inline(stripped)}</p>')

    if in_table:
        flush_table()

    return '\n'.join(html_parts)


# --- HTML Assembly ---

def generate_dashboard(watchlist, accounts, holdings, sector_map, no_open=False):
    """Generate unified HTML dashboard with 4 tabs."""
    date_str = date.today().isoformat()
    total_value = sum(a['total_value'] for a in accounts)
    n_positions = len(holdings)

    overview_html = _build_overview(accounts, holdings, sector_map, date_str)

    all_stocks = [s for s in watchlist if s.get('tier') in ('active', 'candidate', 'passive')]
    scatter_html = _build_opportunity_map(all_stocks, sector_map, date_str)

    earnings_fig = _build_earnings(all_stocks, date_str)
    earnings_html = (
        earnings_fig.to_html(include_plotlyjs=False, full_html=False, div_id="earnings")
        if earnings_fig else
        "<p style='color:#8b949e;padding:40px;'>No upcoming earnings found.</p>"
    )

    # Data-freshness note for the Holdings tab
    _now = datetime.now()
    _acct_dates = sorted({a['last_updated'] for a in accounts if a.get('last_updated')})
    _pos_date = _acct_dates[-1] if _acct_dates else 'unknown'
    if len(_acct_dates) > 1:
        _pos_date = f"{_acct_dates[0]} – {_acct_dates[-1]}"
    data_note = (
        '<div style="background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 12px;'
        'margin-bottom:12px;font-size:12px;color:#8b949e;">'
        f'<b style="color:#e6edf3;">Data as of:</b> Prices, RSI, charts &amp; P/E: Yahoo Finance, pulled '
        f'{_now.strftime("%a %b %d, %Y %I:%M %p")} (latest close if after hours) · '
        f'Shares, Value, % &amp; targets: account files from brokerage screenshots dated <b style="color:#e6edf3;">{_pos_date}</b>'
        '</div>'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:12px;font-size:12px;color:#8b949e;">'
        '<b style="color:#e6edf3;">How this table decides:</b>'
        '<span title="Mostly fundamentals + ~1/8 technicals, from the research file (slow-moving)" style="cursor:help;padding:2px 8px;border-radius:10px;background:#58a6ff22;color:#58a6ff;">Conviction</span>&rarr;'
        '<span title="Conviction × valuation × volatility × sector momentum, cluster-capped. Exceptions use a local band" style="cursor:help;padding:2px 8px;border-radius:10px;background:#58a6ff22;color:#58a6ff;">Target %</span>&rarr;'
        '<span title="Actual % of total portfolio vs target; within ±25% = on target" style="cursor:help;padding:2px 8px;border-radius:10px;background:#58a6ff22;color:#58a6ff;">Status</span>&rarr;'
        '<span title="Status × live technicals (RSI, trend, 20-day stretch, earnings within 7 days)" style="cursor:help;padding:2px 8px;border-radius:10px;background:#3fb95022;color:#3fb950;">Action</span>'
        '<span style="margin-left:6px;">Conviction &amp; target = <i>how much</i> to own · live technicals = <i>when</i> to act</span>'
        '</div>')
    holdings_html = _build_holdings_table(holdings, watchlist, sector_map,
                                          sum(a['total_value'] for a in accounts),
                                          sum(a['cash'] for a in accounts))

    # Trading plan (optional — from most recent PLAN markdown)
    plan_html, plan_date = _load_latest_plan()
    plan_tab = (f'<div class="tab" onclick="showTab(\'plan\')">Trading Plan</div>'
                if plan_html else '')
    plan_panel = ''
    if plan_html:
        plan_panel = f"""
<div id="panel-plan" class="panel">
  <div class="guide" style="margin-bottom:16px;margin-top:0;">
    Source: <code>portfolio/plans/PLAN-{plan_date}.md</code>
  </div>
  {plan_html}
</div>"""

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Dashboard — {date_str}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#e6edf3;
           --muted:#8b949e; --green:#3fb950; --red:#f85149; --orange:#d29922;
           --blue:#58a6ff; --purple:#bc8cff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
  .tabs {{ display:flex; gap:0; background:#010409; border-bottom:2px solid var(--border);
           padding:0 20px; position:sticky; top:0; z-index:100; }}
  .tab {{ padding:12px 24px; cursor:pointer; color:var(--muted); font-size:14px;
          font-weight:600; border-bottom:3px solid transparent; transition:all 0.2s; }}
  .tab:hover {{ color:#c9d1d9; }}
  .tab.active {{ color:var(--text); border-bottom-color:var(--blue); }}
  .panel {{ display:none; padding:20px; max-width:1400px; margin:0 auto; }}
  .panel.active {{ display:block; }}
  .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px; }}
  .metric {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
  .metric .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:0.5px; }}
  .metric .value {{ font-size:28px; font-weight:700; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .tip {{ color: #8b949e; font-size: 11px; cursor: help; font-weight: 400; }}
.tip:hover {{ color: #58a6ff; }}
th {{ text-align:left; padding:8px 8px; border-bottom:2px solid var(--border);
       color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; }}
  td {{ padding:7px 8px; border-bottom:1px solid #21262d; }}
  tr:hover {{ background:var(--card); }}
  .guide {{ background:var(--card); padding:12px 20px; font-size:13px; color:var(--muted);
            line-height:1.6; border-top:1px solid var(--border); margin-top:20px; border-radius:8px; }}
  h1 {{ margin:0; padding:16px 20px 0; font-size:22px; }}
  .subtitle {{ padding:0 20px 8px; font-size:13px; color:#484f58; }}
</style>
</head><body>
<h1>Dashboard</h1>
<p class="subtitle">Generated {date_str} &middot; {n_positions} positions &middot; ${total_value/1000:.0f}K portfolio</p>
<div class="tabs">
  <div class="tab active" onclick="showTab('overview')">Portfolio</div>
  <div class="tab" onclick="showTab('holdings')">Holdings</div>
  <div class="tab" onclick="showTab('scatter')">Opportunity Map</div>
  <div class="tab" onclick="showTab('earnings')">Earnings</div>
  {plan_tab}
</div>
<div id="panel-overview" class="panel active">
  {overview_html}
</div>
<div id="panel-scatter" class="panel">
  {scatter_html}
  <div class="guide">
    <b>How to read:</b> Each point = one stock. <b>X</b> = RSI (left oversold, right overbought).
    <b>Y</b> = forward P/E relative to its sector band (below 0 = cheap for its sector, above 1 = rich).
    <b>Color</b> = trend: <span style="color:#3fb950">green above the 200-day</span>, <span style="color:#f85149">red below</span>.
    <b>Shape</b>: ● held · ◆ watchlist. <b>Size</b> = conviction. Bottom-left green points = candidates for new money; red there = possible falling knives.
    Use the buttons to show watchlist only. Hover or click a point for its card with the 1-year trend.
  </div>
</div>
<div id="panel-earnings" class="panel">
  <div style="font-size:12px;color:#8b949e;margin:4px 0 10px;">
    <b style="color:#e6edf3;">BMO</b> = before market open: results come out pre-market, so the stock reacts <b>that same day</b>. &nbsp;·&nbsp;
    <b style="color:#e6edf3;">AMC</b> = after market close: results come out after 4pm ET, so the reaction trades <b>the next morning</b>. &nbsp;·&nbsp;
    <b style="color:#e6edf3;">(est.)</b> = date not yet confirmed by the company. &nbsp;·&nbsp;
    <b style="color:#e6edf3;">●</b> = you hold it.
  </div>
  {earnings_html}
  
  <div class="guide">
    <b>How to read:</b> Each bar = days until earnings.
    <span style="color:#ef5350">Red</span> = &lt;7 days (imminent),
    <span style="color:#ffa726">Orange</span> = 7-14 days (soon),
    <span style="color:#ffee58">Yellow</span> = 14-30 days (upcoming),
    <span style="color:#66bb6a">Green</span> = 30+ days (safe).
    White dashed line = today.
  </div>
</div>
<div id="panel-holdings" class="panel">
  {data_note}
  <div style="overflow-x:auto;">{holdings_html}</div>
  <div class="guide">
    <b>How to read:</b> All positions grouped by GICS sector, aggregated across accounts.
    Conv / RSI / Fwd P/E from watchlist data. Sector rows show total value and portfolio weight.
  </div>
</div>
{plan_panel}
<script>
function showTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  window.dispatchEvent(new Event('resize'));
}}
</script>
</body></html>"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard saved to {OUTPUT_PATH}")

    if not no_open:
        subprocess.run(["open", str(OUTPUT_PATH)], check=False)


def main():
    parser = argparse.ArgumentParser(description="Unified portfolio + watchlist dashboard")
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    if not HAS_PLOTLY:
        print("Error: plotly required. Install: pip install plotly", file=sys.stderr)
        sys.exit(1)

    watchlist = load_watchlist_json()
    accounts = load_account_summaries()
    holdings = parse_portfolio_holdings()
    sector_map = build_sector_map(watchlist)

    generate_dashboard(watchlist, accounts, holdings, sector_map,
                       no_open=args.no_open)


if __name__ == "__main__":
    main()
