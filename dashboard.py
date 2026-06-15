from __future__ import annotations

from pathlib import Path

import numpy as np
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


def _daily_pnl(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.Series:
    col = pnl_column(cfg)
    return tradesheet.groupby("Entry Date", observed=True)[col].sum().sort_index()


def _rolling_sharpe(nav: pd.Series, window: int = 20) -> pd.Series:
    ret = nav.pct_change()
    roll_mean = ret.rolling(window).mean()
    roll_std = ret.rolling(window).std()
    return (roll_mean / roll_std) * np.sqrt(252)


def _rolling_vol(nav: pd.Series, window: int = 20) -> pd.Series:
    return nav.pct_change().rolling(window).std() * np.sqrt(252) * 100


def _monthly_returns(nav: pd.Series) -> pd.DataFrame:
    monthly = nav.resample("ME").last().pct_change() * 100
    monthly.iloc[0] = (nav.resample("ME").last().iloc[0] / nav.iloc[0] - 1) * 100
    df = monthly.reset_index()
    df.columns = ["Month", "Return %"]
    df["Month"] = df["Month"].dt.strftime("%Y-%m")
    return df.round(2)


def _trade_stats(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> dict:
    col = pnl_column(cfg)
    wins = tradesheet[tradesheet[col] > 0]
    losses = tradesheet[tradesheet[col] <= 0]
    avg_win = wins[col].mean() if len(wins) else 0.0
    avg_loss = abs(losses[col].mean()) if len(losses) else 0.0
    sl_count = (tradesheet["Exit Reason"] == "Stop Loss").sum()
    return {
        "win_rate": (tradesheet[col] > 0).mean() * 100,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": avg_win / avg_loss if avg_loss > 0 else float("inf"),
        "sl_hit_rate": sl_count / len(tradesheet) * 100 if len(tradesheet) else 0,
        "sl_count": int(sl_count),
        "scheduled_count": int((tradesheet["Exit Reason"] == "Scheduled Exit").sum()),
        "margin_days": int(tradesheet.groupby("Entry Date")["Margin Exceeded"].first().sum())
        if "Margin Exceeded" in tradesheet.columns
        else 0,
    }


def _filter_trades(tradesheet: pd.DataFrame) -> pd.DataFrame:
    df = tradesheet.copy()
    opt_types = st.multiselect("Option type", ["CE", "PE"], default=["CE", "PE"], key="flt_opt")
    if opt_types:
        df = df[df["Option Type"].isin(opt_types)]
    exit_reasons = st.multiselect(
        "Exit reason",
        ["Stop Loss", "Scheduled Exit"],
        default=["Stop Loss", "Scheduled Exit"],
        key="flt_exit",
    )
    if exit_reasons:
        df = df[df["Exit Reason"].isin(exit_reasons)]
    day_types = st.multiselect(
        "Day type", ["Expiry", "Non-expiry"], default=["Expiry", "Non-expiry"], key="flt_day"
    )
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


def _daily_pnl_chart(daily: pd.Series) -> go.Figure:
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in daily.values]
    fig = go.Figure(go.Bar(x=daily.index, y=daily.values, marker_color=colors, name="Daily P&L"))
    fig.update_layout(
        title="Daily P&L (INR)",
        xaxis_title="Date",
        yaxis_title="P&L (INR)",
        height=320,
        showlegend=False,
    )
    return fig


def _rolling_metrics_chart(nav: pd.Series) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    roll_sh = _rolling_sharpe(nav, 20)
    roll_vol = _rolling_vol(nav, 20)
    fig.add_trace(
        go.Scatter(x=roll_sh.index, y=roll_sh.values, name="Rolling Sharpe (20d)", line=dict(color="#2563EB")),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=roll_vol.index, y=roll_vol.values, name="Rolling Vol % (20d ann.)", line=dict(color="#9333EA")),
        secondary_y=True,
    )
    fig.update_layout(height=360, title="Rolling Sharpe & Volatility", hovermode="x unified")
    fig.update_yaxes(title_text="Sharpe", secondary_y=False)
    fig.update_yaxes(title_text="Volatility %", secondary_y=True)
    return fig


