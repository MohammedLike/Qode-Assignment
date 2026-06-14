"""
Bank Nifty 09:20 Short Strangle Backtest
Qode Quant Research Analyst Assignment
"""

from __future__ import annotations

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
OPTIONS_FILE = BASE_DIR / "Options_data_2023.csv"
SPOT_FILE = BASE_DIR / "BANKNIFTY_SPOT.csv"
OUTPUT_XLSX = BASE_DIR / "backtest_output.xlsx"
EQUITY_PNG = BASE_DIR / "equity_curve.png"
DRAWDOWN_PNG = BASE_DIR / "drawdown.png"

TARGET_PREMIUM = 50.0
ENTRY_TIME = "09:20:59"
EXIT_TIME = "15:20:59"
LOTS = 1
LOT_SIZE = 15
QUANTITY = LOTS * LOT_SIZE
STARTING_CAPITAL = 100_000
BASE_NAV = 100.0
SL_MULTIPLIER = 1.5  # 50% stop loss above entry (short)

TIMINGS: dict[str, float] = {}


def _tick(label: str, t0: float) -> float:
    elapsed = time.perf_counter() - t0
    TIMINGS[label] = elapsed
    return time.perf_counter()


# ---------------------------------------------------------------------------
# Module 1 — Data Loading
# ---------------------------------------------------------------------------
def load_options() -> pd.DataFrame:
    """Load and preprocess options data (09:20–15:20 window only)."""
    t0 = time.perf_counter()

    usecols = ["Date", "Ticker", "Time", "Open", "High", "Low", "Close", "Call/Put"]
    df = pd.read_csv(
        OPTIONS_FILE,
        usecols=usecols,
        dtype={"Ticker": "category", "Call/Put": "category"},
    )
    df["Time"] = df["Time"].astype(str)

    # Keep only bars needed for entry, SL scan, and scheduled exit
    time_mask = (df["Time"] >= ENTRY_TIME) & (df["Time"] <= EXIT_TIME)
    df = df.loc[time_mask].copy()
    df = df.drop_duplicates(subset=["Date", "Ticker", "Time"], keep="last")

    extracted = df["Ticker"].astype(str).str.extract(r"BANKNIFTY(\d+)(CE|PE)")
    df["strike"] = extracted[0].astype(np.int32)
    df["option_type"] = extracted[1]
    df["minute"] = df["Time"].astype(str).str.slice(0, 5)  # HH:MM

    _tick("1_load_options_sec", t0)
    return df


def load_spot() -> pd.DataFrame:
    """Load spot index and normalize to Date + minute for merge."""
    t0 = time.perf_counter()

    spot = pd.read_csv(SPOT_FILE, parse_dates=["ts"])
    spot["Date"] = spot["ts"].dt.strftime("%Y-%m-%d")
    spot["minute"] = spot["ts"].dt.strftime("%H:%M")
    spot = spot.rename(columns={"c": "underlying_close"})
    spot = spot[["Date", "minute", "underlying_close"]].drop_duplicates(
        subset=["Date", "minute"], keep="last"
    )

    _tick("2_load_spot_sec", t0)
    return spot


# ---------------------------------------------------------------------------
# Module 2 — Strike Selection
# ---------------------------------------------------------------------------
def select_strikes(entry_bars: pd.DataFrame) -> pd.DataFrame:
    """Pick CE and PE strikes with 09:20 close closest to Rs. 50."""
    t0 = time.perf_counter()

    bars = entry_bars.copy()
    bars = bars.drop(columns=["option_type"], errors="ignore")
    bars["premium_dist"] = (bars["Close"] - TARGET_PREMIUM).abs()

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
    selected["entry_time"] = ENTRY_TIME

    _tick("3_strike_selection_sec", t0)
    return selected[
        [
            "Date",
            "Ticker",
            "strike",
            "option_type",
            "entry_price",
            "entry_time",
            "minute",
        ]
    ]


