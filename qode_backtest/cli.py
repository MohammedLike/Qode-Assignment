from __future__ import annotations

import argparse
from pathlib import Path

from dataclasses import replace

from qode_backtest.config import DEFAULT_CONFIG_PATH, StrategyConfig
from qode_backtest.engine import print_summary, run_pipeline


def _run_db_command(args) -> None:
    from qode_backtest import db as pg

    if args.db_command == "init":
        pg.init_schema(args.dsn)
    elif args.db_command == "status":
        counts = pg.table_counts(args.dsn)
        print("\n=== PostgreSQL table counts ===")
        for table, count in counts.items():
            print(f"  {table}: {count:,}")
    elif args.db_command == "load":
        cfg = StrategyConfig.from_yaml(args.config)
        pg.init_schema(args.dsn)
        if args.options_only:
            pg.load_options_to_db(cfg, dsn=args.dsn, truncate=args.truncate)
        elif args.spot_only:
            pg.load_spot_to_db(cfg, dsn=args.dsn, truncate=args.truncate)
        else:
            pg.load_all_to_db(
                cfg,
                dsn=args.dsn,
                include_trades=not args.no_trades,
                truncate=args.truncate,
            )
        counts = pg.table_counts(args.dsn)
        print("\n=== PostgreSQL table counts ===")
        for table, count in counts.items():
            print(f"  {table}: {count:,}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bank Nifty Short Strangle Backtest")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run backtest and export Excel")
    run_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    run_p.add_argument("--no-cache", action="store_true", help="Disable parquet cache")
    run_p.add_argument("--rebuild-cache", action="store_true", help="Force rebuild parquet cache")
    run_p.add_argument("--no-export", action="store_true", help="Skip Excel/plot export")

    sweep_p = sub.add_parser("sweep", help="Run parameter sensitivity sweep")
    sweep_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    sweep_p.add_argument("--premiums", default="40,45,50,55,60")
    sweep_p.add_argument("--sl", default="1.3,1.5,1.7,2.0")

    db_p = sub.add_parser("db", help="PostgreSQL setup and data load")
    db_sub = db_p.add_subparsers(dest="db_command", required=True)

    db_init = db_sub.add_parser("init", help="Create database schema")
    db_init.add_argument("--dsn", default=None, help="PostgreSQL DSN (or set DATABASE_URL)")

    db_load = db_sub.add_parser("load", help="Load options, spot, and backtest trades")
    db_load.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    db_load.add_argument("--dsn", default=None)
    db_load.add_argument("--truncate", action="store_true", help="Clear tables before load")
    db_load.add_argument("--options-only", action="store_true")
    db_load.add_argument("--spot-only", action="store_true")
    db_load.add_argument("--no-trades", action="store_true", help="Skip backtest trade insert")

    db_status = db_sub.add_parser("status", help="Show row counts per table")
    db_status.add_argument("--dsn", default=None)

    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "run":
        cfg = StrategyConfig.from_yaml(args.config)
        cfg = replace(
            cfg,
            use_parquet_cache=not args.no_cache,
            force_rebuild_cache=args.rebuild_cache,
        )
        tradesheet, stats, _ = run_pipeline(cfg, export=not args.no_export)
        print_summary(tradesheet, stats)

    elif command == "sweep":
        cfg = StrategyConfig.from_yaml(args.config)
        premiums = [float(x) for x in args.premiums.split(",")]
        sl_mults = [float(x) for x in args.sl.split(",")]
        tradesheet, stats, sweep_df = run_pipeline(
            cfg, run_sweep_analysis=True, sweep_premiums=premiums, sweep_sl=sl_mults
        )
        print_summary(tradesheet, stats)
        print(f"\nSweep combinations: {len(sweep_df) if sweep_df is not None else 0}")
        if sweep_df is not None:
            print(sweep_df.to_string(index=False))

    elif command == "db":
        _run_db_command(args)


if __name__ == "__main__":
    main()
