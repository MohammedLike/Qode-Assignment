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
