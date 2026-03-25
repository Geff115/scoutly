"""
Scoutly — PDF report builder (v2).

Assembles a polished, insight-rich PDF report using ReportLab.
Designed to feel like a premium deliverable worth paying for.

Layout:
    Page 1 — Branded header, stats strip, key insights, score chart
    Page 2 — Scatter chart, top leads table
    Page 3 — Data quality chart, methodology note, footer
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
    KeepTogether,
)
from reportlab.pdfgen import canvas as pdfcanvas

from report.charts import (
    create_score_distribution,
    create_rating_vs_score_scatter,
    create_data_quality_bar,
)

logger = logging.getLogger("scoutly.report.pdf_builder")

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
C_BLUE_700 = colors.HexColor("#1D4ED8")
C_BLUE_500 = colors.HexColor("#3B82F6")
C_BLUE_100 = colors.HexColor("#DBEAFE")
C_BLUE_50 = colors.HexColor("#EFF6FF")
C_GREEN_600 = colors.HexColor("#059669")
C_GREEN_500 = colors.HexColor("#10B981")
C_GREEN_50 = colors.HexColor("#ECFDF5")
C_AMBER_500 = colors.HexColor("#F59E0B")
C_AMBER_50 = colors.HexColor("#FFFBEB")
C_RED_500 = colors.HexColor("#EF4444")
C_SLATE_900 = colors.HexColor("#0F172A")
C_SLATE_700 = colors.HexColor("#334155")
C_SLATE_500 = colors.HexColor("#64748B")
C_SLATE_300 = colors.HexColor("#CBD5E1")
C_SLATE_200 = colors.HexColor("#E2E8F0")
C_SLATE_100 = colors.HexColor("#F1F5F9")
C_SLATE_50 = colors.HexColor("#F8FAFC")
C_WHITE = colors.HexColor("#FFFFFF")

PAGE_W, PAGE_H = A4
MARGIN_L = 0.7 * inch
MARGIN_R = 0.7 * inch
MARGIN_T = 0.55 * inch
MARGIN_B = 0.55 * inch
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ---------------------------------------------------------------------------
# Page decorations (header line + page numbers)
# ---------------------------------------------------------------------------
def _page_header_footer(canvas, doc):
    """Draw a thin blue top line and page number on every page."""
    canvas.saveState()

    # Top accent line
    canvas.setStrokeColor(C_BLUE_700)
    canvas.setLineWidth(3)
    canvas.line(MARGIN_L, PAGE_H - MARGIN_T + 12, PAGE_W - MARGIN_R, PAGE_H - MARGIN_T + 12)

    # Page number
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(C_SLATE_500)
    canvas.drawRightString(
        PAGE_W - MARGIN_R,
        MARGIN_B - 16,
        f"Page {doc.page}",
    )

    # Footer branding
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C_SLATE_300)
    canvas.drawString(
        MARGIN_L,
        MARGIN_B - 16,
        "scoutly.sbs",
    )

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Custom styles
# ---------------------------------------------------------------------------
def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "T", fontName="Helvetica-Bold", fontSize=26,
            textColor=C_SLATE_900, leading=30, spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "Tag", fontName="Helvetica", fontSize=9.5,
            textColor=C_BLUE_700, leading=13, spaceAfter=0,
        ),
        "meta": ParagraphStyle(
            "Meta", fontName="Helvetica", fontSize=9,
            textColor=C_SLATE_500, leading=13, spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "H2", fontName="Helvetica-Bold", fontSize=14,
            textColor=C_SLATE_900, leading=18,
            spaceBefore=18, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "H3", fontName="Helvetica-Bold", fontSize=11,
            textColor=C_SLATE_700, leading=14,
            spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "B", fontName="Helvetica", fontSize=9,
            textColor=C_SLATE_700, leading=13, spaceAfter=4,
        ),
        "body_sm": ParagraphStyle(
            "BSm", fontName="Helvetica", fontSize=8,
            textColor=C_SLATE_500, leading=11, spaceAfter=2,
        ),
        "insight_text": ParagraphStyle(
            "Ins", fontName="Helvetica", fontSize=9.5,
            textColor=C_SLATE_900, leading=14, spaceAfter=2,
        ),
        "stat_val": ParagraphStyle(
            "SV", fontName="Helvetica-Bold", fontSize=22,
            textColor=C_BLUE_700, alignment=TA_CENTER, leading=26,
        ),
        "stat_lbl": ParagraphStyle(
            "SL", fontName="Helvetica", fontSize=7.5,
            textColor=C_SLATE_500, alignment=TA_CENTER, leading=10,
        ),
        "th": ParagraphStyle(
            "TH", fontName="Helvetica-Bold", fontSize=7.5,
            textColor=C_WHITE, leading=10,
        ),
        "td": ParagraphStyle(
            "TD", fontName="Helvetica", fontSize=7.5,
            textColor=C_SLATE_900, leading=10,
        ),
        "td_score": ParagraphStyle(
            "TDS", fontName="Helvetica-Bold", fontSize=8,
            textColor=C_BLUE_700, alignment=TA_CENTER, leading=10,
        ),
        "footer": ParagraphStyle(
            "Ft", fontName="Helvetica", fontSize=7.5,
            textColor=C_SLATE_500, alignment=TA_CENTER, leading=10,
        ),
    }


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------
def generate_summary_stats(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {k: 0 for k in [
            "total_leads", "pct_with_email", "pct_with_phone",
            "pct_with_website", "avg_rating", "avg_score",
            "top_score", "bottom_score", "median_score",
        ]}

    scores = df["ml_score"] if "ml_score" in df.columns else pd.Series([0])
    return {
        "total_leads": total,
        "pct_with_email": (df["email"].astype(str).str.len() > 0).sum() / total * 100,
        "pct_with_phone": (df["phone"].astype(str).str.len() > 0).sum() / total * 100,
        "pct_with_website": (df["website"].astype(str).str.len() > 0).sum() / total * 100,
        "avg_rating": float(df["rating"].dropna().mean()) if df["rating"].notna().any() else 0.0,
        "avg_score": float(scores.mean()),
        "top_score": int(scores.max()),
        "bottom_score": int(scores.min()),
        "median_score": int(scores.median()),
    }


# ---------------------------------------------------------------------------
# Insight generator — auto-creates 3-4 key findings
# ---------------------------------------------------------------------------
def _generate_insights(df: pd.DataFrame, stats: dict) -> list[str]:
    insights = []
    total = stats["total_leads"]
    if total == 0:
        return ["No leads were found for this search."]

    # 1. Email coverage insight
    pct_email = stats["pct_with_email"]
    if pct_email >= 80:
        insights.append(
            f"<b>Strong email coverage.</b> {pct_email:.0f}% of leads have a "
            f"publicly listed email address — well above average for this type of search."
        )
    elif pct_email >= 50:
        insights.append(
            f"<b>Moderate email coverage.</b> {pct_email:.0f}% of leads have an "
            f"email address. The remaining businesses may use contact forms instead."
        )
    else:
        insights.append(
            f"<b>Low email coverage ({pct_email:.0f}%).</b> Many businesses in this "
            f"niche don't list email addresses publicly. Consider phone outreach instead."
        )

    # 2. Score quality insight
    high_score_count = int((df["ml_score"] >= 80).sum()) if "ml_score" in df.columns else 0
    high_pct = high_score_count / total * 100
    if high_pct >= 60:
        insights.append(
            f"<b>High-quality list.</b> {high_score_count} of {total} leads "
            f"({high_pct:.0f}%) scored 80 or above, meaning they have strong "
            f"online presence and multiple contact channels."
        )
    else:
        insights.append(
            f"<b>{high_score_count} premium leads.</b> These scored 80+ and have "
            f"the richest contact data. Start your outreach here for the best response rates."
        )

    # 3. Rating insight
    avg_rating = stats["avg_rating"]
    if avg_rating >= 4.5:
        insights.append(
            f"<b>Highly rated businesses.</b> The average Google rating is "
            f"{avg_rating:.1f}/5.0 — these are well-reviewed, established businesses."
        )
    elif avg_rating >= 3.5:
        insights.append(
            f"<b>Average rating: {avg_rating:.1f}/5.0.</b> A healthy mix of "
            f"established and newer businesses in this market."
        )

    # 4. Phone + completeness
    pct_phone = stats["pct_with_phone"]
    if pct_phone >= 90:
        insights.append(
            f"<b>Nearly all leads have phone numbers ({pct_phone:.0f}%).</b> "
            f"Cold calling is a viable channel for this list."
        )

    return insights[:4]  # Cap at 4 insights


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _header(s, query, stats):
    els = []
    els.append(Spacer(1, 4))
    els.append(Paragraph("SCOUTLY", s["title"]))
    els.append(Paragraph("Find businesses. Score leads. Deliver insights.", s["tagline"]))
    els.append(Spacer(1, 6))
    els.append(
        Paragraph(
            f"<b>Report:</b> {query}<br/>"
            f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y')} &nbsp;|&nbsp; "
            f"<b>Leads delivered:</b> {stats['total_leads']}",
            s["meta"],
        )
    )
    # Divider
    els.append(
        HRFlowable(width="100%", thickness=1, color=C_SLATE_200, spaceBefore=2, spaceAfter=12)
    )
    return els


def _stat_strip(s, stats):
    """Five stat cards in a row with coloured accent tops."""
    cards = [
        (str(stats["total_leads"]), "Leads"),
        (f"{stats['pct_with_email']:.0f}%", "Have Email"),
        (f"{stats['pct_with_phone']:.0f}%", "Have Phone"),
        (f"{stats['avg_rating']:.1f}", "Avg Rating"),
        (f"{stats['avg_score']:.0f}", "Avg Score"),
    ]

    # Accent colours for each card
    accents = [C_BLUE_500, C_GREEN_500, C_GREEN_600, C_AMBER_500, C_BLUE_700]
    bg_colors = [C_BLUE_50, C_GREEN_50, C_GREEN_50, C_AMBER_50, C_BLUE_50]

    col_w = CONTENT_W / 5
    val_row = []
    lbl_row = []
    for val, label in cards:
        val_row.append(Paragraph(val, s["stat_val"]))
        lbl_row.append(Paragraph(label, s["stat_lbl"]))

    t = Table([val_row, lbl_row], colWidths=[col_w] * 5, rowHeights=[32, 14])

    style_cmds = [
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]

    # Per-card background and top accent line
    for i in range(5):
        style_cmds.append(("BACKGROUND", (i, 0), (i, -1), bg_colors[i]))
        style_cmds.append(("LINEABOVE", (i, 0), (i, 0), 2.5, accents[i]))

    # Subtle gaps between cards
    for i in range(4):
        style_cmds.append(("RIGHTPADDING", (i, 0), (i, -1), 6))
        style_cmds.append(("LEFTPADDING", (i + 1, 0), (i + 1, -1), 6))

    t.setStyle(TableStyle(style_cmds))
    return [t, Spacer(1, 16)]


def _insights_box(s, df, stats):
    """Key Insights section with auto-generated findings."""
    els = []
    els.append(Paragraph("Key Insights", s["h2"]))

    insights = _generate_insights(df, stats)

    rows = []
    for ins in insights:
        rows.append([
            Paragraph("\u2022", ParagraphStyle(
                "bullet", fontName="Helvetica-Bold", fontSize=11,
                textColor=C_BLUE_500, leading=14,
            )),
            Paragraph(ins, s["insight_text"]),
        ])

    if rows:
        t = Table(rows, colWidths=[16, CONTENT_W - 20])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("LEFTPADDING", (1, 0), (1, -1), 4),
        ]))
        els.append(t)

    els.append(Spacer(1, 10))
    return els


def _chart_section(s, title, description, chart_path, doc_width):
    """Wrap a chart image with heading and description."""
    els = []
    els.append(Paragraph(title, s["h2"]))
    els.append(Paragraph(description, s["body_sm"]))
    els.append(Spacer(1, 4))

    chart_h = doc_width * 0.43
    els.append(Image(str(chart_path), width=doc_width, height=chart_h))
    els.append(Spacer(1, 8))
    return els


def _top_leads_table(s, df):
    """Build the top 10 leads table."""
    els = []
    els.append(Paragraph("Top 10 Leads", s["h2"]))
    els.append(
        Paragraph(
            "Ranked by lead score. Higher scores reflect stronger online presence "
            "and more complete contact information.",
            s["body_sm"],
        )
    )
    els.append(Spacer(1, 6))

    top = df.head(10)

    header = [
        Paragraph("#", s["th"]),
        Paragraph("Business", s["th"]),
        Paragraph("Location", s["th"]),
        Paragraph("Email", s["th"]),
        Paragraph("Phone", s["th"]),
        Paragraph("Score", s["th"]),
    ]

    rows = [header]
    for i, (_, r) in enumerate(top.iterrows(), 1):
        name = str(r.get("name", ""))
        if len(name) > 35:
            name = name[:33] + ".."
        addr = str(r.get("address", ""))
        if len(addr) > 38:
            addr = addr[:36] + ".."
        email_val = str(r.get("email", ""))
        if len(email_val) > 28:
            email_val = email_val[:26] + ".."
        phone = str(r.get("phone", ""))
        score = str(int(r.get("ml_score", 0)))

        rows.append([
            Paragraph(str(i), s["td"]),
            Paragraph(f"<b>{name}</b>", s["td"]),
            Paragraph(addr, s["td"]),
            Paragraph(email_val, s["td"]),
            Paragraph(phone, s["td"]),
            Paragraph(score, s["td_score"]),
        ])

    col_w = [0.28 * inch, 1.45 * inch, 1.6 * inch, 1.4 * inch, 1.0 * inch, 0.42 * inch]
    t = Table(rows, colWidths=col_w, repeatRows=1)

    style_cmds = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), C_BLUE_700),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, C_SLATE_200),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, C_BLUE_700),
        # Alignment
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]

    # Alternating rows
    for i in range(1, len(rows)):
        bg = C_SLATE_50 if i % 2 == 0 else C_WHITE
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    t.setStyle(TableStyle(style_cmds))
    els.append(t)
    els.append(Spacer(1, 10))
    return els


def _methodology_note(s):
    """Short methodology section to build trust."""
    els = []
    els.append(Paragraph("How We Score Leads", s["h3"]))
    els.append(
        Paragraph(
            "Every lead receives a 0&#8211;100 score based on data completeness and "
            "online presence. Points are awarded for: having an email address (+25), "
            "phone number (+20), website (+15), Google rating above 4.0 (+15), "
            "10+ reviews (+10), social media presence (+10), and a complete address (+5). "
            "Higher scores indicate leads that are easier to contact and more likely "
            "to be active, established businesses.",
            s["body"],
        )
    )
    els.append(Spacer(1, 8))
    return els


def _closing_footer(s):
    els = []
    els.append(
        HRFlowable(width="100%", thickness=0.75, color=C_SLATE_300, spaceBefore=14, spaceAfter=10)
    )
    els.append(
        Paragraph(
            "Generated by <b>Scoutly</b> &nbsp;|&nbsp; scoutly.sbs &nbsp;|&nbsp; "
            "Find businesses. Score leads. Deliver insights.",
            s["footer"],
        )
    )
    return els


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_pdf_report(
    df: pd.DataFrame,
    query: str,
    output_path: Path,
    charts_dir: Optional[Path] = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if charts_dir is None:
        charts_dir = output_path.parent
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building PDF report: {output_path}")

    s = _styles()
    stats = generate_summary_stats(df)

    # Generate charts
    logger.info("Generating charts...")
    score_chart = create_score_distribution(df, charts_dir / "_chart_score.png")
    scatter_chart = create_rating_vs_score_scatter(df, charts_dir / "_chart_scatter.png")
    quality_chart = create_data_quality_bar(df, charts_dir / "_chart_quality.png")

    # Set up doc with page decoration
    frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B, id="main")
    template = PageTemplate(id="report", frames=frame, onPage=_page_header_footer)
    doc = BaseDocTemplate(str(output_path), pagesize=A4, pageTemplates=[template])

    story = []

    # Page 1: Header + stats + insights + score chart
    story.extend(_header(s, query, stats))
    story.extend(_stat_strip(s, stats))
    story.extend(_insights_box(s, df, stats))
    story.extend(_chart_section(
        s, "Score Distribution",
        "How leads are distributed across score ranges. The green bar highlights "
        "the most common score bracket.",
        score_chart, CONTENT_W,
    ))

    # Page 2: Scatter + table
    story.extend(_chart_section(
        s, "Rating vs. Lead Score",
        "Each dot represents a business. Dot size reflects review count. "
        "The dashed line shows the general trend between Google rating and lead score.",
        scatter_chart, CONTENT_W,
    ))
    story.extend(_top_leads_table(s, df))

    # Page 3: Quality + methodology + footer
    story.extend(_chart_section(
        s, "Data Quality",
        "Percentage of leads with each contact field. "
        "Green = 80%+, amber = 50-79%, red = below 50%.",
        quality_chart, CONTENT_W,
    ))
    story.extend(_methodology_note(s))
    story.extend(_closing_footer(s))

    doc.build(story)

    # Clean up chart images
    for f in [score_chart, scatter_chart, quality_chart]:
        try:
            Path(f).unlink()
        except Exception:
            pass

    logger.info(f"PDF report saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# CLI testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        df = pd.read_csv(csv_path)
        query = Path(csv_path).stem.replace("scoutly_", "").replace("_", " ")
    else:
        import random
        random.seed(42)
        data = []
        for i in range(30):
            data.append({
                "name": f"Business {i+1}",
                "address": f"{random.randint(1, 999)} Main St, City, State",
                "phone": f"+1 555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                "email": f"contact@business{i+1}.com" if random.random() > 0.3 else "",
                "website": f"https://business{i+1}.com" if random.random() > 0.1 else "",
                "rating": round(random.uniform(2.5, 5.0), 1),
                "review_count": random.randint(1, 200),
                "social_url": "https://facebook.com/biz" if random.random() > 0.6 else "",
                "ml_score": random.randint(30, 100),
            })
        df = pd.DataFrame(data)
        query = "test businesses in Test City, Testland"

    output = Path("./outputs/scoutly_report_test.pdf")
    build_pdf_report(df, query, output)
    print(f"Report generated: {output}")