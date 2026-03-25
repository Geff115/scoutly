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

    # Test Redis connection before entering the loop
    try:
        from utils.redis_client import get_redis
        r = get_redis()
        logger.info(f"Redis connected. Pending jobs: {r.llen('scoutly:jobs')}")
    except Exception as e:
        logger.error(f"Cannot connect to Redis: {e}")
        logger.error("Check UPSTASH_REDIS_URL in your .env file")
        sys.exit(1)

    # Start the blocking job loop
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