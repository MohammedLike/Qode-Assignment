from __future__ import annotations

import os
import time
from io import StringIO

import pandas as pd
import psycopg

from qode_backtest.config import BASE_DIR, StrategyConfig
from qode_backtest.data_loader import load_options

SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"
DEFAULT_DSN = "postgresql://qode:qode@localhost:5434/qode_backtest"


def get_dsn(dsn: str | None = None) -> str:
    return dsn or os.environ.get("DATABASE_URL", DEFAULT_DSN)


def connect(dsn: str | None = None, *, connect_timeout: int = 5) -> psycopg.Connection:
    return psycopg.connect(get_dsn(dsn), connect_timeout=connect_timeout)


def init_schema(dsn: str | None = None) -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with connect(dsn) as conn:
        conn.execute(sql)
        conn.commit()
    print(f"Schema initialized ({SCHEMA_FILE.name})")


def _copy_dataframe(
    conn: psycopg.Connection,
    table: str,
    columns: list[str],
    df: pd.DataFrame,
) -> int:
    if df.empty:
        return 0

    buf = StringIO()
    df[columns].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    col_list = ", ".join(columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({col_list}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as copy:
            copy.write(buf.read())
    return len(df)


def _options_for_db(df: pd.DataFrame) -> pd.DataFrame:
    call_put = df["Call/Put"].astype(str) if "Call/Put" in df.columns else df["option_type"].astype(str)
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(df["Date"]).dt.date,
            "ticker": df["Ticker"].astype(str),
            "bar_time": pd.to_datetime(df["Time"], format="%H:%M:%S").dt.time,
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": df["Close"].astype(float),
            "call_put": call_put,
            "strike": df["strike"].astype(int),
            "option_type": df["option_type"].astype(str),
            "bar_minute": df["minute"].astype(str),
        }
    )
    return out


def _spot_raw_for_db(cfg: StrategyConfig) -> pd.DataFrame:
    spot = pd.read_csv(cfg.spot_file, parse_dates=["ts"])
    return pd.DataFrame(
        {
            "trade_date": spot["ts"].dt.date,
            "bar_minute": spot["ts"].dt.strftime("%H:%M"),
            "ts": spot["ts"],
            "open": spot["o"].astype(float),
            "high": spot["h"].astype(float),
            "low": spot["l"].astype(float),
            "close": spot["c"].astype(float),
        }
    ).drop_duplicates(subset=["trade_date", "bar_minute"], keep="last")


def load_options_to_db(
    cfg: StrategyConfig | None = None,
    *,
    dsn: str | None = None,
    truncate: bool = False,
) -> int:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()
    df = load_options(cfg)
    db_df = _options_for_db(df)

    columns = [
        "trade_date",
        "ticker",
        "bar_time",
        "open",
        "high",
        "low",
        "close",
        "call_put",
        "strike",
        "option_type",
        "bar_minute",
    ]

    with connect(dsn) as conn:
        if truncate:
            conn.execute("TRUNCATE options_bars RESTART IDENTITY")
        inserted = _copy_dataframe(conn, "options_bars", columns, db_df)
        conn.commit()

    elapsed = time.perf_counter() - t0
    print(f"Inserted {inserted:,} options rows in {elapsed:.1f}s")
    return inserted


def load_spot_to_db(
    cfg: StrategyConfig | None = None,
    *,
    dsn: str | None = None,
    truncate: bool = False,
) -> int:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()
    db_df = _spot_raw_for_db(cfg)

    columns = ["trade_date", "bar_minute", "ts", "open", "high", "low", "close"]

    with connect(dsn) as conn:
        if truncate:
            conn.execute("TRUNCATE spot_bars RESTART IDENTITY")
        inserted = _copy_dataframe(conn, "spot_bars", columns, db_df)
        conn.commit()

    elapsed = time.perf_counter() - t0
    print(f"Inserted {inserted:,} spot rows in {elapsed:.1f}s")
    return inserted


