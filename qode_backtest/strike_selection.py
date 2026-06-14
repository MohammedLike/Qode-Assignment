from __future__ import annotations

import time

import pandas as pd

from qode_backtest.config import StrategyConfig
from qode_backtest.timing import tick


def select_strikes(entry_bars: pd.DataFrame, cfg: StrategyConfig | None = None) -> pd.DataFrame:
    cfg = cfg or StrategyConfig.from_yaml()
    """Pick CE and PE strikes with entry close closest to target premium."""
    t0 = time.perf_counter()

    bars = entry_bars.drop(columns=["option_type"], errors="ignore").copy()
    bars["premium_dist"] = (bars["Close"] - cfg.target_premium).abs()

    ce = (
        bars[bars["Call/Put"] == "CE"]
        .sort_values(["Date", "premium_dist", "strike"], ascending=[True, True, False])
        .groupby("Date", observed=True)
        .first()
        .reset_index()
    )
    pe = (
        bars[bars["Call/Put"] == "PE"]
        .sort_values(["Date", "premium_dist", "strike"], ascending=[True, True, True])
        .groupby("Date", observed=True)
        .first()
        .reset_index()
    )
    selected = pd.concat([ce, pe], ignore_index=True)
    selected = selected.rename(columns={"Close": "entry_price", "Call/Put": "option_type"})
    selected["entry_time"] = cfg.entry_time

    tick("3_strike_selection_sec", t0)
    return selected[
        ["Date", "Ticker", "strike", "option_type", "entry_price", "entry_time", "minute"]
    ]
