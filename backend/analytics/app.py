"""
Datadog Marketplace — Analytics Service
Handles stats dashboard, compute endpoint, and memory leak background thread.
Intentional bugs preserved for Datadog demo purposes.
"""
import os
import sys
import time
import random
import threading
import logging
import traceback
import requests as http_client
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# ── Datadog APM — must be first ──────────────────────────────────────────────
from ddtrace import tracer, patch_all

patch_all()

# ── App setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"])

_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL environment variable is not set.")
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False

from shared.models import db, Product, User, Order

db.init_app(app)

# ── Service URLs ──────────────────────────────────────────────────────────────
PRODUCT_SERVICE = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8081")
ORDER_SERVICE = os.getenv("ORDER_SERVICE_URL", "http://localhost:8082")

# ── Structured logging ────────────────────────────────────────────────────────
from shared.logging import setup_logging
logger = setup_logging("analytics")

# ── DogStatsD metrics ─────────────────────────────────────────────────────────
try:
    from datadog import initialize, statsd
    initialize(statsd_host="localhost", statsd_port=8125)
    STATSD_ENABLED = True
except Exception:
    STATSD_ENABLED = False


def emit(metric, value=1, tags=None):
    if STATSD_ENABLED:
        try:
            statsd.increment(metric, value, tags=tags or [])
        except Exception:
            pass


# ── BUG: memory leak — background thread accumulates unbounded list ───────────
_leaked_memory = []
_worker_start_time = time.time()


def _memory_leak_worker():
    """Simulates a background job that leaks memory by never releasing data."""
    while True:
        chunk = {
            "timestamp": datetime.utcnow().isoformat(),
            "payload": "x" * 10_000,
            "orders_processed": random.randint(1, 100),
        }
        _leaked_memory.append(chunk)
        leak_bytes = len(_leaked_memory) * 10_000
        uptime_min = (time.time() - _worker_start_time) / 60

        if len(_leaked_memory) % 20 == 0 and len(_leaked_memory) > 0:
            logger.warning(f"Memory leak growing — cache at {len(_leaked_memory)} entries (~{leak_bytes/1024/1024:.1f}MB), never cleared since startup ({uptime_min:.0f}m ago)", extra={
                "worker": {"cache_size": len(_leaked_memory), "leak_bytes": leak_bytes, "leak_mb": round(leak_bytes/1024/1024, 2), "uptime_minutes": round(uptime_min, 1)},
                "action": "memory_leak_warning",
                "bug": "unbounded_cache",
            })
        else:
            logger.info(f"Background worker processed batch — cache size: {len(_leaked_memory)} (~{leak_bytes/1024:.0f}KB)", extra={
                "worker": {"cache_size": len(_leaked_memory), "leak_bytes": leak_bytes, "orders_in_batch": chunk["orders_processed"]},
                "action": "worker_batch_processed",
            })
        time.sleep(15)


threading.Thread(target=_memory_leak_worker, daemon=True).start()

# ── Request hooks ─────────────────────────────────────────────────────────────
@app.before_request
def start_timer():
    from flask import g
    g.start = time.time()


@app.after_request
def log_request(response):
    from flask import g
    duration_ms = (time.time() - g.start) * 1000
    emit("ddstore.request.count", tags=[
        f"method:{request.method}", f"path:{request.path}", f"status:{response.status_code}",
    ])
    emit("ddstore.request.duration", duration_ms, tags=[f"path:{request.path}"])
    return response


