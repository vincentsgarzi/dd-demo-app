# Datadog Marketplace — Demo App

A full-stack e-commerce app that sells Datadog products. Built specifically to demonstrate Datadog's observability platform end-to-end — the app is fully instrumented and contains deliberate bugs and performance issues to make every feature meaningful to show.

---

## Why This Exists

The dedicated Datadog demo org is great for standard demos, but it's a shared environment — you can't customize it, break things intentionally, or tailor the data story to a specific prospect.

This app exists to change that.

Every SE has a **sandbox account** with full admin access. This repo lets you spin up a complete, realistic demo environment inside your own sandbox — fully instrumented, fully under your control. You can:

- **Customize the data** — seed products, users, and orders that match your prospect's industry
- **Tune the bugs** — enable or disable specific issues depending on which Datadog features you're demoing
- **Own the narrative** — because it's your sandbox, you control what the dashboards show and when
- **Experiment freely** — break things, fix things, try new configurations without affecting anyone else

The goal is a demo that feels like *their* environment, not a generic sandbox.

---

## Architecture

```
┌─────────────────┐
│  React Frontend  │  (Vite :5173)
│  DD RUM + Replay │
└────────┬────────┘
         ▼
┌─────────────────┐
│  API Gateway     │  ddstore-gateway (:8080)
└──┬─────┬─────┬──┘
   │     │     │
   ▼     ▼     ▼
┌──────┐ ┌──────┐ ┌──────────┐
│Prod- │ │Order │ │Analytics │
│ucts  │ │Svc   │ │Service   │
│:8081 │ │:8082 │ │:8083     │
└──┬───┘ └──┬───┘ └────┬─────┘
   │     ▲  │          │
   │     │  │          │
   │     └──┼──────────┘  (orders→products, analytics→orders+products)
   │        │
   ▼        ▼
┌─────────────────┐
│  PostgreSQL 16   │  (DBM enabled)
└─────────────────┘
```

The backend is split into **4 microservices** — each with its own `DD_SERVICE` tag, creating a rich service map with distributed traces that cross service boundaries.

| Service | Port | DD_SERVICE | Responsibility |
|---------|------|------------|----------------|
| **API Gateway** | 8080 | `ddstore-gateway` | Routes all requests to downstream services |
| **Product Service** | 8081 | `ddstore-products` | Products, categories, search, recommendations |
| **Order Service** | 8082 | `ddstore-orders` | Cart, checkout, order history |
| **Analytics Service** | 8083 | `ddstore-analytics` | Stats dashboard, compute, memory leak worker |

**Cross-service calls** (visible as multi-service flamegraphs in APM):
- Checkout: `orders → products` (validates each cart item)
- Stats: `analytics → orders + products` (aggregates data across services)

---

## What's Inside

| Layer | Tech |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | 4 Python Flask microservices + SQLAlchemy |
| Database | PostgreSQL (shared, DBM enabled) |
| APM | ddtrace (auto-instrumented across all services) |
| RUM | @datadog/browser-rum + React plugin |
| Logs | Structured JSON logs + browser-logs |
| Metrics | DogStatsD custom metrics |
| Profiling | DD Continuous Profiler (enabled via env) |

---

## Datadog Features Demonstrated

- **APM & Distributed Tracing** — every request traced across multiple services; service map shows gateway → {products, orders, analytics} → postgres
- **Database Monitoring** — slow queries, explain plans, `pg_stat_statements` enabled
- **RUM + Session Replay** — 100% session capture, React component tracking, frontend errors
- **Log Management** — structured JSON logs correlated to traces via `dd.trace_id`
- **Error Tracking** — backend exceptions + frontend JS errors grouped automatically, attributed to the correct service
- **Continuous Profiler** — CPU and memory profiles from each Flask process
- **Custom Metrics** — `ddstore.*` namespace via DogStatsD (request count, revenue, errors)

---

## Intentional Bugs (for demo)

