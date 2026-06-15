from __future__ import annotations

import time

import pandas as pd

from qode_backtest.config import StrategyConfig
from qode_backtest.timing import tick


def apply_signals(
    selected: pd.DataFrame, intraday: pd.DataFrame, cfg: StrategyConfig | None = None
) -> pd.DataFrame:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()

    keys = selected[["Date", "Ticker"]].drop_duplicates()
    sl_cols = ["Date", "Ticker", "Time", "High", "Close"]

    sl_window = intraday[intraday["Time"] > cfg.entry_time][sl_cols]
    sl_window = sl_window.merge(keys, on=["Date", "Ticker"], how="inner")

    path = selected.merge(sl_window, on=["Date", "Ticker"], how="left")
    path["sl_price"] = path["entry_price"] * cfg.sl_multiplier
    path["sl_hit"] = path["High"] >= path["sl_price"]

    sl_exits = (
        path[path["sl_hit"]]
        .sort_values(["Date", "Ticker", "Time"])
        .groupby(["Date", "Ticker"], observed=True)
        .first()
        .reset_index()
        .assign(
            exit_time=lambda d: d["Time"],
            exit_price=lambda d: d["sl_price"],
            exit_reason="Stop Loss",
        )
    )

    scheduled = (
        intraday[intraday["Time"] == cfg.exit_time][sl_cols]
        .merge(keys, on=["Date", "Ticker"], how="inner")
        .rename(columns={"Time": "exit_time", "Close": "exit_price"})
        .assign(exit_reason="Scheduled Exit")
    )

    trades = selected.merge(
        sl_exits[["Date", "Ticker", "exit_time", "exit_price", "exit_reason"]],
        on=["Date", "Ticker"],
        how="left",
    ).merge(
        scheduled[["Date", "Ticker", "exit_time", "exit_price", "exit_reason"]],
        on=["Date", "Ticker"],
        how="left",
        suffixes=("_sl", "_sched"),
    )

    trades["exit_time"] = trades["exit_time_sl"].fillna(trades["exit_time_sched"])
    trades["exit_price"] = trades["exit_price_sl"].fillna(trades["exit_price_sched"])
    trades["exit_reason"] = trades["exit_reason_sl"].fillna(trades["exit_reason_sched"])
    trades = trades.drop(
        columns=[
            "exit_time_sl", "exit_time_sched",
            "exit_price_sl", "exit_price_sched",
            "exit_reason_sl", "exit_reason_sched",
        ]
    )

    tick("4_signal_stoploss_sec", t0)
    return trades
