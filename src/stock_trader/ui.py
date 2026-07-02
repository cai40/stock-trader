from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import YFinanceMarketData
from stock_trader.models import BacktestResult, OrderSide, PortfolioBacktestResult, Trade
from stock_trader.strategies import get_strategy, list_strategies

MARKET_DATA = YFinanceMarketData()
ENGINE = BacktestEngine(MARKET_DATA)

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
    st.caption("Paper trading & backtesting — educational use only")


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
        xaxis_title="Date",
        yaxis_title="Price ($)",
    )
    st.plotly_chart(fig, use_container_width=True)


def tab_quote() -> None:
    st.subheader("Live quote")
    symbol = st.text_input("Symbol", value="AAPL", placeholder="e.g. AAPL").upper().strip()

    if st.button("Get quote", type="primary", use_container_width=True):
        if not symbol:
            st.error("Enter a ticker symbol.")
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


def tab_backtest() -> None:
    st.subheader("Backtest")
    symbol = st.text_input("Symbol", value="AAPL", key="bt_symbol").upper().strip()
    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=pd.Timestamp("2023-01-01"))
    end = col2.date_input("End", value=pd.Timestamp("2024-01-01"))
    strategy = st.selectbox("Strategy", list_strategies())
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0)

    if st.button("Run backtest", type="primary", use_container_width=True):
        if not symbol:
            st.error("Enter a ticker symbol.")
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
        price_chart(symbol, start.isoformat(), end.isoformat(), result.trades)
        if result.trades:
            st.dataframe(trades_dataframe(result.trades), use_container_width=True, hide_index=True)


def tab_paper_trade() -> None:
    st.subheader("Paper trade")
    st.caption("Shared portfolio — one cash pool across all symbols")
    symbols_raw = st.text_input("Symbols (comma-separated)", value="AAPL, MSFT")
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
    col1, col2 = st.columns(2)
    start = col1.date_input("Start", value=pd.Timestamp("2023-01-01"), key="pt_start")
    end = col2.date_input("End", value=pd.Timestamp("2024-01-01"), key="pt_end")
    strategy = st.selectbox("Strategy", list_strategies(), key="pt_strategy")
    cash = st.number_input("Starting cash ($)", min_value=100.0, value=10_000.0, step=500.0, key="pt_cash")

    if st.button("Run paper trade", type="primary", use_container_width=True):
        if not symbols:
            st.error("Enter at least one symbol.")
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
    quote_tab, backtest_tab, paper_tab = st.tabs(["Quote", "Backtest", "Paper trade"])

    with quote_tab:
        tab_quote()
    with backtest_tab:
        tab_backtest()
    with paper_tab:
        tab_paper_trade()

    st.divider()
    st.caption("Not financial advice. Past performance does not guarantee future results.")


if __name__ == "__main__":
    main()
