# AureoStays — Full-Stack Villa Booking Platform with Live ETL Pipeline

A production-grade villa booking platform built as a **data engineering portfolio project**. Every guest interaction like browsing properties, selecting dates, entering details, confirming a booking flows through a real ETL pipeline into a structured PostgreSQL database that is queryable in real time.

**Live Site**: [villa-frontend.vercel.app](https://villa-frontend.vercel.app)  
**Live API**: [villa-api-production-f7b1.up.railway.app/docs](https://villa-api-production-f7b1.up.railway.app/docs)

---

## What This Project Demonstrates

Most data engineering portfolios show pipelines built on CSV files and Jupyter notebooks. This project demonstrates a **real, end-to-end ETL pipeline** where:

- A guest visits the live website, selects a villa, picks dates, and books
- That interaction creates clean, structured records across 4 PostgreSQL tables
- The guest instantly receives a **branded HTML confirmation email** with full booking details
- The data is immediately queryable via SQL — revenue, occupancy, guest analytics
- The pipeline handles edge cases: double-booking prevention, atomic transactions, price snapshotting

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        GUEST                                │
│              villa-frontend.vercel.app                      │
│         Next.js 15 + Tailwind CSS + TypeScript              │
└─────────────────────┬───────────────────────────────────────┘
                      │  HTTPS POST /bookings/
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      BACKEND API                            │
│        villa-api-production-f7b1.up.railway.app             │
│              FastAPI (Python 3.13)                          │
│                                                             │
│  • Validates availability (inventory table)                 │
│  • Upserts guest record                                     │
│  • Creates booking with atomic transaction                  │
│  • Blocks inventory dates                                   │
│  • Sends HTML confirmation email via Resend                 │
└──────────┬──────────────────────────┬───────────────────────┘
           │  PostgreSQL (asyncpg)    │  Resend API
           ▼                          ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│      DATABASE       │   │         GUEST'S INBOX            │
│  Supabase (PG 15)   │   │   Branded HTML email with:       │
│                     │   │   • Booking reference            │
│  properties         │   │   • Property & location          │
│  inventory          │   │   • Check-in / Check-out dates   │
│  guests             │   │   • Total amount in ₹            │
│  bookings           │   │   • Special requests             │
└─────────┬───────────┘   └──────────────────────────────────┘
          │  SQL queries
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ANALYTICS                                │
│                  Metabase / Redash                          │
│                                                             │
│  • Revenue per property                                     │
│  • Occupancy rates                                          │
│  • Guest analytics                                          │
│  • Bookings over time                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 15, Tailwind CSS, TypeScript | Deployed on Vercel |
| Backend | FastAPI, Python 3.13, Pydantic v2 | Deployed on Railway |
| Database | PostgreSQL 15, asyncpg | Hosted on Supabase |
| Email | Resend | Transactional HTML emails |
| Analytics | Metabase | Connected to live Supabase DB |

---

## Confirmation Email

Every confirmed booking automatically triggers a branded HTML email to the guest containing:

- AureoStays branding with dark/amber theme
- Unique booking reference in a highlighted box
- Full booking details — property, location, check-in, check-out, duration, guests, special requests
- Total amount in Indian Rupees
- Check-in instructions note

Built with **Resend** — fires automatically after every successful booking transaction.

> Note: Currently using Resend's sandbox mode which delivers to the registered address only. Production deployment would use a verified custom domain to send to all guests.

---

## Database Schema

Four tables form the core of the ETL pipeline:

**`properties`** — One row per villa. Stores name, slug, location, bedrooms, bathrooms, max guests, price per night, amenities array, photos array, and pet-friendly flag.

**`inventory`** — One row per property per date. 273 rows auto-generated at seed time (3 properties × 91 days). When a booking is confirmed, the API flips `is_available = FALSE` for those dates. This is what enables availability checking and prevents double-booking.

**`guests`** — One row per unique guest identified by email. The `UNIQUE(email)` constraint means repeat guests reuse their record — one guest, many bookings.

**`bookings`** — The core transactional table. Contains three auto-computed columns — `total_guests`, `num_nights`, and `total_amount` — calculated by Postgres automatically. The `price_per_night` is snapshotted at the time of booking so revenue reports always reflect what the guest actually paid, even if prices change later.

```sql
-- Key design decisions

-- Generated columns — Postgres computes these automatically
total_guests  INT GENERATED ALWAYS AS (num_adults + num_kids) STORED,
num_nights    INT GENERATED ALWAYS AS (checkout_date - checkin_date) STORED,
total_amount  NUMERIC GENERATED ALWAYS AS ((checkout_date - checkin_date) * price_per_night) STORED,

-- Price snapshot — revenue reports are always accurate
price_per_night NUMERIC(10, 2) NOT NULL,  -- captured at booking time

-- Prevents double-booking at the database level
UNIQUE (property_id, date)  -- on inventory table
```

---

## The ETL Pipeline in Detail

When a guest clicks **Confirm Booking**, a single API call triggers this sequence:

```
1.  Validate property slug exists
2.  Check guest count ≤ property max_guests
3.  Query inventory → confirm all dates are available
4.  Upsert guest record (INSERT ... ON CONFLICT DO UPDATE)
5.  Generate booking reference (BK-YYYYMMDD-XXXX)
6.  INSERT booking row with snapshotted price
7.  UPDATE inventory → set is_available = FALSE for all booked dates
8.  COMMIT — steps 4–7 are one atomic transaction
9.  Send branded HTML confirmation email via Resend

If any step from 4–7 fails → ROLLBACK (no partial writes, no orphaned records)
Email failure (step 9) never affects the booking — it is non-blocking
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/properties` | List all active villas |
| GET | `/properties/{slug}` | Get one villa's details |
| GET | `/properties/{slug}/availability` | Check date availability |
| POST | `/bookings/` | Create a booking (full ETL + email) |
| GET | `/bookings` | Admin — all bookings with guest & property data |

Full interactive docs: [villa-api-production-f7b1.up.railway.app/docs](https://villa-api-production-f7b1.up.railway.app/docs)

---

## Analytics Queries

These SQL queries run against the live database in Metabase:

```sql
-- All bookings with guest and property details
SELECT
    b.booking_ref,
    p.name AS property_name,
    p.location,
    g.full_name AS guest_name,
    g.email,
    g.phone,
    b.checkin_date,
    b.checkout_date,
    b.num_nights,
    b.total_amount,
    b.status,
    b.created_at
FROM bookings b
JOIN properties p ON b.property_id = p.id
JOIN guests g ON b.guest_id = g.id
ORDER BY b.created_at DESC;

-- Revenue per property
SELECT
    p.name AS property_name,
    COUNT(b.id) AS total_bookings,
    SUM(b.total_amount) AS total_revenue,
    ROUND(AVG(b.total_amount), 2) AS avg_booking_value
FROM bookings b
JOIN properties p ON b.property_id = p.id
WHERE b.status = 'confirmed'
GROUP BY p.name
ORDER BY total_revenue DESC;

-- Occupancy rate per property (booked days out of 90)
SELECT
    p.name AS property_name,
    COUNT(*) AS total_days,
    SUM(CASE WHEN i.is_available = FALSE THEN 1 ELSE 0 END) AS booked_days,
    ROUND(
        SUM(CASE WHEN i.is_available = FALSE THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
    ) AS occupancy_pct
FROM inventory i
JOIN properties p ON i.property_id = p.id
GROUP BY p.name
ORDER BY occupancy_pct DESC;
```

---

## Running Locally

**Prerequisites:** Python 3.10+, Node.js 18+, a Supabase project, a Resend account

**Backend:**
```bash
git clone https://github.com/s-keshri/villa-api.git
cd villa-api
pip install -r requirements.txt
cp .env.example .env
# Add your Supabase connection string and Resend API key to .env
uvicorn app.main:app --reload
# API running at http://localhost:8000
```

**Frontend:**
```bash
git clone https://github.com/s-keshri/villa-frontend.git
cd villa-frontend
npm install
# Update const API in app/page.tsx to http://localhost:8000
npm run dev
# Site running at http://localhost:3000
```

**Database:**
Run `schema.sql` in your Supabase SQL Editor. This creates all 4 tables, indexes, triggers, seeds 3 properties, and generates 273 inventory rows.

---

## Project Structure

```
villa-api/
├── app/
│   ├── main.py           # FastAPI app, CORS config
│   ├── database.py       # asyncpg connection pool
│   └── routers/
│       ├── properties.py # GET /properties endpoints
│       └── bookings.py   # POST /bookings/ — ETL core + email
├── Procfile              # Railway start command
├── requirements.txt
└── .env.example

villa-frontend/
├── app/
│   ├── page.tsx                     # Listing page
│   └── properties/[slug]/
│       ├── page.tsx                 # Detail page
│       └── BookingWidget.tsx        # Date picker + guest form + API call
└── ...
```

---

## Key Engineering Decisions

**Why raw SQL over an ORM?** Direct asyncpg queries give full control over transactions. ORMs abstract away the exact SQL that runs — for a data engineering project, that's the wrong tradeoff.

**Why snapshot price at booking time?** Revenue queries need to reflect what guests actually paid. If a villa's price changes next week, historical bookings should not be affected.

**Why a separate inventory table?** A naive approach would check bookings to determine availability. The inventory table makes availability a simple `is_available = TRUE/FALSE` lookup and enables features like maintenance blocks and owner holds without touching the bookings table.

**Why generated columns?** `num_nights`, `total_guests`, and `total_amount` are always consistent because Postgres computes them — not the application layer. Metabase queries never need to recalculate them.

**Why is email non-blocking?** The confirmation email fires after the transaction commits. If Resend is down, the booking still succeeds — the guest's data is safe. Email delivery is a notification layer, not part of the core transaction.

---

## What's Next

- Deploy Metabase to Render for a publicly shareable analytics dashboard
- Add a `/dashboard` page to the frontend showing live booking analytics
- Migrate API from Railway to Render when trial ends (free forever)
- Verify a custom domain on Resend to send confirmation emails to all guests
- Add more properties and real villa photos

---

*Built by Shivam Keshri as a data engineering portfolio project — April 2026*
