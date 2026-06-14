from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OPTIONS_FILE = BASE_DIR / "Options_data_2023.csv"
SPOT_FILE = BASE_DIR / "BANKNIFTY_SPOT.csv"
OPTIONS_PARQUET = DATA_DIR / "options_0920_1520.parquet"
OUTPUT_XLSX = BASE_DIR / "backtest_output.xlsx"
EQUITY_PNG = BASE_DIR / "equity_curve.png"
DRAWDOWN_PNG = BASE_DIR / "drawdown.png"
SENSITIVITY_PNG = BASE_DIR / "sensitivity_heatmap.png"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"


@dataclass
class StrategyConfig:
    target_premium: float = 50.0
    entry_time: str = "09:20:59"
    exit_time: str = "15:20:59"
    sl_multiplier: float = 1.5
    lots: int = 1
    lot_size: int = 15
    starting_capital: float = 100_000
    base_nav: float = 100.0
    options_file: Path = field(default_factory=lambda: OPTIONS_FILE)
    spot_file: Path = field(default_factory=lambda: SPOT_FILE)
    use_parquet_cache: bool = True
    force_rebuild_cache: bool = False
    realism_enabled: bool = True
    slippage_pct: float = 0.005
    brokerage_per_leg: float = 20.0
    risk_free_rate: float = 0.06

    @property
    def quantity(self) -> int:
        return self.lots * self.lot_size

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> StrategyConfig:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in raw.items() if k in known}
        if "options_file" in kwargs:
            kwargs["options_file"] = Path(kwargs["options_file"])
        if "spot_file" in kwargs:
            kwargs["spot_file"] = Path(kwargs["spot_file"])
        return cls(**kwargs)
