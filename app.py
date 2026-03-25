"""
Scoutly — Streamlit app entry point.

Fully wired to the Redis job queue. Handles:
    1. Input form (niche, city, country, lead count, filters, email)
    2. Job submission → Redis queue via producer
    3. Live progress polling every 3 seconds
    4. Free preview (top 5 leads, name + address only)
    5. Payment gate (Lemon Squeezy — Phase 5)
    6. Download buttons for CSV + PDF after payment
"""

import json
import time
from pathlib import Path

import streamlit as st
import pandas as pd

from utils.config import PRICING, JobStatus


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
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "job_status" not in st.session_state:
    st.session_state.job_status = None
if "lead_count" not in st.session_state:
    st.session_state.lead_count = 50


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
                from jobs.producer import enqueue_job

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

            except Exception as e:
                st.error(f"Failed to submit job: {e}")


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------
if st.session_state.job_id and st.session_state.job_status not in (
    JobStatus.DONE,
    JobStatus.PAID,
    JobStatus.FAILED,
    None,
):
    st.markdown("---")
    st.subheader("⏳ Preparing your report…")

    status_labels = {
        JobStatus.QUEUED: ("Waiting in queue…", 0.05),
        JobStatus.SCRAPING: ("Scraping Google Maps…", 0.25),
        JobStatus.ENRICHING: ("Hunting for email addresses…", 0.50),
        JobStatus.SCORING: ("Scoring and cleaning leads…", 0.70),
        JobStatus.BUILDING_REPORT: ("Building your PDF report…", 0.90),
    }

    current = st.session_state.job_status
    label, progress = status_labels.get(current, ("Working…", 0.5))

    st.progress(progress, text=label)

    st.caption(f"Job ID: `{st.session_state.job_id}`")

    # Poll for status update
    time.sleep(3)
    try:
        from jobs.producer import get_job_status
        new_status = get_job_status(st.session_state.job_id)
        if new_status and new_status != st.session_state.job_status:
            st.session_state.job_status = new_status
        st.rerun()
    except Exception:
        st.rerun()


# ---------------------------------------------------------------------------
# Failed job
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.FAILED:
    st.markdown("---")
    st.error("❌ Something went wrong with your scrape job.")

    try:
        from utils.redis_client import get_redis
        r = get_redis()
        error_msg = r.get(f"scoutly:error:{st.session_state.job_id}")
        if error_msg:
            st.caption(f"Error: {error_msg}")
    except Exception:
        pass

    if st.button("🔄 Try again", use_container_width=True):
        st.session_state.job_id = None
        st.session_state.job_status = None
        st.rerun()


# ---------------------------------------------------------------------------
# Free preview + payment gate
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.DONE:
    st.markdown("---")
    st.subheader("✅ Your leads are ready!")

    # Show free preview
    try:
        from jobs.producer import get_job_preview, get_job_result

        preview_json = get_job_preview(st.session_state.job_id)
        result = get_job_result(st.session_state.job_id)

        if result:
            total = result.get("total_leads", "?")
            avg_score = result.get("avg_score", "?")
            pct_email = result.get("pct_with_email", "?")
            st.markdown(
                f"**{total} leads** found · Average score: **{avg_score}** · "
                f"**{pct_email}%** have email addresses"
            )

        if preview_json:
            st.markdown("**Free preview — top 5 leads (name + address only):**")
            preview = json.loads(preview_json)
            preview_df = pd.DataFrame(preview)
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
        else:
            st.info("Preview data not available.")

    except Exception as e:
        st.warning(f"Could not load preview: {e}")

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

    try:
        from jobs.producer import get_job_result

        result = get_job_result(st.session_state.job_id)

        if result:
            csv_path = Path(result.get("csv_path", ""))
            pdf_path = Path(result.get("pdf_path", ""))

            dl_col1, dl_col2 = st.columns(2)

            with dl_col1:
                if csv_path.exists():
                    with open(csv_path, "rb") as f:
                        st.download_button(
                            "📥 Download CSV",
                            data=f.read(),
                            file_name=csv_path.name,
                            mime="text/csv",
                            use_container_width=True,
                        )
                else:
                    st.warning("CSV file not found.")

            with dl_col2:
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📥 Download PDF Report",
                            data=f.read(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            use_container_width=True,
                        )
                else:
                    st.warning("PDF file not found.")

            # Show summary stats
            total = result.get("total_leads", "?")
            avg_score = result.get("avg_score", "?")
            pct_email = result.get("pct_with_email", "?")
            pct_phone = result.get("pct_with_phone", "?")

            st.markdown("---")
            st.markdown("**Report summary:**")
            stat_cols = st.columns(4)
            stat_cols[0].metric("Total Leads", total)
            stat_cols[1].metric("Avg Score", avg_score)
            stat_cols[2].metric("Have Email", f"{pct_email}%")
            stat_cols[3].metric("Have Phone", f"{pct_phone}%")

        else:
            st.error("Could not retrieve job results.")

    except Exception as e:
        st.error(f"Error loading results: {e}")

    # Start new search
    st.markdown("---")
    if st.button("🔍 Start a new search", use_container_width=True):
        st.session_state.job_id = None
        st.session_state.job_status = None
        st.rerun()


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("Built with 🔍 by Scoutly — © 2026 · scoutly.sbs")