# ── Error handler — ensures full stack trace on the root span ─────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    span = tracer.current_span()
    if span:
        span.set_tag("error.message", str(e))
        span.set_tag("error.type", type(e).__name__)
        span.set_tag("error.stack", tb)
        span.error = 1
    logger.error(f"Unhandled {type(e).__name__}: {e}", extra={
        "error_type": type(e).__name__, "error_message": str(e),
    })
    return jsonify({"error": type(e).__name__, "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "ddstore-analytics"})


@app.route("/api/stats")
def stats():
    """
    Dashboard stats — makes cross-service calls for distributed tracing,
    then runs unoptimized aggregate queries locally.
    """
    logger.info("Stats dashboard requested — aggregating data across services", extra={
        "action": "stats_requested",
    })

    # ── Cross-service calls: creates distributed traces ───────────────────
    try:
        prod_resp = http_client.get(f"{PRODUCT_SERVICE}/api/products", timeout=10)
        logger.info(f"Fetched product catalog from product service — {len(prod_resp.json()) if prod_resp.ok else 'FAILED'} products", extra={
            "cross_service": {"target": "ddstore-products", "status": prod_resp.status_code},
            "action": "stats_fetch_products",
        })
    except Exception as e:
        logger.error(f"Failed to reach product service for stats: {e}", extra={
            "cross_service": {"target": "ddstore-products", "error": str(e)},
            "action": "stats_fetch_products_failed",
        })

    try:
        orders_resp = http_client.get(f"{ORDER_SERVICE}/api/orders", timeout=10)
        logger.info(f"Fetched recent orders from order service — {len(orders_resp.json()) if orders_resp.ok else 'FAILED'} orders", extra={
            "cross_service": {"target": "ddstore-orders", "status": orders_resp.status_code},
            "action": "stats_fetch_orders",
        })
    except Exception as e:
        logger.error(f"Failed to reach order service for stats: {e}", extra={
            "cross_service": {"target": "ddstore-orders", "error": str(e)},
            "action": "stats_fetch_orders_failed",
        })

    # BUG: 7% chance of Redis cache deserialization failure
    if random.random() < 0.07:
        def _get_cached_stats(cache_key):
            """Fetch pre-computed stats from Redis cache."""
            def _deserialize_msgpack(raw_bytes):
                """Deserialize msgpack-encoded stats payload."""
                raise ValueError(f"msgpack: unpack failed — unexpected byte 0xc1 at offset 847 in cached stats (key={cache_key}, size=2.3KB, ttl=expired)")
            _deserialize_msgpack(b"\xc1\x00")

        _get_cached_stats("stats:dashboard:v3")

    # ── Local DB queries (bugs preserved) ─────────────────────────────────
    total_orders = Order.query.count()
    total_products = Product.query.count()
    total_users = User.query.count()

    # BUG: loads all orders into memory for Python-side sum instead of SQL SUM()
    all_orders = Order.query.all()
    total_revenue = sum(o.total for o in all_orders if o.status == "completed")

    logger.warning(f"Stats computed using Python-side aggregation — loaded {len(all_orders)} orders into memory instead of using SQL SUM()", extra={
        "stats": {
            "total_orders": total_orders, "total_products": total_products,
            "total_users": total_users, "total_revenue": round(total_revenue, 2),
            "memory_leak_entries": len(_leaked_memory),
            "orders_loaded_in_memory": len(all_orders),
        },
        "performance": {"pattern": "python_side_aggregation", "should_use": "SQL SUM()", "rows_loaded": len(all_orders)},
        "action": "stats_computed",
    })

    return jsonify({
        "total_orders": total_orders,
        "total_products": total_products,
        "total_users": total_users,
        "total_revenue": round(total_revenue, 2),
        "memory_leak_entries": len(_leaked_memory),
    })


@app.route("/api/compute")
def cpu_spike():
    """
    BUG (CPU): Intentional CPU-intensive endpoint — naive prime sieve with no caching.
    """
    n = int(request.args.get("n", 50000))
    n = min(n, 500_000)

    span = tracer.current_span()
    if span:
        span.set_tag("compute.n", n)

    logger.warning(f"CPU-intensive prime computation requested — n={n:,} with naive O(n*sqrt(n)) algorithm, no cache", extra={
        "compute": {"n": n, "algorithm": "naive_trial_division", "cached": False, "max_allowed": 500_000},
        "action": "compute_started",
    })

    start = time.time()
    # BUG: naive prime check — O(n * sqrt(n)), no cache
    primes = []
    for num in range(2, n):
        is_prime = all(num % i != 0 for i in range(2, int(num**0.5) + 1))
        if is_prime:
            primes.append(num)

    elapsed = time.time() - start
    if span:
        span.set_tag("compute.primes_found", len(primes))
        span.set_tag("compute.elapsed_ms", int(elapsed * 1000))

    level = "error" if elapsed > 5 else "warning" if elapsed > 1 else "info"
    getattr(logger, level)(f"Prime computation complete — found {len(primes):,} primes up to {n:,} in {elapsed*1000:.0f}ms", extra={
        "compute": {"n": n, "primes_found": len(primes), "elapsed_ms": round(elapsed * 1000, 1), "algorithm": "naive_trial_division"},
        "action": "compute_complete",
    })

    return jsonify({"primes_found": len(primes), "elapsed_ms": round(elapsed * 1000, 1)})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8083, debug=False)
