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
    logger.info("🔍 Scoutly worker starting…")
    logger.info("Waiting for jobs on Redis queue 'scoutly:jobs'")

    try:
        # TODO: Phase 4 — call poll_for_jobs() from queue.consumer
        # from jobs.consumer import poll_for_jobs
        # poll_for_jobs()
        logger.warning(
            "Worker is scaffolded but not yet wired up. "
            "Implement Phase 4 (Redis job queue) to activate."
        )
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
