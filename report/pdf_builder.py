"""
Scoutly — PDF report builder.

Assembles charts and summary data into a polished multi-section PDF
using ReportLab. This is the visual report that users receive alongside
the raw CSV after payment.

Sections:
    1. Header — Scoutly branding, query, date, total leads
    2. Summary stats — key metrics in a grid
    3. Score distribution chart
    4. Rating vs. score scatter
    5. Top 10 leads table
    6. Data quality bar chart
    7. Footer — Scoutly branding
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
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
    KeepTogether,
)

from report.charts import (
    create_score_distribution,
    create_rating_vs_score_scatter,
    create_data_quality_bar,
)

logger = logging.getLogger("scoutly.report.pdf_builder")

# ---------------------------------------------------------------------------
# Colours matching the chart palette
# ---------------------------------------------------------------------------
C_PRIMARY = colors.HexColor("#2563EB")
C_SECONDARY = colors.HexColor("#10B981")
C_DARK = colors.HexColor("#1E293B")
C_MEDIUM = colors.HexColor("#64748B")
C_LIGHT = colors.HexColor("#F1F5F9")
C_WHITE = colors.HexColor("#FFFFFF")
C_ACCENT = colors.HexColor("#F59E0B")


# ---------------------------------------------------------------------------
# Custom paragraph styles
# ---------------------------------------------------------------------------
def _get_styles() -> dict:
    """Build a dict of custom ParagraphStyles for the report."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ScoutlyTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=C_DARK,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "ScoutlySubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=C_MEDIUM,
            fontName="Helvetica",
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "ScoutlyHeading",
            parent=base["Heading2"],
            fontSize=14,
            textColor=C_DARK,
            fontName="Helvetica-Bold",
            spaceBefore=16,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "ScoutlyBody",
            parent=base["Normal"],
            fontSize=10,
            textColor=C_DARK,
            fontName="Helvetica",
            leading=14,
        ),
        "stat_value": ParagraphStyle(
            "StatValue",
            parent=base["Normal"],
            fontSize=20,
            textColor=C_PRIMARY,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "stat_label": ParagraphStyle(
            "StatLabel",
            parent=base["Normal"],
            fontSize=8,
            textColor=C_MEDIUM,
            fontName="Helvetica",
            alignment=TA_CENTER,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontSize=8,
            textColor=C_WHITE,
            fontName="Helvetica-Bold",
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=C_DARK,
            fontName="Helvetica",
            leading=10,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=C_MEDIUM,
            fontName="Helvetica",
            alignment=TA_CENTER,
        ),
    }


