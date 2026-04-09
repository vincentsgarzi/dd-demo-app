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
- **Database Monitoring** — slow queries, explain plans, `pg_stat_statements` enabled, APM↔DBM correlation
- **RUM + Session Replay** — 100% session capture, React component tracking, frontend errors
- **Log Management** — structured JSON logs correlated to traces via `dd.trace_id`
- **Error Tracking** — backend exceptions + frontend JS errors grouped automatically, attributed to the correct service
- **Continuous Profiler** — CPU and memory profiles from each Flask process
- **Custom Metrics** — `ddstore.*` namespace via DogStatsD (request count, revenue, errors)

---

## Intentional Bugs (for demo)

### Backend Errors

| Bug | Service | Endpoint | What It Looks Like |
|---|---|---|---|
| N+1 query | `ddstore-products` | `GET /api/products` | APM shows N duplicate DB spans per request |
| NULL description | `ddstore-products` | `GET /api/products` | AttributeError grouped in Error Tracking |
| Stale CDN cache | `ddstore-products` | `GET /api/products/{id}` | `KeyError` — schema v2.8 vs v3.2 mismatch, edge node ignoring cache headers |
| Feature flag crash | `ddstore-products` | `GET /api/products/{id}` | `RuntimeError` — archived experiment variant pool, 1,247 products affected |
| Elasticsearch circuit breaker | `ddstore-products` | `GET /api/search` | `ConnectionError` — heap at 89%, 47 in-flight queries, specific shard + node |
| SageMaker model timeout | `ddstore-products` | `GET /api/recommendations` | `TimeoutError` — auto-scaling cold start, Redis fallback expired, 2,300 users affected |
| Slow recommendations (1–3s) | `ddstore-products` | `GET /api/recommendations` | APM p99 latency spike, visible in service map |
| PCI vault cert expiry | `ddstore-orders` | `POST /api/checkout` | `ConnectionError` — TLS handshake failure, cert auto-renewal broken by infra migration |
| Idempotency conflict | `ddstore-orders` | `POST /api/checkout` | `ValueError` — cart modified between payment attempts, duplicate charge prevented |
| Fraud detection block | `ddstore-orders` | `POST /api/checkout` | `PermissionError` — ML risk score 0.92, new email domain, case # generated |
| Stripe API timeout | `ddstore-orders` | `POST /api/checkout` | `TimeoutError` — circuit breaker OPEN, 23/25 failures, retry budget exhausted |
| Distributed lock contention | `ddstore-orders` | `POST /api/checkout` | `TimeoutError` — Redis lock held 15s, 25 waiters, possible primary failover |
| No stock validation | `ddstore-orders` | `POST /api/checkout` | Oversold products — stock goes negative, logged as business error |
| Data pipeline staleness | `ddstore-analytics` | `GET /api/stats` | `RuntimeError` — Kafka consumer lag 500K messages, stale dashboards |
| Memory leak | `ddstore-analytics` | Background thread | Continuous Profiler heap growth over time |
| CPU spike | `ddstore-analytics` | `GET /api/compute` | Profiler CPU flame graph, APM slow span |
| Python-side aggregation | `ddstore-analytics` | `GET /api/stats` | Full table loaded into memory instead of SQL SUM |
| Rate limit exceeded | `ddstore-gateway` | POST/PUT requests | `PermissionError` — sliding window counter, retry-after header |

### Frontend Errors (RUM Error Tracking)

| Bug | Page | Trigger | What It Looks Like |
|---|---|---|---|
| Price feed WebSocket crash | Product detail | Product ID % 5 | `PriceFeedError` — malformed SSE event, schema v2.3 missing real-time fields |
| Third-party analytics long task | Product detail | Product ID % 7 | 120ms main thread block + memory leak detected by RUM |
| Personalization engine crash | Home page | 4% random | `TypeError` — A/B test variant config undefined for returning/high_value cohort |
| Session hydration failure | Checkout | 6% random | `TypeError` — expired session storage, encrypted payment token is null |
| WebGL heatmap crash | Admin dashboard | 8% after compute | `TypeError` — canvas element missing, WebGL context creation fails |

---

## Prerequisites

You need these installed before starting:

