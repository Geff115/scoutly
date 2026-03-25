"""
Scoutly — Redis client.

Provides a shared Redis connection to Upstash.
All queue and status operations go through this client.
"""

import logging
import redis
from utils.config import REDIS_URL, REDIS_TOKEN

logger = logging.getLogger("scoutly.utils.redis_client")

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """
    Get a shared Redis connection.

    Upstash provides a rediss:// URL that includes auth.
    If REDIS_URL already contains credentials, we use it directly.
    Otherwise, we build the connection with the token as password.
    """
    global _client

    if _client is not None:
        return _client

    if not REDIS_URL:
        raise RuntimeError(
            "UPSTASH_REDIS_URL is not set. "
            "Add it to your .env file to enable the job queue."
        )

    try:
        if REDIS_TOKEN and "@" not in REDIS_URL:
            # URL doesn't have credentials embedded — add the token as password
            _client = redis.from_url(
                REDIS_URL,
                password=REDIS_TOKEN,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
        else:
            # URL already has credentials (standard Upstash format)
            _client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
            )

        # Test the connection
        _client.ping()
        logger.info("Connected to Redis (Upstash)")
        return _client

    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    except Exception as e:
        logger.error(f"Redis error: {e}")
        raise