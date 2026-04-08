# Datadog Marketplace — Demo App

A full-stack e-commerce app that sells Datadog products. Built specifically to demonstrate Datadog's observability platform end-to-end — the app is fully instrumented and contains deliberate bugs and performance issues to make every feature meaningful to show.

---

## What's Inside

| Layer | Tech |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Python Flask + SQLAlchemy |
| Database | PostgreSQL |
| APM | ddtrace (auto-instrumented) |
| RUM | @datadog/browser-rum + React plugin |
| Logs | Structured JSON logs + browser-logs |
| Metrics | DogStatsD custom metrics |
| Profiling | DD Continuous Profiler (enabled via env) |

---

## Datadog Features Demonstrated

- **APM & Distributed Tracing** — every request traced, service map shows frontend → backend → postgres
- **Database Monitoring** — slow queries, explain plans, `pg_stat_statements` enabled
- **RUM + Session Replay** — 100% session capture, React component tracking, frontend errors
- **Log Management** — structured JSON logs correlated to traces via `dd.trace_id`
- **Error Tracking** — backend exceptions + frontend JS errors grouped automatically
- **Continuous Profiler** — CPU and memory profiles from the Flask process
- **Custom Metrics** — `ddstore.*` namespace via DogStatsD (request count, revenue, errors)

---

## Intentional Bugs (for demo)

| Bug | Where | What Datadog catches |
|---|---|---|
| N+1 query | `GET /api/products` | APM shows N duplicate DB spans per request |
| `NoneType` AttributeError | Product with null description | Error Tracking groups repeated exceptions |
| `ZeroDivisionError` | `GET /api/products/3` | Unhandled exception with full stack trace in APM |
| Slow unindexed LIKE query | `GET /api/search` | DBM flags full table scan, high latency in APM |
| Artificial delay (1–3s) | `GET /api/recommendations` | APM p99 latency spike, visible in service map |
| Random 15% checkout failures | `POST /api/checkout` | Error rate monitor, retry storm visible in traces |
| Memory leak | Background worker thread | Continuous Profiler heap growth over time |
| CPU spike | `GET /api/compute` | Profiler CPU flame graph, APM slow span |
| Python-side aggregation | `GET /api/stats` | Full table loaded into memory instead of SQL SUM |

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 16 (running locally)
- Datadog Agent running on `localhost:8126` / `localhost:8125`

### 1. Clone
```bash
git clone git@github.com:vincentsgarzi/dd-demo-app.git
cd dd-demo-app
```

### 2. Configure environment variables

**Backend:**
```bash
cp backend/.env.example backend/.env
# Edit backend/.env — fill in DATABASE_URL
```

**Frontend:**
```bash
cp frontend/.env.example frontend/.env
# Edit frontend/.env — fill in your RUM App ID and Client Token
# from Datadog > UX Monitoring > RUM Applications
```

### 3. Set up the database
```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
psql postgres -c "CREATE DATABASE ddstore;"
psql postgres -c "CREATE USER ddstore_app WITH PASSWORD 'your-password';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE ddstore TO ddstore_app;"
psql ddstore -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
```

### 4. Run everything
```bash
./start.sh
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8080/api/health

### 5. Generate traffic
```bash
python3 loadgen/loadgen.py
```

The load generator simulates browsing, searching, adding to cart, and checking out — hitting all the buggy endpoints on a loop so Datadog has data to show immediately.

---

## Project Structure

```
dd-demo-app/
├── backend/
│   ├── app.py          # Flask API — all routes + intentional bugs
│   ├── models.py       # SQLAlchemy models
│   ├── seed.py         # Database seeder
│   ├── requirements.txt
│   ├── .env.example    # ← copy to .env and fill in
│   └── .env            # ← not committed
├── frontend/
│   ├── src/
│   │   ├── datadog.js  # RUM + Logs init
│   │   ├── App.jsx
│   │   ├── pages/
│   │   └── components/
│   ├── .env.example    # ← copy to .env and fill in
│   └── .env            # ← not committed
├── loadgen/
│   └── loadgen.py      # Traffic generator
├── start.sh            # Starts backend + frontend together
└── README.md
```

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `DD_SERVICE` | Service name in Datadog (`ddstore-api`) |
| `DD_ENV` | Environment tag (`demo`) |
| `DD_VERSION` | Version tag |
| `DD_TRACE_AGENT_URL` | Datadog Agent trace endpoint |
| `DD_LOGS_INJECTION` | Injects trace IDs into log lines |
| `DD_RUNTIME_METRICS_ENABLED` | Enables runtime metrics (GC, heap, threads) |
| `DD_PROFILING_ENABLED` | Enables Continuous Profiler |

### Frontend (`frontend/.env`)
| Variable | Description |
|---|---|
| `VITE_DD_APP_ID` | RUM Application ID (from Datadog UI) |
| `VITE_DD_CLIENT_TOKEN` | RUM Client Token (from Datadog UI) |
| `VITE_DD_SITE` | Datadog site (`datadoghq.com`) |
| `VITE_DD_SERVICE` | Frontend service name |
| `VITE_DD_ENV` | Environment tag |
| `VITE_DD_VERSION` | Version tag |