# ---------------------------------------------------------------------------
# Module 3 — Signal Generation + Stop Loss
# ---------------------------------------------------------------------------
def apply_signals(selected: pd.DataFrame, intraday: pd.DataFrame) -> pd.DataFrame:
    """Determine exit time/price via 50% SL or scheduled 15:20 exit."""
    t0 = time.perf_counter()

    sl_window = intraday[intraday["Time"] > ENTRY_TIME].copy()

    path = selected.merge(
        sl_window[["Date", "Ticker", "Time", "High", "Close"]],
        on=["Date", "Ticker"],
        how="left",
    )
    path["sl_price"] = path["entry_price"] * SL_MULTIPLIER
    path["sl_hit"] = path["High"] >= path["sl_price"]

    sl_exits = (
        path[path["sl_hit"]]
        .sort_values(["Date", "Ticker", "Time"])
        .groupby(["Date", "Ticker"], observed=True)
        .first()
        .reset_index()
    )
    sl_exits = sl_exits.assign(
        exit_time=sl_exits["Time"],
        exit_price=sl_exits["sl_price"],
        exit_reason="Stop Loss",
    )

    scheduled = intraday[intraday["Time"] == EXIT_TIME][
        ["Date", "Ticker", "Time", "Close"]
    ].rename(columns={"Time": "exit_time", "Close": "exit_price"})
    scheduled["exit_reason"] = "Scheduled Exit"

    trades = selected.merge(
        sl_exits[["Date", "Ticker", "exit_time", "exit_price", "exit_reason"]],
        on=["Date", "Ticker"],
        how="left",
    )
    trades = trades.merge(
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
            "exit_time_sl",
            "exit_time_sched",
            "exit_price_sl",
            "exit_price_sched",
            "exit_reason_sl",
            "exit_reason_sched",
        ]
    )

    _tick("4_signal_stoploss_sec", t0)
    return trades


# ---------------------------------------------------------------------------
# Module 4 & 5 — Position Sizing + Trade Sheet
# ---------------------------------------------------------------------------
def build_tradesheet(trades: pd.DataFrame, spot: pd.DataFrame) -> pd.DataFrame:
    """Build full trade log with P&L, capital, and underlying."""
    t0 = time.perf_counter()

    ts = trades.copy()
    ts["quantity"] = QUANTITY
    ts["entry_value"] = ts["entry_price"] * ts["quantity"]
    ts["exit_value"] = ts["exit_price"] * ts["quantity"]
    ts["gross_pnl"] = ts["entry_value"] - ts["exit_value"]
    ts["pct_pnl"] = (ts["gross_pnl"] / ts["entry_value"]) * 100

    ts["is_expiry_day"] = pd.to_datetime(ts["Date"]).dt.dayofweek == 2

    ts = ts.sort_values(["Date", "option_type"], ascending=[True, False])  # CE before PE
    ts["cumulative_pnl"] = ts["gross_pnl"].cumsum()

    daily_pnl = ts.groupby("Date", observed=True)["gross_pnl"].sum()
    daily_capital = STARTING_CAPITAL + daily_pnl.cumsum()
    ts["available_capital"] = ts["Date"].map(daily_capital)

    ts = ts.merge(
        spot.rename(columns={"minute": "entry_minute", "underlying_close": "banknifty_close"}),
        left_on=["Date", "minute"],
        right_on=["Date", "entry_minute"],
        how="left",
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
            "Gross P&L": ts["gross_pnl"].round(2),
            "Cumulative P&L": ts["cumulative_pnl"].round(2),
            "Available Capital": ts["available_capital"].round(2),
            "Banknifty Underlying Close": ts["banknifty_close"],
            "Exit Reason": ts["exit_reason"],
            "Is Expiry Day": ts["is_expiry_day"],
            "% P&L": ts["pct_pnl"].round(2),
        }
    )

    _tick("5_tradesheet_sec", t0)
    return sheet


