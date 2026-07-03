from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_trader.backtest import BacktestEngine
from stock_trader.crash_backtest import backtest_summary_markdown, run_crash_score_backtest
from stock_trader.leading_crash import CRASH_ALERT_THRESHOLD, leading_crash_probability_chart
from stock_trader.crash_warning import (
    DEFAULT_CRASH_HISTORY_START,
    RISK_LABELS,
    SignalTier,
    crash_score_guide_markdown,
    crashes_in_range,
    load_crash_panel,
    nasdaq_normalized,
    risk_level_color,
)
from stock_trader.charts import (
    PLOTLY_MOBILE_CONFIG,
    comparison_figure,
    crash_warning_nasdaq_figure,
    strategy_label,
    strategy_summary,
)
from stock_trader.market_data import YFinanceMarketData
from stock_trader.models import BacktestResult, OrderSide, PortfolioBacktestResult, Trade
from stock_trader.strategies import get_strategy, list_strategies
from stock_trader.watchlist import CUSTOM_OPTION, label_to_symbol, watchlist_labels, watchlist_select_options

APP_VERSION = "0.8.0"

DEFAULT_START = pd.Timestamp("2013-01-01")
DEFAULT_END = pd.Timestamp("2026-06-01")

RESEARCH_STRATEGIES = [
    "buy_and_hold",
    "vol_target",
    "hybrid_vol_crisis",
    "vaa",
    "aurum_momentum",
    "equity_rotation",
    "gem_dual_momentum",
    "faber_sma10",
    "risk_parity",
    "composite_momentum",
    "dual_momentum",
]

COMPARE_OPTIONS = [
    *RESEARCH_STRATEGIES,
    "hybrid_regime",
    *list_strategies(),
]

MARKET_DATA = YFinanceMarketData()
ENGINE = BacktestEngine(MARKET_DATA)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    return MARKET_DATA.get_history(symbol, start=start, end=end)

PAGE_CSS = """
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 720px; }
    .metric-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin-bottom: 0.5rem;
    }
    .quote-price { font-size: 2.4rem; font-weight: 700; color: #4ade80; line-height: 1.1; }
    .quote-symbol { font-size: 1rem; color: #94a3b8; letter-spacing: 0.08em; }
    .picker-box {
        background: #1a1f2e;
        border: 1px solid #4ade80;
        border-radius: 12px;
        padding: 0.75rem 1rem 0.25rem 1rem;
        margin: 0.75rem 0 1rem 0;
    }
    div[data-testid="stMetric"] {
        background: #1a1f2e;
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 0.75rem;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 0.5rem 1rem;
        background: #1a1f2e;
    }
    @media (max-width: 768px) {
        .block-container { max-width: 100% !important; padding-left: 0.5rem; padding-right: 0.5rem; }
        .stTabs [data-baseweb="tab"] { font-size: 0.78rem; padding: 0.35rem 0.55rem; }
        div[data-testid="stMetric"] label { font-size: 0.75rem; }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.1rem; }
    }
</style>
"""


