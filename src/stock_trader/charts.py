from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from stock_trader.crash_warning import CRASH_ALERT_THRESHOLD

STRATEGY_COLORS: dict[str, str] = {
    "buy_and_hold": "#e2e8f0",
    "sma_crossover": "#60a5fa",
    "ema_crossover": "#a78bfa",
    "rsi": "#fb923c",
    "macd": "#facc15",
    "bollinger": "#f472b6",
    "absolute_momentum": "#34d399",
    "trend_filter": "#22d3ee",
    "dual_momentum": "#c084fc",
    "vol_target": "#4ade80",
    "hybrid_regime": "#fbbf24",
    "hybrid_vol_crisis": "#fde047",
    "gem_dual_momentum": "#818cf8",
    "faber_sma10": "#38bdf8",
    "risk_parity": "#fb7185",
    "composite_momentum": "#a3e635",
    "vaa": "#2dd4bf",
    "aurum_momentum": "#e879f9",
    "equity_rotation": "#f97316",
}

STRATEGY_LABELS: dict[str, str] = {
    "buy_and_hold": "Buy & Hold",
    "sma_crossover": "SMA Crossover",
    "ema_crossover": "EMA Crossover",
    "rsi": "RSI",
    "macd": "MACD",
    "bollinger": "Bollinger Bands",
    "absolute_momentum": "Absolute Momentum (12mo)",
    "trend_filter": "Trend Filter (200 SMA)",
    "dual_momentum": "Dual Momentum (SPY vs SHY)",
    "vol_target": "Vol Target (15% target)",
    "hybrid_regime": "Hybrid Regime",
    "hybrid_vol_crisis": "Hybrid Vol + Crisis",
    "gem_dual_momentum": "GEM Dual Momentum",
    "faber_sma10": "Faber 10-Month SMA",
    "risk_parity": "Risk Parity (SPY/TLT/GLD/SHY)",
    "composite_momentum": "Composite Momentum (6+12mo)",
    "vaa": "VAA (Vigilant Asset Allocation)",
    "aurum_momentum": "Aurum Multi-Period Momentum",
    "equity_rotation": "Equity Rotation (SPY/QQQ/VGT)",
}

STRATEGY_SUMMARIES: dict[str, str] = {
    "buy_and_hold": "Buy on day one and hold — the benchmark every other strategy is measured against.",
    "vol_target": "Scales exposure up in calm markets and down when volatility spikes, targeting 15% annual volatility.",
    "dual_momentum": "Holds the stock when its 12-month return beats short-term Treasuries (SHY), otherwise holds SHY.",
    "sma_crossover": "Buys when a short simple moving average crosses above a long one, and sells on the reverse.",
    "ema_crossover": "Same as SMA crossover but uses exponential averages that weight recent prices more heavily.",
    "rsi": "Buys when RSI falls below 30 (oversold) and sells when it rises above 70 (overbought).",
    "macd": "Buys when the MACD line crosses above its signal line, and sells on a bearish cross.",
    "bollinger": "Buys near the lower Bollinger Band and sells near the upper band.",
    "absolute_momentum": "Holds the stock when its 12-month return is positive, otherwise stays in cash.",
    "trend_filter": "Holds only when price is above the 200-day moving average, exiting on a break below.",
    "hybrid_regime": "Detects the market regime each month and switches to the best-suited strategy for that environment.",
    "hybrid_vol_crisis": "Uses vol targeting in normal markets and switches to dual momentum only during crisis regimes.",
    "gem_dual_momentum": "Antonacci GEM: monthly rotation among SPY, EFA, and SHY using absolute and relative momentum.",
    "faber_sma10": "Meb Faber rule: hold when price is above the 10-month moving average, otherwise stay in cash.",
    "risk_parity": "Inverse-volatility weights across SPY, TLT, GLD, and SHY, rebalanced monthly.",
    "composite_momentum": "Blends 6- and 12-month momentum; holds the stock when the composite score is positive, else SHY.",
    "vaa": "Keller VAA-G4: 13612 momentum breadth rotation among offensive ETFs (SPY/EFA/EEM/IWM) or defensive bonds.",
    "aurum_momentum": "Vol-adjusted 1/3/6/12-month momentum rotation across equities and defensive assets (Aurum-style).",
    "equity_rotation": "Monthly rotation to the strongest 3-month performer among SPY, QQQ, and VGT; exits to SHY when SPY is below its 200-day average.",
}

PLOTLY_MOBILE_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "zoom2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
    ],
    "doubleClick": False,
}


def strategy_label(name: str) -> str:
    return STRATEGY_LABELS.get(name, name.replace("_", " ").title())


def strategy_summary(name: str) -> str:
    return STRATEGY_SUMMARIES.get(
        name,
        "A rules-based trading strategy applied to the selected symbol.",
    )


