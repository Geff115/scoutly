"""
Scoutly — Google Maps scraper.

Uses Playwright to launch headless Chromium, search Google Maps,
and extract business listings by scrolling the results panel.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BusinessListing:
    """A single raw business from Google Maps."""
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    rating: Optional[float] = None
    review_count: int = 0
    google_maps_url: str = ""
    category: str = ""


async def scrape_google_maps(
    query: str,
    target_count: int = 50,
) -> list[BusinessListing]:
    """
    Scrape Google Maps for businesses matching `query`.

    Collects target_count * 1.6 raw listings to account for cleaning losses.

    Args:
        query: Full search string, e.g. "dental clinics in Manchester, UK"
        target_count: Number of clean leads the user ordered.

    Returns:
        List of BusinessListing objects with raw scraped data.
    """
    # TODO: Phase 2 — implement Playwright scraping logic
    raise NotImplementedError("Google Maps scraper not yet implemented")
