"""
Datadog Marketplace — Product Service
Handles products, categories, search, and recommendations.
Intentional bugs preserved for Datadog demo purposes.
"""
import os
import sys
import time
import random
import logging
import traceback

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

from shared.models import db, Category, Product

db.init_app(app)

# ── Structured logging ────────────────────────────────────────────────────────
from shared.logging import setup_logging
logger = setup_logging("products")

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


# ── Request hooks ─────────────────────────────────────────────────────────────
@app.before_request
def start_timer():
    from flask import g
    g.start = time.time()


@app.after_request
def log_request(response):
    from flask import g
    duration_ms = (time.time() - g.start) * 1000
    logger.info(f"{request.method} {request.path} {response.status_code} {duration_ms:.1f}ms", extra={
        "http": {"method": request.method, "url": request.path, "status_code": response.status_code},
        "duration_ms": round(duration_ms, 1),
    })
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
    logger.error(f"Unhandled {type(e).__name__}: {e}", extra={
        "error_type": type(e).__name__, "error_message": str(e),
    })
    return jsonify({"error": type(e).__name__, "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "ddstore-products"})


@app.route("/api/products")
def list_products():
    """
    BUG (N+1): iterates products and calls .to_dict_with_category() on each,
    which triggers a separate SQL query per product to load category + causes
    AttributeError when description is None (product id=3).
    """
    span = tracer.current_span()
    if span:
        span.set_tag("products.source", "database")

    products = Product.query.all()

    result = []
    for p in products:
        try:
            result.append(p.to_dict_with_category())
        except AttributeError as e:
            logger.error(f"Failed to serialize product {p.id}: {e}", extra={
                "product_id": p.id, "error_type": "serialization",
            })
            emit("ddstore.error", tags=["type:serialization", f"product_id:{p.id}"])
            result.append({**p.to_dict(), "category": "Unknown", "description_preview": ""})

    emit("ddstore.products.listed", len(result))
    return jsonify(result)


@app.route("/api/products/<int:product_id>")
def get_product(product_id):
    """
    BUG: product IDs ending in 3 throw a deliberate unhandled ZeroDivisionError.
    """
    span = tracer.current_span()
    if span:
        span.set_tag("product.id", product_id)

    # BUG: deliberate divide-by-zero when id ends in 3
    if product_id % 10 == 3:
        discount = 100 / (product_id - product_id)  # ZeroDivisionError

    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict_with_category())


@app.route("/api/search")
def search_products():
    """
    BUG (slow query): Uses LIKE '%term%' with no index — full table scan.
    Also has an artificial sleep to simulate DB connection wait.
    """
    q = request.args.get("q", "")
    if not q:
        return jsonify([])

    span = tracer.current_span()
    if span:
        span.set_tag("search.query", q)
        span.set_tag("db.statement", f"SELECT * FROM products WHERE name LIKE '%{q}%'")

    # BUG: artificial connection pool wait
    time.sleep(random.uniform(0.2, 0.8))

    # BUG: unindexed LIKE query
    products = Product.query.filter(
        Product.name.ilike(f"%{q}%") | Product.description.ilike(f"%{q}%")
    ).all()

    emit("ddstore.search.count", tags=[f"results:{len(products)}"])
    return jsonify([p.to_dict() for p in products])


@app.route("/api/recommendations")
def recommendations():
    """
    BUG (slow): Simulates a recommendation engine that takes too long.
    """
    span = tracer.current_span()

    # BUG: slow — 1-3 second artificial delay every time
    delay = random.uniform(1.0, 3.0)
    if span:
        span.set_tag("recommendation.delay_ms", int(delay * 1000))

    time.sleep(delay)

    # BUG: inefficient — loads ALL products into memory, shuffles, slices in Python
    all_products = Product.query.all()
    random.shuffle(all_products)
    recommended = all_products[:4]

    return jsonify([p.to_dict() for p in recommended])


@app.route("/api/categories")
def list_categories():
    cats = Category.query.all()
    return jsonify([{"id": c.id, "name": c.name} for c in cats])


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8081, debug=False)
