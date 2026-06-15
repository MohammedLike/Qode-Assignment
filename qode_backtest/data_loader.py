from __future__ import annotations

import time

import numpy as np
import pandas as pd

from qode_backtest.config import OPTIONS_PARQUET, StrategyConfig
from qode_backtest.timing import tick


def _preprocess_options(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()
    df["Time"] = df["Time"].astype(str)
    time_mask = (df["Time"] >= cfg.entry_time) & (df["Time"] <= cfg.exit_time)
    df = df.loc[time_mask]
    df = df.drop_duplicates(subset=["Date", "Ticker", "Time"], keep="last")

    extracted = df["Ticker"].astype(str).str.extract(r"BANKNIFTY(\d+)(CE|PE)")
    df["strike"] = extracted[0].astype(np.int32)
    df["option_type"] = extracted[1]
    df["minute"] = df["Time"].str.slice(0, 5)
    return df


def _load_options_from_csv(cfg: StrategyConfig) -> pd.DataFrame:
    usecols = ["Date", "Ticker", "Time", "Open", "High", "Low", "Close", "Call/Put"]
    df = pd.read_csv(
        cfg.options_file,
        usecols=usecols,
        dtype={"Ticker": "category", "Call/Put": "category"},
    )
    return _preprocess_options(df, cfg)


def _cache_is_stale(cfg: StrategyConfig) -> bool:
    if cfg.force_rebuild_cache or not OPTIONS_PARQUET.exists():
        return True
    if not cfg.options_file.exists():
        return False
    return cfg.options_file.stat().st_mtime > OPTIONS_PARQUET.stat().st_mtime


def _write_parquet_cache(df: pd.DataFrame) -> None:
    OPTIONS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OPTIONS_PARQUET, engine="pyarrow", index=False)


def load_options(cfg: StrategyConfig | None = None) -> pd.DataFrame:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()

    if cfg.use_parquet_cache and not _cache_is_stale(cfg):
        df = pd.read_parquet(OPTIONS_PARQUET, engine="pyarrow")
        tick("1_load_options_sec", t0)
        return df

    df = _load_options_from_csv(cfg)
    if cfg.use_parquet_cache:
        _write_parquet_cache(df)

    tick("1_load_options_sec", t0)
    return df


def load_spot(cfg: StrategyConfig | None = None) -> pd.DataFrame:
    cfg = cfg or StrategyConfig.from_yaml()
    t0 = time.perf_counter()
    spot = pd.read_csv(cfg.spot_file, parse_dates=["ts"])
    spot["Date"] = spot["ts"].dt.strftime("%Y-%m-%d")
    spot["minute"] = spot["ts"].dt.strftime("%H:%M")
    spot = spot.rename(columns={"c": "underlying_close"})
    spot = spot[["Date", "minute", "underlying_close"]].drop_duplicates(
        subset=["Date", "minute"], keep="last"
    )
    tick("2_load_spot_sec", t0)
    return spot