# ---------------------------------------------------------------------------
# Module 6 — Statistical Analysis
# ---------------------------------------------------------------------------
def compute_daily_nav(tradesheet: pd.DataFrame) -> pd.Series:
    """Daily NAV series (base 100), trade-wise / day-end."""
    daily_pnl = (
        tradesheet.groupby("Entry Date", observed=True)["Gross P&L"].sum().sort_index()
    )
    dates = pd.to_datetime(daily_pnl.index)
    nav_values = BASE_NAV + (daily_pnl.cumsum().values / STARTING_CAPITAL * BASE_NAV)
    nav = pd.Series(nav_values, index=dates, name="NAV")
    return nav


def compute_drawdown(nav: pd.Series) -> pd.Series:
    peak = nav.cummax()
    return (nav - peak) / peak * 100


def win_loss_stats(tradesheet: pd.DataFrame, label: str) -> dict:
    """Win/loss summary for a subset of trades."""
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
    """Average % P&L for expiry vs non-expiry days."""
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


def compute_statistics(tradesheet: pd.DataFrame) -> dict:
    """Full statistical analysis bundle."""
    t0 = time.perf_counter()

    nav = compute_daily_nav(tradesheet)
    drawdown = compute_drawdown(nav)
    max_dd = drawdown.min()

    years = (nav.index[-1] - nav.index[0]).days / 365.25
    cagr = (nav.iloc[-1] / BASE_NAV) ** (1 / years) - 1 if years > 0 else 0

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
    monthly_pnl.iloc[0] = (monthly_nav.iloc[0] / BASE_NAV - 1) * 100
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

    summary = pd.DataFrame(
        [
            {"Metric": "Starting Capital (INR)", "Value": STARTING_CAPITAL},
            {"Metric": "Base NAV", "Value": BASE_NAV},
            {"Metric": "Final NAV", "Value": round(nav.iloc[-1], 4)},
            {"Metric": "Total Gross P&L (INR)", "Value": round(tradesheet["Gross P&L"].sum(), 2)},
            {"Metric": "CAGR", "Value": f"{cagr * 100:.2f}%"},
            {"Metric": "Max Drawdown", "Value": f"{max_dd:.2f}%"},
            {"Metric": "Total Trading Days", "Value": nav.shape[0]},
            {"Metric": "Total Trades", "Value": len(tradesheet)},
            {"Metric": "SL Exits", "Value": (tradesheet["Exit Reason"] == "Stop Loss").sum()},
            {"Metric": "Scheduled Exits", "Value": (tradesheet["Exit Reason"] == "Scheduled Exit").sum()},
        ]
    )

    _tick("6_statistics_sec", t0)
    return {
        "summary": summary,
        "win_loss": win_loss,
        "expiry_stats": expiry_stats,
        "monthly_table": monthly_table,
        "equity_table": equity_table,
        "nav": nav,
        "drawdown": drawdown,
        "max_dd": max_dd,
        "cagr": cagr,
    }


# ---------------------------------------------------------------------------
# Module 7 — Plots
# ---------------------------------------------------------------------------
def save_plots(nav: pd.Series, drawdown: pd.Series, max_dd: float) -> None:
    t0 = time.perf_counter()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(nav.index, nav.values, color="#1f77b4", linewidth=1.2)
    ax.axhline(BASE_NAV, color="gray", linestyle="--", linewidth=0.8, label="Base NAV (100)")
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

    _tick("7_plots_sec", t0)