def comparison_figure(
    curves: dict[str, pd.Series],
    *,
    title: str,
    start_cash: float,
) -> go.Figure:
    fig = go.Figure()

    for name, series in curves.items():
        if series.empty:
            continue
        color = STRATEGY_COLORS.get(name, "#94a3b8")
        line_style = dict(color=color, width=2.5 if name == "buy_and_hold" else 2)
        if name == "buy_and_hold":
            line_style["dash"] = "dash"

        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                mode="lines",
                name=strategy_label(name),
                line=line_style,
                hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra>%{fullData.name}</extra>",
            )
        )

    fig.add_hline(
        y=start_cash,
        line_dash="dot",
        line_color="#64748b",
        annotation_text="Start cash",
        annotation_position="bottom right",
    )

    fig.update_layout(
        template="plotly_dark",
        title=title,
        height=480,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        dragmode=False,
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True, thickness=0.08),
            type="date",
            fixedrange=True,
        ),
        yaxis=dict(title="Account value ($)", fixedrange=True, tickformat="$,.0f"),
    )

    return fig


CRASH_LABEL_SHORT: dict[str, str] = {
    "Dot-com bust": "Dot-com",
    "Global Financial Crisis": "GFC",
    "2011 debt crisis": "2011",
    "2018 Q4 selloff": "2018",
    "COVID crash": "COVID",
    "2022 bear market": "2022",
}


def _crash_chart_span(
    event: object,
    x_min: pd.Timestamp,
    x_max: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp] | None:
    peak = pd.Timestamp(event.peak)
    trough = pd.Timestamp(event.trough)
    x0 = max(peak, x_min)
    x1 = min(trough, x_max)
    if x0 >= x1:
        return None
    return x0, x1, peak


def _add_crash_markers(
    fig: go.Figure,
    event: object,
    *,
    x_min: pd.Timestamp,
    x_max: pd.Timestamp,
    rows: tuple[int, ...] = (1, 2),
) -> None:
    span = _crash_chart_span(event, x_min, x_max)
    if span is None:
        return
    x0, x1, peak = span
    mid = x0 + (x1 - x0) / 2
    label = CRASH_LABEL_SHORT.get(event.name, event.name[:8])

    for row in rows:
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor="rgba(248, 113, 113, 0.18)",
            line_width=1,
            line_color="rgba(248, 113, 113, 0.45)",
            layer="below",
            row=row,
            col=1,
        )
        fig.add_vline(
            x=peak,
            line_width=1,
            line_dash="dot",
            line_color="rgba(248, 113, 113, 0.7)",
            row=row,
            col=1,
        )

    yref_top = {1: "y domain", 2: "y2 domain"}
    for row in rows:
        fig.add_annotation(
            x=mid,
            y=0.98,
            xref="x",
            yref=yref_top[row],
            text=label,
            showarrow=False,
            yanchor="top",
            font=dict(size=10, color="#fca5a5"),
            bgcolor="rgba(26, 31, 46, 0.75)",
            borderpad=2,
        )


def crash_warning_nasdaq_figure(
    nasdaq: pd.Series,
    composite_score: pd.Series,
    crashes: list,
) -> go.Figure:
    """Stacked NASDAQ + crash score charts (mobile-friendly, shared timeline)."""
    from plotly.subplots import make_subplots

    if len(nasdaq) > 520:
        nasdaq = nasdaq.resample("W").last().dropna()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.58, 0.42],
        subplot_titles=("NASDAQ (start = 100)", "6-month crash probability (quarterly)"),
    )

    x_min = min(
        nasdaq.index.min() if not nasdaq.empty else pd.Timestamp.max,
        composite_score.index.min() if not composite_score.empty else pd.Timestamp.max,
    )
    x_max = max(
        nasdaq.index.max() if not nasdaq.empty else pd.Timestamp.min,
        composite_score.index.max() if not composite_score.empty else pd.Timestamp.min,
    )

    for event in crashes:
        _add_crash_markers(fig, event, x_min=x_min, x_max=x_max, rows=(1, 2))

    if not nasdaq.empty:
        fig.add_trace(
            go.Scatter(
                x=nasdaq.index,
                y=nasdaq.values,
                mode="lines",
                line=dict(color="#c084fc", width=2),
                hovertemplate="%{x|%b %Y}<br>%{y:.0f}<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    if not composite_score.empty:
        fig.add_trace(
            go.Scatter(
                x=composite_score.index,
                y=composite_score.values,
                mode="lines",
                line=dict(color="#60a5fa", width=2.5, shape="spline"),
                fill="tozeroy",
                fillcolor="rgba(96,165,250,0.2)",
                hovertemplate="%{x|%b %Y}<br>%{y:.0f}%<extra></extra>",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    alert_pct = CRASH_ALERT_THRESHOLD * 100.0
    fig.add_hline(y=alert_pct, line_dash="dot", line_color="#f87171", row=2, col=1)

    prob_max = float(composite_score.max()) if not composite_score.empty else 100.0

    fig.update_layout(
        template="plotly_dark",
        height=560,
        margin=dict(l=44, r=12, t=36, b=40),
        hovermode="x unified",
        dragmode=False,
    )
    fig.update_xaxes(type="date", fixedrange=True, showticklabels=False, row=1, col=1)
    fig.update_xaxes(type="date", fixedrange=True, title_text="", row=2, col=1)
    fig.update_yaxes(title_text="", fixedrange=True, row=1, col=1)
    fig.update_yaxes(
        title_text="",
        fixedrange=True,
        range=[0, max(100.0, prob_max * 1.05)],
        row=2,
        col=1,
    )
    fig.update_annotations(font_size=12)

    return fig