def _trades_for_db(tradesheet: pd.DataFrame, run_id: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_id": run_id,
            "entry_date": pd.to_datetime(tradesheet["Entry Date"]).dt.date,
            "entry_time": pd.to_datetime(tradesheet["Entry Time"], format="%H:%M:%S").dt.time,
            "exit_date": pd.to_datetime(tradesheet["Exit Date"]).dt.date,
            "exit_time": pd.to_datetime(tradesheet["Exit Time"], format="%H:%M:%S").dt.time,
            "option_ticker": tradesheet["Option Ticker"].astype(str),
            "strike_price": tradesheet["Strike Price"].astype(int),
            "option_type": tradesheet["Option Type"].astype(str),
            "entry_price": tradesheet["Entry Price"].astype(float),
            "exit_price": tradesheet["Exit Price"].astype(float),
            "quantity": tradesheet["Quantity"].astype(int),
            "entry_value": tradesheet["Entry Value"].astype(float),
            "exit_value": tradesheet["Exit Value"].astype(float),
            "gross_pnl": tradesheet["Gross P&L"].astype(float),
            "cumulative_pnl": tradesheet["Cumulative P&L"].astype(float),
            "available_capital": tradesheet["Available Capital"].astype(float),
            "banknifty_close": tradesheet["Banknifty Underlying Close"],
            "exit_reason": tradesheet["Exit Reason"].astype(str),
            "is_expiry_day": tradesheet["Is Expiry Day"].astype(bool),
            "pct_pnl": tradesheet["% P&L"].astype(float),
        }
    )


def save_backtest_run(
    tradesheet: pd.DataFrame,
    stats: dict,
    cfg: StrategyConfig,
    *,
    dsn: str | None = None,
) -> int:
    risk = stats.get("risk_metrics", {})
    sharpe = risk.get("Sharpe Ratio")

    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO backtest_runs (
                    target_premium, entry_time, exit_time, sl_multiplier,
                    lot_size, starting_capital, trading_days, total_trades,
                    cagr_pct, max_dd_pct, final_nav, sharpe
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    cfg.target_premium,
                    cfg.entry_time,
                    cfg.exit_time,
                    cfg.sl_multiplier,
                    cfg.lot_size,
                    cfg.starting_capital,
                    tradesheet["Entry Date"].nunique(),
                    len(tradesheet),
                    round(stats["cagr"] * 100, 4),
                    round(stats["max_dd"], 4),
                    round(float(stats["nav"].iloc[-1]), 4),
                    sharpe,
                ),
            )
            run_id = cur.fetchone()[0]

        db_trades = _trades_for_db(tradesheet, run_id)
        trade_columns = [
            "run_id",
            "entry_date",
            "entry_time",
            "exit_date",
            "exit_time",
            "option_ticker",
            "strike_price",
            "option_type",
            "entry_price",
            "exit_price",
            "quantity",
            "entry_value",
            "exit_value",
            "gross_pnl",
            "cumulative_pnl",
            "available_capital",
            "banknifty_close",
            "exit_reason",
            "is_expiry_day",
            "pct_pnl",
        ]
        _copy_dataframe(conn, "trades", trade_columns, db_trades)
        conn.commit()

    print(f"Saved backtest run #{run_id} with {len(tradesheet)} trades")
    return run_id


def load_all_to_db(
    cfg: StrategyConfig | None = None,
    *,
    dsn: str | None = None,
    include_trades: bool = True,
    truncate: bool = False,
) -> dict[str, int]:
    init_schema(dsn)
    counts = {
        "options": load_options_to_db(cfg, dsn=dsn, truncate=truncate),
        "spot": load_spot_to_db(cfg, dsn=dsn, truncate=truncate),
    }
    if include_trades:
        from qode_backtest.engine import run_pipeline

        cfg = cfg or StrategyConfig.from_yaml()
        tradesheet, stats, _ = run_pipeline(cfg, export=False)
        counts["run_id"] = save_backtest_run(tradesheet, stats, cfg, dsn=dsn)
    return counts


def table_counts(dsn: str | None = None) -> dict[str, int]:
    with connect(dsn) as conn:
        with conn.cursor() as cur:
            counts = {}
            for table in ("options_bars", "spot_bars", "backtest_runs", "trades"):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
    return counts