def configure_page() -> None:
    st.set_page_config(
        page_title="Stock Trader",
        page_icon="📈",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


def render_header() -> None:
    st.title("📈 Stock Trader")
    version_line = f"Paper trading & backtesting · v{APP_VERSION}"
    commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if commit:
        version_line += f" · {commit[:7]}"
    st.caption(version_line)


def render_strategy_guide_button() -> None:
    if st.button(
        "What do the strategies do?",
        key=f"strategy_guide_btn_{APP_VERSION}",
        use_container_width=True,
    ):
        st.session_state["strategy_guide_open"] = not st.session_state.get(
            "strategy_guide_open", False
        )

    if st.session_state.get("strategy_guide_open"):
        with st.container(border=True):
            st.markdown("**Strategy guide** — one sentence each:")
            for name in COMPARE_OPTIONS:
                st.markdown(f"**{strategy_label(name)}** — {strategy_summary(name)}")
            st.markdown("**Hybrid Regime** switches by detected market period:")
            from stock_trader.regime import REGIME_STRATEGY, regime_label as regime_name

            for regime, strategy in REGIME_STRATEGY.items():
                st.markdown(
                    f"- **{regime_name(regime)}** → {strategy_label(strategy)}"
                )


def pick_symbol(key_prefix: str, *, default_symbol: str = "VGT") -> str:
    options = watchlist_select_options()
    default_index = next(
        (i for i, opt in enumerate(options) if opt.startswith(default_symbol)),
        0,
    )

    st.markdown("**📋 Pick a stock / ETF**")
    selection = st.selectbox(
        "Stock / ETF",
        options=options,
        index=default_index,
        key=f"{key_prefix}_watchlist",
        label_visibility="collapsed",
    )

    if selection == CUSTOM_OPTION:
        symbol = st.text_input(
            "Enter custom ticker",
            value=default_symbol,
            key=f"{key_prefix}_custom",
        ).upper().strip()
    else:
        symbol = label_to_symbol(selection) or default_symbol
        st.caption(f"Selected: **{symbol}**")

    return symbol


def pick_symbols_multiselect(key: str) -> list[str]:
    default_labels = [
        label
        for label in watchlist_labels()
        if label.startswith(("VGT", "SPY", "TEL"))
    ]

    selected_labels = st.multiselect(
        "Stocks / ETFs",
        options=watchlist_labels(),
        default=default_labels,
        key=key,
        label_visibility="visible",
    )

    return [label_to_symbol(label) or label.split(" — ")[0] for label in selected_labels]


def trades_dataframe(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["Symbol", "Side", "Qty", "Price", "Time"])

    return pd.DataFrame(
        [
            {
                "Symbol": trade.symbol,
                "Side": trade.side.value.upper(),
                "Qty": int(trade.quantity),
                "Price": f"${trade.price:,.2f}",
                "Time": trade.timestamp.strftime("%Y-%m-%d"),
            }
            for trade in trades
        ]
    )


def render_metrics(result: BacktestResult | PortfolioBacktestResult) -> None:
    cols = st.columns(2)
    cols[0].metric("End equity", f"${result.end_equity:,.2f}")
    cols[1].metric("Total return", f"{result.total_return * 100:.2f}%")
    cols = st.columns(2)
    cols[0].metric("Max drawdown", f"{result.max_drawdown * 100:.2f}%")
    cols[1].metric("Win rate", f"{result.win_rate * 100:.1f}%")
    st.metric("Trades", result.trade_count)


def price_chart(symbol: str, start: str, end: str, trades: list[Trade]) -> None:
    try:
        history = MARKET_DATA.get_history(symbol, start=start, end=end)
    except ValueError as exc:
        st.warning(str(exc))
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history.index,
            y=history["Close"],
            mode="lines",
            name="Close",
            line=dict(color="#60a5fa", width=2),
        )
    )

    buys = [t for t in trades if t.side is OrderSide.BUY]
    sells = [t for t in trades if t.side is OrderSide.SELL]

    if buys:
        fig.add_trace(
            go.Scatter(
                x=[t.timestamp for t in buys],
                y=[t.price for t in buys],
                mode="markers",
                name="Buy",
                marker=dict(color="#4ade80", size=12, symbol="triangle-up"),
            )
        )
    if sells:
        fig.add_trace(
            go.Scatter(
                x=[t.timestamp for t in sells],
                y=[t.price for t in sells],
                mode="markers",
                name="Sell",
                marker=dict(color="#f87171", size=12, symbol="triangle-down"),
            )
        )

    fig.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=10, r=10, t=30, b=10),
        title=f"{symbol} price & trades",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        dragmode=False,
        xaxis=dict(title="Date", fixedrange=True),
        yaxis=dict(title="Price ($)", fixedrange=True),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)


def equity_chart(result: BacktestResult, *, title: str) -> None:
    if result.equity_curve.empty:
        return
    fig = comparison_figure(
        {result.strategy_name: result.equity_curve},
        title=title,
        start_cash=result.start_cash,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)


def tab_quote(symbol: str) -> None:
    st.subheader("Live quote")

    if st.button("Get quote", type="primary", use_container_width=True):
        if not symbol:
            st.error("Pick a stock from the dropdown above.")
            return
        try:
            quote = MARKET_DATA.get_quote(symbol)
        except ValueError as exc:
            st.error(str(exc))
            return

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="quote-symbol">{quote.symbol}</div>
                <div class="quote-price">${quote.price:,.2f}</div>
                <div style="color:#94a3b8; margin-top:0.4rem;">
                    {quote.timestamp.strftime("%b %d, %Y · %H:%M UTC")}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def tab_backtest(symbol: str) -> None:
    st.subheader("Backtest")
    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=DEFAULT_START, key=f"bt_start_{APP_VERSION}")
    end = col2.date_input("End", value=DEFAULT_END, key=f"bt_end_{APP_VERSION}")
    strategy = st.selectbox("Strategy", list_strategies())
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0)

    if st.button("Run backtest", type="primary", use_container_width=True):
        if not symbol:
            st.error("Pick a stock from the dropdown above.")
            return
        if start >= end:
            st.error("End date must be after start date.")
            return

        with st.spinner(f"Running {strategy} on {symbol}..."):
            try:
                result = ENGINE.run(
                    symbol,
                    get_strategy(strategy),
                    start=start.isoformat(),
                    end=end.isoformat(),
                    initial_cash=cash,
                )
            except ValueError as exc:
                st.error(str(exc))
                return

        st.success("Backtest complete")
        render_metrics(result)
        equity_chart(result, title=f"{symbol} account value — {strategy_label(strategy)}")
        price_chart(symbol, start.isoformat(), end.isoformat(), result.trades)
        if result.trades:
            st.dataframe(trades_dataframe(result.trades), use_container_width=True, hide_index=True)


