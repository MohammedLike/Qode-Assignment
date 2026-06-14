from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qode_backtest.config import StrategyConfig
from qode_backtest.engine import run_pipeline
from qode_backtest.export import export_excel

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_cfg(tmp_path: Path) -> StrategyConfig:
    return StrategyConfig(
        options_file=FIXTURES / "options_sample.csv",
        spot_file=FIXTURES / "spot_sample.csv",
        use_parquet_cache=False,
        realism_enabled=True,
    )


def test_export_excel_sheets_exist(sample_cfg: StrategyConfig, tmp_path: Path, monkeypatch):
    import qode_backtest.export as export_mod

    out = tmp_path / "test_output.xlsx"
    monkeypatch.setattr(export_mod, "OUTPUT_XLSX", out)

    tradesheet, stats, _ = run_pipeline(sample_cfg, export=False)
    export_excel(tradesheet, stats, 0.0, None, sample_cfg)

    assert out.exists()
    xl = pd.ExcelFile(out)
    assert "Guide" in xl.sheet_names
    assert "Tradesheet" in xl.sheet_names
    assert "Statistics" in xl.sheet_names
    assert "Attribution" in xl.sheet_names

    ts = pd.read_excel(out, sheet_name="Tradesheet")
    assert "Net P&L" in ts.columns
    assert "Gross P&L" in ts.columns
    assert "Moneyness" in ts.columns
