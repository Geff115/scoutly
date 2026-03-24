"""
Scoutly — Streamlit app entry point.

This is the main user-facing interface. It handles:
    1. Input form (niche, city, country, lead count, filters, email)
    2. Job submission → Redis queue
    3. Live progress polling
    4. Free preview (top 5 leads)
    5. Payment gate (Lemon Squeezy checkout redirect)
    6. Download buttons for CSV + PDF after payment
"""

import streamlit as st
import time
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
            index=1,  # Default to 50
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
        # Validate inputs
        if not niche or not city or not country:
            st.error("Please fill in the business type, city, and country.")
        else:
            # TODO: Phase 4 — call enqueue_job() and store job_id in session state
            st.info("⏳ Job queued! Scraping will begin shortly…")
            st.session_state.job_id = "demo_placeholder"
            st.session_state.job_status = JobStatus.QUEUED


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
        JobStatus.QUEUED: ("Waiting in queue…", 0.0),
        JobStatus.SCRAPING: ("Scraping Google Maps…", 0.25),
        JobStatus.ENRICHING: ("Hunting for email addresses…", 0.50),
        JobStatus.SCORING: ("Scoring leads…", 0.70),
        JobStatus.BUILDING_REPORT: ("Building your report…", 0.90),
    }

    current = st.session_state.job_status
    label, progress = status_labels.get(current, ("Working…", 0.5))

    st.progress(progress, text=label)

    # TODO: Phase 4 — replace with actual Redis polling
    # time.sleep(3)
    # st.session_state.job_status = poll_job_status(st.session_state.job_id)
    # st.rerun()


# ---------------------------------------------------------------------------
# Free preview + payment gate
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.DONE:
    st.markdown("---")
    st.subheader("✅ Your leads are ready!")

    # TODO: Phase 4 — fetch preview data from Redis
    st.markdown("**Free preview — top 5 leads (name + address only):**")
    st.info("Preview data will appear here once the pipeline is wired up.")

    st.markdown("---")

    # Payment button
    price = PRICING.get(lead_count, 5.00)
    st.markdown(f"### Unlock the full report — ${price:.0f}")
    st.markdown(
        f"Get all {lead_count} leads with emails, phone numbers, "
        "scores, and a visual PDF report."
    )

    if st.button(f"💳 Pay ${price:.0f} and download", use_container_width=True):
        # TODO: Phase 5 — create Lemon Squeezy checkout URL and redirect
        st.warning("Payment integration coming in Phase 5.")


# ---------------------------------------------------------------------------
# Download section (post-payment)
# ---------------------------------------------------------------------------
if st.session_state.job_status == JobStatus.PAID:
    st.markdown("---")
    st.subheader("🎉 Report unlocked!")
    st.success("Thank you for your purchase. Your files are ready.")

    dl_col1, dl_col2 = st.columns(2)

    with dl_col1:
        # TODO: Phase 5 — wire up actual file paths from Redis
        st.download_button(
            "📥 Download CSV",
            data="placeholder",
            file_name="scoutly_leads.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with dl_col2:
        st.download_button(
            "📥 Download PDF Report",
            data="placeholder",
            file_name="scoutly_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption("Built with 🔍 by Scoutly — © 2026")
