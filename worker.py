"""
Scoutly — Background worker.

Run this as a separate process alongside the Streamlit app.
It continuously polls the Redis job queue and processes scrape jobs.

Usage:
    python worker.py
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scoutly.worker")


def main():
    """Start the worker loop."""
    logger.info("=" * 50)
    logger.info("SCOUTLY WORKER")
    logger.info("=" * 50)

    # Verify Redis connection before starting
    from utils.config import get_redis_client
    r = get_redis_client()
    if r is None:
        logger.error(
            "Redis not configured. "
            "Set UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN in .env"
        )
        sys.exit(1)

    try:
        r.ping()
        logger.info("Redis connection OK")
    except Exception as e:
        logger.error(f"Cannot connect to Redis: {e}")
        sys.exit(1)

    # Start polling for jobs
    try:
        from jobs.consumer import poll_for_jobs
        poll_for_jobs()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()