"""
Scoutly — Shared configuration.

Loads environment variables from .env and exposes them as typed constants
used across all modules. Import this instead of calling os.getenv() directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", "")
REDIS_TOKEN: str = os.getenv("UPSTASH_REDIS_TOKEN", "")

# Job key prefixes
REDIS_JOBS_KEY = "scoutly:jobs"
REDIS_STATUS_PREFIX = "scoutly:status:"
REDIS_RESULT_PREFIX = "scoutly:result:"
REDIS_PREVIEW_PREFIX = "scoutly:preview:"
REDIS_TTL = 86400  # 24 hours


def get_redis_client():
    """
    Create and return a Redis client connected to Upstash.

    Uses the UPSTASH_REDIS_URL which includes the password.
    Returns None if Redis is not configured.
    """
    import redis as _redis

    if not REDIS_URL:
        return None

    return _redis.from_url(
        REDIS_URL,
        password=REDIS_TOKEN,
        decode_responses=True,
        socket_timeout=10,
        socket_connect_timeout=10,
    )

# ---------------------------------------------------------------------------
# Resend
# ---------------------------------------------------------------------------
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "reports@scoutly.app")

# ---------------------------------------------------------------------------
# Lemon Squeezy
# ---------------------------------------------------------------------------
LEMONSQUEEZY_API_KEY: str = os.getenv("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID: str = os.getenv("LEMONSQUEEZY_STORE_ID", "")
LEMONSQUEEZY_WEBHOOK_SECRET: str = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")

# Map lead count → Lemon Squeezy variant ID
LEMONSQUEEZY_VARIANTS: dict[int, str] = {
    25: os.getenv("LEMONSQUEEZY_VARIANT_25", ""),
    50: os.getenv("LEMONSQUEEZY_VARIANT_50", ""),
    100: os.getenv("LEMONSQUEEZY_VARIANT_100", ""),
    200: os.getenv("LEMONSQUEEZY_VARIANT_200", ""),
}

# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------
APP_ENV: str = os.getenv("APP_ENV", "development")
IS_PRODUCTION: bool = APP_ENV == "production"
MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
SCRAPE_DELAY_MIN: float = float(os.getenv("SCRAPE_DELAY_MIN", "0.5"))
SCRAPE_DELAY_MAX: float = float(os.getenv("SCRAPE_DELAY_MAX", "1.5"))
REPORT_OUTPUT_DIR: Path = Path(os.getenv("REPORT_OUTPUT_DIR", "./outputs"))

# Ensure the output directory exists
REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pricing (used by the UI and payment module)
# ---------------------------------------------------------------------------
PRICING: dict[int, float] = {
    25: 3.00,
    50: 5.00,
    100: 8.00,
    200: 14.00,
}

# ---------------------------------------------------------------------------
# Job statuses — single source of truth used by queue + UI
# ---------------------------------------------------------------------------
class JobStatus:
    QUEUED = "queued"
    SCRAPING = "scraping"
    ENRICHING = "enriching"
    SCORING = "scoring"
    BUILDING_REPORT = "building_report"
    DONE = "done"
    FAILED = "failed"
    PAID = "paid"