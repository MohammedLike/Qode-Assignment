from __future__ import annotations

import time

import pandas as pd

from qode_backtest.analytics import compute_statistics
from qode_backtest.config import StrategyConfig
from qode_backtest.data_loader import load_options, load_spot
from qode_backtest.export import export_excel, save_plots
from qode_backtest.signals import apply_signals
from qode_backtest.strike_selection import select_strikes
from qode_backtest.sweep import run_sweep
from qode_backtest.timing import TIMINGS, clear_timings
from qode_backtest.tradesheet import build_tradesheet


def run_pipeline(
    cfg: StrategyConfig | None = None,
    *,
    export: bool = True,
    run_sweep_analysis: bool = False,
    sweep_premiums: list[float] | None = None,
    sweep_sl: list[float] | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame | None]:
    cfg = cfg or StrategyConfig()
    clear_timings()
    total_t0 = time.perf_counter()

    options = load_options(cfg)
    spot = load_spot(cfg)

    entry_bars = options[options["Time"] == cfg.entry_time]
    selected = select_strikes(entry_bars, cfg)
    trades_raw = apply_signals(selected, options, cfg)
    tradesheet = build_tradesheet(trades_raw, spot, cfg)
    stats = compute_statistics(tradesheet, cfg)

    sweep_df = None
    if run_sweep_analysis:
        sweep_df = run_sweep(options, spot, cfg, sweep_premiums, sweep_sl)

    if export:
        save_plots(stats["nav"], stats["drawdown"], stats["max_dd"], cfg)
        export_excel(tradesheet, stats, total_t0, sweep_df, cfg)

    TIMINGS["total_sec"] = time.perf_counter() - total_t0
    return tradesheet, stats, sweep_df


def print_summary(tradesheet: pd.DataFrame, stats: dict) -> None:
    print("\n=== Backtest Complete ===")
    print(f"Trading days : {tradesheet['Entry Date'].nunique()}")
    print(f"Total trades : {len(tradesheet)}")
    print(f"CAGR         : {stats['cagr'] * 100:.2f}%")
    print(f"Max Drawdown : {stats['max_dd']:.2f}%")
    print(f"Sharpe       : {stats['risk_metrics']['Sharpe Ratio']}")
    print(f"Final NAV    : {stats['nav'].iloc[-1]:.4f}")
    print("\nRuntime (seconds):")
    for k, v in TIMINGS.items():
        print(f"  {k}: {v:.3f}")
