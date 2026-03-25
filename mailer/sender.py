"""
Scoutly — Email delivery via Resend.

Sends the CSV + PDF report to the user's email after payment confirmation.
"""

from pathlib import Path
from typing import Optional


def send_report_email(
    to_email: str,
    query: str,
    total_leads: int,
    avg_score: float,
    csv_path: Path,
    pdf_path: Path,
) -> bool:
    """
    Send the completed report to a user via Resend.

    The email includes:
        - Short summary (total leads, average score)
        - CSV file attached
        - PDF file attached
        - Link back to Scoutly

    Args:
        to_email: User's email address.
        query: Original search query for the subject line.
        total_leads: Number of leads in the report.
        avg_score: Average ML score across all leads.
        csv_path: Path to the CSV file.
        pdf_path: Path to the PDF file.

    Returns:
        True if sent successfully, False otherwise.
    """
    # TODO: Phase 5 — implement Resend API call with attachments
    raise NotImplementedError("Email sender not yet implemented")
