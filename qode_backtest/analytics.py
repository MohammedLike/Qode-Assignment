from __future__ import annotations

import time

import numpy as np
import pandas as pd

from qode_backtest.config import StrategyConfig
from qode_backtest.timing import tick


def compute_daily_nav(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.Series:
    daily_pnl = tradesheet.groupby("Entry Date", observed=True)["Gross P&L"].sum().sort_index()
    dates = pd.to_datetime(daily_pnl.index)
    nav_values = cfg.base_nav + (daily_pnl.cumsum().values / cfg.starting_capital * cfg.base_nav)
    return pd.Series(nav_values, index=dates, name="NAV")


def compute_drawdown(nav: pd.Series) -> pd.Series:
    peak = nav.cummax()
    return (nav - peak) / peak * 100


def compute_risk_metrics(nav: pd.Series, tradesheet: pd.DataFrame, cagr: float, max_dd: float) -> dict:
    daily_returns = nav.pct_change().dropna()
    ann_factor = np.sqrt(252)

    sharpe = 0.0
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * ann_factor

    downside = daily_returns[daily_returns < 0]
    sortino = 0.0
    if len(downside) > 0 and downside.std() > 0:
        sortino = (daily_returns.mean() / downside.std()) * ann_factor

    calmar = 0.0
    if max_dd < 0:
        calmar = cagr / abs(max_dd / 100)

    wins = tradesheet.loc[tradesheet["Gross P&L"] > 0, "Gross P&L"].sum()
    losses = abs(tradesheet.loc[tradesheet["Gross P&L"] <= 0, "Gross P&L"].sum())
    profit_factor = wins / losses if losses > 0 else float("inf")

    win_rate = (tradesheet["Gross P&L"] > 0).mean()
    avg_win = tradesheet.loc[tradesheet["Gross P&L"] > 0, "Gross P&L"].mean()
    avg_loss = abs(tradesheet.loc[tradesheet["Gross P&L"] <= 0, "Gross P&L"].mean())
    expectancy = (avg_win * win_rate) - (avg_loss * (1 - win_rate)) if len(tradesheet) else 0

    streak = 0
    max_streak = 0
    for pnl in tradesheet.sort_values(["Entry Date", "Option Type"])["Gross P&L"]:
        if pnl <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return {
        "Sharpe Ratio": round(sharpe, 4),
        "Sortino Ratio": round(sortino, 4),
        "Calmar Ratio": round(calmar, 4),
        "Profit Factor": round(profit_factor, 4) if profit_factor != float("inf") else "inf",
        "Expectancy (INR)": round(expectancy, 2),
        "Max Consecutive Losses": max_streak,
    }


def win_loss_stats(tradesheet: pd.DataFrame, label: str) -> dict:
    n = len(tradesheet)
    if n == 0:
        return {"Category": label, "Winners": 0, "Losers": 0, "Win %": 0, "Loss %": 0, "Avg % P&L": 0}
    winners = (tradesheet["Gross P&L"] > 0).sum()
    losers = (tradesheet["Gross P&L"] <= 0).sum()
    return {
        "Category": label,
        "Winners": int(winners),
        "Losers": int(losers),
        "Win %": round(winners / n * 100, 2),
        "Loss %": round(losers / n * 100, 2),
        "Avg % P&L": round(tradesheet["% P&L"].mean(), 2),
    }


def expiry_split_stats(tradesheet: pd.DataFrame, option_type: str | None = None) -> pd.DataFrame:
    df = tradesheet if option_type is None else tradesheet[tradesheet["Option Type"] == option_type]
    label = option_type if option_type else "Combined"
    rows = []
    for expiry_flag, day_label in [(True, "Expiry Days (Wed)"), (False, "Non-Expiry Days")]:
        sub = df[df["Is Expiry Day"] == expiry_flag]
        rows.append(
            {
                "Segment": label,
                "Day Type": day_label,
                "Trades": len(sub),
                "Avg % P&L": round(sub["% P&L"].mean(), 2) if len(sub) else 0,
                "Avg Gross P&L": round(sub["Gross P&L"].mean(), 2) if len(sub) else 0,
            }
        )
    return pd.DataFrame(rows)


def compute_statistics(tradesheet: pd.DataFrame, cfg: StrategyConfig | None = None) -> dict:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()

    nav = compute_daily_nav(tradesheet, cfg)
    drawdown = compute_drawdown(nav)
    max_dd = drawdown.min()

    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / cfg.base_nav) ** (1 / years) - 1 if years > 0 else 0
    risk = compute_risk_metrics(nav, tradesheet, cagr, max_dd)

    win_loss = pd.DataFrame(
        [
            win_loss_stats(tradesheet[tradesheet["Option Type"] == "CE"], "CE"),
            win_loss_stats(tradesheet[tradesheet["Option Type"] == "PE"], "PE"),
            win_loss_stats(tradesheet, "Combined"),
        ]
    )

    expiry_stats = pd.concat(
        [
            expiry_split_stats(tradesheet, "CE"),
            expiry_split_stats(tradesheet, "PE"),
            expiry_split_stats(tradesheet, None),
        ],
        ignore_index=True,
    )

    monthly_nav = nav.resample("ME").last()
    monthly_pnl = monthly_nav.pct_change(fill_method=None) * 100
    monthly_pnl.iloc[0] = (monthly_nav.iloc[0] / cfg.base_nav - 1) * 100
    monthly_table = pd.DataFrame(
        {
            "Month": monthly_nav.index.strftime("%Y-%m"),
            "End NAV": monthly_nav.round(4).values,
            "Monthly % P&L": monthly_pnl.round(4).values,
        }
    )

    daily_pnl = tradesheet.groupby("Entry Date", observed=True)["Gross P&L"].sum()
    equity_table = pd.DataFrame(
        {
            "Date": nav.index.strftime("%Y-%m-%d"),
            "Daily P&L": daily_pnl.reindex(nav.index.strftime("%Y-%m-%d")).values,
            "NAV": nav.round(4).values,
            "Drawdown %": drawdown.round(4).values,
        }
    )

    summary_rows = [
        {"Metric": "Starting Capital (INR)", "Value": cfg.starting_capital},
        {"Metric": "Base NAV", "Value": cfg.base_nav},
        {"Metric": "Final NAV", "Value": round(nav.iloc[-1], 4)},
        {"Metric": "Total Gross P&L (INR)", "Value": round(tradesheet["Gross P&L"].sum(), 2)},
        {"Metric": "CAGR", "Value": f"{cagr * 100:.2f}%"},
        {"Metric": "Max Drawdown", "Value": f"{max_dd:.2f}%"},
        {"Metric": "Sharpe Ratio", "Value": risk["Sharpe Ratio"]},
        {"Metric": "Sortino Ratio", "Value": risk["Sortino Ratio"]},
        {"Metric": "Calmar Ratio", "Value": risk["Calmar Ratio"]},
        {"Metric": "Profit Factor", "Value": risk["Profit Factor"]},
        {"Metric": "Expectancy (INR)", "Value": risk["Expectancy (INR)"]},
        {"Metric": "Max Consecutive Losses", "Value": risk["Max Consecutive Losses"]},
        {"Metric": "Total Trading Days", "Value": nav.shape[0]},
        {"Metric": "Total Trades", "Value": len(tradesheet)},
        {"Metric": "SL Exits", "Value": (tradesheet["Exit Reason"] == "Stop Loss").sum()},
        {"Metric": "Scheduled Exits", "Value": (tradesheet["Exit Reason"] == "Scheduled Exit").sum()},
    ]
    summary = pd.DataFrame(summary_rows)

    tick("6_statistics_sec", t0)
    return {
        "summary": summary,
        "win_loss": win_loss,
        "expiry_stats": expiry_stats,
        "monthly_table": monthly_table,
        "equity_table": equity_table,
        "risk_metrics": risk,
        "nav": nav,
        "drawdown": drawdown,
        "max_dd": max_dd,
        "cagr": cagr,
    }
