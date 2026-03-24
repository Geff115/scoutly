"""
Scoutly — Shared helper functions.

Small, reusable utilities that don't belong to any single module.
"""

import re
import uuid
import random
import time
from typing import Optional


def generate_job_id() -> str:
    """Return a short, unique job identifier (e.g. 'sct_a1b2c3d4')."""
    short = uuid.uuid4().hex[:8]
    return f"sct_{short}"


def build_search_query(niche: str, city: str, country: str) -> str:
    """
    Build the Google Maps search string.

    >>> build_search_query("dental clinics", "Manchester", "United Kingdom")
    'dental clinics in Manchester, United Kingdom'
    """
    return f"{niche} in {city}, {country}"


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Common false-positive email patterns from scraping
_EMAIL_BLACKLIST_PATTERNS = [
    r".*\.(png|jpg|jpeg|gif|svg|css|js)$",
    r"^(noreply|no-reply|donotreply|mailer-daemon)@",
    r".*@(example\.com|test\.com|sentry\.io|wixpress\.com)$",
]
_EMAIL_BLACKLIST_RE = [re.compile(p, re.IGNORECASE) for p in _EMAIL_BLACKLIST_PATTERNS]


def is_valid_email(email: str) -> bool:
    """Validate an email address format and reject known false positives."""
    if not _EMAIL_RE.match(email):
        return False
    return not any(pat.match(email) for pat in _EMAIL_BLACKLIST_RE)


# ---------------------------------------------------------------------------
# Rate-limiting helper
# ---------------------------------------------------------------------------
def random_delay(min_sec: float = 0.5, max_sec: float = 1.5) -> None:
    """Sleep for a random duration between min_sec and max_sec."""
    time.sleep(random.uniform(min_sec, max_sec))


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------
def clean_text(text: Optional[str]) -> str:
    """Strip whitespace, encoding artifacts, and normalise a string."""
    if not text:
        return ""
    # Remove non-breaking spaces, zero-width chars, etc.
    cleaned = text.replace("\xa0", " ").replace("\u200b", "")
    return " ".join(cleaned.split()).strip()
