"""
Scoutly — Chart generators.

Creates Matplotlib figures for the PDF report:
    - Score distribution histogram
    - Rating vs. score scatter plot
    - Data quality bar chart (% with email, phone, etc.)

All charts use a consistent Scoutly colour palette and are saved as PNGs
for embedding into the ReportLab PDF.
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Scoutly colour palette
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#2563EB",       # Blue
    "primary_light": "#60A5FA",
    "secondary": "#10B981",     # Green
    "accent": "#F59E0B",        # Amber
    "danger": "#EF4444",        # Red
    "dark": "#1E293B",          # Slate dark
    "medium": "#64748B",        # Slate medium
    "light": "#F1F5F9",         # Slate light
    "white": "#FFFFFF",
}

# Consistent figure settings
FIGSIZE_WIDE = (8, 3.5)
FIGSIZE_SQUARE = (5, 4)
DPI = 150


def _apply_style(ax: plt.Axes) -> None:
    """Apply consistent Scoutly styling to an axes object."""
    ax.set_facecolor(COLORS["white"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["medium"])
    ax.spines["bottom"].set_color(COLORS["medium"])
    ax.tick_params(colors=COLORS["dark"], labelsize=9)


# ---------------------------------------------------------------------------
# Chart 1: Score distribution histogram
# ---------------------------------------------------------------------------
def create_score_distribution(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a histogram of lead scores.

    Args:
        df: Scored DataFrame with 'ml_score' column.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE, dpi=DPI)
    fig.patch.set_facecolor(COLORS["white"])
    _apply_style(ax)

    scores = df["ml_score"].dropna()

    # Create bins: 0-20, 20-40, 40-60, 60-80, 80-100
    bins = [0, 20, 40, 60, 80, 100]
    bin_labels = ["0–20", "21–40", "41–60", "61–80", "81–100"]

    counts, _, bars = ax.hist(
        scores,
        bins=bins,
        color=COLORS["primary"],
        edgecolor=COLORS["white"],
        linewidth=1.5,
        rwidth=0.85,
    )

    # Color the highest bin differently
    max_idx = int(np.argmax(counts))
    for i, bar in enumerate(bars):
        if i == max_idx:
            bar.set_facecolor(COLORS["secondary"])
        else:
            bar.set_facecolor(COLORS["primary"])

    ax.set_xlabel("Lead Score", fontsize=10, color=COLORS["dark"], fontweight="medium")
    ax.set_ylabel("Number of Leads", fontsize=10, color=COLORS["dark"], fontweight="medium")
    ax.set_title("Score Distribution", fontsize=13, color=COLORS["dark"], fontweight="bold", pad=12)

    # Set x-tick labels to bin ranges
    ax.set_xticks([10, 30, 50, 70, 90])
    ax.set_xticklabels(bin_labels)

    # Add count labels on top of bars
    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.3,
                str(int(count)),
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=COLORS["dark"],
            )

    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=COLORS["white"])
    plt.close(fig)

    return output_path


# ---------------------------------------------------------------------------
# Chart 2: Rating vs. Score scatter
# ---------------------------------------------------------------------------
def create_rating_vs_score_scatter(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a scatter plot: Google rating (x) vs. ML score (y).

    Args:
        df: Scored DataFrame with 'rating' and 'ml_score' columns.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE, dpi=DPI)
    fig.patch.set_facecolor(COLORS["white"])
    _apply_style(ax)

    # Filter out rows without ratings
    plot_df = df.dropna(subset=["rating", "ml_score"])
    plot_df = plot_df[plot_df["rating"] > 0]

    if plot_df.empty:
        # If no rating data, show a placeholder message
        ax.text(
            0.5, 0.5,
            "No rating data available",
            ha="center", va="center",
            fontsize=12, color=COLORS["medium"],
            transform=ax.transAxes,
        )
    else:
        # Size dots by review count (bigger = more reviews)
        reviews = plot_df["review_count"].fillna(0).clip(lower=1)
        sizes = np.clip(reviews * 0.8, 15, 200)

        scatter = ax.scatter(
            plot_df["rating"],
            plot_df["ml_score"],
            s=sizes,
            c=COLORS["primary"],
            alpha=0.6,
            edgecolors=COLORS["primary_light"],
            linewidth=0.5,
        )

        ax.set_xlim(0, 5.5)
        ax.set_ylim(-5, 105)

    ax.set_xlabel("Google Rating", fontsize=10, color=COLORS["dark"], fontweight="medium")
    ax.set_ylabel("Lead Score", fontsize=10, color=COLORS["dark"], fontweight="medium")
    ax.set_title(
        "Rating vs. Lead Score",
        fontsize=13, color=COLORS["dark"], fontweight="bold", pad=12,
    )

    plt.tight_layout()
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=COLORS["white"])
    plt.close(fig)

    return output_path


# ---------------------------------------------------------------------------
# Chart 3: Data quality bar chart
# ---------------------------------------------------------------------------
def create_data_quality_bar(df: pd.DataFrame, output_path: Path) -> Path:
    """
    Generate a horizontal bar chart showing % of leads with each field.

    Args:
        df: Scored DataFrame.
        output_path: Where to save the PNG.

    Returns:
        Path to the saved chart image.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE, dpi=DPI)
    fig.patch.set_facecolor(COLORS["white"])
    _apply_style(ax)

    total = len(df)
    if total == 0:
        ax.text(
            0.5, 0.5, "No data available",
            ha="center", va="center", fontsize=12, color=COLORS["medium"],
            transform=ax.transAxes,
        )
        plt.tight_layout()
        fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=COLORS["white"])
        plt.close(fig)
        return output_path

    # Calculate percentages
    fields = {
        "Email": (df["email"].astype(str).str.len() > 0).sum() / total * 100,
        "Phone": (df["phone"].astype(str).str.len() > 0).sum() / total * 100,
        "Website": (df["website"].astype(str).str.len() > 0).sum() / total * 100,
        "Rating": (df["rating"].fillna(0) > 0).sum() / total * 100,
        "Social": (df["social_url"].astype(str).str.len() > 0).sum() / total * 100 if "social_url" in df.columns else 0,
    }

    labels = list(fields.keys())
    values = list(fields.values())

    # Assign colours based on threshold
    bar_colors = []
    for v in values:
        if v >= 80:
            bar_colors.append(COLORS["secondary"])
        elif v >= 50:
            bar_colors.append(COLORS["accent"])
        else:
            bar_colors.append(COLORS["danger"])

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=bar_colors, height=0.55, edgecolor=COLORS["white"])

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10, color=COLORS["dark"])
    ax.set_xlim(0, 110)
    ax.set_xlabel("% of Leads", fontsize=10, color=COLORS["dark"], fontweight="medium")
    ax.set_title(
        "Data Quality Overview",
        fontsize=13, color=COLORS["dark"], fontweight="bold", pad=12,
    )

    # Add percentage labels at the end of each bar
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}%",
            ha="left", va="center",
            fontsize=10, fontweight="bold", color=COLORS["dark"],
        )

    ax.invert_yaxis()  # Highest quality field on top
    plt.tight_layout()
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=COLORS["white"])
    plt.close(fig)

    return output_path