# ---------------------------------------------------------------------------
# Summary stats computation
# ---------------------------------------------------------------------------
def generate_summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics for the report header.

    Returns dict with: total_leads, pct_with_email, pct_with_phone,
    avg_rating, avg_score.
    """
    total = len(df)
    if total == 0:
        return {
            "total_leads": 0,
            "pct_with_email": 0.0,
            "pct_with_phone": 0.0,
            "pct_with_website": 0.0,
            "avg_rating": 0.0,
            "avg_score": 0.0,
        }

    return {
        "total_leads": total,
        "pct_with_email": (df["email"].astype(str).str.len() > 0).sum() / total * 100,
        "pct_with_phone": (df["phone"].astype(str).str.len() > 0).sum() / total * 100,
        "pct_with_website": (df["website"].astype(str).str.len() > 0).sum() / total * 100,
        "avg_rating": df["rating"].dropna().mean() if df["rating"].notna().any() else 0.0,
        "avg_score": df["ml_score"].mean() if "ml_score" in df.columns else 0.0,
    }


# ---------------------------------------------------------------------------
# Report section builders
# ---------------------------------------------------------------------------
def _build_header(styles: dict, query: str, stats: dict) -> list:
    """Build the report header section."""
    elements = []

    elements.append(Paragraph("SCOUTLY", styles["title"]))
    elements.append(
        Paragraph(
            f"Lead Report: <b>{query}</b>",
            styles["subtitle"],
        )
    )
    elements.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} "
            f"&bull; {stats['total_leads']} leads",
            styles["subtitle"],
        )
    )
    elements.append(
        HRFlowable(
            width="100%", thickness=1.5,
            color=C_PRIMARY, spaceBefore=4, spaceAfter=12,
        )
    )

    return elements


def _build_stat_cards(styles: dict, stats: dict) -> list:
    """Build the summary stats grid."""
    elements = []

    cards_data = [
        [
            Paragraph(str(stats["total_leads"]), styles["stat_value"]),
            Paragraph(f"{stats['pct_with_email']:.0f}%", styles["stat_value"]),
            Paragraph(f"{stats['pct_with_phone']:.0f}%", styles["stat_value"]),
            Paragraph(f"{stats['avg_rating']:.1f}", styles["stat_value"]),
            Paragraph(f"{stats['avg_score']:.0f}", styles["stat_value"]),
        ],
        [
            Paragraph("Total Leads", styles["stat_label"]),
            Paragraph("Have Email", styles["stat_label"]),
            Paragraph("Have Phone", styles["stat_label"]),
            Paragraph("Avg Rating", styles["stat_label"]),
            Paragraph("Avg Score", styles["stat_label"]),
        ],
    ]

    col_width = (A4[0] - 2 * inch) / 5
    stat_table = Table(cards_data, colWidths=[col_width] * 5)
    stat_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(stat_table)
    elements.append(Spacer(1, 16))

    return elements


def _build_top_leads_table(styles: dict, df: pd.DataFrame) -> list:
    """Build the top 10 leads table."""
    elements = []

    elements.append(Paragraph("Top 10 Leads", styles["heading"]))

    top10 = df.head(10)

    # Table header
    header = [
        Paragraph("#", styles["table_header"]),
        Paragraph("Business Name", styles["table_header"]),
        Paragraph("Address", styles["table_header"]),
        Paragraph("Email", styles["table_header"]),
        Paragraph("Phone", styles["table_header"]),
        Paragraph("Score", styles["table_header"]),
    ]

    table_data = [header]

    for i, (_, row) in enumerate(top10.iterrows(), 1):
        name = str(row.get("name", ""))[:40]
        address = str(row.get("address", ""))[:45]
        email_val = str(row.get("email", ""))
        phone = str(row.get("phone", ""))
        score = str(int(row.get("ml_score", 0)))

        # Truncate long emails
        if len(email_val) > 30:
            email_val = email_val[:28] + ".."

        table_data.append([
            Paragraph(str(i), styles["table_cell"]),
            Paragraph(name, styles["table_cell"]),
            Paragraph(address, styles["table_cell"]),
            Paragraph(email_val, styles["table_cell"]),
            Paragraph(phone, styles["table_cell"]),
            Paragraph(score, styles["table_cell"]),
        ])

    col_widths = [0.3 * inch, 1.6 * inch, 1.8 * inch, 1.5 * inch, 1.0 * inch, 0.45 * inch]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        # Alternating row colours
        *[
            ("BACKGROUND", (0, i), (-1, i), C_LIGHT if i % 2 == 0 else C_WHITE)
            for i in range(1, len(table_data))
        ],
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        # Score column alignment
        ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 16))

    return elements


def _build_footer(styles: dict) -> list:
    """Build the report footer."""
    elements = []

    elements.append(
        HRFlowable(
            width="100%", thickness=0.5,
            color=C_MEDIUM, spaceBefore=12, spaceAfter=8,
        )
    )
    elements.append(
        Paragraph(
            "Generated by Scoutly &bull; scoutly.sbs &bull; "
            "Find businesses. Score leads. Deliver insights.",
            styles["footer"],
        )
    )

    return elements


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_pdf_report(
    df: pd.DataFrame,
    query: str,
    output_path: Path,
    charts_dir: Optional[Path] = None,
) -> Path:
    """
    Generate the full PDF report.

    Args:
        df: Scored and sorted DataFrame.
        query: Original search query string.
        output_path: Where to save the PDF.
        charts_dir: Temp dir for chart images. Defaults to output_path's parent.

    Returns:
        Path to the generated PDF file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if charts_dir is None:
        charts_dir = output_path.parent
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Building PDF report: {output_path}")

    styles = _get_styles()
    stats = generate_summary_stats(df)

    # Generate chart images
    logger.info("Generating charts…")
    score_chart = create_score_distribution(
        df, charts_dir / "_chart_score_dist.png"
    )
    scatter_chart = create_rating_vs_score_scatter(
        df, charts_dir / "_chart_rating_scatter.png"
    )
    quality_chart = create_data_quality_bar(
        df, charts_dir / "_chart_data_quality.png"
    )

    # Build the PDF
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []

    # 1. Header
    story.extend(_build_header(styles, query, stats))

    # 2. Summary stats
    story.extend(_build_stat_cards(styles, stats))

    # 3. Score distribution chart
    story.append(Paragraph("Score Distribution", styles["heading"]))
    story.append(
        Paragraph(
            "How your leads are distributed across score ranges. "
            "Higher scores indicate stronger leads with more contact data "
            "and better online presence.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 6))
    chart_width = doc.width
    chart_height = chart_width * 0.44  # Maintain aspect ratio
    story.append(Image(str(score_chart), width=chart_width, height=chart_height))
    story.append(Spacer(1, 12))

    # 4. Rating vs Score scatter
    story.append(Paragraph("Rating vs. Lead Score", styles["heading"]))
    story.append(
        Paragraph(
            "Each dot is a business. Position shows how Google rating "
            "correlates with our lead score. Dot size reflects review count.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(Image(str(scatter_chart), width=chart_width, height=chart_height))
    story.append(Spacer(1, 12))

    # 5. Top 10 leads table
    story.extend(_build_top_leads_table(styles, df))

    # 6. Data quality bar
    story.append(Paragraph("Data Quality Overview", styles["heading"]))
    story.append(
        Paragraph(
            "Percentage of leads that have each contact field. "
            "Green = 80%+, amber = 50-79%, red = below 50%.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(Image(str(quality_chart), width=chart_width, height=chart_height))

    # 7. Footer
    story.extend(_build_footer(styles))

    # Build the PDF
    doc.build(story)

    # Clean up chart images
    for chart_file in [score_chart, scatter_chart, quality_chart]:
        try:
            Path(chart_file).unlink()
        except Exception:
            pass

    logger.info(f"PDF report saved: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Check for a CSV argument or use dummy data
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        df = pd.read_csv(csv_path)
        query = Path(csv_path).stem.replace("scoutly_", "").replace("_", " ")
    else:
        # Generate dummy data for testing
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