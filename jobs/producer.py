"""
Scoutly — Job queue producer.

Pushes scrape jobs onto the Redis queue and creates status tracking keys.

Redis keys created:
    scoutly:jobs              → LIST: pending job payloads (LPUSH)
    scoutly:status:{job_id}   → STRING: current status
    scoutly:meta:{job_id}     → HASH: job metadata (query, count, filters, email)
"""

import json
import logging
from typing import Optional

from utils.config import JobStatus
from utils.helpers import generate_job_id, build_search_query
from utils.redis_client import get_redis

logger = logging.getLogger("scoutly.jobs.producer")

# All job-related keys expire after 24 hours
TTL_SECONDS = 86400


def enqueue_job(
    niche: str,
    city: str,
    country: str,
    lead_count: int,
    require_email: bool = False,
    require_phone: bool = False,
    require_website: bool = False,
    require_social: bool = False,
    user_email: Optional[str] = None,
) -> str:
    """
    Push a new scrape job to the Redis queue.

    Args:
        niche: Business type to search for.
        city: City name.
        country: Country name.
        lead_count: One of 25, 50, 100, 200.
        require_*: Filter flags from the user form.
        user_email: Optional email for report delivery.

    Returns:
        The generated job_id.
    """
    r = get_redis()
    job_id = generate_job_id()

    query = build_search_query(niche, city, country)

    payload = {
        "job_id": job_id,
        "query": query,
        "niche": niche,
        "city": city,
        "country": country,
        "lead_count": lead_count,
        "require_email": require_email,
        "require_phone": require_phone,
        "require_website": require_website,
        "require_social": require_social,
        "user_email": user_email or "",
    }

    # Push job to queue
    r.lpush("scoutly:jobs", json.dumps(payload))

    # Set initial status
    status_key = f"scoutly:status:{job_id}"
    r.set(status_key, JobStatus.QUEUED, ex=TTL_SECONDS)

    # Store job metadata for the UI
    meta_key = f"scoutly:meta:{job_id}"
    r.hset(meta_key, mapping={
        "query": query,
        "lead_count": str(lead_count),
        "user_email": user_email or "",
        "niche": niche,
        "city": city,
        "country": country,
    })
    r.expire(meta_key, TTL_SECONDS)

    logger.info(f"Job {job_id} enqueued: '{query}' ({lead_count} leads)")
    return job_id


def get_job_status(job_id: str) -> Optional[str]:
    """Get the current status of a job."""
    r = get_redis()
    return r.get(f"scoutly:status:{job_id}")


def get_job_result(job_id: str) -> Optional[dict]:
    """Get the result paths and stats for a completed job."""
    r = get_redis()
    result = r.hgetall(f"scoutly:result:{job_id}")
    return result if result else None


def get_job_preview(job_id: str) -> Optional[str]:
    """Get the free preview JSON for a completed job."""
    r = get_redis()
    return r.get(f"scoutly:preview:{job_id}")