def tab_compare(symbol: str) -> None:
    st.subheader("Compare strategies")
    st.caption(
        "Research-backed strategies are selected by default. "
        "Multi-asset strategies (VAA, Aurum, GEM, Risk Parity, Equity Rotation) rotate "
        "across ETF baskets and ignore the selected symbol for allocation. "
        "Table is sorted by Sharpe ratio (risk-adjusted return)."
    )

    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=DEFAULT_START, key=f"cmp_start_{APP_VERSION}")
    end = col2.date_input("End", value=DEFAULT_END, key=f"cmp_end_{APP_VERSION}")
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0, key=f"cmp_cash_{APP_VERSION}")

    selected = st.multiselect(
        "Strategies to plot",
        options=COMPARE_OPTIONS,
        default=RESEARCH_STRATEGIES,
        format_func=strategy_label,
        key=f"cmp_strategies_{APP_VERSION}",
    )

    if st.button("Run comparison", type="primary", use_container_width=True):
        if not symbol:
            st.error("Pick a stock from the dropdown above.")
            return
        if not selected:
            st.error("Select at least one strategy.")
            return
        if start >= end:
            st.error("End date must be after start date.")
            return

        with st.spinner(f"Running {len(selected)} strategies on {symbol}..."):
            try:
                comparison = ENGINE.compare_strategies(
                    symbol,
                    start=start.isoformat(),
                    end=end.isoformat(),
                    initial_cash=cash,
                    strategy_names=selected,
                )
            except ValueError as exc:
                st.error(str(exc))
                return

        st.success("Comparison ready")

        fig = comparison_figure(
            comparison.curves,
            title=f"{symbol} account value by strategy",
            start_cash=cash,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)

        rows = []
        for name in selected:
            result = comparison.results[name]
            rows.append(
                {
                    "Strategy": strategy_label(name),
                    "End equity": f"${result.end_equity:,.2f}",
                    "Return": f"{result.total_return * 100:.2f}%",
                    "Sharpe": result.sharpe_ratio,
                    "Max drawdown": f"{result.max_drawdown * 100:.2f}%",
                    "Trades": result.trade_count,
                }
            )
        summary = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
        summary["Sharpe"] = summary["Sharpe"].map(lambda value: f"{value:.2f}")
        st.dataframe(summary, use_container_width=True, hide_index=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_crash_backtest(start: str, end: str) -> object:
    panel, features, _ = load_crash_panel(start, end, MARKET_DATA)
    nasdaq = panel["IXIC"].reindex(features.index).ffill()
    return run_crash_score_backtest(features, nasdaq)


def tab_crash_warning() -> None:
    st.subheader("Crash early warning")
    st.caption(
        "**Leading** 12-month NASDAQ crash probability — macro/market precursors only. "
        "Suppressed during selloffs. Alerts at **≥80%** when credit/breadth patterns match."
    )

    if st.button(
        "How is the crash score calculated?",
        key=f"crash_score_guide_btn_{APP_VERSION}",
        use_container_width=True,
    ):
        st.session_state["crash_score_guide_open"] = not st.session_state.get(
            "crash_score_guide_open", False
        )

    if st.session_state.get("crash_score_guide_open"):
        with st.container(border=True):
            st.markdown(crash_score_guide_markdown())

    with st.expander("What is VIX?"):
        st.markdown(
            """
            **VIX** (CBOE Volatility Index) is often called the market **“fear gauge.”**
            It measures how much **implied volatility** traders expect on the S&P 500 over the
            next ~30 days, derived from options prices.

            - **Low VIX (≈12–18):** calm markets, investors complacent
            - **High VIX (≈30+):** stress, hedging demand, often during selloffs
            - **VIX z-score:** how unusual today’s VIX is vs the past year

            Our crash dashboard uses VIX level, VIX z-score, and **VIX minus realized volatility**
            (implied fear vs what actually happened). VIX often **spikes during** crashes; it is a
            coincident stress indicator, not a perfect early-warning signal on its own.
            """
        )

    col1, col2 = st.columns(2)
    start = col1.date_input(
        "History start",
        value=pd.Timestamp(DEFAULT_CRASH_HISTORY_START),
        min_value=pd.Timestamp("1990-01-01"),
        key=f"cw_start_{APP_VERSION}",
    )
    end = col2.date_input(
        "As of",
        value=DEFAULT_END,
        key=f"cw_end_{APP_VERSION}",
    )

    if st.button("Refresh crash dashboard", type="primary", use_container_width=True):
        if start >= end:
            st.error("End date must be after start date.")
            return

        with st.spinner("Loading macro panel (SPY, NASDAQ, VIX, yields, credit)..."):
            try:
                panel, features, assessment = load_crash_panel(
                    start.isoformat(),
                    end.isoformat(),
                    MARKET_DATA,
                )
            except ValueError as exc:
                st.error(str(exc))
                return

        st.session_state["crash_assessment"] = assessment
        st.session_state["crash_features"] = features
        st.session_state["crash_panel"] = panel
        st.session_state["crash_start"] = start.isoformat()
        st.session_state["crash_end"] = end.isoformat()

    assessment: object = st.session_state.get("crash_assessment")
    features: object = st.session_state.get("crash_features")
    panel: object = st.session_state.get("crash_panel")
    if assessment is None or features is None or panel is None:
        st.info("Press **Refresh crash dashboard** to load the latest readings.")
        return

    color = risk_level_color(assessment.risk_level)
    st.markdown(
        f"""
        <div class="metric-card" style="border-color:{color};">
            <div style="color:#94a3b8; font-size:0.9rem;">Risk level · {assessment.as_of.strftime("%b %d, %Y")}</div>
            <div style="font-size:2rem; font-weight:700; color:{color};">
                {RISK_LABELS[assessment.risk_level]}
            </div>
            <div style="color:#cbd5e1; margin-top:0.5rem;">{assessment.action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if assessment.fake_panic:
        st.warning(f"**Fake panic filter:** {assessment.fake_panic_reason}")

    if assessment.high_confidence_alert:
        st.error(
            f"**Leading crash alert ({assessment.crash_probability:.0%}, {assessment.horizon_months}mo)** — "
            f"*{assessment.probability_rule}*"
        )
    elif not assessment.leading_eligible:
        st.warning(
            "**Leading score inactive** — market already in selloff. "
            "See live stress indicators below."
        )

    m1, m2 = st.columns(2)
    m1.metric(
        f"{assessment.horizon_months}mo leading probability",
        f"{assessment.crash_probability:.0%}",
        delta="≥80% alert" if assessment.high_confidence_alert else None,
        delta_color="inverse" if assessment.high_confidence_alert else "off",
    )
    m2.metric("Pattern", assessment.probability_rule[:36] + ("…" if len(assessment.probability_rule) > 36 else ""))
    m3, m4 = st.columns(2)
    m3.metric(
        "Macro / market / NASDAQ",
        f"{assessment.macro_count}/{assessment.market_count}/{assessment.nasdaq_count}",
    )
    row = features.iloc[-1]
    m4.metric("Live stress", f"{assessment.stress_score:.0f}/4")
    m5, m6 = st.columns(2)
    m5.metric("VIX", f"{row.get('vix', float('nan')):.1f}" if pd.notna(row.get("vix")) else "—")
    m6.metric("Signal score (legacy)", f"{assessment.composite_score:.1f}")

    predictive_rows = []
    stress_rows = []
    for status in assessment.signals:
        entry = {
            "Signal": status.rule.label,
            "On": "Yes" if status.active else "—",
            "Value": status.display_value,
        }
        if status.rule.tier is SignalTier.COINCIDENT:
            stress_rows.append(entry)
        else:
            predictive_rows.append(entry)

    st.markdown("**Predictive signals** (count toward score)")
    st.dataframe(pd.DataFrame(predictive_rows), use_container_width=True, hide_index=True)
    if stress_rows:
        st.markdown("**Live stress** (during selloffs — not in score)")
        st.dataframe(pd.DataFrame(stress_rows), use_container_width=True, hide_index=True)

    start_ts = pd.Timestamp(st.session_state.get("crash_start", start))
    end_ts = pd.Timestamp(st.session_state.get("crash_end", end))
    score = leading_crash_probability_chart(features)
    nasdaq = nasdaq_normalized(panel, start_ts)
    events = crashes_in_range(start_ts, end_ts)

    overlay = crash_warning_nasdaq_figure(nasdaq, score, events)
    st.plotly_chart(overlay, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)
    st.caption(f"Red line = {CRASH_ALERT_THRESHOLD:.0%} leading alert · shaded bands = historical crashes")

    if events:
        event_rows = [
            {"Crash": e.name, "Peak": e.peak, "Trough": e.trough}
            for e in events
        ]
        st.caption("Historical crash episodes in selected range")
        st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)

    with st.expander("Backtest validation (leading, 12-month horizon)"):
        st.caption(
            "When leading probability ≥ 80% (and not in selloff), "
            "what fraction saw a 15%+ NASDAQ drawdown within 12 months?"
        )
        try:
            bt = fetch_crash_backtest(
                st.session_state.get("crash_start", start.isoformat()),
                st.session_state.get("crash_end", end.isoformat()),
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("AUC 12mo", f"{bt.auc_12m:.2f}")
            c2.metric("Actual @ ≥80%", f"{bt.crash_prob_at_alert:.0%}")
            c3.metric("Precision", f"{bt.alert_precision_12m:.0%}")
            edge = bt.crash_prob_at_alert - bt.crash_prob_baseline
            c4.metric("Edge vs baseline", f"{edge:+.1%}")
            st.markdown(backtest_summary_markdown(bt))
        except ValueError as exc:
            st.warning(str(exc))

    if "vix" in features.columns and "vol_20d" in features.columns:
        vix_fig = go.Figure()
        vix_fig.add_trace(
            go.Scatter(
                x=features.index,
                y=features["vix"],
                mode="lines",
                name="VIX",
                line=dict(color="#f87171", width=2),
            )
        )
        vix_fig.add_trace(
            go.Scatter(
                x=features.index,
                y=features["vol_20d"] * 100,
                mode="lines",
                name="Realized vol (%)",
                line=dict(color="#60a5fa", width=2),
            )
        )
        vix_fig.update_layout(
            template="plotly_dark",
            title="VIX (fear gauge) vs 20-day realized volatility",
            height=300,
            margin=dict(l=10, r=10, t=50, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            dragmode=False,
            xaxis=dict(fixedrange=True),
            yaxis=dict(title="Level", fixedrange=True),
        )
        st.plotly_chart(vix_fig, use_container_width=True, config=PLOTLY_MOBILE_CONFIG)


def tab_paper_trade() -> None:
    st.subheader("Paper trade")
    st.caption("Shared portfolio — one cash pool across all symbols")
    symbols = pick_symbols_multiselect("pt_symbols")
    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=DEFAULT_START, key=f"pt_start_{APP_VERSION}")
    end = col2.date_input("End", value=DEFAULT_END, key=f"pt_end_{APP_VERSION}")
    strategy = st.selectbox("Strategy", list_strategies(), key="pt_strategy")
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0, key="pt_cash")

    if st.button("Run paper trade", type="primary", use_container_width=True):
        if not symbols:
            st.error("Select at least one stock or ETF.")
            return
        if start >= end:
            st.error("End date must be after start date.")
            return

        with st.spinner(f"Simulating {', '.join(symbols)}..."):
            try:
                result = ENGINE.run_portfolio(
                    symbols,
                    get_strategy(strategy),
                    start=start.isoformat(),
                    end=end.isoformat(),
                    initial_cash=cash,
                )
            except ValueError as exc:
                st.error(str(exc))
                return

        st.success("Simulation complete")
        render_metrics(result)
        if result.trades:
            st.dataframe(trades_dataframe(result.trades), use_container_width=True, hide_index=True)
        else:
            st.info("No trades were generated for this period.")


def main() -> None:
    configure_page()
    render_header()

    symbol = pick_symbol("global", default_symbol="VGT")

    render_strategy_guide_button()

    quote_tab, backtest_tab, compare_tab, crash_tab, paper_tab = st.tabs(
        ["Quote", "Backtest", "Compare", "Crash warning", "Paper trade"]
    )

    with quote_tab:
        tab_quote(symbol)
    with backtest_tab:
        tab_backtest(symbol)
    with compare_tab:
        tab_compare(symbol)
    with crash_tab:
        tab_crash_warning()
    with paper_tab:
        tab_paper_trade()

    st.divider()
    st.caption("Not financial advice. Past performance does not guarantee future results.")


if __name__ == "__main__":
    main()
