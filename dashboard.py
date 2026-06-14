from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from qode_backtest.analytics import pnl_column
from qode_backtest.config import (
    DRAWDOWN_PNG,
    EQUITY_PNG,
    OUTPUT_XLSX,
    SENSITIVITY_PNG,
    StrategyConfig,
)
from qode_backtest.engine import run_pipeline
from qode_backtest.export import export_excel, save_plots
from qode_backtest.timing import TIMINGS

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(page_title="Bank Nifty Strangle Backtest", layout="wide")
st.title("Bank Nifty 09:20 Short Strangle Backtest")

if "result" not in st.session_state:
    st.session_state.result = None


def _filter_trades(tradesheet: pd.DataFrame) -> pd.DataFrame:
    df = tradesheet.copy()
    opt_types = st.multiselect("Option type", ["CE", "PE"], default=["CE", "PE"])
    if opt_types:
        df = df[df["Option Type"].isin(opt_types)]
    exit_reasons = st.multiselect(
        "Exit reason", ["Stop Loss", "Scheduled Exit"], default=["Stop Loss", "Scheduled Exit"]
    )
    if exit_reasons:
        df = df[df["Exit Reason"].isin(exit_reasons)]
    day_types = st.multiselect("Day type", ["Expiry", "Non-expiry"], default=["Expiry", "Non-expiry"])
    if "Expiry" in day_types and "Non-expiry" not in day_types:
        df = df[df["Is Expiry Day"]]
    elif "Non-expiry" in day_types and "Expiry" not in day_types:
        df = df[~df["Is Expiry Day"]]
    return df


def _nav_chart(stats: dict, cfg: StrategyConfig, tradesheet: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.08)
    fig.add_trace(
        go.Scatter(x=stats["nav"].index, y=stats["nav"].values, mode="lines", name="Strategy NAV"),
        row=1,
        col=1,
    )
    bench = stats.get("benchmark_nav")
    if bench is not None and len(bench) > 1:
        fig.add_trace(
            go.Scatter(
                x=bench.index, y=bench.values, mode="lines", name="Bank Nifty B&H", line=dict(dash="dot")
            ),
            row=1,
            col=1,
        )
    if cfg.realism_enabled and "Gross P&L" in tradesheet.columns:
        from qode_backtest.analytics import _nav_from_column

        ideal_nav = _nav_from_column(tradesheet, cfg, "Gross P&L")
        fig.add_trace(
            go.Scatter(
                x=ideal_nav.index,
                y=ideal_nav.values,
                mode="lines",
                name="Ideal NAV (no costs)",
                line=dict(dash="dash"),
            ),
            row=1,
            col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=stats["drawdown"].index,
            y=stats["drawdown"].values,
            mode="lines",
            name="Drawdown %",
            fill="tozeroy",
            line=dict(color="#d62728"),
        ),
        row=2,
        col=1,
    )
    fig.update_layout(height=520, title="Equity Curve & Drawdown", showlegend=True)
    fig.update_yaxes(title_text="NAV", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    return fig


def _sweep_heatmap(sweep_df: pd.DataFrame) -> go.Figure:
    pivot = sweep_df.pivot(index="target_premium", columns="sl_multiplier", values="cagr_pct")
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=[str(i) for i in pivot.index],
            colorscale="RdYlGn",
            colorbar=dict(title="CAGR %"),
        )
    )
    fig.update_layout(
        title="Parameter Sweep — CAGR % (Premium × SL Multiplier)",
        xaxis_title="SL Multiplier",
        yaxis_title="Target Premium (Rs.)",
        height=400,
    )
    return fig


with st.sidebar:
    st.header("Strategy Parameters")
    premium = st.slider("Target Premium (Rs.)", 40.0, 60.0, 50.0, 1.0)
    sl_mult = st.slider("SL Multiplier", 1.2, 2.0, 1.5, 0.1)
    lot_size = st.number_input("Lot Size", 1, 30, 15)
    use_cache = st.checkbox("Use Parquet Cache", value=True)
    realism = st.checkbox("Realism (slippage + brokerage)", value=True)
    run_sweep = st.checkbox("Run parameter sweep", value=False)
    run_btn = st.button("Run Backtest", type="primary")

if run_btn:
    cfg = StrategyConfig(
        target_premium=premium,
        sl_multiplier=sl_mult,
        lot_size=int(lot_size),
        use_parquet_cache=use_cache,
        realism_enabled=realism,
    )
    with st.spinner("Running backtest..."):
        tradesheet, stats, sweep_df = run_pipeline(cfg, export=False, run_sweep_analysis=run_sweep)
    st.session_state.result = {
        "cfg": cfg,
        "tradesheet": tradesheet,
        "stats": stats,
        "sweep_df": sweep_df,
    }

