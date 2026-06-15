from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from qode_backtest.analytics import compute_statistics
from qode_backtest.config import StrategyConfig
from qode_backtest.engine import run_pipeline
from qode_backtest.timing import TIMINGS, clear_timings

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = BASE_DIR / "Qode_Assignment_Submission_Report.pdf"

WHITE = colors.white
TEXT = colors.HexColor("#1F2937")
TEXT_MUTED = colors.HexColor("#6B7280")
HEADING = colors.HexColor("#111827")
ACCENT = colors.HexColor("#2563EB")
ACCENT_SOFT = colors.HexColor("#DBEAFE")
TABLE_HEAD_BG = colors.HexColor("#F3F4F6")
TABLE_HEAD_TEXT = colors.HexColor("#374151")
TABLE_BORDER = colors.HexColor("#E5E7EB")
TABLE_ALT = colors.HexColor("#FAFAFA")
RULE = colors.HexColor("#D1D5DB")

CANDIDATE = "Mohammed Like"
ROLE = "Quant Research Analyst"
ORG = "Qode"
ASSIGNMENT = "Bank Nifty 09:20 Short Strangle Backtest"

MARGIN_L = 2.2 * cm
MARGIN_R = 2.2 * cm
MARGIN_T = 2.4 * cm
MARGIN_B = 2.4 * cm
CONTENT_W = A4[0] - MARGIN_L - MARGIN_R


def _gather_data(report_only: bool = False) -> dict:
    if report_only and (BASE_DIR / "backtest_output.xlsx").exists():
        return _load_cached_data()

    cfg = StrategyConfig.from_yaml()
    tradesheet, stats, _ = run_pipeline(cfg, export=True)
    return {
        "tradesheet": tradesheet,
        "stats": stats,
        "timings": dict(TIMINGS),
        "total_runtime": TIMINGS.get("total_sec", 0),
    }


def _load_cached_data() -> dict:
    clear_timings()
    TIMINGS.update({
        "1_load_options_sec": 0,
        "2_load_spot_sec": 0,
        "3_strike_selection_sec": 0,
        "4_signal_stoploss_sec": 0,
        "5_tradesheet_sec": 0,
        "6_statistics_sec": 0,
        "7_plots_sec": 0,
        "8_excel_export_prep_sec": 0,
        "8_excel_write_sec": 0,
        "total_sec": 0,
    })
    guide = pd.read_excel(BASE_DIR / "backtest_output.xlsx", sheet_name="Guide")
    for _, row in guide.iterrows():
        if row["Section"] in TIMINGS or str(row["Section"]).endswith("_sec"):
            try:
                TIMINGS[str(row["Section"])] = float(row["Details"])
            except (ValueError, TypeError):
                pass
        if row["Section"] == "total_sec":
            try:
                TIMINGS["total_sec"] = float(row["Details"])
            except (ValueError, TypeError):
                pass

    tradesheet = pd.read_excel(BASE_DIR / "backtest_output.xlsx", sheet_name="Tradesheet")
    if "Exit Reason" not in tradesheet.columns:
        tradesheet["Exit Reason"] = "Scheduled Exit"
    if "Is Expiry Day" not in tradesheet.columns:
        tradesheet["Is Expiry Day"] = pd.to_datetime(tradesheet["Entry Date"]).dt.dayofweek == 2
    if "% P&L" not in tradesheet.columns:
        tradesheet["% P&L"] = (
            tradesheet["Gross P&L"] / tradesheet["Entry Value"] * 100
        ).round(2)
    stats = compute_statistics(tradesheet)
    return {
        "tradesheet": tradesheet,
        "stats": stats,
        "timings": dict(TIMINGS),
        "total_runtime": TIMINGS.get("total_sec", 0),
    }


def _styles():
    base = getSampleStyleSheet()
    return {
        "CoverLabel": ParagraphStyle(
            "CoverLabel",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
            spaceAfter=8,
            letterSpacing=1.2,
        ),
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=28,
            leading=34,
            textColor=HEADING,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "CoverSub": ParagraphStyle(
            "CoverSub",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=13,
            leading=18,
            textColor=TEXT,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "CoverMeta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "SectionH1": ParagraphStyle(
            "SectionH1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=17,
            leading=22,
            textColor=HEADING,
            spaceBefore=18,
            spaceAfter=10,
        ),
        "SectionH2": ParagraphStyle(
            "SectionH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=16,
            textColor=TEXT,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "Bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10.5,
            leading=15,
            textColor=TEXT,
            leftIndent=14,
            bulletIndent=0,
            spaceAfter=5,
        ),
        "Caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=TEXT_MUTED,
            spaceAfter=6,
        ),
    }


