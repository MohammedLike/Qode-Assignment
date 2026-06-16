<div align="center">

# ⚡ Qode Quant Engine : Bank Nifty Strangle ⚡

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=for-the-badge)](https://github.com/astral-sh/ruff)

*A high-performance algorithmic backtesting framework built for the Qode Quant Research assignment.*

[Explore Features](#-core-features) • [Quick Start](#-quick-start) • [CLI Usage](#-cli-commands) • [Dashboard](#-interactive-dashboard)

</div>

---

## 🚀 Core Features

- **High-Octane Execution**: Processes 247 trading days (494 trades) with Parquet caching in ~5 seconds.
- **Precision Targeting**: Implements a strict 09:20 AM Short Strangle on Bank Nifty weekly options.
- **Interactive Telemetry**: Real-time Streamlit dashboard (`dashboard.py`) for visual analysis and sweep evaluations.
- **Persistent Storage**: Dockerized PostgreSQL integration for trade logging and state management.
- **Automated Intelligence**: Generates comprehensive PDF submission reports automatically.

## 🧠 Strategy Matrix

| Parameter | Specification |
| :--- | :--- |
| **Instrument** | Bank Nifty Week-1 Weekly Options (Wednesday Expiry) |
| **Entry Time** | `09:20 AM` IST |
| **Legs** | Sell 1 CE + 1 PE |
| **Strike Selection** | Premium closest to `Rs. 50` |
| **Exit Condition** | `15:20 PM` or `50%` Stop Loss per leg (1-min High) |
| **Sizing** | 1 Lot (15 Qty) - Non-compounding |

## ⚙️ Quick Start

**1. Data Acquisition**
Download the required datasets from the assignment Drive and place them in the project root:
- `Options_data_2023.csv`
- `BANKNIFTY_SPOT.csv`

**2. System Initialization**
Initialize the environment and install dependencies:
```bash
pip install -r requirements.txt
```

**3. Launch Sequence**
Execute the primary backtest engine:
```bash
python -m qode_backtest run
```

## 💻 CLI Commands

The `qode_backtest` module acts as your command center.

```bash
# Standard backtest execution
python -m qode_backtest run

# Force cache rebuild for fresh data processing
python -m qode_backtest run --rebuild-cache

# Run parameter sweep optimizations
python -m qode_backtest sweep
```

## 📊 Interactive Dashboard

Launch the Streamlit telemetry UI to visualize equity curves, drawdowns, and trade logs:

```bash
streamlit run dashboard.py
```

## 🗄️ Database Integration (Optional)

Spin up the Postgres container for persistent data management:

```bash
# Initialize Docker container
docker compose up -d

# Database lifecycle commands
python -m qode_backtest db init
python -m qode_backtest db load
python -m qode_backtest db status
```
*pgAdmin access: `localhost:5434` | DB: `qode_backtest` | Credentials: `qode` / `qode`*

## 📈 Performance Metrics (Jan '23 - Jan '24)

| Metric | Result |
| :--- | :--- |
| **Total Trading Days** | 247 |
| **Total Trades Executed**| 494 |
| **CAGR** | ~8.3% |
| **Max Drawdown** | ~-3.1% |
| **Sharpe Ratio** | ~1.25 |
| **Final NAV** | ~108.26 |

## 🏗️ Architecture

```text
qode_backtest/
├── config.py              # Global parameters
├── engine.py              # Trade execution engine
├── signals.py             # Entry/Exit signal logic
├── analytics.py           # Performance calculation
├── data_loader.py         # Parquet/CSV I/O handlers
├── db.py                  # PostgreSQL interface
└── cli.py                 # Command-line interface definition
```

## 🛠️ Quality Assurance

Ensure system integrity by running the test suite and linters:
```bash
pytest tests/ -v
ruff check qode_backtest tests short_strangle_backtest.py dashboard.py
```
