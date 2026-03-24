# Scoutly

**Find businesses. Score leads. Deliver insights.**

Scoutly is a pay-per-use SaaS tool that lets anyone in the world search for business leads by niche and location, automatically scores and enriches them using ML, and delivers a clean CSV + visual analytics report — all gated behind a simple payment flow.

---

## Table of contents

- [What it does](#what-it-does)
- [Who it is for](#who-it-is-for)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Environment variables](#environment-variables)
- [Running locally](#running-locally)
- [Deployment](#deployment)
- [Monetisation](#monetisation)
- [Scraper pipeline](#scraper-pipeline)
- [ML scoring layer](#ml-scoring-layer)
- [Report generation](#report-generation)
- [Email delivery](#email-delivery)
- [Job queue (Redis)](#job-queue-redis)
- [Payment flow](#payment-flow)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

A user visits Scoutly, enters:

- A **business type** (e.g. "dental clinics", "co-working spaces", "law firms")
- A **city and country** anywhere in the world
- How many leads they want (25 / 50 / 100 / 200)
- Which contact fields they need (email, phone, website, social)

Scoutly then:

1. Scrapes Google Maps for matching business listings
2. Visits each business website to hunt for publicly listed email addresses
3. Cleans, deduplicates, and scores every lead (0–100) using a rule-based ML model
4. Generates a visual PDF report with summary stats, score distribution, and top leads
5. Delivers the CSV + PDF to the user after a one-time payment via Lemon Squeezy
6. Optionally emails both files to the user via Resend

The entire flow is asynchronous — scraping runs in the background via a Redis job queue, and the user is notified when their report is ready.

---

## Who it is for

Scoutly is built for anyone who needs business contact lists fast, without paying for expensive CRM tools or doing manual research:

- **Sales reps** building outreach lists in new cities or verticals
- **Marketing agencies** sourcing clients in a niche
- **Freelancers** finding local businesses to pitch their services to
- **Founders** doing manual sales before hiring a sales team
- **Recruiters** identifying companies to approach in a new market

It works for any city in any country — Lagos, London, São Paulo, Dubai, Manila, Chicago, or anywhere Google Maps has listings.

---

## How it works

```
User fills form
      │
      ▼
Job queued in Redis (Upstash)
      │
      ▼
Background worker: Playwright scrapes Google Maps
      │
      ▼
Email hunter: visits each website, extracts emails via regex
      │
      ▼
Pandas pipeline: cleans, dedupes, filters by user requirements
      │
      ▼
ML scorer: assigns 0–100 score to each lead
      │
      ▼
Report generator: produces CSV + PDF with charts
      │
      ▼
Payment gate: Lemon Squeezy checkout
      │
      ▼
Delivery: download link in browser + optional Resend email
```

---

## Tech stack

| Layer | Tool | Why |
|---|---|---|
| Frontend + UI | Streamlit | Fastest path to a working Python web UI with no separate frontend needed |
| Scraper | Playwright (Chromium) | Handles JavaScript-rendered pages like Google Maps that BeautifulSoup cannot |
| HTTP client | httpx | Async-friendly, used for visiting business websites to hunt emails |
| Data processing | Pandas | Cleaning, deduplication, filtering, and feature engineering |
| ML scoring | Scikit-learn (v1), rule-based | Simple weighted scorer for v1; upgradeable to a trained model later |
| Job queue | Redis via Upstash | Manages async scrape jobs so the UI doesn't block during long scrapes |
| Email delivery | Resend | Transactional email delivery of CSV + PDF report to the user |
| Payments | Lemon Squeezy | Global payment processor that works without Stripe, handles VAT automatically |
| Report generation | Matplotlib + ReportLab | Charts rendered with Matplotlib, assembled into PDF with ReportLab |
| Deployment | Railway | Simple deployment with environment variable management and free-tier start |
| Language | Python 3.11+ | Entire stack is Python — no context switching |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Scoutly app                          │
│                                                             │
│  ┌─────────────────────────┐   ┌───────────────────────┐   │
│  │       Frontend          │   │       Backend         │   │
│  │  (Streamlit)            │   │  (Python workers)     │   │
│  │                         │   │                       │   │
│  │  • Input form           │   │  • Playwright scraper │   │
│  │  • Job status polling   │   │  • httpx email hunter │   │
│  │  • Payment checkout     │   │  • Pandas cleaner     │   │
│  │  • Report preview       │──▶│  • ML scorer          │   │
│  │  • CSV/PDF download     │   │  • Chart generator    │   │
│  │                         │   │  • PDF builder        │   │
│  └─────────────────────────┘   └───────────┬───────────┘   │
│                                            │               │
└────────────────────────────────────────────┼───────────────┘
                                             │
              ┌──────────────────────────────┼──────────────┐
              │                             │              │
              ▼                             ▼              ▼
       Upstash Redis                  Lemon Squeezy      Resend
       (job queue)                    (payments)         (email)
```

### Key design decisions

**Why Streamlit for v1?**
Streamlit lets you build a complete web UI in pure Python with no HTML/CSS/JS. For a solo founder, this means you ship faster and iterate faster. The tradeoff is limited UI customisation — acceptable for v1, upgradeable to Flask + React later once you have paying users.

**Why async jobs via Redis?**
Scraping 50 leads takes 2–4 minutes. A synchronous approach would leave the user staring at a frozen browser tab. With Redis, the job is queued immediately, the UI shows a live progress bar (polling every 3 seconds), and the user can close the tab and wait for the email.

**Why Lemon Squeezy instead of Stripe?**
Stripe is not available as a direct payment processor in Nigeria. Lemon Squeezy acts as a Merchant of Record — they handle global card payments, VAT, and payouts. You receive the revenue without needing a US/EU entity.

---

## Project structure

```
scoutly/
├── app.py                   # Streamlit entry point
├── worker.py                # Background job worker (runs separately)
├── requirements.txt
├── .env.example
│
├── scraper/
│   ├── __init__.py
│   ├── maps.py              # Playwright Google Maps scraper
│   ├── email_hunter.py      # httpx + regex email extractor
│   └── cleaner.py           # Pandas cleaning and dedup pipeline
│
├── ml/
│   ├── __init__.py
│   └── scorer.py            # Lead scoring model (rule-based v1)
│
├── report/
│   ├── __init__.py
│   ├── charts.py            # Matplotlib chart generators
│   └── pdf_builder.py       # ReportLab PDF assembly
│
├── queue/
│   ├── __init__.py
│   ├── producer.py          # Enqueue scrape jobs
│   └── consumer.py          # Process jobs from queue
│
├── email/
│   ├── __init__.py
│   └── sender.py            # Resend email delivery
│
├── payments/
│   ├── __init__.py
│   └── lemon.py             # Lemon Squeezy checkout + webhook handler
│
└── utils/
    ├── __init__.py
    └── helpers.py           # Shared utilities
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in all values before running locally.

```env
# Redis (Upstash)
UPSTASH_REDIS_URL=rediss://your-upstash-url
UPSTASH_REDIS_TOKEN=your-upstash-token

# Resend (email delivery)
RESEND_API_KEY=re_xxxxxxxxxxxx
RESEND_FROM_EMAIL=reports@yourdomain.com

# Lemon Squeezy (payments)
LEMONSQUEEZY_API_KEY=your-api-key
LEMONSQUEEZY_STORE_ID=your-store-id
LEMONSQUEEZY_VARIANT_25=variant-id-for-25-leads
LEMONSQUEEZY_VARIANT_50=variant-id-for-50-leads
LEMONSQUEEZY_VARIANT_100=variant-id-for-100-leads
LEMONSQUEEZY_VARIANT_200=variant-id-for-200-leads
LEMONSQUEEZY_WEBHOOK_SECRET=your-webhook-secret

# App config
APP_ENV=development           # development | production
MAX_CONCURRENT_JOBS=2         # how many scrape jobs run in parallel
SCRAPE_DELAY_MIN=0.5          # min seconds between requests
SCRAPE_DELAY_MAX=1.5          # max seconds between requests
REPORT_OUTPUT_DIR=./outputs   # where CSVs and PDFs are saved
```

---

## Running locally

### Prerequisites

- Python 3.11+
- A free [Upstash](https://upstash.com) Redis account
- A free [Resend](https://resend.com) account
- A [Lemon Squeezy](https://lemonsqueezy.com) account (free to set up, takes a cut on sales)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/scoutly.git
cd scoutly

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Copy and fill in environment variables
cp .env.example .env

# 6. Run the background worker (in a separate terminal)
python worker.py

# 7. Run the Streamlit app
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Requirements

```
streamlit>=1.35
playwright>=1.44
httpx>=0.27
pandas>=2.2
scikit-learn>=1.5
matplotlib>=3.9
reportlab>=4.2
redis>=5.0
resend>=2.0
python-dotenv>=1.0
```

---

## Deployment

Scoutly runs as two processes — the Streamlit web app and the Redis worker. Both need to be running for the product to work.

### Railway (recommended for v1)

1. Push your code to GitHub
2. Create a new project on [Railway](https://railway.app)
3. Add two services from the same repo:
   - **Web**: start command `streamlit run app.py --server.port $PORT`
   - **Worker**: start command `python worker.py`
4. Add all environment variables from your `.env` to Railway's variable manager
5. Deploy — Railway will build and run both services automatically

Railway's free tier is sufficient to start. Upgrade as traffic grows.

---

## Monetisation

Scoutly uses a **pay-per-report** model. There are no subscriptions — users pay once per report generated.

| Report size | Price | Margin notes |
|---|---|---|
| 25 leads | $3 | Good entry point for testing |
| 50 leads | $5 | Most popular tier |
| 100 leads | $8 | Best value per lead |
| 200 leads | $14 | Power users and agencies |

Payments are processed by Lemon Squeezy. On each successful payment, their webhook triggers delivery of the report files to the user. Scoutly never charges a user before the report is ready.

### Free preview

Every user gets a free preview of the top 5 leads (name + address only, no contact info) before being asked to pay. This removes friction and lets the data sell itself.

## Scraper pipeline

The scraper runs as a background job triggered by the Redis queue. It has four stages:

### Stage 1 — Query construction

```python
query = f"{niche} in {city}, {country}"
# "dental clinics in Manchester, United Kingdom"
```

### Stage 2 — Google Maps scraping (Playwright)

Playwright launches a headless Chromium browser, searches Google Maps, and scrolls the results panel repeatedly to load all listings. It collects: business name, Google Maps URL, rating, review count, address, phone number (where shown), and website URL.

The scraper always collects `n * 1.6` raw listings (e.g. 80 for a 50-lead order) to account for leads that will be dropped in the cleaning step.

### Stage 3 — Email hunting (httpx)

For each listing that has a website URL, `httpx` fetches the homepage (and optionally the `/contact` page) and runs a regex pattern over the HTML to extract email addresses. Common false positives (image filenames, CSS files, JavaScript files) are filtered out.

This step runs with configurable delays between requests to avoid triggering rate limits or bot detection on business websites.

### Stage 4 — Cleaning (Pandas)

- Remove duplicate entries (matched on name + address)
- Standardise phone number formats
- Strip whitespace and encoding artifacts from all text fields
- Drop rows missing required fields (based on user's checkbox selections)
- Validate email format with a stricter secondary regex

---

## ML scoring layer

Every lead receives a score from 0 to 100. In v1 this is a weighted rule-based model. The weights are designed to reflect lead quality from a B2B sales perspective.

| Feature | Weight | Rationale |
|---|---|---|
| Has email address | +25 | Most important for outreach |
| Has phone number | +20 | Direct contact available |
| Has website | +15 | Signals an established business |
| Google rating ≥ 4.0 | +15 | Proxy for business quality |
| Review count ≥ 10 | +10 | Proxy for business activity |
| Has social media link | +10 | Signals digital presence |
| Address completeness | +5 | Full address = real business |

**Planned v2:** Once Scoutly has enough usage data (user feedback on whether leads converted), the rule-based scorer will be replaced by a trained Scikit-learn classifier using those labels as the target variable.

---

## Report generation

Every paid report includes two files:

### CSV

A clean spreadsheet with one row per lead, columns for: name, address, phone, email, website, social media, Google rating, review count, and ML score. Sorted by score descending.

### PDF report

A single-page visual summary including:

- **Header**: query string, date generated, total leads found
- **Summary stats**: total leads, % with email, % with phone, average rating, average score
- **Score distribution chart**: histogram of lead scores across the list
- **Rating vs score scatter**: shows correlation between Google rating and ML score
- **Top 10 leads table**: the highest-scoring leads with all contact fields
- **Data quality bar**: visual breakdown of what contact fields were found

Charts are generated with Matplotlib and assembled into a PDF using ReportLab.

---

## Email delivery

Scoutly uses Resend to deliver the CSV and PDF to the user's email address after payment is confirmed.

The email contains:
- A short summary of the report (total leads, average score)
- The CSV attached directly
- The PDF attached directly
- A link back to Scoutly

Resend's free tier allows 3,000 emails/month — more than enough to start. The `RESEND_FROM_EMAIL` must be a verified domain in your Resend account.

Email delivery is optional — users can choose to only download in the browser. But offering email delivery is important because scrape jobs take 2–4 minutes and users may close the tab.

---

## Job queue (Redis)

Scoutly uses Upstash Redis as a lightweight job queue. This keeps the Streamlit UI responsive during long scrape operations.

### Flow

```
1. User submits form
        ↓
2. producer.py pushes job to Redis list "scoutly:jobs"
   Job payload: { job_id, niche, city, country, count, filters, email }
        ↓
3. UI polls Redis key "scoutly:status:{job_id}" every 3 seconds
   Possible statuses: queued → scraping → enriching → scoring → building_report → done | failed
        ↓
4. worker.py pops job from queue, runs full pipeline, updates status key at each stage
        ↓
5. On "done": output file paths stored in Redis, UI shows payment button
```

### Job status keys

```
scoutly:jobs              → LIST of pending job payloads
scoutly:status:{job_id}   → STRING: current status
scoutly:result:{job_id}   → HASH: csv_path, pdf_path, summary stats
scoutly:preview:{job_id}  → STRING: JSON of top 5 leads (shown free)
```

All job keys expire after 24 hours via Redis TTL.

---

## Payment flow

Scoutly uses Lemon Squeezy's hosted checkout. Each report size maps to a Lemon Squeezy product variant.

```
1. Report is ready (status = "done")
        ↓
2. UI shows free preview (top 5 leads, name + address only)
        ↓
3. User clicks "Unlock full report — $5"
        ↓
4. Scoutly creates a Lemon Squeezy checkout URL with the job_id
   embedded as a custom parameter
        ↓
5. User completes payment on Lemon Squeezy hosted checkout
        ↓
6. Lemon Squeezy sends webhook to /api/webhook/lemonsqueezy
        ↓
7. Webhook handler verifies signature, extracts job_id,
   marks report as paid in Redis
        ↓
8. UI detects "paid" status, shows download buttons for CSV + PDF
        ↓
9. If user provided email: Resend delivers both files
```

The webhook endpoint must be publicly accessible. On Railway, this is handled automatically. For local development, use [ngrok](https://ngrok.com) to expose your local server.

---

## Roadmap

### v1 — MVP (build now)
- [x] Input form (niche, city, country, count, filters, email)
- [ ] Playwright Google Maps scraper
- [ ] httpx email hunter
- [ ] Pandas cleaning pipeline
- [ ] Rule-based ML scorer
- [ ] Matplotlib + ReportLab report generator
- [ ] Upstash Redis job queue
- [ ] Streamlit UI with job status polling
- [ ] Lemon Squeezy payment gate
- [ ] Resend email delivery
- [ ] Railway deployment

### v2 — Growth features
- [ ] User accounts (save past reports, reorder)
- [ ] Trained ML scorer using conversion feedback
- [ ] LinkedIn enrichment (add LinkedIn URLs to leads)
- [ ] Bulk orders (upload a list of cities, get reports for all)
- [ ] API access (pay per API call, target developers)
- [ ] Webhook delivery (POST report data to the user's own system)

### v3 — Scale
- [ ] Proxy rotation for high-volume scraping
- [ ] Custom scoring criteria (user defines what makes a good lead)
- [ ] CRM integrations (push leads directly to HubSpot, Pipedrive, etc.)
- [ ] White-label option (agencies resell under their own brand)

---

## Contributing

Scoutly is a solo project for now. If you find a bug or have a suggestion, open an issue on GitHub. Pull requests welcome once the v1 milestone is complete.

---

## License

This project is licensed under the terms in the [LICENSE](LICENSE) file.

---

*Built by a Data Science student who got tired of empty Upwork inboxes.*
