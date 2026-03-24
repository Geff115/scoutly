"""Scoutly report — Chart generation and PDF assembly."""

from report.charts import (  
    create_score_distribution,
    create_rating_vs_score_scatter,
    create_data_quality_bar,
)
from report.pdf_builder import build_pdf_report, generate_summary_stats
