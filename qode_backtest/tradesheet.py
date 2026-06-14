from __future__ import annotations

import time

import numpy as np
import pandas as pd

from qode_backtest.config import StrategyConfig
from qode_backtest.timing import tick


def _apply_realism_costs(ts: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    ts["ideal_gross_pnl"] = ts["gross_pnl"]
    if not cfg.realism_enabled:
        ts["slippage_cost"] = 0.0
        ts["brokerage"] = 0.0
        ts["net_pnl"] = ts["gross_pnl"]
        return ts

    sl_mask = ts["exit_reason"] == "Stop Loss"
    ts["slippage_cost"] = np.where(
        sl_mask,
        (ts["exit_price"] * cfg.slippage_pct * ts["quantity"]).round(2),
        0.0,
    )
    ts["brokerage"] = cfg.brokerage_per_leg
    ts["net_pnl"] = (ts["ideal_gross_pnl"] - ts["slippage_cost"] - ts["brokerage"]).round(2)
    return ts


def build_tradesheet(
    trades: pd.DataFrame, spot: pd.DataFrame, cfg: StrategyConfig | None = None
) -> pd.DataFrame:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()

    ts = trades.copy()
    ts["quantity"] = cfg.quantity
    ts["entry_value"] = (ts["entry_price"].round(2) * ts["quantity"]).round(2)
    ts["exit_value"] = (ts["exit_price"].round(2) * ts["quantity"]).round(2)
    ts["gross_pnl"] = (ts["entry_value"] - ts["exit_value"]).round(2)
    ts["pct_pnl"] = (ts["gross_pnl"] / ts["entry_value"]) * 100
    ts["is_expiry_day"] = pd.to_datetime(ts["Date"]).dt.dayofweek == 2

    ts = ts.sort_values(["Date", "option_type"], ascending=[True, False])
    ts = _apply_realism_costs(ts, cfg)
    ts["cumulative_pnl"] = ts["net_pnl"].cumsum()

    daily_pnl = ts.groupby("Date", observed=True)["net_pnl"].sum()
    daily_capital = cfg.starting_capital + daily_pnl.cumsum()
    ts["available_capital"] = ts["Date"].map(daily_capital)

    daily_margin = ts.groupby("Date", observed=True)["entry_value"].sum()
    ts["daily_margin_required"] = ts["Date"].map(daily_margin)
    ts["margin_exceeded"] = ts["daily_margin_required"] > cfg.starting_capital

    ts = ts.merge(
        spot.rename(columns={"minute": "entry_minute", "underlying_close": "banknifty_close"}),
        left_on=["Date", "minute"],
        right_on=["Date", "entry_minute"],
        how="left",
    )

    spot_val = ts["banknifty_close"].astype(float)
    strike_val = ts["strike"].astype(float)
    ts["moneyness"] = np.where(
        spot_val > 0,
        np.where(
            ts["option_type"] == "CE",
            (spot_val - strike_val) / spot_val,
            (strike_val - spot_val) / spot_val,
        ),
        np.nan,
    )

    sheet = pd.DataFrame(
        {
            "Entry Date": ts["Date"],
            "Entry Time": ts["entry_time"],
            "Exit Date": ts["Date"],
            "Exit Time": ts["exit_time"],
            "Option Ticker": ts["Ticker"].astype(str),
            "Strike Price": ts["strike"],
            "Option Type": ts["option_type"],
            "Entry Price": ts["entry_price"].round(2),
            "Exit Price": ts["exit_price"].round(2),
            "Quantity": ts["quantity"],
            "Entry Value": ts["entry_value"].round(2),
            "Exit Value": ts["exit_value"].round(2),
            "Gross P&L": ts["ideal_gross_pnl"].round(2),
            "Net P&L": ts["net_pnl"].round(2),
            "Slippage Cost": ts["slippage_cost"].round(2),
            "Brokerage": ts["brokerage"].round(2),
            "Cumulative P&L": ts["cumulative_pnl"].round(2),
            "Available Capital": ts["available_capital"].round(2),
            "Banknifty Underlying Close": ts["banknifty_close"],
            "Moneyness": ts["moneyness"].round(4),
            "Margin Exceeded": ts["margin_exceeded"],
            "Exit Reason": ts["exit_reason"],
            "Is Expiry Day": ts["is_expiry_day"],
            "% P&L": ts["pct_pnl"].round(2),
        }
    )

    tick("5_tradesheet_sec", t0)
    return sheet
