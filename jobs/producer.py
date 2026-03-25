"""
Scoutly — Job queue producer.

Pushes scrape jobs onto the Redis queue and creates status tracking keys.
Called by the Streamlit UI when a user submits the search form.
"""

import json
import logging
from typing import Optional

from utils.config import (
    get_redis_client,
    REDIS_JOBS_KEY,
    REDIS_STATUS_PREFIX,
    REDIS_TTL,
    JobStatus,
)
from utils.helpers import generate_job_id, build_search_query

logger = logging.getLogger("scoutly.jobs.producer")


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

    Creates:
        - scoutly:jobs             → appends job payload (LPUSH)
        - scoutly:status:{job_id}  → set to "queued"

    Returns:
        The generated job_id.

    Raises:
        ConnectionError: If Redis is not reachable.
    """
    r = get_redis_client()
    if r is None:
        raise ConnectionError("Redis is not configured — check UPSTASH_REDIS_URL")

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

    # Push job onto the queue (LPUSH so BRPOP processes FIFO)
    r.lpush(REDIS_JOBS_KEY, json.dumps(payload))

    # Set initial status
    status_key = f"{REDIS_STATUS_PREFIX}{job_id}"
    r.set(status_key, JobStatus.QUEUED, ex=REDIS_TTL)

    logger.info(f"Job {job_id} enqueued: '{query}' ({lead_count} leads)")
    return job_id


def get_job_status(job_id: str) -> Optional[str]:
    """
    Poll the current status of a job.

    Returns one of the JobStatus constants, or None if not found.
    """
    r = get_redis_client()
    if r is None:
        return None

    status_key = f"{REDIS_STATUS_PREFIX}{job_id}"
    return r.get(status_key)


def get_job_result(job_id: str) -> Optional[dict]:
    """
    Fetch the result metadata for a completed job.

    Returns dict with csv_path, pdf_path, total_leads, avg_score,
    or None if the job is not done yet.
    """
    from utils.config import REDIS_RESULT_PREFIX

    r = get_redis_client()
    if r is None:
        return None

    result_key = f"{REDIS_RESULT_PREFIX}{job_id}"
    data = r.hgetall(result_key)
    return data if data else None


def get_job_preview(job_id: str) -> Optional[list]:
    """
    Fetch the free preview data (top 5 leads, name + address only).

    Returns a list of dicts, or None if not available.
    """
    from utils.config import REDIS_PREVIEW_PREFIX

    r = get_redis_client()
    if r is None:
        return None

    preview_key = f"{REDIS_PREVIEW_PREFIX}{job_id}"
    raw = r.get(preview_key)
    if raw:
        return json.loads(raw)
    return None