result = st.session_state.result
if result:
    cfg = result["cfg"]
    tradesheet = result["tradesheet"]
    stats = result["stats"]
    sweep_df = result.get("sweep_df")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("CAGR", f"{stats['cagr'] * 100:.2f}%")
    c2.metric("Max Drawdown", f"{stats['max_dd']:.2f}%")
    c3.metric("Sharpe", stats["risk_metrics"]["Sharpe Ratio"])
    c4.metric("Final NAV", f"{stats['nav'].iloc[-1]:.2f}")
    col = pnl_column(cfg)
    c5.metric("Total P&L", f"Rs. {tradesheet[col].sum():,.0f}")

    st.plotly_chart(_nav_chart(stats, cfg, tradesheet), use_container_width=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Trades", "Attribution", "Sweep", "Exports"])

    with tab1:
        st.subheader("Trade Filters")
        filtered = _filter_trades(tradesheet)
        st.dataframe(filtered, use_container_width=True, height=400)

    with tab2:
        attr = stats.get("attribution", {})
        if attr.get("day_of_week") is not None and not attr["day_of_week"].empty:
            st.subheader("P&L by Day of Week")
            st.dataframe(attr["day_of_week"], use_container_width=True)
            dow = attr["day_of_week"]
            fig_dow = go.Figure(go.Bar(x=dow["Weekday"], y=dow["Total P&L (INR)"], name="Total P&L"))
            fig_dow.update_layout(height=320, title="Total P&L by Weekday")
            st.plotly_chart(fig_dow, use_container_width=True)

        ce_pe = attr.get("ce_pe_daily")
        if ce_pe is not None and not ce_pe.empty:
            st.subheader("CE vs PE Daily Contribution")
            fig_ce = go.Figure()
            fig_ce.add_trace(go.Bar(x=ce_pe["Entry Date"], y=ce_pe["CE"], name="CE"))
            fig_ce.add_trace(go.Bar(x=ce_pe["Entry Date"], y=ce_pe["PE"], name="PE"))
            fig_ce.update_layout(barmode="relative", height=320, title="Stacked CE/PE Daily P&L")
            st.plotly_chart(fig_ce, use_container_width=True)

        if stats.get("realism_comparison") is not None and not stats["realism_comparison"].empty:
            st.subheader("Ideal vs Realistic")
            st.dataframe(stats["realism_comparison"], use_container_width=True)

        if stats.get("benchmark_summary") is not None and not stats["benchmark_summary"].empty:
            st.subheader("Benchmark Comparison")
            st.dataframe(stats["benchmark_summary"], use_container_width=True)

    with tab3:
        if sweep_df is not None and not sweep_df.empty:
            st.plotly_chart(_sweep_heatmap(sweep_df), use_container_width=True)
            st.dataframe(sweep_df, use_container_width=True)
        else:
            st.info("Enable **Run parameter sweep** in the sidebar to generate the heatmap.")

    with tab4:
        st.subheader("Download Outputs")
        if st.button("Generate Excel + PNG charts"):
            save_plots(stats["nav"], stats["drawdown"], stats["max_dd"], cfg)
            export_excel(tradesheet, stats, 0.0, sweep_df, cfg)
            st.success(f"Saved {OUTPUT_XLSX.name}, equity/drawdown PNGs")

        if OUTPUT_XLSX.exists():
            st.download_button(
                "Download Excel",
                OUTPUT_XLSX.read_bytes(),
                file_name=OUTPUT_XLSX.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if EQUITY_PNG.exists():
            st.download_button("Download Equity PNG", EQUITY_PNG.read_bytes(), file_name=EQUITY_PNG.name)
        if DRAWDOWN_PNG.exists():
            st.download_button("Download Drawdown PNG", DRAWDOWN_PNG.read_bytes(), file_name=DRAWDOWN_PNG.name)
        if SENSITIVITY_PNG.exists():
            st.download_button(
                "Download Sweep Heatmap PNG", SENSITIVITY_PNG.read_bytes(), file_name=SENSITIVITY_PNG.name
            )

        pdf_path = BASE_DIR / "Qode_Assignment_Submission_Report.pdf"
        if pdf_path.exists():
            st.download_button(
                "Download PDF Report",
                pdf_path.read_bytes(),
                file_name=pdf_path.name,
                mime="application/pdf",
            )
        else:
            st.caption("Run `python generate_submission_report.py` locally to create the PDF report.")

    st.subheader("Runtime Breakdown")
    st.dataframe(pd.DataFrame({"Step": list(TIMINGS.keys()), "Seconds": list(TIMINGS.values())}))
else:
    st.info("Adjust parameters in the sidebar and click **Run Backtest**.")
