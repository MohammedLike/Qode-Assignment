from __future__ import annotations

from dataclasses import replace

import pandas as pd

from qode_backtest.analytics import compute_statistics, pnl_column
from qode_backtest.config import StrategyConfig
from qode_backtest.export import save_sensitivity_heatmap
from qode_backtest.signals import apply_signals
from qode_backtest.strike_selection import select_strikes
from qode_backtest.tradesheet import build_tradesheet


def run_sweep(
    options: pd.DataFrame,
    spot: pd.DataFrame,
    base_cfg: StrategyConfig,
    premiums: list[float] | None = None,
    sl_multipliers: list[float] | None = None,
) -> pd.DataFrame:
    """Grid sweep over target premium and SL multiplier (data loaded once)."""
    premiums = premiums or [40, 45, 50, 55, 60]
    sl_multipliers = sl_multipliers or [1.3, 1.5, 1.7, 2.0]

    rows = []
    for premium in premiums:
        for sl in sl_multipliers:
            cfg = replace(base_cfg, target_premium=premium, sl_multiplier=sl)
            entry_bars = options[options["Time"] == cfg.entry_time]
            selected = select_strikes(entry_bars, cfg)
            trades_raw = apply_signals(selected, options, cfg)
            tradesheet = build_tradesheet(trades_raw, spot, cfg)
            stats = compute_statistics(tradesheet, cfg)
            col = pnl_column(cfg)
            rows.append(
                {
                    "target_premium": premium,
                    "sl_multiplier": sl,
                    "cagr_pct": round(stats["cagr"] * 100, 2),
                    "max_dd_pct": round(stats["max_dd"], 2),
                    "final_nav": round(stats["nav"].iloc[-1], 4),
                    "total_pnl": round(tradesheet[col].sum(), 2),
                    "total_trades": len(tradesheet),
                }
            )

    sweep_df = pd.DataFrame(rows)
    save_sensitivity_heatmap(sweep_df)
    return sweep_df
