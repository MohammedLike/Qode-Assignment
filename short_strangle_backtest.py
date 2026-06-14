"""Backward-compatible entry point — delegates to qode_backtest package."""

from __future__ import annotations

from qode_backtest.analytics import compute_statistics
from qode_backtest.config import (
    BASE_DIR,
    DRAWDOWN_PNG,
    EQUITY_PNG,
    OPTIONS_FILE,
    OUTPUT_XLSX,
    SPOT_FILE,
    StrategyConfig,
)
from qode_backtest.data_loader import load_options, load_spot
from qode_backtest.engine import print_summary, run_pipeline
from qode_backtest.export import export_excel, save_plots
from qode_backtest.signals import apply_signals
from qode_backtest.strike_selection import select_strikes
from qode_backtest.timing import TIMINGS, tick
from qode_backtest.tradesheet import build_tradesheet

_cfg = StrategyConfig.from_yaml()
TARGET_PREMIUM = _cfg.target_premium
ENTRY_TIME = _cfg.entry_time
EXIT_TIME = _cfg.exit_time
LOTS = _cfg.lots
LOT_SIZE = _cfg.lot_size
QUANTITY = _cfg.quantity
STARTING_CAPITAL = _cfg.starting_capital
BASE_NAV = _cfg.base_nav
SL_MULTIPLIER = _cfg.sl_multiplier


def run_backtest():
    tradesheet, stats, _ = run_pipeline(_cfg)
    print_summary(tradesheet, stats)
    return tradesheet


__all__ = [
    "BASE_DIR",
    "OPTIONS_FILE",
    "SPOT_FILE",
    "OUTPUT_XLSX",
    "EQUITY_PNG",
    "DRAWDOWN_PNG",
    "TARGET_PREMIUM",
    "ENTRY_TIME",
    "EXIT_TIME",
    "LOTS",
    "LOT_SIZE",
    "QUANTITY",
    "STARTING_CAPITAL",
    "BASE_NAV",
    "SL_MULTIPLIER",
    "TIMINGS",
    "load_options",
    "load_spot",
    "select_strikes",
    "apply_signals",
    "build_tradesheet",
    "compute_statistics",
    "save_plots",
    "export_excel",
    "run_backtest",
    "tick",
]

if __name__ == "__main__":
    run_backtest()
