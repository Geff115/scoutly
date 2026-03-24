"""
Scoutly — Lemon Squeezy payment integration.

Handles:
    - Creating hosted checkout URLs for each report tier
    - Verifying webhook signatures on payment confirmation
    - Marking jobs as paid in Redis so the UI can unlock downloads
"""

import hmac
import hashlib
import json
from typing import Optional
from utils.config import (
    LEMONSQUEEZY_API_KEY,
    LEMONSQUEEZY_STORE_ID,
    LEMONSQUEEZY_WEBHOOK_SECRET,
    LEMONSQUEEZY_VARIANTS,
    PRICING,
)


def create_checkout_url(
    job_id: str,
    lead_count: int,
    user_email: Optional[str] = None,
) -> str:
    """
    Create a Lemon Squeezy hosted checkout URL for a report.

    Embeds the job_id as a custom parameter so the webhook can
    link the payment back to the correct report.

    Args:
        job_id: The Scoutly job identifier.
        lead_count: One of 25, 50, 100, 200.
        user_email: Pre-fill the customer email if provided.

    Returns:
        The hosted checkout URL to redirect the user to.
    """
    # TODO: Phase 5 — implement Lemon Squeezy API call
    raise NotImplementedError("Checkout URL creation not yet implemented")


def verify_webhook_signature(
    payload: bytes,
    signature: str,
) -> bool:
    """
    Verify that a webhook request actually came from Lemon Squeezy.

    Uses HMAC-SHA256 with the webhook secret.

    Args:
        payload: Raw request body bytes.
        signature: Value of the X-Signature header.

    Returns:
        True if the signature is valid.
    """
    expected = hmac.new(
        LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def handle_payment_webhook(payload: dict) -> Optional[str]:
    """
    Process a Lemon Squeezy webhook event.

    On a successful 'order_created' event:
        1. Extract the job_id from custom data
        2. Mark the job as paid in Redis
        3. Return the job_id

    Args:
        payload: Parsed JSON body from the webhook.

    Returns:
        The job_id if payment was confirmed, None otherwise.
    """
    # TODO: Phase 5 — implement webhook event processing
    raise NotImplementedError("Webhook handler not yet implemented")
