from __future__ import annotations

import html
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BLUE = colors.HexColor("#2563EB")
DARK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F3F4F6")
BORDER = colors.HexColor("#D1D5DB")


def _text(value: Any, limit: int | None = None) -> str:
    raw = "-" if value is None or value == "" else str(value)
    raw = raw.encode("latin-1", "replace").decode("latin-1")
    if limit and len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return html.escape(raw).replace("\n", "<br/>")


def _percent(value: Any) -> str:
    return "-" if value is None else f"{float(value) * 100:.1f}%"


def build_evaluation_report(run: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=17 * mm,
        bottomMargin=16 * mm,
        title=str(run.get("name") or "Agent Evaluation Report"),
        author="AI Cowork Agent Evaluator",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=DARK, alignment=TA_LEFT, spaceAfter=4 * mm)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=DARK, spaceBefore=4 * mm, spaceAfter=2.5 * mm)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=DARK)
    small_style = ParagraphStyle("Small", parent=body_style, fontSize=7.2, leading=9)
    kpi_label = ParagraphStyle("KpiLabel", parent=small_style, textColor=MUTED)
    kpi_value = ParagraphStyle("KpiValue", parent=body_style, fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=DARK)

    summary = run.get("summary") or {}
    metrics = summary.get("metrics") or []
    results = run.get("results") or []
    evaluated = sum(int(item.get("evaluated") or 0) for item in metrics)
    pass_rate = None
    if evaluated:
        pass_rate = sum(float(item.get("pass_rate") or 0) * int(item.get("evaluated") or 0) for item in metrics) / evaluated

    story = [
        Paragraph(_text(run.get("name") or "Agent Evaluation Report"), title_style),
        Paragraph(
            f"Agent: <b>{_text(run.get('agent_name'))}</b> &nbsp;&nbsp; Dataset: <b>{_text(run.get('dataset_name'))}</b> &nbsp;&nbsp; Status: <b>{_text(str(run.get('status', '')).replace('_', ' '))}</b>",
            body_style,
        ),
        Spacer(1, 5 * mm),
    ]

    kpis = [
        ("Overall score", _percent(summary.get("overall_score"))),
        ("Pass rate", _percent(pass_rate)),
        ("Cases scored", f"{summary.get('scored_cases', 0)} / {run.get('progress_total', 0)}"),
        ("Average latency", "-" if summary.get("average_agent_latency_ms") is None else f"{float(summary['average_agent_latency_ms']):.0f} ms"),
        ("Metric errors", str(summary.get("error_count", 0))),
    ]
    # Render KPI cards horizontally as nested two-row tables.
    cards = [Table([[Paragraph(_text(label), kpi_label)], [Paragraph(_text(value), kpi_value)]], colWidths=[48 * mm]) for label, value in kpis]
    cards_table = Table([cards], colWidths=[50 * mm] * 5, hAlign="LEFT")
    cards_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([cards_table, Paragraph("Metric breakdown", section_style)])

    metric_rows = [["Metric", "Average", "Pass rate", "Range", "Evaluated", "Errors"]]
    for item in metrics:
        metric_rows.append([
            Paragraph(_text(str(item.get("metric_id", "")).replace("_", " ")), body_style),
            _percent(item.get("average_score")),
            _percent(item.get("pass_rate")),
            f"{_percent(item.get('min_score'))} - {_percent(item.get('max_score'))}",
            str(item.get("evaluated", 0)),
            str(item.get("errors", 0)),
        ])
    metric_table = Table(metric_rows, colWidths=[72 * mm, 28 * mm, 28 * mm, 45 * mm, 28 * mm, 25 * mm], repeatRows=1, hAlign="LEFT")
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([metric_table, PageBreak(), Paragraph("Case-level evidence", section_style)])

    result_rows = [["Case", "Metric", "Score", "Input", "Agent output", "Reason or error"]]
    for item in results:
        result_rows.append([
            f"#{item.get('dataset_row', '-')}",
            Paragraph(_text(str(item.get("metric_id", "")).replace("_", " "), 45), small_style),
            _percent(item.get("score")),
            Paragraph(_text(item.get("input_preview"), 500), small_style),
            Paragraph(_text(item.get("output_preview"), 700), small_style),
            Paragraph(_text(item.get("error") or item.get("reason"), 700), small_style),
        ])
    evidence = Table(result_rows, colWidths=[13 * mm, 30 * mm, 18 * mm, 54 * mm, 66 * mm, 76 * mm], repeatRows=1, hAlign="LEFT")
    evidence.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(evidence)

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.line(14 * mm, 11 * mm, landscape(A4)[0] - 14 * mm, 11 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(14 * mm, 7 * mm, "AI Cowork Agent Evaluator")
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()
