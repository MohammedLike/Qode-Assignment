from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qode_backtest.config import StrategyConfig
from qode_backtest.data_loader import _preprocess_options
from qode_backtest.engine import run_pipeline
from qode_backtest.signals import apply_signals
from qode_backtest.strike_selection import select_strikes

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_cfg() -> StrategyConfig:
    return StrategyConfig(
        options_file=FIXTURES / "options_sample.csv",
        spot_file=FIXTURES / "spot_sample.csv",
        use_parquet_cache=False,
        target_premium=50.0,
        sl_multiplier=1.5,
    )


@pytest.fixture
def sample_options(sample_cfg: StrategyConfig) -> pd.DataFrame:
    df = pd.read_csv(sample_cfg.options_file)
    return _preprocess_options(df, sample_cfg)


def test_strike_selection_ce_closest_to_50(sample_options, sample_cfg):
    entry = sample_options[sample_options["Time"] == sample_cfg.entry_time]
    selected = select_strikes(entry, sample_cfg)
    ce = selected[selected["option_type"] == "CE"].iloc[0]
    assert ce["Ticker"] == "BANKNIFTY44000CE"
    assert ce["entry_price"] == pytest.approx(50.05)


def test_stop_loss_ce_exit(sample_options, sample_cfg):
    entry = sample_options[sample_options["Time"] == sample_cfg.entry_time]
    selected = select_strikes(entry, sample_cfg)
    trades = apply_signals(selected, sample_options, sample_cfg)
    ce = trades[(trades["Date"] == "2023-01-02") & (trades["option_type"] == "CE")].iloc[0]
    assert ce["exit_reason"] == "Stop Loss"
    assert ce["exit_price"] == pytest.approx(50.05 * 1.5, rel=1e-4)
    assert ce["exit_time"] == "09:44:59"


def test_short_pnl_sign(sample_options, sample_cfg):
    entry = sample_options[sample_options["Time"] == sample_cfg.entry_time]
    selected = select_strikes(entry, sample_cfg)
    trades = apply_signals(selected, sample_options, sample_cfg)
    from qode_backtest.tradesheet import build_tradesheet
    from qode_backtest.data_loader import load_spot

    spot = load_spot(sample_cfg)
    sheet = build_tradesheet(trades, spot, sample_cfg)
    for _, row in sheet.iterrows():
        assert row["Gross P&L"] == pytest.approx(
            row["Entry Value"] - row["Exit Value"], abs=0.001
        )


def test_two_trades_per_day(sample_options, sample_cfg):
    entry = sample_options[sample_options["Time"] == sample_cfg.entry_time]
    selected = select_strikes(entry, sample_cfg)
    assert selected.groupby("Date").size().max() == 2


def test_nav_starts_at_base(sample_cfg):
    tradesheet, stats, _ = run_pipeline(sample_cfg, export=False)
    assert stats["nav"].iloc[0] == pytest.approx(sample_cfg.base_nav, rel=1e-3)