def _section_rule() -> Table:
    t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _h1(text: str, S: dict) -> list:
    return [Paragraph(text, S["SectionH1"]), _section_rule(), Spacer(1, 8)]


def _table(data, col_widths=None, header_rows=1, font_size=9) -> Table:
    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), TABLE_HEAD_BG),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), TABLE_HEAD_TEXT),
        ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTNAME", (0, header_rows), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [WHITE, TABLE_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _metric_table(rows: list[tuple[str, str]]) -> Table:
    data = [["Metric", "Value"]] + [[k, v] for k, v in rows]
    return _table(data, col_widths=[9.5 * cm, 6.5 * cm])


def _runtime_table(timings: dict, total: float) -> Table:
    steps = [
        ("Data Loading (Options)", timings.get("1_load_options_sec", 0)),
        ("Data Loading (Spot Index)", timings.get("2_load_spot_sec", 0)),
        ("Strike Selection", timings.get("3_strike_selection_sec", 0)),
        ("Backtest / Signal and Stop-Loss", timings.get("4_signal_stoploss_sec", 0)),
        ("Trade Sheet Construction", timings.get("5_tradesheet_sec", 0)),
        ("Statistical Analysis", timings.get("6_statistics_sec", 0)),
        ("Chart Generation", timings.get("7_plots_sec", 0)),
        ("Excel Export", timings.get("8_excel_write_sec", 0) + timings.get("8_excel_export_prep_sec", 0)),
    ]
    data = [["Step", "Time (sec)"]] + [[s, f"{t:.3f}"] for s, t in steps]
    data.append(["Total Runtime", f"{total:.3f}"])
    t = _table(data, col_widths=[11.5 * cm, 4.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, -1), (-1, -1), ACCENT_SOFT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), HEADING),
    ]))
    return t


def _df_to_table(
    df: pd.DataFrame,
    max_rows: int | None = None,
    font_size: float = 8,
    col_widths: list | None = None,
) -> Table:
    sub = df.head(max_rows) if max_rows else df
    cols = [str(c) for c in sub.columns]
    rows = sub.astype(str).values.tolist()

    if col_widths is None:
        col_widths = _auto_col_widths(cols, rows)

    return _table([cols] + rows, col_widths=col_widths, font_size=font_size)


def _auto_col_widths(columns: list[str], rows: list[list[str]]) -> list:
    min_w = 1.3 * cm
    max_w = 5.0 * cm
    weights = []
    for i, col in enumerate(columns):
        cell_lens = [len(str(col))] + [len(str(r[i])) for r in rows]
        weights.append(max(cell_lens))

    total_w = sum(weights) or 1
    raw = [CONTENT_W * w / total_w for w in weights]
    widths = [max(min_w, min(max_w, w)) for w in raw]

    scale = CONTENT_W / sum(widths)
    return [w * scale for w in widths]


def _normalize_widths(widths: list) -> list:
    scale = CONTENT_W / sum(widths)
    return [w * scale for w in widths]


def _table_from_rows(
    columns: list[str],
    rows: list[list[str]],
    col_widths: list,
    font_size: float = 8,
    wrap_col: int | None = None,
) -> Table:
    cell_style = ParagraphStyle(
        "Cell", fontName="Helvetica", fontSize=font_size, leading=font_size + 2, textColor=TEXT
    )
    header = [Paragraph(str(c), cell_style) for c in columns]
    body = []
    for row in rows:
        cells = []
        for i, val in enumerate(row):
            if wrap_col is not None and i == wrap_col:
                cells.append(Paragraph(str(val), cell_style))
            else:
                cells.append(str(val))
        body.append(cells)
    return _table([header] + body, col_widths=_normalize_widths(col_widths), font_size=font_size)


def _sample_trades_table(df: pd.DataFrame) -> Table:
    cols = [str(c) for c in df.columns]
    rows = df.astype(str).values.tolist()
    raw = [2.2, 1.4, 5.4, 1.7, 1.7, 2.0, 2.0]
    return _table_from_rows(cols, rows, [w * cm for w in raw], font_size=8, wrap_col=2)


