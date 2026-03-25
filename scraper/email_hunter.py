"""
Scoutly — Email hunter.

Visits each business website with httpx to extract publicly listed
email addresses via regex patterns.

Strategy:
    1. Fetch the homepage HTML
    2. Optionally fetch /contact, /about, /contact-us pages
    3. Run email regex across all collected HTML
    4. Filter out false positives (images, noreply, known junk domains)
    5. Return deduplicated list of valid emails
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from utils.helpers import is_valid_email, clean_text, random_delay
from utils.config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX

logger = logging.getLogger("scoutly.scraper.email_hunter")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Email regex — uses a non-capturing group to match a boundary before the email.
# This prevents text concatenation like "Addressinfo@domain.com"
_EMAIL_PATTERN = re.compile(
    r"(?:^|[\s:>\"'(,;=\[])"
    r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.MULTILINE,
)

# Subpages likely to contain contact email addresses
_CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/kontakt",       # German
    "/contacto",      # Spanish
    "/contato",       # Portuguese
    "/nous-contacter", # French
]

# Common mailto: pattern in HTML
_MAILTO_PATTERN = re.compile(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})')

# Default headers to look like a real browser
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Request timeout in seconds
_TIMEOUT = 10.0

# Max HTML size to process (5 MB) — skip huge pages
_MAX_CONTENT_LENGTH = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_emails_from_html(html: str) -> set[str]:
    """
    Extract all email addresses from an HTML string.

    Checks both raw text patterns and mailto: links.
    Filters each email through is_valid_email() to remove junk.
    """
    candidates: set[str] = set()

    # Standard email pattern
    for match in _EMAIL_PATTERN.findall(html):
        email = match.lower().strip()
        if is_valid_email(email):
            candidates.add(email)

    # Mailto links (sometimes encoded differently)
    for match in _MAILTO_PATTERN.findall(html):
        email = match.lower().strip()
        if is_valid_email(email):
            candidates.add(email)

    return candidates


def _normalise_url(url: str) -> str:
    """Ensure a URL has a scheme and is clean."""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
) -> Optional[str]:
    """
    Fetch a single page and return its HTML, or None on failure.

    Handles redirects, timeouts, and oversized responses gracefully.
    """
    try:
        response = await client.get(
            url,
            follow_redirects=True,
            timeout=_TIMEOUT,
        )

        # Skip non-HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        # Skip oversized pages
        if len(response.content) > _MAX_CONTENT_LENGTH:
            logger.warning(f"Page too large, skipping: {url}")
            return None

        return response.text

    except httpx.TimeoutException:
        logger.debug(f"Timeout fetching {url}")
        return None
    except httpx.ConnectError:
        logger.debug(f"Connection error for {url}")
        return None
    except httpx.TooManyRedirects:
        logger.debug(f"Too many redirects for {url}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def hunt_emails(
    website_url: str,
    check_contact_page: bool = True,
) -> list[str]:
    """
    Fetch a business website and extract email addresses.

    Visits the homepage and optionally common contact subpages.
    Filters out false positives (image files, CSS, noreply, etc.).

    Args:
        website_url: The business's website URL.
        check_contact_page: Also check /contact, /about pages.

    Returns:
        Deduplicated list of valid email addresses found.
    """
    url = _normalise_url(website_url)
    if not url:
        return []

    all_emails: set[str] = set()

    async with httpx.AsyncClient(headers=_HEADERS, verify=False) as client:
        # 1. Fetch homepage
        logger.debug(f"Fetching homepage: {url}")
        html = await _fetch_page(client, url)
        if html:
            all_emails.update(_extract_emails_from_html(html))

        # 2. Fetch contact/about pages
        if check_contact_page:
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"

            for path in _CONTACT_PATHS:
                subpage_url = urljoin(base, path)
                logger.debug(f"Checking subpage: {subpage_url}")
                sub_html = await _fetch_page(client, subpage_url)
                if sub_html:
                    all_emails.update(_extract_emails_from_html(sub_html))

    result = sorted(all_emails)
    if result:
        logger.info(f"Found {len(result)} email(s) on {url}: {result}")
    else:
        logger.debug(f"No emails found on {url}")

    return result


async def enrich_listings_with_emails(
    listings: list,
    max_concurrent: int = 5,
) -> list:
    """
    Take a list of BusinessListing objects and populate their email field
    by visiting each one's website.

    Uses a semaphore to limit concurrent HTTP requests.

    Args:
        listings: List of BusinessListing objects from the Maps scraper.
        max_concurrent: Max parallel email hunts.

    Returns:
        Same list with email fields populated where found.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _enrich_one(listing) -> None:
        if not listing.website:
            return

        async with semaphore:
            try:
                emails = await hunt_emails(listing.website)
                if emails:
                    # Use the first (most likely primary) email
                    listing.email = emails[0]
                    logger.info(
                        f"Enriched '{listing.name}' with email: {listing.email}"
                    )
            except Exception as e:
                logger.error(
                    f"Email hunt failed for '{listing.name}': {e}"
                )

            # Polite delay
            random_delay(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX)

    total = sum(1 for l in listings if l.website)
    logger.info(
        f"Starting email enrichment for {total} listings with websites "
        f"(out of {len(listings)} total)"
    )

    tasks = [_enrich_one(listing) for listing in listings]
    await asyncio.gather(*tasks)

    enriched_count = sum(1 for l in listings if l.email)
    logger.info(
        f"Email enrichment complete: "
        f"{enriched_count}/{len(listings)} leads now have emails"
    )

    return listings


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    async def run():
        emails = await hunt_emails(url)
        print(f"\nEmails found on {url}:")
        for email in emails:
            print(f"  • {email}")
        if not emails:
            print("  (none)")

    asyncio.run(run())