def _pnl_histogram(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> go.Figure:
    col = pnl_column(cfg)
    fig = go.Figure(go.Histogram(x=tradesheet[col], nbinsx=30, marker_color="#2563EB", opacity=0.85))
    fig.update_layout(title="Per-Trade P&L Distribution", xaxis_title="P&L (INR)", yaxis_title="Count", height=320)
    return fig


def _exit_reason_pie(tradesheet: pd.DataFrame) -> go.Figure:
    counts = tradesheet["Exit Reason"].value_counts()
    fig = go.Figure(
        go.Pie(
            labels=counts.index,
            values=counts.values,
            hole=0.4,
            marker=dict(colors=["#d62728", "#2ca02c"]),
        )
    )
    fig.update_layout(title="Exit Reason Mix", height=320)
    return fig


def _ce_pe_pnl_bar(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> go.Figure:
    col = pnl_column(cfg)
    by_type = tradesheet.groupby("Option Type", observed=True)[col].sum()
    fig = go.Figure(go.Bar(x=by_type.index, y=by_type.values, marker_color=["#2563EB", "#9333EA"]))
    fig.update_layout(title="Total P&L by Leg Type", xaxis_title="Option Type", yaxis_title="P&L (INR)", height=320)
    return fig


def _monthly_returns_chart(nav: pd.Series) -> go.Figure:
    monthly = _monthly_returns(nav)
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in monthly["Return %"]]
    fig = go.Figure(go.Bar(x=monthly["Month"], y=monthly["Return %"], marker_color=colors))
    fig.update_layout(title="Monthly Returns %", xaxis_title="Month", yaxis_title="Return %", height=320)
    return fig


def _returns_histogram(nav: pd.Series) -> go.Figure:
    daily_ret = nav.pct_change().dropna() * 100
    fig = go.Figure(go.Histogram(x=daily_ret, nbinsx=30, marker_color="#64748B", opacity=0.85))
    fig.update_layout(title="Daily Return Distribution", xaxis_title="Daily Return %", yaxis_title="Count", height=320)
    return fig


def _margin_utilization(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> go.Figure | None:
    if "Entry Value" not in tradesheet.columns:
        return None
    daily_margin = tradesheet.groupby("Entry Date", observed=True)["Entry Value"].sum()
    util = (daily_margin / cfg.starting_capital * 100).round(2)
    fig = go.Figure(
        go.Scatter(
            x=util.index,
            y=util.values,
            mode="lines",
            fill="tozeroy",
            name="Margin Utilization %",
            line=dict(color="#F59E0B"),
        )
    )
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="100% capital")
    fig.update_layout(title="Daily Margin Utilization (% of Starting Capital)", height=320)
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
        title="Parameter sweep (CAGR %)",
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
    risk = stats["risk_metrics"]
    col = pnl_column(cfg)
    tstats = _trade_stats(tradesheet, cfg)
    daily = _daily_pnl(tradesheet, cfg)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("CAGR", f"{stats['cagr'] * 100:.2f}%")
    c2.metric("Max Drawdown", f"{stats['max_dd']:.2f}%")
    c3.metric("Sharpe", risk["Sharpe Ratio"])
    c4.metric("Sortino", risk["Sortino Ratio"])
    c5.metric("Calmar", risk["Calmar Ratio"])
    c6.metric("Final NAV", f"{stats['nav'].iloc[-1]:.2f}")

    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("Win Rate", f"{tstats['win_rate']:.1f}%")
    d2.metric("Profit Factor", risk["Profit Factor"])
    d3.metric("Expectancy", f"Rs. {risk['Expectancy (INR)']}")
    d4.metric("Payoff Ratio", f"{tstats['payoff_ratio']:.2f}" if tstats["payoff_ratio"] != float("inf") else "∞")
    d5.metric("SL Hit Rate", f"{tstats['sl_hit_rate']:.1f}%")
    d6.metric("Total P&L", f"Rs. {tradesheet[col].sum():,.0f}")

    st.plotly_chart(_nav_chart(stats, cfg, tradesheet), use_container_width=True)

    pnl_col, roll_col = st.columns(2)
    with pnl_col:
        st.plotly_chart(_daily_pnl_chart(daily), use_container_width=True)
    with roll_col:
        st.plotly_chart(_rolling_metrics_chart(stats["nav"]), use_container_width=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["Trades", "Risk", "Analytics", "Attribution", "Sweep", "Export"]
    )

    with tab1:
        st.subheader("Trade Filters")
        filtered = _filter_trades(tradesheet)
        st.dataframe(filtered, use_container_width=True, height=400)

    with tab2:
        st.subheader("Risk")
        r1, r2 = st.columns(2)
        with r1:
            st.plotly_chart(_returns_histogram(stats["nav"]), use_container_width=True)
            st.plotly_chart(_monthly_returns_chart(stats["nav"]), use_container_width=True)
        with r2:
            margin_fig = _margin_utilization(tradesheet, cfg)
            if margin_fig:
                st.plotly_chart(margin_fig, use_container_width=True)
            st.markdown("**Risk Summary**")
            risk_rows = {
                "Metric": [
                    "Annualized Vol (daily)",
                    "Max Consecutive Losses",
                    "Avg Daily P&L (INR)",
                    "Best Day (INR)",
                    "Worst Day (INR)",
                    "Positive Days %",
                    "Margin Exceeded Days",
                ],
                "Value": [
                    f"{stats['nav'].pct_change().std() * np.sqrt(252) * 100:.2f}%",
                    risk["Max Consecutive Losses"],
                    f"{daily.mean():,.0f}",
                    f"{daily.max():,.0f}",
                    f"{daily.min():,.0f}",
                    f"{(daily > 0).mean() * 100:.1f}%",
                    tstats["margin_days"],
                ],
            }
            st.dataframe(pd.DataFrame(risk_rows), hide_index=True, use_container_width=True)

        if stats.get("benchmark_summary") is not None and not stats["benchmark_summary"].empty:
            st.subheader("Benchmark vs Strategy")
            st.dataframe(stats["benchmark_summary"], use_container_width=True)

    with tab3:
        st.subheader("Trade stats")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.plotly_chart(_pnl_histogram(tradesheet, cfg), use_container_width=True)
        with a2:
            st.plotly_chart(_exit_reason_pie(tradesheet), use_container_width=True)
        with a3:
            st.plotly_chart(_ce_pe_pnl_bar(tradesheet, cfg), use_container_width=True)

        st.markdown("**Win / Loss Breakdown**")
        wl = stats["win_loss"]
        st.dataframe(wl, use_container_width=True, hide_index=True)

        bc1, bc2 = st.columns(2)
        with bc1:
            st.markdown("**Top 5 Winning Trades**")
            st.dataframe(
                tradesheet.nlargest(5, col)[
                    ["Entry Date", "Option Type", "Strike Price", "Entry Price", "Exit Price", col, "Exit Reason"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        with bc2:
            st.markdown("**Top 5 Losing Trades**")
            st.dataframe(
                tradesheet.nsmallest(5, col)[
                    ["Entry Date", "Option Type", "Strike Price", "Entry Price", "Exit Price", col, "Exit Reason"]
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**Best / Worst Trading Days**")
        daily_df = daily.reset_index()
        daily_df.columns = ["Date", "Daily P&L"]
        bd1, bd2 = st.columns(2)
        with bd1:
            st.dataframe(daily_df.nlargest(5, "Daily P&L"), use_container_width=True, hide_index=True)
        with bd2:
            st.dataframe(daily_df.nsmallest(5, "Daily P&L"), use_container_width=True, hide_index=True)

        st.markdown("**Avg Win vs Avg Loss**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Metric": ["Avg Win (INR)", "Avg Loss (INR)", "SL Exits", "Scheduled Exits"],
                    "Value": [
                        f"{tstats['avg_win']:,.0f}",
                        f"{tstats['avg_loss']:,.0f}",
                        tstats["sl_count"],
                        tstats["scheduled_count"],
                    ],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab4:
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

        exp = stats.get("expiry_stats")
        if exp is not None and not exp.empty:
            st.subheader("Expiry vs Non-Expiry")
            st.dataframe(exp, use_container_width=True, hide_index=True)

        vol = attr.get("vol_regime")
        if vol is not None and not vol.empty:
            st.subheader("Volatility Regime")
            st.dataframe(vol, use_container_width=True, hide_index=True)

        money = attr.get("moneyness")
        if money is not None and not money.empty:
            st.subheader("Moneyness at Entry")
            st.dataframe(money, use_container_width=True, hide_index=True)

        if stats.get("realism_comparison") is not None and not stats["realism_comparison"].empty:
            st.subheader("Ideal vs Realistic")
            st.dataframe(stats["realism_comparison"], use_container_width=True)

    with tab5:
        if sweep_df is not None and not sweep_df.empty:
            st.plotly_chart(_sweep_heatmap(sweep_df), use_container_width=True)
            st.dataframe(sweep_df, use_container_width=True)
        else:
            st.info("Enable **Run parameter sweep** in the sidebar to generate the heatmap.")

    with tab6:
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

    with st.expander("Runtime Breakdown"):
        st.dataframe(pd.DataFrame({"Step": list(TIMINGS.keys()), "Seconds": list(TIMINGS.values())}))
else:
    st.info("Adjust parameters in the sidebar and click **Run Backtest**.")
