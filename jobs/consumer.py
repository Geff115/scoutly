"""
Scoutly — Job queue consumer.

Pops jobs from the Redis queue and runs the full pipeline:
scrape → enrich → clean → score → report.

Updates the status key at each stage so the UI can poll progress.
"""

import asyncio
import json
import logging
import traceback
from dataclasses import asdict
from pathlib import Path

from utils.config import JobStatus, REPORT_OUTPUT_DIR
from utils.redis_client import get_redis

logger = logging.getLogger("scoutly.jobs.consumer")

# Keys expire after 24 hours
TTL_SECONDS = 86400


def _update_status(job_id: str, status: str) -> None:
    """Update the job status in Redis."""
    r = get_redis()
    r.set(f"scoutly:status:{job_id}", status, ex=TTL_SECONDS)
    logger.info(f"[{job_id}] Status → {status}")


def _store_result(job_id: str, csv_path: str, pdf_path: str, stats: dict) -> None:
    """Store job results in Redis for the UI to retrieve."""
    r = get_redis()
    result_key = f"scoutly:result:{job_id}"
    r.hset(result_key, mapping={
        "csv_path": csv_path,
        "pdf_path": pdf_path,
        "total_leads": str(stats.get("total_leads", 0)),
        "pct_with_email": f"{stats.get('pct_with_email', 0):.0f}",
        "pct_with_phone": f"{stats.get('pct_with_phone', 0):.0f}",
        "avg_score": f"{stats.get('avg_score', 0):.1f}",
        "avg_rating": f"{stats.get('avg_rating', 0):.1f}",
    })
    r.expire(result_key, TTL_SECONDS)


def _store_preview(job_id: str, df) -> None:
    """Store a free preview of the top 5 leads (name + address only)."""
    r = get_redis()
    top5 = df.head(5)[["name", "address"]].to_dict(orient="records")
    r.set(f"scoutly:preview:{job_id}", json.dumps(top5), ex=TTL_SECONDS)


async def process_job(job_payload: dict) -> None:
    """
    Execute the full Scoutly pipeline for a single job.

    Stages:
        1. scraping       — Playwright Google Maps
        2. enriching      — httpx email hunting
        3. scoring        — clean + ML lead scoring
        4. building_report — CSV + PDF generation
        5. done           — files ready, paths stored in Redis
    """
    job_id = job_payload["job_id"]
    query = job_payload["query"]
    lead_count = int(job_payload["lead_count"])
    require_email = job_payload.get("require_email", False)
    require_phone = job_payload.get("require_phone", False)
    require_website = job_payload.get("require_website", False)

    logger.info(f"[{job_id}] Starting pipeline: '{query}' ({lead_count} leads)")

    try:
        # ---- Stage 1: Scrape Google Maps ----
        _update_status(job_id, JobStatus.SCRAPING)

        from scraper.maps import scrape_google_maps
        listings = await scrape_google_maps(query, target_count=lead_count)

        if not listings:
            raise ValueError("No listings found on Google Maps for this query")

        logger.info(f"[{job_id}] Scraped {len(listings)} raw listings")

        # ---- Stage 2: Enrich with emails ----
        _update_status(job_id, JobStatus.ENRICHING)

        from scraper.email_hunter import enrich_listings_with_emails
        listings = await enrich_listings_with_emails(listings)

        email_count = sum(1 for l in listings if l.email)
        logger.info(f"[{job_id}] Enriched: {email_count}/{len(listings)} have emails")

        # ---- Stage 3: Clean + Score ----
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
        logger.info(f"[{job_id}] Scored {len(df)} leads (avg: {df['ml_score'].mean():.1f})")

        # ---- Stage 4: Build report ----
        _update_status(job_id, JobStatus.BUILDING_REPORT)

        from report.pdf_builder import build_pdf_report, generate_summary_stats

        # Create output directory for this job
        job_output_dir = REPORT_OUTPUT_DIR / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        # Save CSV
        safe_query = query.replace(" ", "_").replace(",", "")[:50]
        csv_path = job_output_dir / f"scoutly_{safe_query}.csv"
        df.to_csv(csv_path, index=False)

        # Build PDF
        pdf_path = job_output_dir / f"scoutly_{safe_query}.pdf"
        build_pdf_report(df, query, pdf_path, charts_dir=job_output_dir)

        # Generate summary stats
        stats = generate_summary_stats(df)

        # Store free preview (top 5: name + address only)
        _store_preview(job_id, df)

        # Store result paths
        _store_result(job_id, str(csv_path), str(pdf_path), stats)

        # ---- Done ----
        _update_status(job_id, JobStatus.DONE)
        logger.info(
            f"[{job_id}] Pipeline complete: {len(df)} leads, "
            f"CSV: {csv_path}, PDF: {pdf_path}"
        )

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}")
        logger.error(traceback.format_exc())

        # Store error info
        r = get_redis()
        r.set(f"scoutly:status:{job_id}", JobStatus.FAILED, ex=TTL_SECONDS)
        r.set(f"scoutly:error:{job_id}", str(e), ex=TTL_SECONDS)


def poll_for_jobs() -> None:
    """
    Blocking loop: pop jobs from Redis and process them one at a time.
    Called by worker.py as the main entry point.

    Uses BRPOP for efficient blocking — no busy-wait polling.
    """
    r = get_redis()
    logger.info("Waiting for jobs on 'scoutly:jobs'...")

    while True:
        try:
            # BRPOP blocks until a job appears (timeout 0 = wait forever)
            result = r.brpop("scoutly:jobs", timeout=5)

            if result is None:
                # Timeout — no jobs, loop and try again
                continue

            _, raw_payload = result
            payload = json.loads(raw_payload)
            job_id = payload.get("job_id", "unknown")

            logger.info(f"Picked up job: {job_id}")

            # Run the async pipeline in an event loop
            asyncio.run(process_job(payload))

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except json.JSONDecodeError as e:
            logger.error(f"Invalid job payload: {e}")
            continue
        except Exception as e:
            logger.error(f"Error processing job: {e}")
            logger.error(traceback.format_exc())
            continue