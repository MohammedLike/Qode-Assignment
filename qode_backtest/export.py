from __future__ import annotations

import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from qode_backtest.config import (
    DRAWDOWN_PNG,
    EQUITY_PNG,
    OUTPUT_XLSX,
    SENSITIVITY_PNG,
    StrategyConfig,
)
from qode_backtest.timing import TIMINGS, tick


def save_plots(
    nav: pd.Series, drawdown: pd.Series, max_dd: float, cfg: StrategyConfig | None = None
) -> None:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(nav.index, nav.values, color="#1f77b4", linewidth=1.2)
    ax.axhline(cfg.base_nav, color="gray", linestyle="--", linewidth=0.8, label="Base NAV (100)")
    ax.set_title("Equity Curve (Base NAV = 100)")
    ax.set_xlabel("Date")
    ax.set_ylabel("NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(EQUITY_PNG, dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#d62728", alpha=0.4)
    ax.plot(drawdown.index, drawdown.values, color="#d62728", linewidth=1.2)
    ax.axhline(max_dd, color="black", linestyle="--", linewidth=0.8, label=f"Max DD: {max_dd:.2f}%")
    ax.set_title("Drawdown from Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown %")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(DRAWDOWN_PNG, dpi=150)
    plt.close(fig)

    tick("7_plots_sec", t0)


def save_sensitivity_heatmap(sweep_df: pd.DataFrame) -> None:
    if sweep_df.empty:
        return
    pivot = sweep_df.pivot(index="target_premium", columns="sl_multiplier", values="cagr_pct")
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(c) for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(i) for i in pivot.index])
    ax.set_xlabel("SL Multiplier")
    ax.set_ylabel("Target Premium (Rs.)")
    ax.set_title("CAGR % Sensitivity Heatmap")
    plt.colorbar(im, ax=ax, label="CAGR %")
    fig.tight_layout()
    fig.savefig(SENSITIVITY_PNG, dpi=150)
    plt.close(fig)


def build_guide_sheet(cfg: StrategyConfig) -> pd.DataFrame:
    lines = [
        ("Section", "Details"),
        ("Assignment", "09:20 AM Bank Nifty Short Strangle Backtest"),
        ("Strategy", "Sell 1 CE + 1 PE at entry; exit at scheduled time or SL per leg"),
        ("Strike Selection", f"Entry close closest to Rs. {cfg.target_premium} for CE and PE"),
        ("Entry Time", cfg.entry_time),
        ("Exit Time", cfg.exit_time),
        ("Stop Loss", f"{int((cfg.sl_multiplier - 1) * 100)}% above entry; checked via High column"),
        ("SL Fill Price", f"Entry x {cfg.sl_multiplier} at first breach minute"),
        ("Position Size", f"{cfg.lots} lot x {cfg.lot_size} = {cfg.quantity} qty per leg"),
        ("Starting Capital", f"Rs. {cfg.starting_capital:,.0f}"),
        ("Base NAV", str(cfg.base_nav)),
        ("Realism (slippage + brokerage)", str(cfg.realism_enabled)),
        ("Slippage on SL exits", f"{cfg.slippage_pct * 100:.2f}% adverse fill"),
        ("Brokerage per leg", f"Rs. {cfg.brokerage_per_leg:.0f}"),
        ("Parquet Cache", str(cfg.use_parquet_cache)),
        ("", ""),
        ("Runtime Breakdown (seconds)", ""),
    ]
    for key, val in TIMINGS.items():
        lines.append((key, f"{val:.3f}"))
    return pd.DataFrame(lines[1:], columns=lines[0])


def export_excel(
    tradesheet: pd.DataFrame,
    stats: dict,
    total_t0: float,
    sweep_df: pd.DataFrame | None = None,
    cfg: StrategyConfig | None = None,
) -> None:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()
    export_tradesheet = tradesheet.drop(columns=["Exit Reason", "Is Expiry Day", "% P&L"], errors="ignore")

    tick("8_excel_export_prep_sec", t0)
    TIMINGS["total_sec"] = time.perf_counter() - total_t0
    guide = build_guide_sheet(cfg)

    t0 = time.perf_counter()
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        guide.to_excel(writer, sheet_name="Guide", index=False)
        export_tradesheet.to_excel(writer, sheet_name="Tradesheet", index=False)

        row = 0
        stats["summary"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
        row += len(stats["summary"]) + 3

        for title, df in [
            ("Win/Loss Analysis", stats["win_loss"]),
            ("Expiry vs Non-Expiry Avg % P&L", stats["expiry_stats"]),
            ("Monthly % P&L (from NAV)", stats["monthly_table"]),
            ("Equity Curve Table", stats["equity_table"]),
        ]:
            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                continue
            pd.DataFrame([{"Metric": title}]).to_excel(
                writer, sheet_name="Statistics", index=False, header=False, startrow=row
            )
            row += 2
            df.to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
            row += len(df) + 3

        realism = stats.get("realism_comparison")
        if realism is not None and not realism.empty:
            pd.DataFrame([{"Metric": "Ideal vs Realistic P&L"}]).to_excel(
                writer, sheet_name="Statistics", index=False, header=False, startrow=row
            )
            row += 2
            realism.to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
            row += len(realism) + 3

        benchmark = stats.get("benchmark_summary")
        if benchmark is not None and not benchmark.empty:
            pd.DataFrame([{"Metric": "Benchmark vs Strategy"}]).to_excel(
                writer, sheet_name="Statistics", index=False, header=False, startrow=row
            )
            row += 2
            benchmark.to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
            row += len(benchmark) + 3

        attr = stats.get("attribution", {})
        if attr:
            attr_row = 0
            for title, df in [
                ("P&L by Day of Week", attr.get("day_of_week")),
                ("CE vs PE Daily Contribution", attr.get("ce_pe_daily")),
                ("Volatility Regime Attribution", attr.get("vol_regime")),
                ("Moneyness at Entry", attr.get("moneyness")),
            ]:
                if df is None or df.empty:
                    continue
                pd.DataFrame([{"Section": title}]).to_excel(
                    writer, sheet_name="Attribution", index=False, header=False, startrow=attr_row
                )
                attr_row += 2
                df.to_excel(writer, sheet_name="Attribution", index=False, startrow=attr_row)
                attr_row += len(df) + 3

        if sweep_df is not None and not sweep_df.empty:
            sweep_df.to_excel(writer, sheet_name="Sensitivity", index=False)

    tick("8_excel_write_sec", t0)
