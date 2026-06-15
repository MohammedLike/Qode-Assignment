from __future__ import annotations

import time

import numpy as np
import pandas as pd

from qode_backtest.config import StrategyConfig
from qode_backtest.data_loader import load_spot
from qode_backtest.timing import tick


def pnl_column(cfg: StrategyConfig) -> str:
    return "Net P&L" if cfg.realism_enabled else "Gross P&L"


def compute_daily_nav(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.Series:
    col = pnl_column(cfg)
    daily_pnl = tradesheet.groupby("Entry Date", observed=True)[col].sum().sort_index()
    dates = pd.to_datetime(daily_pnl.index)
    nav_values = cfg.base_nav + (daily_pnl.cumsum().values / cfg.starting_capital * cfg.base_nav)
    return pd.Series(nav_values, index=dates, name="NAV")


def compute_drawdown(nav: pd.Series) -> pd.Series:
    peak = nav.cummax()
    return (nav - peak) / peak * 100


def compute_risk_metrics(
    nav: pd.Series, tradesheet: pd.DataFrame, cagr: float, max_dd: float, col: str = "Gross P&L"
) -> dict:
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

    wins = tradesheet.loc[tradesheet[col] > 0, col].sum()
    losses = abs(tradesheet.loc[tradesheet[col] <= 0, col].sum())
    profit_factor = wins / losses if losses > 0 else float("inf")

    win_rate = (tradesheet[col] > 0).mean()
    avg_win = tradesheet.loc[tradesheet[col] > 0, col].mean()
    avg_loss = abs(tradesheet.loc[tradesheet[col] <= 0, col].mean())
    expectancy = (avg_win * win_rate) - (avg_loss * (1 - win_rate)) if len(tradesheet) else 0

    streak = 0
    max_streak = 0
    for pnl in tradesheet.sort_values(["Entry Date", "Option Type"])[col]:
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


def win_loss_stats(tradesheet: pd.DataFrame, label: str, col: str = "Gross P&L") -> dict:
    n = len(tradesheet)
    if n == 0:
        return {"Category": label, "Winners": 0, "Losers": 0, "Win %": 0, "Loss %": 0, "Avg % P&L": 0}
    winners = (tradesheet[col] > 0).sum()
    losers = (tradesheet[col] <= 0).sum()
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
    col = "Net P&L" if "Net P&L" in df.columns else "Gross P&L"
    rows = []
    for expiry_flag, day_label in [(True, "Expiry Days (Wed)"), (False, "Non-Expiry Days")]:
        sub = df[df["Is Expiry Day"] == expiry_flag]
        rows.append(
            {
                "Segment": label,
                "Day Type": day_label,
                "Trades": len(sub),
                "Avg % P&L": round(sub["% P&L"].mean(), 2) if len(sub) else 0,
                "Avg Gross P&L": round(sub[col].mean(), 2) if len(sub) else 0,
            }
        )
    return pd.DataFrame(rows)


def compute_realism_comparison(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    if not cfg.realism_enabled or "Net P&L" not in tradesheet.columns:
        return pd.DataFrame(
            [{"Scenario": "Ideal", "Total P&L (INR)": round(tradesheet["Gross P&L"].sum(), 2)}]
        )

    ideal_nav = _nav_from_column(tradesheet, cfg, "Gross P&L")
    net_nav = _nav_from_column(tradesheet, cfg, "Net P&L")
    rows = []
    for label, nav, col in [
        ("Ideal (no costs)", ideal_nav, "Gross P&L"),
        ("Realistic (slippage + brokerage)", net_nav, "Net P&L"),
    ]:
        dd = compute_drawdown(nav)
        years = (nav.index[-1] - nav.index[0]).days / 365.25 if len(nav) > 1 else 0
        cagr = (nav.iloc[-1] / cfg.base_nav) ** (1 / years) - 1 if years > 0 else 0
        rows.append(
            {
                "Scenario": label,
                "Total P&L (INR)": round(tradesheet[col].sum(), 2),
                "Final NAV": round(nav.iloc[-1], 4),
                "CAGR %": round(cagr * 100, 2),
                "Max Drawdown %": round(dd.min(), 2),
            }
        )
    margin_days = tradesheet.groupby("Entry Date")["Margin Exceeded"].first().sum()
    rows.append(
        {
            "Scenario": "Margin exceeded days",
            "Total P&L (INR)": int(margin_days),
            "Final NAV": "",
            "CAGR %": "",
            "Max Drawdown %": "",
        }
    )
    return pd.DataFrame(rows)


def _nav_from_column(tradesheet: pd.DataFrame, cfg: StrategyConfig, col: str) -> pd.Series:
    daily_pnl = tradesheet.groupby("Entry Date", observed=True)[col].sum().sort_index()
    dates = pd.to_datetime(daily_pnl.index)
    nav_values = cfg.base_nav + (daily_pnl.cumsum().values / cfg.starting_capital * cfg.base_nav)
    return pd.Series(nav_values, index=dates, name="NAV")


def day_of_week_attribution(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    col = pnl_column(cfg)
    df = tradesheet.copy()
    df["Weekday"] = pd.to_datetime(df["Entry Date"]).dt.day_name()
    agg = df.groupby("Weekday", observed=True).agg(
        Trades=(col, "count"),
        Total_PnL=(col, "sum"),
        Avg_PnL=(col, "mean"),
    ).reset_index()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    agg["Weekday"] = pd.Categorical(agg["Weekday"], categories=order, ordered=True)
    return agg.sort_values("Weekday").rename(
        columns={"Total_PnL": "Total P&L (INR)", "Avg_PnL": "Avg P&L (INR)"}
    ).round(2)


def ce_pe_daily_contribution(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    col = pnl_column(cfg)
    pivot = tradesheet.pivot_table(
        index="Entry Date",
        columns="Option Type",
        values=col,
        aggfunc="sum",
        fill_value=0,
        observed=True,
    ).reset_index()
    pivot.columns.name = None
    if "CE" not in pivot.columns:
        pivot["CE"] = 0.0
    if "PE" not in pivot.columns:
        pivot["PE"] = 0.0
    pivot["Combined"] = pivot["CE"] + pivot["PE"]
    return pivot.round(2)


def volatility_regime_attribution(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    col = pnl_column(cfg)
    daily = (
        tradesheet.groupby("Entry Date", observed=True)
        .agg(spot=("Banknifty Underlying Close", "first"), pnl=(col, "sum"))
        .sort_index()
    )
    daily["return"] = daily["spot"].pct_change()
    daily["vol_20d"] = daily["return"].rolling(20, min_periods=5).std()
    valid = daily.dropna(subset=["vol_20d"])
    if valid.empty:
        return pd.DataFrame(columns=["Regime", "Days", "Total P&L (INR)", "Avg Daily P&L"])

    q33, q66 = valid["vol_20d"].quantile([0.33, 0.66])

    def bucket(v: float) -> str:
        if v <= q33:
            return "Low Vol"
        if v <= q66:
            return "Mid Vol"
        return "High Vol"

    valid = valid.copy()
    valid["regime"] = valid["vol_20d"].map(bucket)
    regime_map = {str(k): v for k, v in valid["regime"].items()}
    merged = tradesheet.copy()
    merged["regime"] = merged["Entry Date"].astype(str).map(regime_map)
    merged = merged.dropna(subset=["regime"])
    agg = merged.groupby("regime", observed=True).agg(
        Days=("Entry Date", "nunique"),
        Total_PnL=(col, "sum"),
        Avg_Daily=(col, "mean"),
    ).reset_index()
    return agg.rename(
        columns={"regime": "Regime", "Total_PnL": "Total P&L (INR)", "Avg_Daily": "Avg P&L per Leg"}
    ).round(2)


def moneyness_attribution(tradesheet: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    col = pnl_column(cfg)
    if "Moneyness" not in tradesheet.columns:
        return pd.DataFrame()
    df = tradesheet.copy()

    def bucket(m: float) -> str:
        if m < 0.01:
            return "ATM (0-1%)"
        if m < 0.03:
            return "Near OTM (1-3%)"
        return "Far OTM (>3%)"

    df["Moneyness Bucket"] = df["Moneyness"].map(bucket)
    return (
        df.groupby(["Option Type", "Moneyness Bucket"], observed=True)
        .agg(Trades=(col, "count"), Total_PnL=(col, "sum"), Avg_PnL=(col, "mean"))
        .reset_index()
        .rename(columns={"Total_PnL": "Total P&L (INR)", "Avg_PnL": "Avg P&L (INR)"})
        .round(2)
    )


def compute_benchmark_comparison(
    tradesheet: pd.DataFrame, cfg: StrategyConfig
) -> tuple[pd.DataFrame, pd.Series | None]:
    try:
        spot = load_spot(cfg)
    except Exception:
        return pd.DataFrame(), None

    entry_spot = spot[spot["minute"] == cfg.entry_time[:5]].copy()
    if entry_spot.empty:
        entry_spot = spot.groupby("Date", observed=True).first().reset_index()

    entry_spot["Date"] = pd.to_datetime(entry_spot["Date"])
    entry_spot = entry_spot.sort_values("Date").drop_duplicates("Date", keep="last")
    if entry_spot.empty:
        return pd.DataFrame(), None

    first_price = entry_spot["underlying_close"].iloc[0]
    bench_nav = cfg.base_nav * (entry_spot["underlying_close"] / first_price)
    bench_nav.index = entry_spot["Date"]

    strat_nav = compute_daily_nav(tradesheet, cfg)
    aligned = pd.DataFrame({"strategy": strat_nav}).join(
        pd.DataFrame({"benchmark": bench_nav}), how="inner"
    )
    if len(aligned) < 2:
        return pd.DataFrame(), bench_nav

    s_ret = aligned["strategy"].pct_change().dropna()
    b_ret = aligned["benchmark"].pct_change().dropna()
    common = s_ret.index.intersection(b_ret.index)
    s_ret = s_ret.loc[common]
    b_ret = b_ret.loc[common]

    beta = s_ret.cov(b_ret) / b_ret.var() if b_ret.var() > 0 else 0.0
    ann_rf = cfg.risk_free_rate / 252
    alpha_daily = s_ret.mean() - ann_rf - beta * (b_ret.mean() - ann_rf)
    alpha_annual = alpha_daily * 252

    tracking = s_ret - b_ret
    info_ratio = (tracking.mean() / tracking.std()) * np.sqrt(252) if tracking.std() > 0 else 0.0

    years = (strat_nav.index[-1] - strat_nav.index[0]).days / 365.25
    bench_cagr = (bench_nav.iloc[-1] / cfg.base_nav) ** (1 / years) - 1 if years > 0 else 0
    strat_cagr = (strat_nav.iloc[-1] / cfg.base_nav) ** (1 / years) - 1 if years > 0 else 0

    summary = pd.DataFrame(
        [
            {"Metric": "Strategy CAGR %", "Value": round(strat_cagr * 100, 2)},
            {"Metric": "Benchmark CAGR % (Buy & Hold)", "Value": round(bench_cagr * 100, 2)},
            {"Metric": "Alpha (annualized)", "Value": round(alpha_annual, 4)},
            {"Metric": "Beta vs Bank Nifty", "Value": round(beta, 4)},
            {"Metric": "Information Ratio", "Value": round(info_ratio, 4)},
            {"Metric": "Strategy Final NAV", "Value": round(strat_nav.iloc[-1], 4)},
            {"Metric": "Benchmark Final NAV", "Value": round(bench_nav.iloc[-1], 4)},
        ]
    )
    return summary, bench_nav


def compute_statistics(tradesheet: pd.DataFrame, cfg: StrategyConfig | None = None) -> dict:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()
    col = pnl_column(cfg)

    nav = compute_daily_nav(tradesheet, cfg)
    drawdown = compute_drawdown(nav)
    max_dd = drawdown.min()

    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / cfg.base_nav) ** (1 / years) - 1 if years > 0 else 0
    risk = compute_risk_metrics(nav, tradesheet, cagr, max_dd, col)

    win_loss = pd.DataFrame(
        [
            win_loss_stats(tradesheet[tradesheet["Option Type"] == "CE"], "CE", col),
            win_loss_stats(tradesheet[tradesheet["Option Type"] == "PE"], "PE", col),
            win_loss_stats(tradesheet, "Combined", col),
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

    daily_pnl = tradesheet.groupby("Entry Date", observed=True)[col].sum()
    equity_table = pd.DataFrame(
        {
            "Date": nav.index.strftime("%Y-%m-%d"),
            "Daily P&L": daily_pnl.reindex(nav.index.strftime("%Y-%m-%d")).values,
            "NAV": nav.round(4).values,
            "Drawdown %": drawdown.round(4).values,
        }
    )

    realism_comparison = compute_realism_comparison(tradesheet, cfg)
    benchmark_summary, benchmark_nav = compute_benchmark_comparison(tradesheet, cfg)
    attribution = {
        "day_of_week": day_of_week_attribution(tradesheet, cfg),
        "ce_pe_daily": ce_pe_daily_contribution(tradesheet, cfg),
        "vol_regime": volatility_regime_attribution(tradesheet, cfg),
        "moneyness": moneyness_attribution(tradesheet, cfg),
    }

    summary_rows = [
        {"Metric": "Starting Capital (INR)", "Value": cfg.starting_capital},
        {"Metric": "Base NAV", "Value": cfg.base_nav},
        {"Metric": "Final NAV", "Value": round(nav.iloc[-1], 4)},
        {"Metric": f"Total P&L (INR) [{col}]", "Value": round(tradesheet[col].sum(), 2)},
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
        {"Metric": "Realism Enabled", "Value": cfg.realism_enabled},
    ]
    if cfg.realism_enabled and "Net P&L" in tradesheet.columns:
        summary_rows.append(
            {"Metric": "Total Ideal P&L (INR)", "Value": round(tradesheet["Gross P&L"].sum(), 2)}
        )
        summary_rows.append(
            {"Metric": "Total Slippage (INR)", "Value": round(tradesheet["Slippage Cost"].sum(), 2)}
        )
        summary_rows.append(
            {"Metric": "Total Brokerage (INR)", "Value": round(tradesheet["Brokerage"].sum(), 2)}
        )
    if not benchmark_summary.empty:
        for _, row in benchmark_summary.iterrows():
            summary_rows.append({"Metric": row["Metric"], "Value": row["Value"]})

    summary = pd.DataFrame(summary_rows)

    tick("6_statistics_sec", t0)
    return {
        "summary": summary,
        "win_loss": win_loss,
        "expiry_stats": expiry_stats,
        "monthly_table": monthly_table,
        "equity_table": equity_table,
        "risk_metrics": risk,
        "realism_comparison": realism_comparison,
        "benchmark_summary": benchmark_summary,
        "benchmark_nav": benchmark_nav,
        "attribution": attribution,
        "nav": nav,
        "drawdown": drawdown,
        "max_dd": max_dd,
        "cagr": cagr,
    }
