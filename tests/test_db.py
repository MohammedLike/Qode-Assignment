from __future__ import annotations

import pytest

from qode_backtest.config import StrategyConfig
from qode_backtest.db import connect, init_schema, load_options_to_db, load_spot_to_db, table_counts


def _db_available(dsn: str | None = None) -> bool:
    try:
        with connect(dsn, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not available (start with: docker compose up -d)",
)


@pytest.fixture
def db_cfg() -> StrategyConfig:
    from pathlib import Path

    fixtures = Path(__file__).parent / "fixtures"
    return StrategyConfig(
        options_file=fixtures / "options_sample.csv",
        spot_file=fixtures / "spot_sample.csv",
        use_parquet_cache=False,
    )


def test_init_schema():
    init_schema()


def test_load_fixture_data(db_cfg: StrategyConfig):
    init_schema()
    opt_n = load_options_to_db(db_cfg, truncate=True)
    spot_n = load_spot_to_db(db_cfg, truncate=True)
    assert opt_n > 0
    assert spot_n > 0
    counts = table_counts()
    assert counts["options_bars"] == opt_n
    assert counts["spot_bars"] == spot_n
