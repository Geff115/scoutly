"""
Scoutly — Job queue consumer.

Pops jobs from the Redis queue and runs the full pipeline:
scrape → enrich → clean → score → report.

Updates the status key at each stage so the UI can poll progress.
"""

import asyncio
import json
import logging
import time
import traceback
from dataclasses import asdict
from pathlib import Path

from utils.config import (
    get_redis_client,
    REDIS_JOBS_KEY,
    REDIS_STATUS_PREFIX,
    REDIS_RESULT_PREFIX,
    REDIS_PREVIEW_PREFIX,
    REDIS_TTL,
    REPORT_OUTPUT_DIR,
    JobStatus,
)

logger = logging.getLogger("scoutly.jobs.consumer")


def _update_status(job_id: str, status: str) -> None:
    """Update the job status key in Redis."""
    r = get_redis_client()
    if r:
        r.set(f"{REDIS_STATUS_PREFIX}{job_id}", status, ex=REDIS_TTL)
    logger.info(f"[{job_id}] Status → {status}")


def _store_result(job_id: str, result: dict) -> None:
    """Store the job result metadata in Redis as a hash."""
    r = get_redis_client()
    if r:
        result_key = f"{REDIS_RESULT_PREFIX}{job_id}"
        r.hset(result_key, mapping=result)
        r.expire(result_key, REDIS_TTL)


def _store_preview(job_id: str, df) -> None:
    """Store the top 5 leads (name + address only) as a JSON preview."""
    r = get_redis_client()
    if r:
        preview = df.head(5)[["name", "address"]].to_dict(orient="records")
        preview_key = f"{REDIS_PREVIEW_PREFIX}{job_id}"
        r.set(preview_key, json.dumps(preview), ex=REDIS_TTL)


async def process_job(job_payload: dict) -> None:
    """
    Execute the full Scoutly pipeline for a single job.

    Stages (status key updated at each):
        1. scraping       — Playwright Google Maps
        2. enriching      — httpx email hunting
        3. scoring        — ML lead scoring
        4. building_report — CSV + PDF generation
        5. done           — files ready, paths stored in Redis

    On error, status is set to "failed" with an error message.
    """
    job_id = job_payload["job_id"]
    query = job_payload["query"]
    lead_count = job_payload["lead_count"]
    require_email = job_payload.get("require_email", False)
    require_phone = job_payload.get("require_phone", False)
    require_website = job_payload.get("require_website", False)

    logger.info(f"[{job_id}] Starting pipeline: '{query}' ({lead_count} leads)")

    try:
        # ---------------------------------------------------------------
        # Stage 1: Scrape Google Maps
        # ---------------------------------------------------------------
        _update_status(job_id, JobStatus.SCRAPING)

        from scraper.maps import scrape_google_maps
        listings = await scrape_google_maps(query, target_count=lead_count)

        if not listings:
            raise ValueError(f"No listings found for '{query}'")

        logger.info(f"[{job_id}] Scraped {len(listings)} raw listings")

        # ---------------------------------------------------------------
        # Stage 2: Enrich with emails
        # ---------------------------------------------------------------
        _update_status(job_id, JobStatus.ENRICHING)

        from scraper.email_hunter import enrich_listings_with_emails
        listings = await enrich_listings_with_emails(listings)

        email_count = sum(1 for l in listings if l.email)
        logger.info(f"[{job_id}] {email_count}/{len(listings)} enriched with email")

        # ---------------------------------------------------------------
        # Stage 3: Clean + Score
        # ---------------------------------------------------------------
        _update_status(job_id, JobStatus.SCORING)

        from scraper.cleaner import clean_leads
        from ml.scorer import score_dataframe

        raw_dicts = [asdict(l) for l in listings]
        df = clean_leads(
            raw_dicts,
            target_count=lead_count,
            require_email=require_email,
            require_phone=require_phone,
            require_website=require_website,
        )

        if df.empty:
            raise ValueError("No leads survived the cleaning pipeline")

        df = score_dataframe(df)
        avg_score = float(df["ml_score"].mean())
        logger.info(f"[{job_id}] {len(df)} clean leads, avg score {avg_score:.1f}")

        # Store the free preview (top 5 leads)
        _store_preview(job_id, df)

        # ---------------------------------------------------------------
        # Stage 4: Build CSV + PDF report
        # ---------------------------------------------------------------
        _update_status(job_id, JobStatus.BUILDING_REPORT)

        safe_name = query.replace(" ", "_").replace(",", "")[:50]
        csv_path = REPORT_OUTPUT_DIR / f"{job_id}_{safe_name}.csv"
        pdf_path = REPORT_OUTPUT_DIR / f"{job_id}_{safe_name}.pdf"

        df.to_csv(csv_path, index=False)

        from report.pdf_builder import build_pdf_report
        build_pdf_report(df, query, pdf_path)

        logger.info(f"[{job_id}] CSV: {csv_path}")
        logger.info(f"[{job_id}] PDF: {pdf_path}")

        # ---------------------------------------------------------------
        # Stage 5: Store result and mark done
        # ---------------------------------------------------------------
        _store_result(job_id, {
            "csv_path": str(csv_path),
            "pdf_path": str(pdf_path),
            "total_leads": str(len(df)),
            "avg_score": f"{avg_score:.1f}",
            "query": query,
        })

        _update_status(job_id, JobStatus.DONE)
        logger.info(f"[{job_id}] Pipeline complete ✓")

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        _update_status(job_id, JobStatus.FAILED)

        # Store error details
        r = get_redis_client()
        if r:
            r.set(
                f"{REDIS_RESULT_PREFIX}{job_id}:error",
                str(e),
                ex=REDIS_TTL,
            )


def poll_for_jobs(poll_interval: int = 2) -> None:
    """
    Blocking loop: pop jobs from Redis and process them one at a time.

    Uses BRPOP with a timeout so it doesn't spin.
    Called by worker.py as the main entry point.
    """
    r = get_redis_client()
    if r is None:
        raise ConnectionError(
            "Redis is not configured. Set UPSTASH_REDIS_URL and "
            "UPSTASH_REDIS_TOKEN in your .env file."
        )

    # Test the connection
    try:
        r.ping()
        logger.info("Connected to Redis ✓")
    except Exception as e:
        raise ConnectionError(f"Cannot reach Redis: {e}")

    logger.info(f"Polling '{REDIS_JOBS_KEY}' for jobs...")

    while True:
        try:
            # BRPOP blocks until a job is available (timeout = poll_interval)
            result = r.brpop(REDIS_JOBS_KEY, timeout=poll_interval)

            if result is None:
                # Timeout — no job available, loop again
                continue

            _, raw_payload = result
            payload = json.loads(raw_payload)
            job_id = payload.get("job_id", "unknown")

            logger.info(f"Picked up job: {job_id}")

            # Run the async pipeline in an event loop
            asyncio.run(process_job(payload))

        except json.JSONDecodeError as e:
            logger.error(f"Invalid job payload: {e}")
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except Exception as e:
            logger.error(f"Error processing job: {e}", exc_info=True)
            # Brief pause before retrying to avoid tight error loops
            time.sleep(5)