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
