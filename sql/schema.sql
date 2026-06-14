-- Bank Nifty backtest PostgreSQL schema

CREATE TABLE IF NOT EXISTS options_bars (
    id          BIGSERIAL PRIMARY KEY,
    trade_date  DATE NOT NULL,
    ticker      VARCHAR(32) NOT NULL,
    bar_time    TIME NOT NULL,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4),
    call_put    VARCHAR(4),
    strike      INTEGER,
    option_type VARCHAR(2),
    bar_minute  CHAR(5),
    UNIQUE (trade_date, ticker, bar_time)
);

CREATE INDEX IF NOT EXISTS idx_options_bars_date_ticker
    ON options_bars (trade_date, ticker);
CREATE INDEX IF NOT EXISTS idx_options_bars_bar_time
    ON options_bars (bar_time);

CREATE TABLE IF NOT EXISTS spot_bars (
    id          BIGSERIAL PRIMARY KEY,
    trade_date  DATE NOT NULL,
    bar_minute  CHAR(5) NOT NULL,
    ts          TIMESTAMP,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4),
    UNIQUE (trade_date, bar_minute)
);

CREATE INDEX IF NOT EXISTS idx_spot_bars_date
    ON spot_bars (trade_date);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id               SERIAL PRIMARY KEY,
    run_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_premium   NUMERIC(8, 2),
    entry_time       TIME,
    exit_time        TIME,
    sl_multiplier    NUMERIC(6, 2),
    lot_size         INTEGER,
    starting_capital NUMERIC(14, 2),
    trading_days     INTEGER,
    total_trades     INTEGER,
    cagr_pct         NUMERIC(10, 4),
    max_dd_pct       NUMERIC(10, 4),
    final_nav        NUMERIC(12, 4),
    sharpe           NUMERIC(10, 4)
);

CREATE TABLE IF NOT EXISTS trades (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES backtest_runs (id) ON DELETE CASCADE,
    entry_date          DATE,
    entry_time          TIME,
    exit_date           DATE,
    exit_time           TIME,
    option_ticker       VARCHAR(32),
    strike_price        INTEGER,
    option_type         VARCHAR(2),
    entry_price         NUMERIC(12, 4),
    exit_price          NUMERIC(12, 4),
    quantity            INTEGER,
    entry_value         NUMERIC(14, 2),
    exit_value          NUMERIC(14, 2),
    gross_pnl           NUMERIC(14, 2),
    cumulative_pnl      NUMERIC(14, 2),
    available_capital   NUMERIC(16, 2),
    banknifty_close     NUMERIC(12, 4),
    exit_reason         VARCHAR(32),
    is_expiry_day       BOOLEAN,
    pct_pnl             NUMERIC(10, 4)
);

CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades (run_id);
CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades (entry_date);