| Requirement | Check | Install |
|---|---|---|
| **macOS with Homebrew** | `brew --version` | [brew.sh](https://brew.sh) |
| **Python 3.10+** | `python3 --version` | `brew install python` |
| **Node.js 18+** | `node --version` | `brew install node` |
| **Datadog Agent** | `datadog-agent status` | [Install docs](https://docs.datadoghq.com/agent/) |

You also need from your **Datadog sandbox account** (must be grabbed manually from the UI):

1. **Datadog API Key** — for the Agent ([Organization Settings > API Keys](https://app.datadoghq.com/organization-settings/api-keys))
2. **RUM Application ID + Client Token** — for frontend monitoring
   - Go to **Digital Experience > RUM > New Application**
   - Select **React**, name it `ddstore`, click **Create**
   - Copy the `applicationId` and `clientToken` from the snippet shown

---

## Setup

### Option A: Spin up with Claude (recommended)

Clone the repo, open it in [Claude Code](https://claude.com/claude-code), and paste this prompt:

```
I just cloned the dd-demo-app repo. Please set it up end-to-end on my machine:

1. Install PostgreSQL via Homebrew if not already installed, start it, and create
   the ddstore database and ddstore_app user with pg_stat_statements enabled
2. Create a 'datadog' PostgreSQL monitoring user with pg_monitor role, create the
   datadog.explain_statement function, and configure the Agent's postgres.d/conf.yaml
   for DBM (use datadog-agent-configs/postgres.yaml.example as a reference)
3. Create backend/.env from backend/.env.example — fill in the DATABASE_URL
4. Create frontend/.env from frontend/.env.example — I'll give you my RUM credentials:
     VITE_DD_APP_ID=<paste your App ID here>
     VITE_DD_CLIENT_TOKEN=<paste your Client Token here>
5. Set up the Python virtualenv, install dependencies, and seed the database
6. Start the app (./start.sh) and confirm all services are healthy
```

Claude will handle every step, ask if anything is unclear, and confirm when the app is live.

---

### Option B: Manual setup

#### 1. Install and configure PostgreSQL

```bash
brew install postgresql@16
brew services start postgresql@16
```

Create the database and app user:

```sql
-- Run with: psql postgres
CREATE DATABASE ddstore;
CREATE USER ddstore_app WITH PASSWORD 'ddstore123';
GRANT ALL PRIVILEGES ON DATABASE ddstore TO ddstore_app;
ALTER DATABASE ddstore OWNER TO ddstore_app;
```

Enable `pg_stat_statements` for DBM:

```bash
# Find your postgresql.conf:
psql postgres -c "SHOW config_file;"

# Add/edit these lines in postgresql.conf:
#   shared_preload_libraries = 'pg_stat_statements'
#   track_activity_query_size = 4096

# Restart PostgreSQL for changes to take effect:
brew services restart postgresql@16
```

#### 2. Set up Database Monitoring (DBM)

Create the Datadog monitoring user and explain plan function:

```sql
-- Run with: psql ddstore
CREATE USER datadog WITH PASSWORD 'datadog123';
GRANT pg_monitor TO datadog;
GRANT SELECT ON pg_stat_activity TO datadog;

CREATE SCHEMA IF NOT EXISTS datadog;
GRANT USAGE ON SCHEMA datadog TO datadog;

CREATE OR REPLACE FUNCTION datadog.explain_statement(
   l_query TEXT, OUT explain JSON
) RETURNS SETOF JSON AS $$
DECLARE curs REFCURSOR; plan JSON;
BEGIN
   OPEN curs FOR EXECUTE pg_catalog.concat('EXPLAIN (FORMAT JSON) ', l_query);
   FETCH curs INTO plan; CLOSE curs;
   RETURN QUERY SELECT plan;
END; $$ LANGUAGE 'plpgsql' RETURNS NULL ON NULL INPUT SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION datadog.explain_statement(TEXT) TO datadog;
```

Configure the Datadog Agent's PostgreSQL integration:

```bash
# Copy the example config
cp datadog-agent-configs/postgres.yaml.example \
   /opt/datadog-agent/etc/conf.d/postgres.d/conf.yaml

# Edit it — set the password you chose for the datadog user
# Then restart the Agent:
launchctl kickstart -k gui/$(id -u)/com.datadoghq.agent
```

#### 3. Configure environment files

```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env — set DATABASE_URL:
#   DATABASE_URL=postgresql://ddstore_app:ddstore123@localhost:5432/ddstore

# Frontend
cp frontend/.env.example frontend/.env
# Edit frontend/.env — paste your RUM Application ID and Client Token:
#   VITE_DD_APP_ID=your-app-id-here
#   VITE_DD_CLIENT_TOKEN=your-client-token-here
```

#### 4. Install dependencies and seed the database

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 seed.py

cd ../frontend
npm install
```

#### 5. Start everything

```bash
./start.sh
```

This launches all 4 microservices, the frontend, and the load generator. Verify:

```bash
curl http://localhost:8080/api/health
# Should show: {"status":"ok","services":{"ddstore-products":"ok","ddstore-orders":"ok","ddstore-analytics":"ok","gateway":"ok"}}
```

To stop everything:

```bash
./stop.sh
```

Data will start appearing in your Datadog sandbox within 1–2 minutes.

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
├── datadog-agent-configs/
│   └── postgres.yaml.example  # DBM config template
├── start.sh                # Starts all 4 microservices + frontend + loadgen
├── stop.sh                 # Stops all running services
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (shared by all services) |

The following are set automatically by `start.sh` — you don't need to configure them:

| Variable | Value | Description |
|---|---|---|
| `DD_SERVICE` | per-service | `ddstore-gateway`, `ddstore-products`, `ddstore-orders`, `ddstore-analytics` |
| `DD_ENV` | `demo` | Environment tag |
| `DD_VERSION` | `1.0.0` | Version tag |
| `DD_LOGS_INJECTION` | `true` | Injects trace IDs into log lines |
| `DD_RUNTIME_METRICS_ENABLED` | `true` | Enables runtime metrics (GC, heap, threads) |
| `DD_PROFILING_ENABLED` | `true` | Enables Continuous Profiler |
| `DD_DBM_PROPAGATION_MODE` | `full` | Correlates APM traces with DBM query samples |
| `DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED` | `true` | Prevents ghost inferred services |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_DD_APP_ID` | RUM Application ID (from Datadog UI) |
| `VITE_DD_CLIENT_TOKEN` | RUM Client Token (from Datadog UI) |
| `VITE_DD_SITE` | Datadog site (`datadoghq.com`) |
| `VITE_DD_SERVICE` | Frontend service name (`ddstore-frontend`) |
| `VITE_DD_ENV` | Environment tag (`demo`) |
| `VITE_DD_VERSION` | Version tag (`1.0.0`) |
