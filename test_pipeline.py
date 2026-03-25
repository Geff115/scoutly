"""
Scoutly — End-to-end pipeline test.

Runs the full scrape → enrich → clean → score pipeline from the command line
and outputs results as a CSV file.

Usage:
    python test_pipeline.py "dental clinics" "Lagos" "Nigeria" 25
    python test_pipeline.py "co-working spaces" "London" "United Kingdom" 50
"""

import asyncio
import sys
import logging
import json
from dataclasses import asdict
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scoutly.test_pipeline")


async def run_pipeline(
    niche: str,
    city: str,
    country: str,
    lead_count: int = 25,
    require_email: bool = False,
    require_phone: bool = False,
    require_website: bool = False,
    headless: bool = True,
) -> None:
    """Run the full Scoutly pipeline end-to-end."""

    from utils.helpers import build_search_query
    from scraper.maps import scrape_google_maps
    from scraper.email_hunter import enrich_listings_with_emails
    from scraper.cleaner import clean_leads
    from ml.scorer import score_dataframe

    # 1. Build query
    query = build_search_query(niche, city, country)
    logger.info(f"{'=' * 60}")
    logger.info(f"SCOUTLY PIPELINE TEST")
    logger.info(f"Query: {query}")
    logger.info(f"Target: {lead_count} leads")
    logger.info(f"{'=' * 60}")

    # 2. Scrape Google Maps
    logger.info("\n📍 STAGE 1: Scraping Google Maps…")
    listings = await scrape_google_maps(query, target_count=lead_count, headless=headless)
    logger.info(f"   → Got {len(listings)} raw listings")

    if not listings:
        logger.error("No listings scraped — aborting pipeline")
        return

    # 3. Enrich with emails
    logger.info("\n📧 STAGE 2: Hunting for emails…")
    listings = await enrich_listings_with_emails(listings)
    email_count = sum(1 for l in listings if l.email)
    logger.info(f"   → {email_count}/{len(listings)} listings now have emails")

    # 4. Clean leads
    logger.info("\n🧹 STAGE 3: Cleaning leads…")
    raw_dicts = [asdict(l) for l in listings]
    df = clean_leads(
        raw_dicts,
        target_count=lead_count,
        require_email=require_email,
        require_phone=require_phone,
        require_website=require_website,
    )
    logger.info(f"   → {len(df)} clean leads after filtering")

    if df.empty:
        logger.error("No leads survived cleaning — aborting")
        return

    # 5. Score leads
    logger.info("\n🏆 STAGE 4: Scoring leads…")
    df = score_dataframe(df)
    avg_score = df["ml_score"].mean()
    logger.info(f"   → Average score: {avg_score:.1f}")

    # 6. Save to CSV
    output_dir = Path("./outputs")
    output_dir.mkdir(exist_ok=True)

    safe_query = query.replace(" ", "_").replace(",", "")[:50]
    csv_path = output_dir / f"scoutly_{safe_query}.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"\n💾 Saved to: {csv_path}")

    # 7. Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PIPELINE COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Total clean leads:  {len(df)}")
    logger.info(f"With email:         {(df['email'].str.len() > 0).sum()}")
    logger.info(f"With phone:         {(df['phone'].str.len() > 0).sum()}")
    logger.info(f"With website:       {(df['website'].str.len() > 0).sum()}")
    logger.info(f"Avg rating:         {df['rating'].mean():.2f}")
    logger.info(f"Avg ML score:       {avg_score:.1f}")
    logger.info(f"{'=' * 60}")

    # Print top 5
    print("\n🔝 Top 5 leads:\n")
    top5 = df.head(5)[["name", "address", "email", "phone", "ml_score"]]
    print(top5.to_string(index=False))
    print()


def main():
    # Parse CLI args
    if len(sys.argv) < 4:
        print("Usage: python test_pipeline.py <niche> <city> <country> [lead_count]")
        print('Example: python test_pipeline.py "dental clinics" "Lagos" "Nigeria" 25')
        sys.exit(1)

    niche = sys.argv[1]
    city = sys.argv[2]
    country = sys.argv[3]
    lead_count = int(sys.argv[4]) if len(sys.argv) > 4 else 25

    asyncio.run(run_pipeline(niche, city, country, lead_count))


if __name__ == "__main__":
    main()