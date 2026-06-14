from __future__ import annotations

from pathlib import Path

from dataclasses import replace

import pytest

from qode_backtest.analytics import compute_daily_nav, pnl_column
from qode_backtest.config import StrategyConfig
from qode_backtest.engine import run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_cfg() -> StrategyConfig:
    return StrategyConfig(
        options_file=FIXTURES / "options_sample.csv",
        spot_file=FIXTURES / "spot_sample.csv",
        use_parquet_cache=False,
        target_premium=50.0,
        sl_multiplier=1.5,
        realism_enabled=False,
    )


def test_nav_starts_at_base(sample_cfg: StrategyConfig):
    tradesheet, stats, _ = run_pipeline(sample_cfg, export=False)
    assert stats["nav"].iloc[0] == pytest.approx(sample_cfg.base_nav, rel=1e-3)


def test_drawdown_non_positive(sample_cfg: StrategyConfig):
    _, stats, _ = run_pipeline(sample_cfg, export=False)
    assert float(stats["drawdown"].max()) <= 0.0 + 1e-6
    assert stats["max_dd"] <= 0


def test_sharpe_finite_with_trades(sample_cfg: StrategyConfig):
    _, stats, _ = run_pipeline(sample_cfg, export=False)
    sharpe = stats["risk_metrics"]["Sharpe Ratio"]
    assert isinstance(sharpe, (int, float))
    assert sharpe == sharpe  # not NaN


def test_realism_reduces_pnl(sample_cfg: StrategyConfig):
    _, stats_ideal, _ = run_pipeline(sample_cfg, export=False)
    cfg_real = replace(sample_cfg, realism_enabled=True)
    tradesheet, stats_real, _ = run_pipeline(cfg_real, export=False)
    assert tradesheet["Net P&L"].sum() <= tradesheet["Gross P&L"].sum()
    assert stats_real["nav"].iloc[-1] <= stats_ideal["nav"].iloc[-1]


def test_pnl_column_switches(sample_cfg: StrategyConfig):
    tradesheet, _, _ = run_pipeline(sample_cfg, export=False)
    assert pnl_column(sample_cfg) == "Gross P&L"
    cfg_real = replace(sample_cfg, realism_enabled=True)
    assert pnl_column(cfg_real) == "Net P&L"
    nav = compute_daily_nav(tradesheet, cfg_real)
    assert len(nav) >= 1


def test_attribution_keys_present(sample_cfg: StrategyConfig):
    tradesheet, stats, _ = run_pipeline(sample_cfg, export=False)
    attr = stats["attribution"]
    assert "day_of_week" in attr
    assert "ce_pe_daily" in attr
    assert not attr["day_of_week"].empty
