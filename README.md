# Qode Assignment — Bank Nifty Short Strangle Backtest

09:20 AM short strangle backtest on Bank Nifty week-1 weekly options (Wednesday expiry), built for the Qode Quant Research Analyst assignment.

## Strategy

- **Entry:** 09:20 — sell 1 CE + 1 PE (strikes with premium closest to Rs. 50)
- **Exit:** 15:20 scheduled exit, or 50% stop-loss per leg (checked via 1-min `High`)
- **Sizing:** 1 lot × 15 quantity, no compounding
- **Period:** Full options dataset (247 trading days, Jan 2023 – Jan 2024)

## Project structure

| File | Description |
|---|---|
| `short_strangle_backtest.py` | Main backtest script (vectorized) |
| `short_strangle_backtest.ipynb` | Interactive Jupyter notebook |
| `backtest_output.xlsx` | Output: Guide, Tradesheet, Statistics sheets |
| `equity_curve.png` | Equity curve plot (base NAV = 100) |
| `drawdown.png` | Drawdown plot |
| `BANKNIFTY_SPOT.csv` | Bank Nifty spot 1-min data |
| `Options_data_2023.csv` | Options 1-min data *(not in repo — see below)* |

## Data setup

The options file (`Options_data_2023.csv`, ~720 MB) is **not tracked in Git** because it exceeds GitHub’s file size limit. Download it from the assignment Google Drive link and place it in the project root:

```
Options_data_2023.csv
BANKNIFTY_SPOT.csv
```

## Quick start

```bash
pip install -r requirements.txt
python short_strangle_backtest.py
```

Or open `short_strangle_backtest.ipynb` in Jupyter / VS Code and run cells top-to-bottom (execute **Section 1 Setup** first).

## Advanced usage

```bash
# CLI with YAML config
python -m qode_backtest run
python -m qode_backtest run --rebuild-cache
python -m qode_backtest sweep --premiums 40,50,60 --sl 1.3,1.5,1.7

# Streamlit dashboard
streamlit run dashboard.py

# PostgreSQL (optional)
docker compose up -d
copy .env.example .env
python -m qode_backtest db init
python -m qode_backtest db load
python -m qode_backtest db status
```

## Project structure

| Path | Description |
|---|---|
| `qode_backtest/` | Modular backtest package (config, data, signals, analytics, sweep) |
| `config.yaml` | Strategy parameters |
| `data/` | Auto-generated parquet cache |
| `tests/` | pytest suite with sample fixtures |
| `dashboard.py` | Interactive Streamlit UI |
| `docker-compose.yml` | Local PostgreSQL 16 instance |
| `sql/schema.sql` | Database tables for options, spot, trades |

## PostgreSQL

Market data and backtest results can be stored in PostgreSQL for querying and dashboards.

**Tables:** `options_bars`, `spot_bars`, `backtest_runs`, `trades`

```bash
docker compose up -d
pip install -r requirements.txt
python -m qode_backtest db init
python -m qode_backtest db load          # options + spot + trades
python -m qode_backtest db load --no-trades   # market data only
python -m qode_backtest db status
```

Connection string (default): `postgresql://qode:qode@localhost:5434/qode_backtest`  
Override with `DATABASE_URL` env var or `--dsn` flag.

## Performance

| Run | Typical runtime |
|---|---|
| First run (CSV parse + cache build) | ~35-40s |
| Repeat run (parquet cache) | ~5-8s |

## Sample results

| Metric | Value |
|---|---|
| Trading days | 247 |
| Total trades | 494 (2 per day) |
| CAGR | ~8.3% |
| Max drawdown | ~-3.1% |
| Runtime | ~40 seconds |

## Outputs

- **Tradesheet:** entry/exit, ticker, strike, P&L, cumulative P&L, available capital
- **Statistics:** CAGR, max drawdown, win/loss (CE/PE/combined), expiry vs non-expiry, monthly P&L, equity curve table
