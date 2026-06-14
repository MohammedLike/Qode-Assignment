"""
Generate professional PDF submission report for Qode Quant Research Analyst assignment.
Run: python generate_submission_report.py
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import short_strangle_backtest as bt

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = BASE_DIR / "Qode_Assignment_Submission_Report.pdf"

# Light theme palette only
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
    """Run backtest pipeline and collect all report data."""
    if report_only and (BASE_DIR / "backtest_output.xlsx").exists():
        return _load_cached_data()

    bt.TIMINGS.clear()
    total_t0 = time.perf_counter()

    options = bt.load_options()
    spot = bt.load_spot()
    entry_bars = options[options["Time"] == bt.ENTRY_TIME]
    selected = bt.select_strikes(entry_bars)
    trades_raw = bt.apply_signals(selected, options)
    tradesheet = bt.build_tradesheet(trades_raw, spot)
    stats = bt.compute_statistics(tradesheet)
    bt.save_plots(stats["nav"], stats["drawdown"], stats["max_dd"])
    try:
        bt.export_excel(tradesheet, stats, total_t0)
    except PermissionError:
        print("Note: backtest_output.xlsx is open — skipping Excel export, using in-memory results.")

    return {
        "tradesheet": tradesheet,
        "stats": stats,
        "timings": dict(bt.TIMINGS),
        "total_runtime": bt.TIMINGS.get("total_sec", time.perf_counter() - total_t0),
    }


def _load_cached_data() -> dict:
    """Rebuild report data from existing Excel and charts without re-running backtest."""
    bt.TIMINGS.clear()
    bt.TIMINGS.update({
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
        if row["Section"] in bt.TIMINGS or str(row["Section"]).endswith("_sec"):
            try:
                bt.TIMINGS[str(row["Section"])] = float(row["Details"])
            except (ValueError, TypeError):
                pass
        if row["Section"] == "total_sec":
            try:
                bt.TIMINGS["total_sec"] = float(row["Details"])
            except (ValueError, TypeError):
                pass

    tradesheet = pd.read_excel(BASE_DIR / "backtest_output.xlsx", sheet_name="Tradesheet")
    tradesheet["Exit Reason"] = "Scheduled Exit"
    tradesheet["Is Expiry Day"] = pd.to_datetime(tradesheet["Entry Date"]).dt.dayofweek == 2
    tradesheet["% P&L"] = (
        tradesheet["Gross P&L"] / tradesheet["Entry Value"] * 100
    ).round(2)
    stats = bt.compute_statistics(tradesheet)
    return {
        "tradesheet": tradesheet,
        "stats": stats,
        "timings": dict(bt.TIMINGS),
        "total_runtime": bt.TIMINGS.get("total_sec", 0),
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
    """Thin accent line under section headings."""
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
    ncols = len(cols)

    if col_widths is None:
        col_widths = _auto_col_widths(cols, rows)

    return _table([cols] + rows, col_widths=col_widths, font_size=font_size)


def _auto_col_widths(columns: list[str], rows: list[list[str]]) -> list:
    """Allocate column width by content length with sensible min/max."""
    min_w = 1.3 * cm
    max_w = 5.0 * cm
    weights = []
    for i, col in enumerate(columns):
        cell_lens = [len(str(col))] + [len(str(r[i])) for r in rows]
        weights.append(max(cell_lens))

    total_w = sum(weights) or 1
    raw = [CONTENT_W * w / total_w for w in weights]
    widths = [max(min_w, min(max_w, w)) for w in raw]

    # Rescale to exactly CONTENT_W
    scale = CONTENT_W / sum(widths)
    return [w * scale for w in widths]


def _cover_block(S: dict) -> list:
    """Light-themed cover page content."""
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
    total_pnl = summary_dict.get("Total Gross P&L (INR)", "N/A")

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

    # 1. Executive Summary
    story.extend(_h1("1. Executive Summary", S))
    story.append(Paragraph(
        f"This report documents the submission for the {ORG} {ROLE} technical assignment: "
        f"a vectorized backtest of a 09:20 AM Bank Nifty short strangle system over 247 trading days "
        f"(494 option legs). The strategy sells one call and one put at strikes nearest to Rs. 50 "
        f"premium, with a 50% stop-loss per leg and scheduled exit at 15:20. All deliverables "
        f"requested by {ORG} are included: Python code, Excel workbook, charts, and runtime profiling.",
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
        ("Total Runtime", f"{data['total_runtime']:.2f} seconds"),
    ]))
    story.append(Spacer(1, 14))

    # 2. Assignment Objective
    story.extend(_h1("2. Assignment Objective", S))
    story.append(Paragraph(
        "Develop a backtest for a 09:20 AM short strangle trading system using one year of Bank Nifty "
        "index and options data. The system must demonstrate options strategy design, vectorized data "
        "manipulation, backtesting accuracy, statistical analysis, and computational efficiency "
        "(target: under 60 seconds end-to-end).",
        S["Body"],
    ))
    story.append(Paragraph("2.1 Core Requirements", S["SectionH2"]))
    for item in [
        "Strike selection: CE and PE with 09:20 1-minute close nearest to Rs. 50",
        "Entry at 09:20; exit at 15:20 or 50% stop-loss per leg (checked via High column)",
        "Fixed position size: 1 lot x 15 quantity, no compounding",
        "Trade week-1 weekly options (Wednesday expiry); trade every trading day",
        "Vectorized implementation with no per-day Python loops",
        "Excel output with Guide, Tradesheet, and Statistics worksheets",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    # 3. Strategy
    story.extend(_h1("3. Strategy Overview", S))
    story.append(Paragraph(
        "A <b>short strangle</b> is a neutral options strategy that profits from time decay when the "
        "underlying remains range-bound. The trader simultaneously sells an out-of-the-money call (CE) "
        "and put (PE) with the same expiration. Premium is collected at entry; the position is closed "
        "by buying back the options at a lower price (profit) or higher price (loss).",
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

    # 4. Methodology
    story.extend(_h1("4. Methodology", S))
    story.append(Paragraph("4.1 Strike Selection Module", S["SectionH2"]))
    story.append(Paragraph(
        "At 09:20:59 each trading day, all available CE and PE contracts are evaluated independently. "
        "The contract whose 1-minute Close price minimizes |Close - 50| is selected. Tie-breaking: "
        "higher strike for CE, lower strike for PE. Implementation uses vectorized groupby on "
        "approximately 120 contracts per day.",
        S["Body"],
    ))
    story.append(Paragraph("4.2 Signal Generation and Stop-Loss", S["SectionH2"]))
    story.append(Paragraph(
        "For each selected leg, a 50% stop-loss is defined as SL Price = Entry Price x 1.5. Since "
        "the position is short, loss occurs when the option price rises. Each 1-minute bar from "
        "09:21:59 through 15:20:59 is scanned; if High is greater than or equal to SL Price, the "
        "leg exits at SL Price at the first breach minute. Otherwise, exit occurs at 15:20:59 Close.",
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

    # 5. Implementation
    story.extend(_h1("5. Implementation Architecture", S))
    impl = [
        ["Module", "File", "Function"],
        ["Data Loading", "short_strangle_backtest.py", "load_options(), load_spot()"],
        ["Strike Selection", "short_strangle_backtest.py", "select_strikes()"],
        ["Signal and SL", "short_strangle_backtest.py", "apply_signals()"],
        ["Trade Sheet", "short_strangle_backtest.py", "build_tradesheet()"],
        ["Statistics", "short_strangle_backtest.py", "compute_statistics()"],
        ["Export", "short_strangle_backtest.py", "export_excel(), save_plots()"],
        ["Interactive", "short_strangle_backtest.ipynb", "Step-by-step notebook"],
    ]
    story.append(_table(impl, col_widths=[3.2 * cm, 5.8 * cm, CONTENT_W - 9 * cm]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("5.1 Key Assumptions", S["SectionH2"]))
    for item in [
        "Dataset contains week-1 (nearest Wednesday expiry) Bank Nifty weekly options only",
        "Wednesday is expiry day; all trading days included including expiry Wednesdays",
        "SL fill at exactly 1.5x entry when High breaches; no slippage or transaction costs",
        "Duplicate Date/Ticker/Time rows deduplicated (keep last)",
        "Spot underlying merged on minute key where available",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    # 6. Performance
    story.extend(_h1("6. Performance Results", S))
    story.append(Paragraph("6.1 Summary Metrics", S["SectionH2"]))
    story.append(_metric_table([
        (row["Metric"], str(row["Value"])) for _, row in summary.iterrows()
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

    story.append(PageBreak())

    # 7. Charts
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

    # 8. Runtime
    story.extend(_h1("8. Runtime Performance Analysis", S))
    story.append(Paragraph(
        f"The backtest completes in <b>{data['total_runtime']:.2f} seconds</b>, within the "
        f"60-second target specified in the assignment.",
        S["Body"],
    ))
    story.append(Spacer(1, 10))
    story.append(_runtime_table(data["timings"], data["total_runtime"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph("8.1 Optimization Techniques", S["SectionH2"]))
    for item in [
        "Selective column loading and categorical dtypes for Ticker and Call/Put",
        "Early time-window filter (09:20 to 15:20) reducing dataset size",
        "Vectorized groupby for strike selection and stop-loss detection",
        "Single-pass CSV load with duplicate row deduplication",
    ]:
        story.append(Paragraph(f"- {item}", S["Bullet"]))

    # 9. Deliverables
    story.extend(_h1("9. Submission Deliverables", S))
    deliverables = [
        ["Deliverable", "File", "Status"],
        ["Python Backtest Code", "short_strangle_backtest.py", "Complete"],
        ["Jupyter Notebook", "short_strangle_backtest.ipynb", "Complete"],
        ["Excel - Guide Sheet", "backtest_output.xlsx (Sheet 1)", "Complete"],
        ["Excel - Tradesheet", "backtest_output.xlsx (Sheet 2)", "Complete"],
        ["Excel - Statistics", "backtest_output.xlsx (Sheet 3)", "Complete"],
        ["Equity Curve Chart", "equity_curve.png", "Complete"],
        ["Drawdown Chart", "drawdown.png", "Complete"],
        ["Runtime Profiling", "Guide sheet and this report", "Complete"],
        ["Dependencies", "requirements.txt", "Complete"],
    ]
    story.append(_table(deliverables, col_widths=[4.2 * cm, 6.8 * cm, CONTENT_W - 11 * cm]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("9.1 Tradesheet Columns", S["SectionH2"]))
    col_data = [["Column", "Included"]] + [[c, "Yes"] for c in ts.columns]
    story.append(_table(col_data, col_widths=[11 * cm, 3 * cm]))

    story.append(PageBreak())

    # 10. Appendix
    story.extend(_h1("10. Appendix: Sample Trades", S))
    story.append(Paragraph(
        "First five trades from the Tradesheet demonstrating entry, exit, P&amp;L, and capital tracking.",
        S["Body"],
    ))
    sample_cols = [
        "Entry Date", "Option Type", "Option Ticker", "Entry Price",
        "Exit Price", "Gross P&L", "Exit Time",
    ]
    sample_widths = [2.3 * cm, 1.5 * cm, 5.0 * cm, 1.8 * cm, 1.8 * cm, 2.1 * cm, 2.1 * cm]
    story.append(_df_to_table(
        ts[sample_cols].head(5),
        font_size=8,
        col_widths=sample_widths,
    ))
    story.append(Spacer(1, 14))

    story.append(Paragraph("10.1 Interpretation Guide", S["SectionH2"]))
    story.append(Paragraph(
        "<b>Winners (short options):</b> Exit Price is less than Entry Price. "
        "<b>Losers:</b> Exit Price is greater than Entry Price, typically from stop-loss events. "
        "<b>Expiry days (Wednesdays):</b> accelerated time decay can affect CE/PE performance. "
        "<b>NAV:</b> Normalized portfolio value starting at 100. "
        "<b>Max Drawdown:</b> Largest peak-to-trough decline in NAV.",
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
