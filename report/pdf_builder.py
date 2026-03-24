"""
Scoutly — PDF report builder.

Assembles charts and summary data into a single-page PDF using ReportLab.
"""

import pandas as pd
from pathlib import Path


def generate_summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics for the report header.

    Returns dict with: total_leads, pct_with_email, pct_with_phone,
    avg_rating, avg_score.
    """
    # TODO: Phase 3 — implement summary stat computation
    raise NotImplementedError("Summary stats not yet implemented")


def build_pdf_report(
    df: pd.DataFrame,
    query: str,
    output_path: Path,
) -> Path:
    """
    Generate the full PDF report.

    Sections:
        - Header (query, date, total leads)
        - Summary stats
        - Score distribution chart
        - Rating vs. score scatter
        - Top 10 leads table
        - Data quality bar

    Args:
        df: Scored and sorted DataFrame.
        query: Original search query string.
        output_path: Where to save the PDF.

    Returns:
        Path to the generated PDF file.
    """
    # TODO: Phase 3 — implement ReportLab PDF assembly
    raise NotImplementedError("PDF builder not yet implemented")
