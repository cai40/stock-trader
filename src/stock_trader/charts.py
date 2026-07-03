from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

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
