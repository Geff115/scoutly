"""
Scoutly — Lead scoring model.

v1: Weighted rule-based scorer that assigns 0–100 to each lead.
v2 (planned): Trained scikit-learn classifier using conversion feedback.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Scoring weights — v1 rule-based
# ---------------------------------------------------------------------------
SCORING_RULES: dict[str, dict] = {
    "has_email":       {"weight": 25, "check": lambda row: bool(row.get("email"))},
    "has_phone":       {"weight": 20, "check": lambda row: bool(row.get("phone"))},
    "has_website":     {"weight": 15, "check": lambda row: bool(row.get("website"))},
    "high_rating":     {"weight": 15, "check": lambda row: (row.get("rating") or 0) >= 4.0},
    "active_reviews":  {"weight": 10, "check": lambda row: (row.get("review_count") or 0) >= 10},
    "has_social":      {"weight": 10, "check": lambda row: bool(row.get("social_url"))},
    "full_address":    {"weight": 5,  "check": lambda row: len(str(row.get("address", ""))) > 15},
}


def score_lead(lead: dict) -> int:
    """
    Score a single lead using the v1 rule-based model.

    Args:
        lead: Dictionary of lead fields.

    Returns:
        Integer score between 0 and 100.
    """
    total = 0
    for rule in SCORING_RULES.values():
        if rule["check"](lead):
            total += rule["weight"]
    return min(total, 100)


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Score every lead in a DataFrame and add an 'ml_score' column.

    Args:
        df: Cleaned leads DataFrame.

    Returns:
        Same DataFrame with 'ml_score' column added, sorted descending.
    """
    df["ml_score"] = df.apply(lambda row: score_lead(row.to_dict()), axis=1)
    return df.sort_values("ml_score", ascending=False).reset_index(drop=True)
