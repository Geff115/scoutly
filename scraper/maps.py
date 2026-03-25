"""
Scoutly — Google Maps scraper.

Uses Playwright to launch headless Chromium, search Google Maps,
and extract business listings by scrolling the results panel.

Strategy:
    1. Navigate to Google Maps search URL
    2. Scroll the results panel repeatedly to load listings
    3. Collect URLs for each listing
    4. Visit each listing page to extract full details
    5. Return structured BusinessListing objects
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page, BrowserContext

from utils.helpers import random_delay, clean_text

logger = logging.getLogger("scoutly.scraper.maps")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class BusinessListing:
    """A single raw business from Google Maps."""
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    email: str = ""
    rating: Optional[float] = None
    review_count: int = 0
    google_maps_url: str = ""
    category: str = ""
    social_url: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}"
OVERSCRAPE_FACTOR = 1.6  # Collect 60% more than needed to account for cleaning losses
MAX_SCROLL_ATTEMPTS = 80  # Safety cap to prevent infinite scrolling
SCROLL_PAUSE_MS = 1500  # Pause between scrolls for content to load


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
async def _accept_cookies(page: Page) -> None:
    """Dismiss the Google consent/cookie dialog if it appears."""
    try:
        accept_btn = page.locator(
            "button",
            has_text=re.compile(
                r"Accept all|Tout accepter|Alle akzeptieren|Aceptar todo",
                re.IGNORECASE,
            ),
        )
        if await accept_btn.count() > 0:
            await accept_btn.first.click()
            await page.wait_for_timeout(1000)
            logger.info("Dismissed cookie consent dialog")
    except Exception:
        pass  # No consent dialog — continue


async def _scroll_results_panel(page: Page, target_count: int) -> int:
    """
    Scroll the Google Maps results panel to load more listings.

    Returns the number of listing elements found after scrolling.
    """
    feed_selector = 'div[role="feed"]'

    try:
        await page.wait_for_selector(feed_selector, timeout=10000)
    except Exception:
        logger.warning("Results feed not found — trying alternative selector")
        feed_selector = 'div[aria-label*="Results"]'
        try:
            await page.wait_for_selector(feed_selector, timeout=5000)
        except Exception:
            logger.error("Could not locate results panel")
            return 0

    previous_count = 0
    stale_rounds = 0

    for attempt in range(MAX_SCROLL_ATTEMPTS):
        # Each result links to a /maps/place/ URL
        listings = page.locator(
            f'{feed_selector} > div > div > a[href*="/maps/place/"]'
        )
        current_count = await listings.count()

        logger.info(f"Scroll {attempt + 1}: {current_count} listings loaded")

        if current_count >= target_count:
            logger.info(f"Reached target: {current_count} >= {target_count}")
            return current_count

        # Check for end of results
        end_of_list = page.locator(
            "p.fontBodyMedium span",
            has_text=re.compile(
                r"end of results|no more results|You've reached the end",
                re.IGNORECASE,
            ),
        )
        if await end_of_list.count() > 0:
            logger.info(
                f"Reached end of Google Maps results at {current_count} listings"
            )
            return current_count

        # Detect stale scrolls
        if current_count == previous_count:
            stale_rounds += 1
            if stale_rounds >= 5:
                logger.info(
                    f"No new results after {stale_rounds} scrolls "
                    f"— stopping at {current_count}"
                )
                return current_count
        else:
            stale_rounds = 0

        previous_count = current_count

        # Scroll the feed container down
        await page.evaluate(
            f"""
            const feed = document.querySelector('{feed_selector}');
            if (feed) feed.scrollTop = feed.scrollHeight;
        """
        )
        await page.wait_for_timeout(SCROLL_PAUSE_MS)

    return previous_count


async def _extract_listing_urls(page: Page) -> list[str]:
    """Extract all unique Google Maps place URLs from the results panel."""
    feed_selector = 'div[role="feed"]'

    feed = page.locator(feed_selector)
    if await feed.count() == 0:
        feed_selector = 'div[aria-label*="Results"]'

    links = page.locator(
        f'{feed_selector} > div > div > a[href*="/maps/place/"]'
    )
    count = await links.count()

    urls: list[str] = []
    seen: set[str] = set()
    for i in range(count):
        href = await links.nth(i).get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            urls.append(href)

    logger.info(f"Extracted {len(urls)} unique listing URLs")
    return urls


async def _extract_listing_details(
    page: Page, url: str
) -> Optional[BusinessListing]:
    """
    Navigate to a single listing page and extract all available details.

    Returns a BusinessListing or None if extraction fails.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        listing = BusinessListing(google_maps_url=url)

        # --- Name ---
        name_el = page.locator('h1.fontHeadlineLarge, h1[class*="fontHeadline"]')
        if await name_el.count() > 0:
            listing.name = clean_text(await name_el.first.text_content())

        if not listing.name:
            main_el = page.locator('div[role="main"]')
            if await main_el.count() > 0:
                label = await main_el.first.get_attribute("aria-label")
                if label:
                    listing.name = clean_text(label)

        # --- Category ---
        cat_el = page.locator('button[jsaction*="category"]')
        if await cat_el.count() > 0:
            listing.category = clean_text(await cat_el.first.text_content())

        # --- Rating ---
        rating_el = page.locator(
            'div.fontBodyMedium span[aria-hidden="true"]'
        ).first
        try:
            rating_text = await rating_el.text_content(timeout=2000)
            if rating_text:
                rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                if rating_match:
                    val = float(rating_match.group(1))
                    if 0 <= val <= 5:
                        listing.rating = val
        except Exception:
            pass

        # --- Review count ---
        review_el = page.locator(
            'div.fontBodyMedium span[aria-label*="review"]'
        )
        if await review_el.count() > 0:
            review_text = (
                await review_el.first.get_attribute("aria-label") or ""
            )
            review_match = re.search(
                r"([\d,]+)\s*review", review_text, re.IGNORECASE
            )
            if review_match:
                listing.review_count = int(
                    review_match.group(1).replace(",", "")
                )

        # --- Address ---
        addr_el = page.locator(
            'button[data-item-id="address"] div.fontBodyMedium, '
            'button[aria-label*="Address"] div.fontBodyMedium'
        )
        if await addr_el.count() > 0:
            listing.address = clean_text(await addr_el.first.text_content())

        if not listing.address:
            addr_fallback = page.locator('button[data-item-id="address"]')
            if await addr_fallback.count() > 0:
                aria = (
                    await addr_fallback.first.get_attribute("aria-label") or ""
                )
                listing.address = clean_text(
                    aria.replace("Address:", "").strip()
                )

        # --- Phone ---
        phone_el = page.locator(
            'button[data-item-id*="phone"] div.fontBodyMedium'
        )
        if await phone_el.count() > 0:
            listing.phone = clean_text(await phone_el.first.text_content())

        if not listing.phone:
            phone_fallback = page.locator('button[data-item-id*="phone"]')
            if await phone_fallback.count() > 0:
                aria = (
                    await phone_fallback.first.get_attribute("aria-label") or ""
                )
                listing.phone = clean_text(
                    aria.replace("Phone:", "").strip()
                )

        # --- Website ---
        website_el = page.locator('a[data-item-id="authority"]')
        if await website_el.count() > 0:
            listing.website = (
                await website_el.first.get_attribute("href") or ""
            )

        if not listing.website:
            website_fallback = page.locator(
                'button[data-item-id="authority"]'
            )
            if await website_fallback.count() > 0:
                aria = (
                    await website_fallback.first.get_attribute("aria-label")
                    or ""
                )
                listing.website = clean_text(
                    aria.replace("Website:", "").strip()
                )

        # --- Social media link ---
        for platform in [
            "facebook.com",
            "instagram.com",
            "linkedin.com",
            "twitter.com",
            "x.com",
        ]:
            social_el = page.locator(f'a[href*="{platform}"]')
            if await social_el.count() > 0:
                listing.social_url = (
                    await social_el.first.get_attribute("href") or ""
                )
                break

        # Only return if we got at least a name
        if listing.name:
            logger.info(f"Extracted: {listing.name}")
            return listing
        else:
            logger.warning(f"Could not extract name from {url}")
            return None

    except Exception as e:
        logger.error(f"Error extracting details from {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def scrape_google_maps(
    query: str,
    target_count: int = 50,
    headless: bool = True,
) -> list[BusinessListing]:
    """
    Scrape Google Maps for businesses matching `query`.

    Collects target_count * 1.6 raw listings to account for cleaning losses.

    Args:
        query: Full search string, e.g. "dental clinics in Manchester, UK"
        target_count: Number of clean leads the user ordered.
        headless: Run browser in headless mode (True for production).

    Returns:
        List of BusinessListing objects with raw scraped data.
    """
    raw_target = int(target_count * OVERSCRAPE_FACTOR)
    search_url = MAPS_SEARCH_URL.format(query=quote_plus(query))

    logger.info(f"Starting scrape: '{query}' — target {raw_target} raw listings")
    logger.info(f"Search URL: {search_url}")

    listings: list[BusinessListing] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        page = await context.new_page()

        try:
            # 1. Navigate to Google Maps search
            logger.info("Navigating to Google Maps…")
            await page.goto(
                search_url, wait_until="domcontentloaded", timeout=30000
            )
            await page.wait_for_timeout(3000)

            # 2. Handle cookie consent
            await _accept_cookies(page)

            # 3. Scroll to load listings
            logger.info("Scrolling results panel…")
            loaded = await _scroll_results_panel(page, raw_target)
            logger.info(f"Loaded {loaded} listings in results panel")

            if loaded == 0:
                logger.error(
                    "No listings found — "
                    "check if the query returned results"
                )
                await browser.close()
                return []

            # 4. Collect all listing URLs
            urls = await _extract_listing_urls(page)
            urls = urls[:raw_target]  # Cap at what we need
            logger.info(f"Will extract details from {len(urls)} listings")

            # 5. Visit each listing and extract details
            for i, url in enumerate(urls):
                logger.info(f"Extracting {i + 1}/{len(urls)}")
                listing = await _extract_listing_details(page, url)
                if listing:
                    listings.append(listing)

                # Polite delay between page visits
                if i < len(urls) - 1:
                    random_delay(0.3, 0.8)

        except Exception as e:
            logger.error(f"Scrape failed: {e}", exc_info=True)

        finally:
            await browser.close()

    logger.info(f"Scrape complete: {len(listings)} listings extracted")
    return listings


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import json

    query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "dental clinics in Lagos, Nigeria"
    )
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    async def run():
        results = await scrape_google_maps(
            query, target_count=count, headless=True
        )
        output = []
        for r in results:
            output.append(
                {
                    "name": r.name,
                    "address": r.address,
                    "phone": r.phone,
                    "website": r.website,
                    "rating": r.rating,
                    "review_count": r.review_count,
                    "category": r.category,
                    "google_maps_url": r.google_maps_url,
                }
            )
        print(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"\nTotal: {len(results)} listings")

    asyncio.run(run())