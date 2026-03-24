"""
Scoutly — Chart generators.

Creates Matplotlib figures for the PDF report:
    - Score distribution histogram
    - Rating vs. score scatter plot
    - Data quality bar chart (% with email, phone, etc.)
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path


def create_score_distribution(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a histogram of lead scores.

    Args:
        df: Scored DataFrame with 'ml_score' column.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    # TODO: Phase 3 — implement Matplotlib histogram
    raise NotImplementedError("Score distribution chart not yet implemented")


def create_rating_vs_score_scatter(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a scatter plot: Google rating (x) vs. ML score (y).

    Args:
        df: Scored DataFrame with 'rating' and 'ml_score' columns.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    # TODO: Phase 3 — implement Matplotlib scatter plot
    raise NotImplementedError("Rating vs score scatter not yet implemented")


def create_data_quality_bar(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a horizontal bar chart showing % of leads with each field.

    Args:
        df: Scored DataFrame.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    # TODO: Phase 3 — implement data quality bar chart
    raise NotImplementedError("Data quality bar chart not yet implemented")
