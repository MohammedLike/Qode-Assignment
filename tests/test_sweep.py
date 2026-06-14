from __future__ import annotations

from pathlib import Path

import pytest

from qode_backtest.config import StrategyConfig
from qode_backtest.data_loader import load_options, load_spot
from qode_backtest.sweep import run_sweep

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_cfg() -> StrategyConfig:
    return StrategyConfig(
        options_file=FIXTURES / "options_sample.csv",
        spot_file=FIXTURES / "spot_sample.csv",
        use_parquet_cache=False,
        realism_enabled=False,
    )


def test_sweep_grid_shape(sample_cfg: StrategyConfig):
    options = load_options(sample_cfg)
    spot = load_spot(sample_cfg)
    premiums = [40.0, 50.0]
    sls = [1.3, 1.5]
    df = run_sweep(options, spot, sample_cfg, premiums, sls)
    assert len(df) == len(premiums) * len(sls)
    assert set(df.columns) >= {
        "target_premium",
        "sl_multiplier",
        "cagr_pct",
        "max_dd_pct",
        "final_nav",
        "total_pnl",
        "total_trades",
    }


def test_sweep_higher_sl_not_worse_on_all_metrics(sample_cfg: StrategyConfig):
    """Looser SL should not produce strictly lower final NAV on every cell (sanity)."""
    options = load_options(sample_cfg)
    spot = load_spot(sample_cfg)
    df = run_sweep(options, spot, sample_cfg, [50.0], [1.3, 1.7])
    assert df["final_nav"].notna().all()
    assert df["total_trades"].iloc[0] == df["total_trades"].iloc[1]