def _cover_block(S: dict) -> list:
    top_rule = Table([[""]], colWidths=[CONTENT_W], rowHeights=[3])
    top_rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))

    items = [
        Spacer(1, 2.8 * cm),
        top_rule,
        Spacer(1, 1.6 * cm),
        Paragraph("QUANTITATIVE RESEARCH ASSIGNMENT", S["CoverLabel"]),
        Paragraph("Submission Report", S["CoverTitle"]),
        Spacer(1, 0.3 * cm),
        Paragraph(ASSIGNMENT, S["CoverSub"]),
        Spacer(1, 1.4 * cm),
        Paragraph(CANDIDATE, S["CoverSub"]),
        Paragraph(f"{ROLE} - {ORG}", S["CoverMeta"]),
        Spacer(1, 0.5 * cm),
        Paragraph(datetime.now().strftime("%d %B %Y"), S["CoverMeta"]),
        Spacer(1, 1.8 * cm),
        Paragraph(
            "Bank Nifty Weekly Options  |  Short Strangle  |  Jan 2023 to Jan 2024",
            S["CoverMeta"],
        ),
    ]

    bottom_rule = Table([[""]], colWidths=[CONTENT_W], rowHeights=[1])
    bottom_rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RULE)]))
    items.extend([Spacer(1, 2 * cm), bottom_rule])
    return items


