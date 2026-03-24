"""
Scoutly — Data cleaning pipeline.

Uses Pandas to deduplicate, standardise, and filter scraped leads
before they're scored and delivered to the user.
"""

import pandas as pd
from typing import Optional


def clean_leads(
    raw_leads: list[dict],
    target_count: int,
    require_email: bool = False,
    require_phone: bool = False,
    require_website: bool = False,
) -> pd.DataFrame:
    """
    Clean and filter raw scraped leads into a delivery-ready DataFrame.

    Steps:
        1. Convert to DataFrame
        2. Remove duplicates (matched on name + address)
        3. Standardise phone formats
        4. Strip whitespace and encoding artifacts
        5. Drop rows missing required fields
        6. Validate emails with a strict regex
        7. Trim to target_count rows

    Args:
        raw_leads: List of dicts from scraper (one dict per business).
        target_count: Max leads the user ordered.
        require_email: Drop leads without an email.
        require_phone: Drop leads without a phone number.
        require_website: Drop leads without a website.

    Returns:
        Cleaned pandas DataFrame sorted by readiness for scoring.
    """
    # TODO: Phase 2 — implement full Pandas cleaning pipeline
    raise NotImplementedError("Cleaning pipeline not yet implemented")
