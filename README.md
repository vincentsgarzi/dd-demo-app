# DD Store — Datadog Demo App

A full-stack SaaS marketplace e-commerce app built to demo Datadog end-to-end. Sells fictional Datadog products (APM, RUM, DBM, etc.), runs as 4 Python Flask microservices + React frontend, and is fully instrumented with APM, RUM, DBM, Logs, Profiler, ASM, and custom metrics. Contains deliberate, realistic bugs so every Datadog feature has something interesting to show.

---

## Quick Start (Recommended — Let Claude Do It)

1. **Clone the repo**
   ```bash
   git clone https://github.com/vincentsgarzi/dd-demo-app.git
   cd dd-demo-app
   ```

2. **Get your RUM credentials** from your Datadog sandbox:
   - Go to **Digital Experience → RUM → New Application**
   - Select **React**, name it `ddstore`, click **Create**
   - Copy the `applicationId` and `clientToken` from the snippet

3. **Open in [Claude Code](https://claude.ai/download)** and paste this prompt:

   ```
   I just cloned the dd-demo-app repo. Please set it up end-to-end on my machine.

   My RUM credentials:
     VITE_DD_APP_ID=<paste your App ID>
     VITE_DD_CLIENT_TOKEN=<paste your Client Token>

   Steps needed:
   1. Install PostgreSQL 16 via Homebrew if not already installed, start it,
      create the `ddstore` database and `ddstore_app` user, enable
      pg_stat_statements in postgresql.conf, and restart Postgres.
   2. Create the `datadog` Postgres monitoring user (pg_monitor role),
      create the datadog schema and explain_statement function, and configure
      the Agent's postgres.d/conf.yaml for DBM using
      datadog-agent-configs/postgres.yaml.example as a template.
   3. Create backend/.env from backend/.env.example — fill in DATABASE_URL.
   4. Create frontend/.env from frontend/.env.example — fill in my RUM credentials above.
   5. Create the Python venv, install dependencies, and seed the database.
   6. Run ./start.sh and confirm all 5 services are healthy.
   ```

   Claude will handle every step autonomously and confirm when the app is live.

---

## Prerequisites

Check these before starting. Claude can install missing items but needs to know what's there.

| Requirement | Min Version | Check | Install |
|---|---|---|---|
| macOS | any recent | — | — |
| Homebrew | any | `brew --version` | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| Python | 3.10+ | `python3 --version` | `brew install python` |
| Node.js | 18+ | `node --version` | `brew install node` |
| PostgreSQL | 14+ (16 recommended) | `psql --version` | `brew install postgresql@16` |
| Datadog Agent | 7.x | `datadog-agent version` | [Agent install docs](https://docs.datadoghq.com/agent/basic_agent_usage/macos/) |
| Playwright (for RUM loadgen) | any | `python3 -m playwright --version` | `pip install playwright && playwright install chromium` |

### Datadog Sandbox Account Items

You need two things from your **own** Datadog sandbox account (not the shared demo org):

| Item | Where to Find It | Used For |
|---|---|---|
| **Agent API Key** | Organization Settings → API Keys | Datadog Agent config (`/opt/datadog-agent/etc/datadog.yaml`) |
| **RUM App ID + Client Token** | Digital Experience → RUM → New Application → React → `ddstore` | `frontend/.env` |

> **Note:** The Agent API key should already be in `/opt/datadog-agent/etc/datadog.yaml` if your Agent is running. You only need to create the RUM application.

---

## Manual Setup (Step-by-Step)

Skip this if you're using the Claude Quick Start above.

### 1. PostgreSQL

```bash
brew install postgresql@16
brew services start postgresql@16
```

Create the database and app user:

```bash
psql postgres <<'SQL'
CREATE DATABASE ddstore;
CREATE USER ddstore_app WITH PASSWORD 'ddstore123';
GRANT ALL PRIVILEGES ON DATABASE ddstore TO ddstore_app;
ALTER DATABASE ddstore OWNER TO ddstore_app;
SQL
```

Enable `pg_stat_statements` (required for DBM):

```bash
# Find your config file:
psql postgres -c "SHOW config_file;"

# Add these lines to postgresql.conf:
#   shared_preload_libraries = 'pg_stat_statements'
#   track_activity_query_size = 4096

brew services restart postgresql@16
```

### 2. Database Monitoring (DBM) Setup

Run as a superuser on the `ddstore` database:

```bash
psql ddstore <<'SQL'
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
SQL
```

Configure the Agent:

```bash
cp datadog-agent-configs/postgres.yaml.example \
   /opt/datadog-agent/etc/conf.d/postgres.d/conf.yaml

# Edit the file — set the password for the datadog user
# Then restart the Agent:
launchctl kickstart -k gui/$(id -u)/com.datadoghq.agent
```

### 3. Environment Files

```bash
# Backend — only needs DATABASE_URL
cp backend/.env.example backend/.env
# Edit: DATABASE_URL=postgresql://ddstore_app:ddstore123@localhost:5432/ddstore

# Frontend — needs your RUM credentials
cp frontend/.env.example frontend/.env
# Edit: VITE_DD_APP_ID and VITE_DD_CLIENT_TOKEN
```

### 4. Python Dependencies + Seed Database

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DD_TRACE_ENABLED=false python3 seed.py   # seeds 18 products, 5 users, ~30 orders

cd ../frontend
npm install
```

### 5. Start Everything

```bash
./start.sh
```

### 6. Verify

```bash
curl http://localhost:8080/api/health    # gateway
curl http://localhost:8081/api/health    # products
curl http://localhost:8082/api/health    # orders
curl http://localhost:8083/api/health    # analytics
# frontend at http://localhost:5173
```

Data appears in Datadog within **1–2 minutes**.

```bash
./stop.sh    # stop all services
```

---

## What's Running After Start

| Service | URL | DD Service Tag |
|---|---|---|
| React frontend | http://localhost:5173 | `ddstore-frontend` |
| API Gateway | http://localhost:8080 | `ddstore-gateway` |
| Product Service | http://localhost:8081 | `ddstore-products` |
| Order Service | http://localhost:8082 | `ddstore-orders` |
| Analytics Service | http://localhost:8083 | `ddstore-analytics` |
| Load generator | (background) | — |
| RUM load generator (Playwright) | (background, 2 browsers) | — |

### CPU Guard

All services run at `nice +10`, load generators at `nice +15` — they yield CPU to your other apps automatically. The intentional CPU spike endpoint is also guarded: it caps compute at 75k (normal), 15k (>75% host CPU), or skips entirely (>85%) to protect your machine during demos.

---

## Datadog Features Demonstrated

| Feature | What to Show |
|---|---|
| **APM + Distributed Tracing** | Service map: gateway → {products, orders, analytics} → postgres. Multi-service flamegraphs on checkout and stats. |
| **Database Monitoring** | Slow queries, explain plans, N+1 query visible in DBM query samples. `DD_DBM_PROPAGATION_MODE=full` correlates APM traces → SQL queries. |
| **RUM + Session Replay** | 100% session capture, React component tracking, frontend errors with session replay, RUM↔APM correlation. |
| **Log Management** | Structured JSON logs from all services, correlated to APM traces via `dd.trace_id`. |
| **Error Tracking** | 10+ distinct backend error types + 5 frontend errors, each grouped by fingerprint with full stack traces. |
| **Continuous Profiler** | CPU flame graph from the compute endpoint. Memory heap growth from the analytics leak worker. |
| **ASM** | Attack traffic in the loadgen fires SQL injection, XSS, Log4Shell, path traversal, SSRF payloads. |
| **Custom Metrics** | `ddstore.*` namespace — request count, duration, revenue via DogStatsD. |
| **Service Catalog** | 5 service YAML definitions in `service-catalog/`. Run `register.sh` with your API+App keys to push them. |
| **NPM** | System probe config in `datadog-agent-configs/`. Limited on macOS vs Linux. |

---

## Architecture

```
┌─────────────────────┐
│   React Frontend    │  Vite :5173 · Datadog RUM + Session Replay
│   DD RUM + Replay   │  allowedTracingUrls → RUM↔APM correlation
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│    API Gateway      │  :8080 · ddstore-gateway
│  (thin proxy/CORS)  │  Routes all /api/* to downstream services
└───┬─────┬──────┬────┘
    │     │      │
    ▼     ▼      ▼
┌──────┐ ┌──────┐ ┌────────────┐
│Prods │ │Orders│ │ Analytics  │
│:8081 │ │:8082 │ │ :8083      │
│      │ │      │ │ + bg leak  │
└──┬───┘ └──┬───┘ └─────┬──────┘
   │    ▲   │           │
   │    └───┘           │  (analytics calls orders + products for stats)
   └────────────────────┘
              │
              ▼
   ┌──────────────────┐
   │  PostgreSQL 16   │  DBM enabled · pg_stat_statements · explain plans
   └──────────────────┘
```

**Cross-service traces** (shows as multi-service flamegraph in APM):
- `POST /api/checkout` → orders calls products to validate cart items
- `GET /api/stats` → analytics calls both orders and products

---

## Intentional Bugs (Do Not Fix)

These are preserved intentionally for demo purposes. All are realistic infrastructure failures — not toy errors.

### Backend

| Bug | Service | Trigger | Error Type |
|---|---|---|---|
| N+1 query | products | Every catalog load | 19 DB queries instead of 1 — visible in APM + DBM |
| NULL description | products | Product #3 | `AttributeError` — `.upper()` on NULL field |
| Stale CDN cache | products | Product ID % 10 == 3 | `KeyError` — schema v2.8 vs v3.2 field mismatch, edge ignoring cache headers |
| Feature flag crash | products | Product ID % 10 == 7 | `RuntimeError` — archived variant pool, 1,247 products affected |
| ES circuit breaker | products | 8% of requests | `ConnectionError` — heap at 89%, 47 in-flight queries |
| SageMaker timeout | products | 5% of recommendations | `TimeoutError` — cold start, Redis fallback expired |
| Slow recommendations | products | Always | 1–3s artificial delay — APM p99 latency spike |
| PCI vault cert expiry | orders | ~8% of checkouts | `ConnectionError` — TLS handshake failure |
| Idempotency conflict | orders | ~6% of checkouts | `ValueError` — duplicate payment key detected |
| Fraud detection block | orders | ~5% of checkouts | `PermissionError` — ML risk score 0.92 |
| Stripe timeout | orders | ~4% of checkouts | `TimeoutError` — circuit breaker OPEN |
| Data pipeline stale | analytics | 7% of /stats | `RuntimeError` — Kafka consumer lag 500K messages |
| Memory leak | analytics | Always (capped at 500 entries ~5MB) | Heap growth visible in Continuous Profiler |
| CPU spike | analytics | `/api/compute` endpoint | O(n√n) prime sieve — flame graph spike |
| Python-side aggregation | analytics | Every /stats | Full table loaded into memory instead of SQL SUM() |
| Rate limit exceeded | gateway | 3% of POST/PUT | `PermissionError` — sliding window counter exceeded |

### Frontend (RUM Error Tracking)

| Bug | Page | Trigger | Error |
|---|---|---|---|
| Price feed crash | Product detail | Product ID % 5 == 0 | `PriceFeedError` — malformed SSE event |
| Long task / memory | Product detail | Product ID % 7 == 0 | 120ms main thread block |
| Personalization crash | Home page | 4% random | `TypeError` — A/B variant config undefined |
| Session hydration fail | Checkout | 6% random | `TypeError` — encrypted payment token null |
| WebGL context crash | Admin dashboard | 8% after compute | `TypeError` — canvas element missing |

---

## Project Structure

```
dd-demo-app/
├── backend/
│   ├── gateway/app.py          # API Gateway — proxies all /api/* requests
│   ├── products/app.py         # Products, search, recommendations
│   ├── orders/app.py           # Cart, checkout, order history
│   ├── analytics/app.py        # Stats, CPU spike, memory leak worker
│   ├── shared/
│   │   ├── models.py           # SQLAlchemy models (shared)
│   │   ├── logging.py          # setup_logging() — structured JSON
│   │   └── cpu_guard.py        # Host CPU monitor — throttles compute, protects machine
│   ├── seed.py                 # Seeds 18 products, 5 users, ~30 orders
│   ├── requirements.txt
│   ├── .env.example            # ← template, committed
│   └── .env                    # ← your values, gitignored
├── frontend/
│   ├── src/
│   │   ├── datadog.js          # RUM + Logs init (reads VITE_DD_* from .env)
│   │   ├── App.jsx
│   │   ├── api.js              # API client
│   │   ├── pages/
│   │   │   ├── HomePage.jsx
│   │   │   ├── ProductPage.jsx
│   │   │   ├── CartPage.jsx
│   │   │   ├── CheckoutPage.jsx
│   │   │   ├── OrdersPage.jsx
│   │   │   └── AdminPage.jsx   # Admin dashboard — memory leak + CPU spike demo
│   │   └── components/
│   │       ├── Navbar.jsx
│   │       ├── ProductCard.jsx
│   │       └── ErrorBoundary.jsx
│   ├── .env.example            # ← template, committed
│   └── .env                    # ← your values, gitignored
├── loadgen/
│   ├── loadgen.py              # HTTP traffic generator (browse/buy/attack, CPU-aware)
│   └── rum_loadgen.py          # Playwright headless browser RUM sessions
├── service-catalog/
│   ├── ddstore-*.yaml          # Service Catalog v2.2 definitions (all 5 services)
│   └── register.sh             # Push YAMLs to Datadog API
├── datadog-agent-configs/
│   ├── postgres.yaml.example   # DBM config template
│   └── ddstore-logs.yaml.example # Log collection config template
├── start.sh                    # Starts all services + loadgens (auto-detects agent ports)
├── stop.sh                     # Kills all services by port
└── README.md
```

---

## Environment Variables

### `backend/.env` (only one required)

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://ddstore_app:ddstore123@localhost:5432/ddstore` | Postgres connection string |

### `frontend/.env`

| Variable | Example | Description |
|---|---|---|
| `VITE_DD_APP_ID` | `abc123...` | RUM Application ID (from Datadog UI) |
| `VITE_DD_CLIENT_TOKEN` | `pub123...` | RUM Client Token (from Datadog UI) |
| `VITE_DD_SITE` | `datadoghq.com` | Datadog site |
| `VITE_DD_SERVICE` | `ddstore-frontend` | RUM service name |
| `VITE_DD_ENV` | `demo` | Environment tag |
| `VITE_DD_VERSION` | `1.0.0` | Version tag |

### Set automatically by `start.sh` (no action needed)

| Variable | Value |
|---|---|
| `DD_ENV` | `demo` |
| `DD_VERSION` | `1.0.0` |
| `DD_LOGS_INJECTION` | `true` |
| `DD_RUNTIME_METRICS_ENABLED` | `true` |
| `DD_PROFILING_ENABLED` | `true` |
| `DD_DBM_PROPAGATION_MODE` | `full` |
| `DD_APPSEC_ENABLED` | `true` |
| `DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED` | `true` |
| `DD_TRACE_AGENT_PORT` | auto-detected (8126 or 8136) |
| `DD_DOGSTATSD_PORT` | auto-detected (8125 or 8135) |

---

## Service Catalog

YAML definitions for all 5 services live in `service-catalog/`. To register them with Datadog:

```bash
DD_API_KEY=<your-api-key> DD_APP_KEY=<your-app-key> bash service-catalog/register.sh
```

Your App Key is in **Organization Settings → Application Keys** (different from the API key).

---

## Adapting for a Customer Demo

The app is designed to be modified. Common customizations:

| Goal | What to Change |
|---|---|
| Rename the app | Update `DD_SERVICE` tags in `start.sh`, `VITE_DD_SERVICE` in `frontend/.env`, and the `DD Store` title in `frontend/src/pages/HomePage.jsx` |
| Change the product catalog | Edit `backend/seed.py` — the products array seeds the DB on every start |
| Adjust error rates | Search for `random.random() < 0.XX` in the service files and change the threshold |
| Enable/disable a specific bug | Comment out the relevant `if` block in the service file |
| Add a new error scenario | Add a new `if random.random() < 0.XX: raise ErrorType(...)` block to any service endpoint |
| Change environment name | Update `DD_ENV` in `start.sh` and `VITE_DD_ENV` in `frontend/.env` |

---

## Context for AI Assistants

> This section is for Claude or other AI coding tools picking up a new session.

**What this repo is:** A Datadog demo app used by Datadog SEs to showcase observability features in their personal sandbox accounts. It is a SaaS e-commerce store (`DD Store`) selling fictional Datadog products.

**Stack:** Python 3.12 · Flask · SQLAlchemy · PostgreSQL · React 18 · Vite · Tailwind CSS · ddtrace · Playwright

**Key rules:**
1. **Always push to GitHub after every change** (`git add`, `git commit`, `git push`)
2. **Never commit secrets** — no API keys, passwords, or tokens in any committed file
3. **Never fix intentional bugs** — the bugs in `backend/*/app.py` and `frontend/src/pages/*.jsx` are demo features, not defects
4. **Always use the Python venv** at `backend/.venv` for any Python commands
5. **Start the load generator alongside the app** — `start.sh` does this automatically

**Current intentional bugs are in:**
- `backend/products/app.py` — N+1 query, NULL AttributeError, CDN KeyError, feature flag RuntimeError, ES ConnectionError, SageMaker TimeoutError
- `backend/orders/app.py` — PCI ConnectionError, idempotency ValueError, fraud PermissionError, Stripe TimeoutError
- `backend/analytics/app.py` — memory leak (capped at 500 entries), CPU spike (guarded by cpu_guard.py), data pipeline RuntimeError
- `backend/gateway/app.py` — rate limit PermissionError (3% of POST/PUT)
- `frontend/src/pages/ProductPage.jsx` — PriceFeedError, long task
- `frontend/src/pages/HomePage.jsx` — personalization TypeError
- `frontend/src/pages/CheckoutPage.jsx` — session hydration TypeError
- `frontend/src/pages/AdminPage.jsx` — WebGL crash

**To start the app:** `bash start.sh` from the repo root
**To stop the app:** `bash stop.sh` from the repo root
**Agent ports:** auto-detected by `start.sh` (handles both standard :8126 and enterprise IT :8136)
