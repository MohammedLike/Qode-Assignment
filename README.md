# Qode Assignment — Bank Nifty Short Strangle Backtest

09:20 AM short strangle backtest on Bank Nifty week-1 weekly options (Wednesday expiry), built for the Qode Quant Research Analyst assignment.

**Repository:** [github.com/MohammedLike/Qode-Assignment](https://github.com/MohammedLike/Qode-Assignment)

![CI](https://github.com/MohammedLike/Qode-Assignment/actions/workflows/ci.yml/badge.svg)

## Strategy

- **Entry:** 09:20 — sell 1 CE + 1 PE (strikes with premium closest to Rs. 50)
- **Exit:** 15:20 scheduled exit, or 50% stop-loss per leg (checked via 1-min `High`)
- **Sizing:** 1 lot × 15 quantity, no compounding
- **Period:** Full options dataset (247 trading days, Jan 2023 – Jan 2024)

## Project structure

| Path | Description |
|---|---|
| `short_strangle_backtest.py` | Backward-compatible entry point |
| `short_strangle_backtest.ipynb` | Interactive Jupyter notebook |
| `qode_backtest/` | Modular package (config, data, signals, analytics, sweep, db) |
| `config.yaml` | Strategy parameters |
| `dashboard.py` | Streamlit UI with Plotly charts |
| `generate_submission_report.py` | HR submission PDF generator |
| `docker-compose.yml` | Local PostgreSQL 16 instance |
| `sql/schema.sql` | Database schema |
| `tests/` | pytest suite with small CSV fixtures |
| `.github/workflows/ci.yml` | GitHub Actions (ruff + pytest) |

## Data setup

Raw data files are **not in Git** (too large). Download both from the assignment Google Drive link and place them in the project root:

```
Options_data_2023.csv   (~720 MB)
BANKNIFTY_SPOT.csv      (~8 MB)
```

Running the backtest generates these files locally (also gitignored):

```
backtest_output.xlsx
equity_curve.png
drawdown.png
sensitivity_heatmap.png   (after parameter sweep)
Qode_Assignment_Submission_Report.pdf
data/options_0920_1520.parquet   (auto cache)
```

## Quick start

```bash
pip install -r requirements.txt
python short_strangle_backtest.py
# or
python -m qode_backtest run
```

Or open `short_strangle_backtest.ipynb` in Jupyter / VS Code (run **Section 1 Setup** first).

## CLI commands

```bash
# Backtest
python -m qode_backtest run
python -m qode_backtest run --rebuild-cache
python -m qode_backtest run --no-export

# Parameter sweep (premium x SL multiplier)
python -m qode_backtest sweep
python -m qode_backtest sweep --premiums 40,50,60 --sl 1.3,1.5,1.7

# Streamlit dashboard
streamlit run dashboard.py

# HR submission PDF
python generate_submission_report.py
python generate_submission_report.py --report-only   # if Excel is already built
```

## PostgreSQL (optional)

Store market data and backtest results for SQL querying (pgAdmin, DBeaver, etc.).

**Tables:** `options_bars`, `spot_bars`, `backtest_runs`, `trades`

```bash
docker compose up -d
python -m qode_backtest db init
python -m qode_backtest db load
python -m qode_backtest db status
```

**pgAdmin connection settings:**

| Field | Value |
|---|---|
| Host | `localhost` |
| Port | `5434` |
| Database | `qode_backtest` |
| Username | `qode` |
| Password | `qode` |

Connection URL: `postgresql://qode:qode@localhost:5434/qode_backtest`

## Performance

| Run type | Typical runtime |
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
| Sharpe ratio | ~1.25 |
| Final NAV (base 100) | ~108.26 |

## Testing and CI

```bash
pytest tests/ -v
ruff check qode_backtest tests short_strangle_backtest.py dashboard.py
```

CI runs automatically on push to `main` via GitHub Actions.

## Outputs

- **Tradesheet:** entry/exit, ticker, strike, P&L, cumulative P&L, available capital
- **Statistics:** CAGR, max drawdown, Sharpe/Sortino/Calmar, win/loss (CE/PE/combined), expiry vs non-expiry, monthly P&L
- **Sensitivity sheet:** parameter sweep results (after `sweep` command)
- **Submission report:** `Qode_Assignment_Submission_Report.pdf` for HR review
