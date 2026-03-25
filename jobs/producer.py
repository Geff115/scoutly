"""
Scoutly — Job queue producer.

Pushes scrape jobs onto the Redis queue and creates status tracking keys.
"""

import json
from typing import Optional
from utils.config import REDIS_URL, JobStatus
from utils.helpers import generate_job_id


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
        - scoutly:jobs         → appends job payload to the list
        - scoutly:status:{id}  → set to "queued"

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
    # TODO: Phase 4 — implement Redis LPUSH + status key creation
    raise NotImplementedError("Job producer not yet implemented")