# ---------------------------------------------------------------------------
# Module 8 — Excel Export
# ---------------------------------------------------------------------------
def build_guide_sheet() -> pd.DataFrame:
    """Documentation / guide worksheet."""
    lines = [
        ("Section", "Details"),
        ("Assignment", "09:20 AM Bank Nifty Short Strangle Backtest"),
        ("Strategy", "Sell 1 CE + 1 PE at 09:20; exit at 15:20 or 50% SL per leg"),
        ("Strike Selection", f"09:20 1-min Close closest to Rs. {TARGET_PREMIUM} for CE and PE separately"),
        ("Entry Time", ENTRY_TIME),
        ("Exit Time", EXIT_TIME),
        ("Stop Loss", "50% above entry price; checked via High column (short position)"),
        ("SL Fill Price", f"Entry × {SL_MULTIPLIER} at first breach minute"),
        ("Position Size", f"{LOTS} lot × {LOT_SIZE} = {QUANTITY} quantity per leg, no compounding"),
        ("Expiry Day", "Wednesday (week-1 weekly Bank Nifty options)"),
        ("Week-1 Filter", "Dataset contains nearest Wednesday expiry contracts only"),
        ("Starting Capital", f"Rs. {STARTING_CAPITAL:,}"),
        ("Base NAV", str(BASE_NAV)),
        ("P&L Formula", "Gross P&L = Entry Value - Exit Value (short option)"),
        ("", ""),
        ("Runtime Breakdown (seconds)", ""),
    ]
    for key, val in TIMINGS.items():
        lines.append((key, f"{val:.3f}"))

    return pd.DataFrame(lines[1:], columns=lines[0])


def export_excel(tradesheet: pd.DataFrame, stats: dict, total_t0: float) -> None:
    t0 = time.perf_counter()

    export_tradesheet = tradesheet.drop(columns=["Exit Reason", "Is Expiry Day", "% P&L"])

    _tick("8_excel_export_prep_sec", t0)
    TIMINGS["total_sec"] = time.perf_counter() - total_t0
    guide = build_guide_sheet()

    t0 = time.perf_counter()
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        guide.to_excel(writer, sheet_name="Guide", index=False)
        export_tradesheet.to_excel(writer, sheet_name="Tradesheet", index=False)

        row = 0
        stats["summary"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
        row += len(stats["summary"]) + 3

        pd.DataFrame([{"Metric": "Win/Loss Analysis"}]).to_excel(
            writer, sheet_name="Statistics", index=False, header=False, startrow=row
        )
        row += 2
        stats["win_loss"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
        row += len(stats["win_loss"]) + 3

        pd.DataFrame([{"Metric": "Expiry vs Non-Expiry Avg % P&L"}]).to_excel(
            writer, sheet_name="Statistics", index=False, header=False, startrow=row
        )
        row += 2
        stats["expiry_stats"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
        row += len(stats["expiry_stats"]) + 3

        pd.DataFrame([{"Metric": "Monthly % P&L (from NAV)"}]).to_excel(
            writer, sheet_name="Statistics", index=False, header=False, startrow=row
        )
        row += 2
        stats["monthly_table"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)
        row += len(stats["monthly_table"]) + 3

        pd.DataFrame([{"Metric": "Equity Curve Table"}]).to_excel(
            writer, sheet_name="Statistics", index=False, header=False, startrow=row
        )
        row += 2
        stats["equity_table"].to_excel(writer, sheet_name="Statistics", index=False, startrow=row)

    _tick("8_excel_write_sec", t0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_backtest() -> pd.DataFrame:
    total_t0 = time.perf_counter()

    options = load_options()
    spot = load_spot()

    entry_bars = options[options["Time"] == ENTRY_TIME]
    selected = select_strikes(entry_bars)

    trades_raw = apply_signals(selected, options)
    tradesheet = build_tradesheet(trades_raw, spot)

    stats = compute_statistics(tradesheet)
    save_plots(stats["nav"], stats["drawdown"], stats["max_dd"])
    export_excel(tradesheet, stats, total_t0)

    print("\n=== Backtest Complete ===")
    print(f"Trading days : {tradesheet['Entry Date'].nunique()}")
    print(f"Total trades : {len(tradesheet)}")
    print(f"CAGR         : {stats['cagr'] * 100:.2f}%")
    print(f"Max Drawdown : {stats['max_dd']:.2f}%")
    print(f"Final NAV    : {stats['nav'].iloc[-1]:.4f}")
    print("\nRuntime (seconds):")
    for k, v in TIMINGS.items():
        print(f"  {k}: {v:.3f}")

    return tradesheet


if __name__ == "__main__":
    run_backtest()
