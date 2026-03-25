"""
Scoutly — Chart generators (v2).

Creates polished Matplotlib figures for the PDF report:
    - Score distribution histogram
    - Rating vs. score scatter plot
    - Data quality bar chart

All charts use the Scoutly brand palette with clean, modern styling.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
BRAND = {
    "blue_700": "#1D4ED8",
    "blue_500": "#3B82F6",
    "blue_200": "#BFDBFE",
    "blue_50": "#EFF6FF",
    "green_600": "#059669",
    "green_500": "#10B981",
    "green_100": "#D1FAE5",
    "amber_500": "#F59E0B",
    "amber_100": "#FEF3C7",
    "red_500": "#EF4444",
    "red_100": "#FEE2E2",
    "slate_900": "#0F172A",
    "slate_700": "#334155",
    "slate_500": "#64748B",
    "slate_300": "#CBD5E1",
    "slate_100": "#F1F5F9",
    "white": "#FFFFFF",
}

DPI = 180


def _setup_axes(ax, fig):
    """Apply clean minimal styling."""
    fig.patch.set_facecolor(BRAND["white"])
    ax.set_facecolor(BRAND["white"])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(BRAND["slate_300"])
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(
        colors=BRAND["slate_700"], labelsize=8.5,
        length=3, width=0.8, direction="out",
    )
    ax.grid(axis="y", color=BRAND["slate_100"], linewidth=0.6, zorder=0)


# ---------------------------------------------------------------------------
# Chart 1: Score distribution
# ---------------------------------------------------------------------------
def create_score_distribution(df: pd.DataFrame, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=DPI)
    _setup_axes(ax, fig)

    scores = df["ml_score"].dropna()
    bins = [0, 20, 40, 60, 80, 100]
    bin_labels = ["0–20", "21–40", "41–60", "61–80", "81–100"]

    # Gradient-like colours from light to dark blue
    bin_colors = [
        BRAND["blue_200"], BRAND["blue_200"],
        BRAND["blue_500"], BRAND["blue_500"],
        BRAND["blue_700"],
    ]

    counts, _, bars = ax.hist(
        scores, bins=bins,
        color=BRAND["blue_500"],
        edgecolor=BRAND["white"], linewidth=2,
        rwidth=0.78, zorder=3,
    )

    # Apply gradient colours + highlight the max bin green
    max_idx = int(np.argmax(counts))
    for i, bar in enumerate(bars):
        if i == max_idx:
            bar.set_facecolor(BRAND["green_500"])
        else:
            bar.set_facecolor(bin_colors[i])

    # Count labels above bars
    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.4,
                str(int(count)),
                ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=BRAND["slate_900"],
            )

    ax.set_xticks([10, 30, 50, 70, 90])
    ax.set_xticklabels(bin_labels)
    ax.set_xlabel("Lead Score", fontsize=9, color=BRAND["slate_500"], labelpad=8)
    ax.set_ylabel("Number of Leads", fontsize=9, color=BRAND["slate_500"], labelpad=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    plt.tight_layout(pad=0.8)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=BRAND["white"])
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Chart 2: Rating vs Score scatter
# ---------------------------------------------------------------------------
def create_rating_vs_score_scatter(df: pd.DataFrame, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=DPI)
    _setup_axes(ax, fig)

    plot_df = df.dropna(subset=["rating", "ml_score"])
    plot_df = plot_df[plot_df["rating"] > 0]

    if plot_df.empty:
        ax.text(
            0.5, 0.5, "No rating data available",
            ha="center", va="center", fontsize=11,
            color=BRAND["slate_500"], transform=ax.transAxes,
        )
    else:
        reviews = plot_df["review_count"].fillna(0).clip(lower=1)
        sizes = np.clip(reviews * 0.6, 20, 180)

        ax.scatter(
            plot_df["rating"], plot_df["ml_score"],
            s=sizes, c=BRAND["blue_500"], alpha=0.55,
            edgecolors=BRAND["blue_700"], linewidth=0.6, zorder=3,
        )

        # Add a subtle trend line if enough data
        if len(plot_df) >= 5:
            z = np.polyfit(plot_df["rating"], plot_df["ml_score"], 1)
            p = np.poly1d(z)
            x_range = np.linspace(plot_df["rating"].min(), plot_df["rating"].max(), 50)
            ax.plot(
                x_range, p(x_range),
                color=BRAND["amber_500"], linewidth=1.5,
                linestyle="--", alpha=0.7, zorder=2,
            )

        ax.set_xlim(
            max(0, plot_df["rating"].min() - 0.5),
            min(5.5, plot_df["rating"].max() + 0.5),
        )
        ax.set_ylim(-5, 105)

    ax.set_xlabel("Google Rating", fontsize=9, color=BRAND["slate_500"], labelpad=8)
    ax.set_ylabel("Lead Score", fontsize=9, color=BRAND["slate_500"], labelpad=8)

    plt.tight_layout(pad=0.8)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=BRAND["white"])
    plt.close(fig)
    return output_path


# ---------------------------------------------------------------------------
# Chart 3: Data quality bar
# ---------------------------------------------------------------------------
def create_data_quality_bar(df: pd.DataFrame, output_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 2.6), dpi=DPI)
    _setup_axes(ax, fig)
    ax.grid(False)

    total = len(df)
    if total == 0:
        ax.text(
            0.5, 0.5, "No data available",
            ha="center", va="center", fontsize=11,
            color=BRAND["slate_500"], transform=ax.transAxes,
        )
        plt.tight_layout()
        fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=BRAND["white"])
        plt.close(fig)
        return output_path

    fields = {
        "Email": (df["email"].astype(str).str.len() > 0).sum() / total * 100,
        "Phone": (df["phone"].astype(str).str.len() > 0).sum() / total * 100,
        "Website": (df["website"].astype(str).str.len() > 0).sum() / total * 100,
        "Rating": (df["rating"].fillna(0) > 0).sum() / total * 100,
        "Social": (df["social_url"].astype(str).str.len() > 0).sum() / total * 100 if "social_url" in df.columns else 0,
    }

    labels = list(fields.keys())
    values = list(fields.values())

    bar_colors = []
    for v in values:
        if v >= 80:
            bar_colors.append(BRAND["green_500"])
        elif v >= 50:
            bar_colors.append(BRAND["amber_500"])
        else:
            bar_colors.append(BRAND["red_500"])

    y_pos = np.arange(len(labels))

    # Background track bars (full width)
    ax.barh(y_pos, [100] * len(labels), color=BRAND["slate_100"], height=0.5, zorder=1)
    # Actual value bars
    bars = ax.barh(y_pos, values, color=bar_colors, height=0.5, zorder=2)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9.5, color=BRAND["slate_700"], fontweight="medium")
    ax.set_xlim(0, 115)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}%",
            ha="left", va="center",
            fontsize=10, fontweight="bold", color=BRAND["slate_900"],
        )

    ax.invert_yaxis()
    plt.tight_layout(pad=0.6)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=BRAND["white"])
    plt.close(fig)
    return output_path