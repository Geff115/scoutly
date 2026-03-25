"""
Scoutly — Streamlit app entry point.

Fully wired to the Redis job queue. Handles:
    1. Input form → enqueue job to Redis
    2. Live status polling with auto-refresh
    3. Free preview (top 5 leads, name + address only)
    4. Payment gate (Lemon Squeezy — Phase 5)
    5. CSV + PDF download after payment
"""

import streamlit as st
import time
from pathlib import Path

from utils.config import PRICING, JobStatus
from jobs.producer import enqueue_job, get_job_status, get_job_result, get_job_preview


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Scoutly — Find businesses. Score leads. Deliver insights.",
    page_icon="🔍",
    layout="centered",
)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🔍 Scoutly")
st.markdown("**Find businesses. Score leads. Deliver insights.**")
st.markdown("---")


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
defaults = {
    "job_id": None,
    "job_status": None,
    "lead_count": 50,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------
st.subheader("What are you looking for?")

with st.form("search_form"):
    col1, col2 = st.columns(2)

    with col1:
        niche = st.text_input(
            "Business type",
            placeholder="e.g. dental clinics, co-working spaces, law firms",
        )
        city = st.text_input(
            "City",
            placeholder="e.g. Lagos, London, São Paulo",
        )

    with col2:
        country = st.text_input(
            "Country",
            placeholder="e.g. Nigeria, United Kingdom, Brazil",
        )
        lead_count = st.selectbox(
            "How many leads?",
            options=[25, 50, 100, 200],
            index=1,
            format_func=lambda x: f"{x} leads — ${PRICING[x]:.0f}",
        )

    st.markdown("**Which contact fields do you need?**")
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        require_email = st.checkbox("Email address", value=True)
        require_phone = st.checkbox("Phone number")
    with filter_col2:
        require_website = st.checkbox("Website")
        require_social = st.checkbox("Social media links")

    user_email = st.text_input(
        "Your email (optional — we'll send the report here too)",
        placeholder="you@example.com",
    )

    submitted = st.form_submit_button("🔎 Find leads", use_container_width=True)

    if submitted:
        if not niche or not city or not country:
            st.error("Please fill in the business type, city, and country.")
        else:
            try:
                job_id = enqueue_job(
                    niche=niche,
                    city=city,
                    country=country,
                    lead_count=lead_count,
                    require_email=require_email,
                    require_phone=require_phone,
                    require_website=require_website,
                    require_social=require_social,
                    user_email=user_email if user_email else None,
                )
                st.session_state.job_id = job_id
                st.session_state.job_status = JobStatus.QUEUED
                st.session_state.lead_count = lead_count
                st.rerun()
            except ConnectionError as e:
                st.error(f"Could not connect to the job queue: {e}")
            except Exception as e:
                st.error(f"Something went wrong: {e}")


# ---------------------------------------------------------------------------
# Job status polling (auto-refreshes while in progress)
# ---------------------------------------------------------------------------
if st.session_state.job_id and st.session_state.job_status not in (
    JobStatus.DONE,
    JobStatus.PAID,
    JobStatus.FAILED,
    None,
):
    st.markdown("---")
    st.subheader("⏳ Preparing your report…")

    # Fetch real status from Redis
    live_status = get_job_status(st.session_state.job_id)
    if live_status:
        st.session_state.job_status = live_status

    status_labels = {
        JobStatus.QUEUED: ("Waiting in queue…", 0.05),
        JobStatus.SCRAPING: ("Scraping Google Maps…", 0.25),
        JobStatus.ENRICHING: ("Hunting for email addresses…", 0.50),
        JobStatus.SCORING: ("Scoring leads…", 0.70),
        JobStatus.BUILDING_REPORT: ("Building your report…", 0.90),
    }

    current = st.session_state.job_status
    label, progress = status_labels.get(current, ("Working…", 0.5))

    st.progress(progress, text=label)
    st.caption(f"Job ID: `{st.session_state.job_id}`")

    # Auto-refresh every 3 seconds while job is in progress
    time.sleep(3)
    st.rerun()


# ---------------------------------------------------------------------------
# Failed state
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.FAILED:
    st.markdown("---")
    st.error(
        "❌ Something went wrong while processing your request. "
        "Please try again or contact support."
    )
    st.caption(f"Job ID: `{st.session_state.job_id}`")

    if st.button("🔄 Start a new search", use_container_width=True):
        st.session_state.job_id = None
        st.session_state.job_status = None
        st.rerun()


# ---------------------------------------------------------------------------
# Free preview + payment gate
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.DONE:
    st.markdown("---")
    st.subheader("✅ Your leads are ready!")

    # Fetch result metadata
    result = get_job_result(st.session_state.job_id)
    if result:
        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.metric("Total Leads", result.get("total_leads", "—"))
        with mcol2:
            st.metric("Avg Score", result.get("avg_score", "—"))
        with mcol3:
            st.metric("Query", result.get("query", "—")[:30])

    # Free preview
    st.markdown("### Free preview — top 5 leads")
    st.caption("Name and address only. Pay to unlock full contact details, scores, and PDF report.")

    preview = get_job_preview(st.session_state.job_id)
    if preview:
        for i, lead in enumerate(preview, 1):
            st.markdown(
                f"**{i}. {lead.get('name', 'Unknown')}**  \n"
                f"📍 {lead.get('address', 'No address')}"
            )
    else:
        st.info("Preview loading…")

    st.markdown("---")

    # Payment button
    lc = st.session_state.lead_count
    price = PRICING.get(lc, 5.00)
    st.markdown(f"### Unlock the full report — ${price:.0f}")
    st.markdown(
        f"Get all **{lc} leads** with emails, phone numbers, "
        "scores, and a visual PDF report."
    )

    if st.button(f"💳 Pay ${price:.0f} and download", use_container_width=True):
        # TODO: Phase 5 — create Lemon Squeezy checkout URL and redirect
        # For now, skip payment and go straight to download (dev mode)
        st.session_state.job_status = JobStatus.PAID
        st.rerun()


# ---------------------------------------------------------------------------
# Download section (post-payment)
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.PAID:
    st.markdown("---")
    st.subheader("🎉 Report unlocked!")
    st.success("Thank you for your purchase. Your files are ready.")

    result = get_job_result(st.session_state.job_id)

    dl_col1, dl_col2 = st.columns(2)

    if result:
        csv_path = Path(result.get("csv_path", ""))
        pdf_path = Path(result.get("pdf_path", ""))

        with dl_col1:
            if csv_path.exists():
                with open(csv_path, "rb") as f:
                    st.download_button(
                        "📥 Download CSV",
                        data=f.read(),
                        file_name=f"scoutly_leads_{st.session_state.job_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            else:
                st.warning("CSV file not found")

        with dl_col2:
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📥 Download PDF Report",
                        data=f.read(),
                        file_name=f"scoutly_report_{st.session_state.job_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.warning("PDF file not found")
    else:
        st.warning("Could not load result metadata.")

    st.markdown("---")

    # Option to start a new search
    if st.button("🔍 Start a new search", use_container_width=True):
        st.session_state.job_id = None
        st.session_state.job_status = None
        st.rerun()


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("Built with 🔍 by Scoutly — © 2026 · scoutly.sbs")