"""
Scoutly — Email hunter.

Visits each business website with httpx to extract publicly listed
email addresses via regex patterns.
"""

import httpx
from dataclasses import dataclass
from typing import Optional


async def hunt_emails(
    website_url: str,
    check_contact_page: bool = True,
) -> list[str]:
    """
    Fetch a business website and extract email addresses.

    Visits the homepage and optionally the /contact page.
    Filters out common false positives (image files, CSS, etc.).

    Args:
        website_url: The business's website URL.
        check_contact_page: Also check /contact and /about pages.

    Returns:
        Deduplicated list of valid email addresses found.
    """
    # TODO: Phase 2 — implement httpx fetch + regex extraction
    raise NotImplementedError("Email hunter not yet implemented")


async def enrich_listings_with_emails(
    listings: list,
) -> list:
    """
    Take a list of BusinessListing objects and populate their email field
    by visiting each one's website.

    Args:
        listings: List of BusinessListing objects from the Maps scraper.

    Returns:
        Same list with email fields populated where found.
    """
    # TODO: Phase 2 — iterate listings, call hunt_emails, respect rate limits
    raise NotImplementedError("Email enrichment not yet implemented")
