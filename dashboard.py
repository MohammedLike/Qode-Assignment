import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from qode_backtest.config import StrategyConfig
from qode_backtest.engine import run_pipeline
from qode_backtest.timing import TIMINGS

st.set_page_config(page_title="Bank Nifty Strangle Backtest", layout="wide")
st.title("Bank Nifty 09:20 Short Strangle Backtest")

with st.sidebar:
    st.header("Strategy Parameters")
    premium = st.slider("Target Premium (Rs.)", 40.0, 60.0, 50.0, 1.0)
    sl_mult = st.slider("SL Multiplier", 1.2, 2.0, 1.5, 0.1)
    lot_size = st.number_input("Lot Size", 1, 30, 15)
    use_cache = st.checkbox("Use Parquet Cache", value=True)
    run_btn = st.button("Run Backtest", type="primary")

if run_btn:
    cfg = StrategyConfig(
        target_premium=premium,
        sl_multiplier=sl_mult,
        lot_size=int(lot_size),
        use_parquet_cache=use_cache,
    )
    with st.spinner("Running backtest..."):
        tradesheet, stats, _ = run_pipeline(cfg, export=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CAGR", f"{stats['cagr'] * 100:.2f}%")
    c2.metric("Max Drawdown", f"{stats['max_dd']:.2f}%")
    c3.metric("Sharpe", stats["risk_metrics"]["Sharpe Ratio"])
    c4.metric("Final NAV", f"{stats['nav'].iloc[-1]:.2f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=stats["nav"].index, y=stats["nav"].values, mode="lines", name="NAV"))
    fig.update_layout(title="Equity Curve", xaxis_title="Date", yaxis_title="NAV", height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Runtime Breakdown")
    st.dataframe(pd.DataFrame({"Step": list(TIMINGS.keys()), "Seconds": list(TIMINGS.values())}))

    st.subheader("Trades")
    st.dataframe(tradesheet, use_container_width=True)
else:
    st.info("Adjust parameters in the sidebar and click **Run Backtest**.")
