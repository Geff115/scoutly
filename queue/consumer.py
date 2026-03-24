"""
Scoutly — Job queue consumer.

Pops jobs from the Redis queue and runs the full pipeline:
scrape → enrich → clean → score → report.

Updates the status key at each stage so the UI can poll progress.
"""

import json
from utils.config import JobStatus


async def process_job(job_payload: dict) -> None:
    """
    Execute the full Scoutly pipeline for a single job.

    Stages (status key updated at each):
        1. scraping     — Playwright Google Maps
        2. enriching    — httpx email hunting
        3. scoring      — ML lead scoring
        4. building_report — CSV + PDF generation
        5. done         — files ready, paths stored in Redis

    On error, status is set to "failed" with an error message.

    Args:
        job_payload: Dict with niche, city, country, count, filters, email.
    """
    # TODO: Phase 4 — implement full pipeline orchestration
    raise NotImplementedError("Job consumer not yet implemented")


def poll_for_jobs() -> None:
    """
    Blocking loop: pop jobs from Redis and process them one at a time.
    Called by worker.py as the main entry point.
    """
    # TODO: Phase 4 — implement BRPOP loop
    raise NotImplementedError("Job polling not yet implemented")
