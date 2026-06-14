from pathlib import Path

import pytest

from qode_backtest.config import StrategyConfig
from qode_backtest.db import connect, init_schema, load_options_to_db, load_spot_to_db, table_counts


def _skip_db_tests() -> bool:
    try:
        with connect(connect_timeout=2):
            return False
    except Exception:
        return True


pytestmark = pytest.mark.skipif(
    _skip_db_tests(),
    reason="PostgreSQL integration tests skipped (CI or DB unavailable)",
)


@pytest.fixture
def db_cfg() -> StrategyConfig:
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