| Bug | Service | Endpoint | What Datadog catches |
|---|---|---|---|
| N+1 query | `ddstore-products` | `GET /api/products` | APM shows N duplicate DB spans per request |
| `NoneType` AttributeError | `ddstore-products` | `GET /api/products` | Error Tracking groups repeated exceptions |
| `ZeroDivisionError` | `ddstore-products` | `GET /api/products/3` | Unhandled exception with full stack trace in APM |
| Slow unindexed LIKE query | `ddstore-products` | `GET /api/search` | DBM flags full table scan, high latency in APM |
| Artificial delay (1–3s) | `ddstore-products` | `GET /api/recommendations` | APM p99 latency spike, visible in service map |
| Random 15% checkout failures | `ddstore-orders` | `POST /api/checkout` | Error rate monitor, retry storm in multi-service trace |
| Memory leak | `ddstore-analytics` | Background thread | Continuous Profiler heap growth over time |
| CPU spike | `ddstore-analytics` | `GET /api/compute` | Profiler CPU flame graph, APM slow span |
| Python-side aggregation | `ddstore-analytics` | `GET /api/stats` | Full table loaded into memory instead of SQL SUM |

---

## Setup

### Before you start — grab two things manually

These require logging into Datadog and cannot be automated:

1. **RUM Application ID + Client Token**
   - Go to **Datadog > Digital Experience > RUM > New Application**
   - Select React, name it `ddstore`, click Create
   - Copy the `applicationId` and `clientToken` from the snippet shown

2. **A Datadog Agent** must be running on your machine (port `8126` / `8125`)
   - If you don't have one: https://docs.datadoghq.com/agent/

That's it. Everything else is handled by Claude.

---

### Spin up with Claude

Clone the repo, open it in Claude Code, and paste this prompt:

```
I just cloned the dd-demo-app repo. Please set it up end-to-end on my machine:

1. Install PostgreSQL via Homebrew if not already installed, start it, and create
   the ddstore database and ddstore_app user with pg_stat_statements enabled
2. Create backend/.env from backend/.env.example — fill in the DATABASE_URL
3. Create frontend/.env from frontend/.env.example — I'll give you my RUM credentials:
     VITE_DD_APP_ID=<paste your App ID here>
     VITE_DD_CLIENT_TOKEN=<paste your Client Token here>
4. Set up the Python virtualenv, install dependencies, and seed the database
5. Start the app (./start.sh) and confirm both services are healthy
6. Start the load generator in the background so Datadog has data immediately
```

Claude will handle every step, ask if anything is unclear, and confirm when the app is live.

---

## Project Structure

```
dd-demo-app/
├── backend/
│   ├── gateway/app.py      # API Gateway — thin proxy, routes to services
│   ├── products/app.py     # Product Service — catalog, search, recommendations
│   ├── orders/app.py       # Order Service — cart, checkout, order history
│   ├── analytics/app.py    # Analytics Service — stats, compute, memory leak
│   ├── shared/models.py    # SQLAlchemy models (shared across services)
│   ├── app.py              # Original monolith (kept for seed.py)
│   ├── models.py           # Original models (kept for seed.py)
│   ├── seed.py             # Database seeder
│   ├── requirements.txt
│   ├── .env.example        # ← template, never committed
│   └── .env                # ← your local values, gitignored
├── frontend/
│   ├── src/
│   │   ├── datadog.js      # RUM + Logs init (reads from .env)
│   │   ├── App.jsx
│   │   ├── pages/
│   │   └── components/
│   ├── .env.example        # ← template, never committed
│   └── .env                # ← your local values, gitignored
├── loadgen/
│   ├── loadgen.py          # Backend API traffic generator
│   └── rum_loadgen.py      # Playwright headless browser RUM generator
├── start.sh                # Starts all 4 microservices + frontend
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (shared by all services) |
| `DD_ENV` | Environment tag (`demo`) — set in `start.sh` |
| `DD_VERSION` | Version tag — set in `start.sh` |
| `DD_LOGS_INJECTION` | Injects trace IDs into log lines |
| `DD_RUNTIME_METRICS_ENABLED` | Enables runtime metrics (GC, heap, threads) |
| `DD_PROFILING_ENABLED` | Enables Continuous Profiler |

`DD_SERVICE` is set per-process in `start.sh`: `ddstore-gateway`, `ddstore-products`, `ddstore-orders`, `ddstore-analytics`.

### Frontend (`frontend/.env`)
| Variable | Description |
|---|---|
| `VITE_DD_APP_ID` | RUM Application ID (from Datadog UI) |
| `VITE_DD_CLIENT_TOKEN` | RUM Client Token (from Datadog UI) |
| `VITE_DD_SITE` | Datadog site (`datadoghq.com`) |
| `VITE_DD_SERVICE` | Frontend service name |
| `VITE_DD_ENV` | Environment tag |
| `VITE_DD_VERSION` | Version tag |
