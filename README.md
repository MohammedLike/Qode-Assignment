# Bank Nifty Short Strangle Backtest

09:20 AM short strangle on Bank Nifty week-1 weekly options (Wednesday expiry).  
Built for the Qode Quant Research Analyst assignment.

Repo: [github.com/MohammedLike/Qode-Assignment](https://github.com/MohammedLike/Qode-Assignment)

## Strategy

- Entry 09:20 — sell 1 CE + 1 PE, strike with premium closest to Rs. 50
- Exit 15:20 or 50% SL per leg (checked on 1-min High)
- 1 lot x 15 qty, no compounding
- Jan 2023 – Jan 2024 (247 trading days)

## Setup

Download from the assignment Drive and put in project root:

```
Options_data_2023.csv
BANKNIFTY_SPOT.csv
```

```bash
pip install -r requirements.txt
python short_strangle_backtest.py
```

Or: `python -m qode_backtest run`

Outputs (local, gitignored): `backtest_output.xlsx`, equity/drawdown PNGs, optional PDF report.

## Project layout

| File / folder | What it does |
|---|---|
| `short_strangle_backtest.py` | Main entry point |
| `short_strangle_backtest.ipynb` | Notebook version |
| `qode_backtest/` | Backtest modules |
| `config.yaml` | Parameters |
| `dashboard.py` | Streamlit UI |
| `generate_submission_report.py` | PDF report |
| `tests/` | pytest |

## Commands

```bash
python -m qode_backtest run
python -m qode_backtest run --rebuild-cache
python -m qode_backtest sweep
streamlit run dashboard.py
python generate_submission_report.py
```

## PostgreSQL (optional)

```bash
docker compose up -d
python -m qode_backtest db init
python -m qode_backtest db load
python -m qode_backtest db status
```

pgAdmin: `localhost:5434`, db `qode_backtest`, user/pass `qode`

## Results (full run)

| Metric | Value |
|---|---|
| Trading days | 247 |
| Trades | 494 |
| CAGR | ~8.3% |
| Max DD | ~-3.1% |
| Sharpe | ~1.25 |
| Final NAV | ~108.26 |

Repeat runs with parquet cache take about 5–8 seconds.

## Tests

```bash
pytest tests/ -v
ruff check qode_backtest tests short_strangle_backtest.py dashboard.py
```
