"""
Scoutly — Data cleaning pipeline.

Uses Pandas to deduplicate, standardise, and filter scraped leads
before they're scored and delivered to the user.

Steps:
    1. Convert raw listing dicts to DataFrame
    2. Remove duplicates (matched on name + address)
    3. Standardise phone formats
    4. Strip whitespace and encoding artifacts
    5. Drop rows missing required fields
    6. Validate emails with a strict regex
    7. Trim to target_count rows
"""

import logging
import re
from typing import Optional

import pandas as pd

from utils.helpers import is_valid_email, clean_text

logger = logging.getLogger("scoutly.scraper.cleaner")


# ---------------------------------------------------------------------------
# Phone number cleaning
# ---------------------------------------------------------------------------
def _standardise_phone(phone: str) -> str:
    """
    Standardise a phone number string.

    Keeps only digits, spaces, dashes, parens, and leading +.
    Returns empty string if the result looks invalid (too short).
    """
    if not phone:
        return ""

    # Strip common non-phone text
    phone = phone.strip()
    phone = re.sub(r"(phone|tel|call|fax|whatsapp)[:\s]*", "", phone, flags=re.IGNORECASE)

    # Keep only phone-like characters
    cleaned = re.sub(r"[^\d\s\-\+\(\)]", "", phone)

    # Remove excessive whitespace
    cleaned = " ".join(cleaned.split()).strip()

    # A valid phone number has at least 7 digits
    digit_count = sum(c.isdigit() for c in cleaned)
    if digit_count < 7:
        return ""

    return cleaned


# ---------------------------------------------------------------------------
# URL cleaning
# ---------------------------------------------------------------------------
def _clean_url(url: str) -> str:
    """Normalise a URL — ensure scheme, strip trailing slashes."""
    if not url:
        return ""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def clean_leads(
    raw_leads: list[dict],
    target_count: int,
    require_email: bool = False,
    require_phone: bool = False,
    require_website: bool = False,
) -> pd.DataFrame:
    """
    Clean and filter raw scraped leads into a delivery-ready DataFrame.

    Args:
        raw_leads: List of dicts from scraper (one dict per business).
        target_count: Max leads the user ordered.
        require_email: Drop leads without an email.
        require_phone: Drop leads without a phone number.
        require_website: Drop leads without a website.

    Returns:
        Cleaned pandas DataFrame sorted by data completeness (most complete first).
    """
    if not raw_leads:
        logger.warning("No raw leads to clean")
        return pd.DataFrame()

    logger.info(f"Cleaning {len(raw_leads)} raw leads (target: {target_count})")

    # 1. Convert to DataFrame
    df = pd.DataFrame(raw_leads)

    # Ensure all expected columns exist
    expected_cols = [
        "name", "address", "phone", "website", "email",
        "rating", "review_count", "google_maps_url", "category", "social_url",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    initial_count = len(df)

    # 2. Strip whitespace and encoding artifacts from all text fields
    text_cols = ["name", "address", "phone", "website", "email", "category", "social_url"]
    for col in text_cols:
        df[col] = df[col].astype(str).apply(clean_text)
        # Replace "None" and "nan" strings with empty
        df[col] = df[col].replace({"None": "", "nan": "", "NaN": ""})

    # 3. Remove duplicates (matched on normalised name + address)
    df["_name_lower"] = df["name"].str.lower().str.strip()
    df["_addr_lower"] = df["address"].str.lower().str.strip()
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["_name_lower", "_addr_lower"], keep="first")
    df = df.drop(columns=["_name_lower", "_addr_lower"])
    dupes_removed = before_dedup - len(df)
    if dupes_removed:
        logger.info(f"Removed {dupes_removed} duplicate leads")

    # 4. Drop rows with no name (unusable)
    df = df[df["name"].str.len() > 0]

    # 5. Standardise phone formats
    df["phone"] = df["phone"].apply(_standardise_phone)

    # 6. Clean URLs
    df["website"] = df["website"].apply(_clean_url)
    df["social_url"] = df["social_url"].apply(_clean_url)

    # 7. Validate emails — blank out invalid ones
    def _validate_email(email: str) -> str:
        if email and is_valid_email(email):
            return email.lower().strip()
        return ""

    df["email"] = df["email"].apply(_validate_email)

    # 8. Ensure numeric fields are correct types
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0).astype(int)

    # 9. Apply user-required field filters
    before_filter = len(df)

    if require_email:
        df = df[df["email"].str.len() > 0]
        logger.info(f"Filter: require_email — {before_filter - len(df)} dropped")
        before_filter = len(df)

    if require_phone:
        df = df[df["phone"].str.len() > 0]
        logger.info(f"Filter: require_phone — {before_filter - len(df)} dropped")
        before_filter = len(df)

    if require_website:
        df = df[df["website"].str.len() > 0]
        logger.info(f"Filter: require_website — {before_filter - len(df)} dropped")

    # 10. Sort by data completeness (leads with more fields filled = better)
    def _completeness_score(row) -> int:
        score = 0
        if row["email"]:
            score += 3
        if row["phone"]:
            score += 2
        if row["website"]:
            score += 1
        if row["social_url"]:
            score += 1
        if row["rating"] and row["rating"] > 0:
            score += 1
        return score

    df["_completeness"] = df.apply(_completeness_score, axis=1)
    df = df.sort_values("_completeness", ascending=False).reset_index(drop=True)
    df = df.drop(columns=["_completeness"])

    # 11. Trim to target count
    if len(df) > target_count:
        df = df.head(target_count)

    logger.info(
        f"Cleaning complete: {initial_count} raw → {len(df)} clean leads "
        f"(target was {target_count})"
    )

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick test with dummy data
    sample_leads = [
        {
            "name": "Smile Dental Clinic",
            "address": "123 Main Street, Lagos, Nigeria",
            "phone": "+234 801 234 5678",
            "website": "https://smileclinic.com",
            "email": "info@smileclinic.com",
            "rating": 4.5,
            "review_count": 42,
            "google_maps_url": "https://maps.google.com/...",
            "category": "Dental clinic",
            "social_url": "",
        },
        {
            "name": "Smile Dental Clinic",  # Duplicate
            "address": "123 Main Street, Lagos, Nigeria",
            "phone": "+234 801 234 5678",
            "website": "https://smileclinic.com",
            "email": "info@smileclinic.com",
            "rating": 4.5,
            "review_count": 42,
            "google_maps_url": "https://maps.google.com/...",
            "category": "Dental clinic",
            "social_url": "",
        },
        {
            "name": "Quick Fix Dentistry",
            "address": "456 Victoria Island, Lagos",
            "phone": "",
            "website": "",
            "email": "bad-email@",
            "rating": 3.2,
            "review_count": 5,
            "google_maps_url": "https://maps.google.com/...",
            "category": "Dentist",
            "social_url": "",
        },
    ]

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    df = clean_leads(sample_leads, target_count=25)
    print(df.to_string())
    print(f"\nTotal clean leads: {len(df)}")