def build_report(data: dict) -> None:
    S = _styles()
    stats = data["stats"]
    ts = data["tradesheet"]
    wl = stats["win_loss"]
    exp = stats["expiry_stats"]
    monthly = stats["monthly_table"]
    equity = stats["equity_table"]
    summary = stats["summary"]

    summary_dict = dict(zip(summary["Metric"], summary["Value"].astype(str)))
    cagr = summary_dict.get("CAGR", "N/A")
    max_dd = summary_dict.get("Max Drawdown", "N/A")
    final_nav = summary_dict.get("Final NAV", "N/A")
    pnl_key = next((k for k in summary_dict if k.startswith("Total P&L")), "Total P&L (INR)")
    total_pnl = summary_dict.get(pnl_key, "N/A")

    risk = stats.get("risk_metrics", {})

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="Qode Assignment Submission Report",
        author=CANDIDATE,
    )

    story = []
    story.extend(_cover_block(S))
    story.append(PageBreak())

    story.extend(_h1("1. Executive Summary", S))
    story.append(Paragraph(
        f"This report is my submission for the {ORG} {ROLE} assignment ? a backtest of a "
        f"09:20 AM Bank Nifty short strangle over 247 days (494 legs). Each day I sell CE and PE "
        f"nearest Rs. 50 premium, with 50% stop-loss per leg and exit at 15:20. "
        f"Deliverables: Python code, Excel workbook, charts, and this report.",
        S["Body"],
    ))
    story.append(Spacer(1, 10))
    story.append(_metric_table([
        ("Compounded Annual Growth Rate (CAGR)", cagr),
        ("Maximum Drawdown", max_dd),
        ("Final NAV (Base 100)", str(final_nav)),
        ("Total Gross P&L", f"Rs. {total_pnl}"),
        ("Total Trades", "494 (247 days x 2 legs)"),
        ("Win Rate (Combined)", f"{wl.loc[wl['Category']=='Combined', 'Win %'].iloc[0]:.2f}%"),
        ("Sharpe Ratio", str(risk.get("Sharpe Ratio", "N/A"))),
        ("Sortino Ratio", str(risk.get("Sortino Ratio", "N/A"))),
        ("Calmar Ratio", str(risk.get("Calmar Ratio", "N/A"))),
        ("Profit Factor", str(risk.get("Profit Factor", "N/A"))),
        ("Total Runtime (cached)", f"{data['total_runtime']:.2f} seconds"),
    ]))
    story.append(Spacer(1, 14))

    story.extend(_h1("2. Assignment Objective", S))
    story.append(Paragraph(
        "Build a backtest for the 09:20 AM short strangle using one year of Bank Nifty options "
        "and index data. Output should include trade log, performance stats, equity curve, "
        "drawdown, and monthly returns. Target runtime under 60 seconds.",
        S["Body"],
    ))
    story.append(Paragraph("2.1 Core Requirements", S["SectionH2"]))
    for item in [
        "Strike selection: CE and PE with 09:20 1-minute close nearest to Rs. 50",
        "Entry at 09:20; exit at 15:20 or 50% stop-loss per leg (checked via High column)",
        "Fixed position size: 1 lot x 15 quantity, no compounding",
        "Trade week-1 weekly options (Wednesday expiry); trade every trading day",
        "Vectorized pandas code (no day-by-day loops)",
        "Excel output with Guide, Tradesheet, and Statistics worksheets",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    story.extend(_h1("3. Strategy Overview", S))
    story.append(Paragraph(
        "Short strangle: sell OTM call and put, collect premium, buy back later. "
        "Works when spot stays in a range; losses when one leg runs against you (often via SL).",
        S["Body"],
    ))
    story.append(Paragraph("3.1 Trade Lifecycle", S["SectionH2"]))
    lifecycle = [
        ["Phase", "Time", "Action"],
        ["Strike Selection", "09:20:59", "Identify CE and PE with Close nearest to Rs. 50"],
        ["Entry", "09:20:59", "Sell both legs at 1-min Close (short)"],
        ["Monitoring", "09:21 - 15:20", "Check High each minute for 50% SL breach"],
        ["Stop-Loss Exit", "First breach", "Buy back at Entry x 1.5"],
        ["Scheduled Exit", "15:20:59", "Buy back at 1-min Close if SL not hit"],
    ]
    story.append(_table(lifecycle, col_widths=[3.8 * cm, 3.2 * cm, CONTENT_W - 7 * cm]))
    story.append(Spacer(1, 12))

    story.extend(_h1("4. Methodology", S))
    story.append(Paragraph("4.1 Strike Selection", S["SectionH2"]))
    story.append(Paragraph(
        "At 09:20:59, pick CE and PE whose close is closest to Rs. 50. "
        "If tied, higher strike for CE, lower for PE. Done with groupby per date.",
        S["Body"],
    ))
    story.append(Paragraph("4.2 Stop-Loss and Exit", S["SectionH2"]))
    story.append(Paragraph(
        "SL = entry x 1.5. Scan 1-min bars from 09:21 to 15:20; if High >= SL, exit at SL price "
        "on first hit. Otherwise exit at 15:20 close.",
        S["Body"],
    ))
    story.append(Paragraph("4.3 Position Sizing", S["SectionH2"]))
    story.append(Paragraph(
        "Fixed quantity of 15 units (1 lot x lot size 15) per leg per day. No compounding. "
        "Available capital tracks cumulative P&amp;L for reporting only (starting capital: Rs. 1,00,000).",
        S["Body"],
    ))
    story.append(Paragraph("4.4 P&amp;L Calculation", S["SectionH2"]))
    story.append(Paragraph(
        "Gross P&amp;L = Entry Value - Exit Value = (Entry Price - Exit Price) x Quantity. "
        "NAV starts at base 100 and updates daily: "
        "NAV = 100 + (Cumulative P&amp;L / Starting Capital) x 100.",
        S["Body"],
    ))

    story.append(PageBreak())

    story.extend(_h1("5. Implementation Architecture", S))
    impl = [
        ["Module", "Path", "Role"],
        ["Config", "qode_backtest/config.py", "StrategyConfig + YAML loading"],
        ["Data Loader", "qode_backtest/data_loader.py", "CSV/parquet cache, spot load"],
        ["Strike Selection", "qode_backtest/strike_selection.py", "Vectorized strike pick"],
        ["Signals", "qode_backtest/signals.py", "SL + scheduled exit (semi-join)"],
        ["Tradesheet", "qode_backtest/tradesheet.py", "Trade log and P&L"],
        ["Analytics", "qode_backtest/analytics.py", "CAGR, drawdown, risk metrics"],
        ["Export", "qode_backtest/export.py", "Excel, plots, sensitivity heatmap"],
        ["Sweep", "qode_backtest/sweep.py", "Parameter grid analysis"],
        ["Database", "qode_backtest/db.py", "PostgreSQL bulk load"],
        ["CLI", "qode_backtest/cli.py", "run / sweep / db commands"],
        ["Entry Point", "short_strangle_backtest.py", "Backward-compatible wrapper"],
        ["Notebook", "short_strangle_backtest.ipynb", "Interactive walkthrough"],
    ]
    story.append(_table(impl, col_widths=[3.0 * cm, 5.5 * cm, CONTENT_W - 8.5 * cm]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("5.1 Other additions", S["SectionH2"]))
    for item in [
        "Parquet cache for faster reload on repeat runs",
        "Parameter sweep on premium and SL multiplier",
        "Streamlit dashboard for charts and trade filters",
        "Slippage and brokerage option in config",
        "PostgreSQL loader for options/spot/trades",
        "pytest + GitHub Actions CI",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("5.2 Key Assumptions", S["SectionH2"]))
    for item in [
        "Dataset contains week-1 (nearest Wednesday expiry) Bank Nifty weekly options only",
        "Wednesday is expiry day; all trading days included including expiry Wednesdays",
        "SL fill at exactly 1.5x entry when High breaches; optional slippage on SL exits (config)",
        "Flat brokerage per leg when realism layer enabled (config.yaml)",
        "Duplicate Date/Ticker/Time rows deduplicated (keep last)",
        "Spot underlying merged on minute key where available",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    story.extend(_h1("6. Performance Results", S))
    story.append(Paragraph("6.1 Summary Metrics", S["SectionH2"]))
    story.append(_metric_table([
        (row["Metric"], str(row["Value"])) for _, row in summary.iterrows()
    ]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("6.1a Extended Risk Metrics", S["SectionH2"]))
    story.append(_metric_table([
        ("Sharpe Ratio", str(risk.get("Sharpe Ratio", "N/A"))),
        ("Sortino Ratio", str(risk.get("Sortino Ratio", "N/A"))),
        ("Calmar Ratio", str(risk.get("Calmar Ratio", "N/A"))),
        ("Profit Factor", str(risk.get("Profit Factor", "N/A"))),
        ("Expectancy (INR)", str(risk.get("Expectancy (INR)", "N/A"))),
        ("Max Consecutive Losses", str(risk.get("Max Consecutive Losses", "N/A"))),
    ]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("6.2 Win / Loss Analysis", S["SectionH2"]))
    wl_data = [["Category", "Winners", "Losers", "Win %", "Loss %", "Avg % P&L"]]
    for _, r in wl.iterrows():
        wl_data.append([
            r["Category"], str(int(r["Winners"])), str(int(r["Losers"])),
            f"{r['Win %']:.2f}%", f"{r['Loss %']:.2f}%", f"{r['Avg % P&L']:.2f}%",
        ])
    story.append(_table(wl_data, col_widths=[2.4 * cm, 2 * cm, 2 * cm, 2 * cm, 2 * cm, 2.6 * cm]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("6.3 Average % P&amp;L: Expiry vs Non-Expiry Days", S["SectionH2"]))
    exp_data = [["Segment", "Day Type", "Trades", "Avg % P&L", "Avg Gross P&L (Rs.)"]]
    for _, r in exp.iterrows():
        exp_data.append([
            r["Segment"], r["Day Type"], str(int(r["Trades"])),
            f"{r['Avg % P&L']:.2f}%", f"{r['Avg Gross P&L']:.2f}",
        ])
    story.append(_table(exp_data, col_widths=[2 * cm, 3.8 * cm, 1.6 * cm, 2.4 * cm, CONTENT_W - 9.8 * cm]))

    realism = stats.get("realism_comparison")
    if realism is not None and not realism.empty and len(realism) > 1:
        story.append(Spacer(1, 14))
        story.append(Paragraph("6.4 Ideal vs Realistic P&amp;L", S["SectionH2"]))
        story.append(Paragraph(
            "Slippage on SL fills and flat brokerage per leg (see config.yaml). "
            "Gross P&L is before costs; net P&L after.",
            S["Body"],
        ))
        story.append(_df_to_table(realism, font_size=9))

    attr = stats.get("attribution", {})
    dow = attr.get("day_of_week")
    if dow is not None and not dow.empty:
        story.append(Spacer(1, 14))
        story.append(Paragraph("6.5 Regime Attribution", S["SectionH2"]))
        story.append(Paragraph("6.5a P&amp;L by Day of Week", S["SectionH2"]))
        story.append(_df_to_table(dow, font_size=9))
        vol = attr.get("vol_regime")
        if vol is not None and not vol.empty:
            story.append(Paragraph("6.5b Volatility Regime (20-day rolling spot std)", S["SectionH2"]))
            story.append(_df_to_table(vol, font_size=9))
        money = attr.get("moneyness")
        if money is not None and not money.empty:
            story.append(Paragraph("6.5c Moneyness at Entry", S["SectionH2"]))
            story.append(_df_to_table(money, font_size=9))

    benchmark = stats.get("benchmark_summary")
    if benchmark is not None and not benchmark.empty:
        story.append(Spacer(1, 14))
        story.append(Paragraph("6.6 Benchmark Comparison (Bank Nifty Buy &amp; Hold)", S["SectionH2"]))
        story.append(_df_to_table(benchmark, font_size=9))

    story.append(PageBreak())

    story.extend(_h1("7. Equity Curve and Drawdown", S))
    eq_path = BASE_DIR / "equity_curve.png"
    dd_path = BASE_DIR / "drawdown.png"
    if eq_path.exists():
        story.append(Paragraph("7.1 Equity Curve (Base NAV = 100)", S["SectionH2"]))
        story.append(Image(str(eq_path), width=CONTENT_W, height=CONTENT_W * 0.42))
        story.append(Spacer(1, 12))
    if dd_path.exists():
        story.append(Paragraph("7.2 Drawdown Profile", S["SectionH2"]))
        story.append(Image(str(dd_path), width=CONTENT_W, height=CONTENT_W * 0.42))
        story.append(Spacer(1, 12))

    story.append(Paragraph("7.3 Equity Curve Table (First and Last 10 Days)", S["SectionH2"]))
    story.append(_df_to_table(pd.concat([equity.head(10), equity.tail(10)])))
    story.append(Spacer(1, 14))

    story.append(Paragraph("7.4 Monthly % P&amp;L (from NAV)", S["SectionH2"]))
    story.append(_df_to_table(
        monthly,
        font_size=9,
        col_widths=[4.5 * cm, 4.5 * cm, CONTENT_W - 9 * cm],
    ))

    story.append(PageBreak())

    story.extend(_h1("8. Runtime Performance Analysis", S))
    story.append(Paragraph(
        f"Repeat run with parquet cache: <b>{data['total_runtime']:.2f} sec</b>. "
        f"First CSV load is slower (~35-40 sec). Under the 60 sec target either way.",
        S["Body"],
    ))
    story.append(Spacer(1, 10))
    story.append(_runtime_table(data["timings"], data["total_runtime"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("8.1 Speed notes", S["SectionH2"]))
    for item in [
        "Parquet cache for filtered 09:20-15:20 window",
        "Only merge SL path for selected tickers",
        "Categorical dtypes on ticker columns",
        "Dedup duplicate bars (keep last)",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    story.extend(_h1("9. Submission Deliverables", S))
    deliverables = [
        ["Deliverable", "File", "Status"],
        ["Entry Point", "short_strangle_backtest.py", "Done"],
        ["Notebook", "short_strangle_backtest.ipynb", "Done"],
        ["Excel output", "backtest_output.xlsx", "Done"],
        ["Charts", "equity_curve.png, drawdown.png", "Done"],
        ["Dashboard", "dashboard.py", "Done"],
        ["Tests + CI", "tests/, .github/workflows/ci.yml", "Done"],
        ["This report", "Qode_Assignment_Submission_Report.pdf", "Done"],
    ]
    story.append(_table(deliverables, col_widths=[4.2 * cm, 6.8 * cm, CONTENT_W - 11 * cm]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("9.1 Tradesheet Columns", S["SectionH2"]))
    col_data = [["Column", "Included"]] + [[c, "Yes"] for c in ts.columns]
    story.append(_table(col_data, col_widths=[11 * cm, 3 * cm]))

    story.append(PageBreak())

    story.extend(_h1("10. Appendix: Sample Trades", S))
    story.append(Paragraph(
        "Sample rows from the tradesheet.",
        S["Body"],
    ))
    sample_cols = [
        "Entry Date", "Option Type", "Option Ticker", "Entry Price",
        "Exit Price", "Gross P&L", "Exit Time",
    ]
    story.append(_sample_trades_table(ts[sample_cols].head(5)))
    story.append(Spacer(1, 14))

    story.append(Paragraph("10.1 Notes", S["SectionH2"]))
    story.append(Paragraph(
        "Short option profit when exit &lt; entry. SL exits are usually the losing trades. "
        "NAV starts at 100. Drawdown is peak-to-trough on NAV.",
        S["Body"],
    ))

    doc.build(story)
    print(f"Report saved: {OUTPUT_PDF} ({OUTPUT_PDF.stat().st_size:,} bytes)")


if __name__ == "__main__":
    import sys
    report_only = "--report-only" in sys.argv
    print("Generating PDF report..." + (" (cached data)" if report_only else " (full backtest)"))
    data = _gather_data(report_only=report_only)
    build_report(data)
    print("Done.")
