from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_trader.backtest import BacktestEngine
from stock_trader.charts import PLOTLY_MOBILE_CONFIG, comparison_figure, strategy_label
from stock_trader.market_data import YFinanceMarketData
from stock_trader.models import BacktestResult, OrderSide, PortfolioBacktestResult, Trade
from stock_trader.strategies import get_strategy, list_strategies
from stock_trader.watchlist import CUSTOM_OPTION, label_to_symbol, watchlist_labels, watchlist_select_options

APP_VERSION = "0.3.7"

DEFAULT_START = pd.Timestamp("2013-01-01")
DEFAULT_END = pd.Timestamp("2026-06-01")

COMPARE_OPTIONS = ["buy_and_hold", "vol_target", "dual_momentum", *list_strategies()]

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
        "Use the range slider below the chart to change the visible period. "
        "On long bull runs, **Vol Target** scales exposure up in calm markets and can beat buy-and-hold. "
        "Trend/momentum strategies reduce drawdowns but often lag in straight rallies."
    )

    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=DEFAULT_START, key=f"cmp_start_{APP_VERSION}")
    end = col2.date_input("End", value=DEFAULT_END, key=f"cmp_end_{APP_VERSION}")
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0, key=f"cmp_cash_{APP_VERSION}")

    selected = st.multiselect(
        "Strategies to plot",
        options=COMPARE_OPTIONS,
        default=COMPARE_OPTIONS,
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
                    "Max drawdown": f"{result.max_drawdown * 100:.2f}%",
                    "Trades": result.trade_count,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


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

    quote_tab, backtest_tab, compare_tab, paper_tab = st.tabs(
        ["Quote", "Backtest", "Compare", "Paper trade"]
    )

    with quote_tab:
        tab_quote(symbol)
    with backtest_tab:
        tab_backtest(symbol)
    with compare_tab:
        tab_compare(symbol)
    with paper_tab:
        tab_paper_trade()

    st.divider()
    st.caption("Not financial advice. Past performance does not guarantee future results.")


if __name__ == "__main__":
    main()
