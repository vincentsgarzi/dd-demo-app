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
_log_fmt = '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "dd.trace_id": "%(dd.trace_id)s", "dd.span_id": "%(dd.span_id)s"}'
logging.basicConfig(level=logging.INFO, format=_log_fmt)
_log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(_log_dir, exist_ok=True)
_fh = logging.FileHandler(os.path.join(_log_dir, "analytics.log"))
_fh.setFormatter(logging.Formatter(_log_fmt))
logging.getLogger().addHandler(_fh)
logger = logging.getLogger("ddstore.analytics")

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


def _memory_leak_worker():
    """Simulates a background job that leaks memory by never releasing data."""
    while True:
        chunk = {
            "timestamp": datetime.utcnow().isoformat(),
            "payload": "x" * 10_000,
            "orders_processed": random.randint(1, 100),
        }
        _leaked_memory.append(chunk)
        logger.info(f"Background worker processed batch, cache size: {len(_leaked_memory)}")
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
    logger.info(f"{request.method} {request.path} {response.status_code} {duration_ms:.1f}ms")
    emit("ddstore.request.count", tags=[
        f"method:{request.method}", f"path:{request.path}", f"status:{response.status_code}",
    ])
    emit("ddstore.request.duration", duration_ms, tags=[f"path:{request.path}"])
    return response


# ── Error handler — ensures full stack trace on the root span ─────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    span = tracer.current_span()
    if span:
        span.set_tag("error.message", str(e))
        span.set_tag("error.type", type(e).__name__)
        span.set_tag("error.stack", traceback.format_exc())
        span.error = 1
    logger.error(f"Unhandled {type(e).__name__}: {e}")
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
    # ── Cross-service calls: creates distributed traces ───────────────────
    # analytics → products (fetch product list for count)
    try:
        prod_resp = http_client.get(f"{PRODUCT_SERVICE}/api/products", timeout=10)
    except Exception:
        pass

    # analytics → orders (fetch recent orders)
    try:
        orders_resp = http_client.get(f"{ORDER_SERVICE}/api/orders", timeout=10)
    except Exception:
        pass

    # ── Local DB queries (bugs preserved) ─────────────────────────────────
    total_orders = Order.query.count()
    total_products = Product.query.count()
    total_users = User.query.count()

    # BUG: loads all orders into memory for Python-side sum instead of SQL SUM()
    all_orders = Order.query.all()
    total_revenue = sum(o.total for o in all_orders if o.status == "completed")

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

    return jsonify({"primes_found": len(primes), "elapsed_ms": round(elapsed * 1000, 1)})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8083, debug=False)
