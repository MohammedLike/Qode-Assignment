# Qode Assignment — Bank Nifty Short Strangle Backtest

09:20 AM short strangle backtest on Bank Nifty week-1 weekly options (Wednesday expiry), built for the Qode Quant Research Analyst assignment.

**Repository:** [github.com/MohammedLike/Qode-Assignment](https://github.com/MohammedLike/Qode-Assignment)

![CI](https://github.com/MohammedLike/Qode-Assignment/actions/workflows/ci.yml/badge.svg)

## Strategy

- **Entry:** 09:20 — sell 1 CE + 1 PE (strikes with premium closest to Rs. 50)
- **Exit:** 15:20 scheduled exit, or 50% stop-loss per leg (checked via 1-min `High`)
- **Sizing:** 1 lot × 15 quantity, no compounding
- **Period:** Full options dataset (247 trading days, Jan 2023 – Jan 2024)

## Architecture

```mermaid
flowchart LR
    CSV[Options + Spot CSV] --> Loader[data_loader]
    Loader --> Cache[(Parquet Cache)]
    Cache --> Strike[strike_selection]
    Strike --> Signals[signals / SL]
    Signals --> Sheet[tradesheet + realism]
    Sheet --> Analytics[analytics]
    Analytics --> Export[export Excel + PNG]
    Analytics --> Dash[Streamlit dashboard]
    Analytics --> PDF[submission PDF]
    Loader --> PG[(PostgreSQL)]
    Analytics --> Sweep[sweep heatmap]
```

## Features

| Layer | Capability |
|---|---|
| **Realism** | Slippage on SL exits, flat brokerage per leg, margin-exceeded flag; ideal vs realistic comparison |
| **Attribution** | Day-of-week, CE/PE daily contribution, volatility regimes, moneyness buckets |
| **Benchmark** | Strategy NAV vs Bank Nifty buy-and-hold; alpha, beta, information ratio |
| **Dashboard v2** | Drawdown chart, trade filters, sweep heatmap, ideal vs realistic overlay, export downloads |
| **Tests + CI** | `test_analytics`, `test_sweep`, `test_export`, PostgreSQL service in GitHub Actions |

## Project structure

| Path | Description |
|---|---|
| `short_strangle_backtest.py` | Backward-compatible entry point |
| `short_strangle_backtest.ipynb` | Interactive Jupyter notebook |
| `qode_backtest/` | Modular package (config, data, signals, analytics, sweep, db) |
| `config.yaml` | Strategy parameters |
| `dashboard.py` | Streamlit UI v2 (drawdown, filters, sweep, exports) |
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

# Streamlit dashboard (local)
streamlit run dashboard.py
```

### Deploy on Streamlit Cloud (public demo URL)

1. Push this repo to GitHub (data files stay gitignored).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repository.
3. Set **Main file path** to `dashboard.py`.
4. Add secrets only if needed (not required for local CSV mode).
5. For cloud demo, upload sample CSVs or use a smaller public dataset branch.

> **Demo GIF:** Screen-record the dashboard (`streamlit run dashboard.py`) showing equity curve, drawdown, attribution tab, and sweep heatmap. Save as `docs/dashboard_demo.gif` and embed in README for recruiters.

## Realism configuration (`config.yaml`)

```yaml
realism_enabled: true
slippage_pct: 0.005      # 0.5% adverse fill on SL exits
brokerage_per_leg: 20    # Rs. per leg
risk_free_rate: 0.06     # for alpha/beta vs benchmark
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
ruff check qode_backtest tests short_strangle_backtest.py dashboard.py generate_submission_report.py
```

CI runs ruff, pytest (including PostgreSQL integration via GitHub Actions service), on push to `main`.

## Outputs

- **Tradesheet:** entry/exit, gross/net P&L, slippage, brokerage, moneyness, margin flag
- **Statistics:** CAGR, drawdown, risk metrics, ideal vs realistic, benchmark alpha/beta
- **Attribution sheet:** day-of-week, CE/PE, volatility regimes, moneyness
- **Sensitivity sheet:** parameter sweep results (after `sweep` command)
- **Submission report:** `Qode_Assignment_Submission_Report.pdf` for HR review

```bash
# HR submission PDF
python generate_submission_report.py
python generate_submission_report.py --report-only   # if Excel is already built
```
