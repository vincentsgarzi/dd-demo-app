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
    emit("ddstore.request.count", tags=[
        f"method:{request.method}", f"path:{request.path}", f"status:{response.status_code}",
    ])
    emit("ddstore.request.duration", duration_ms, tags=[f"path:{request.path}"])
    return response


# ── Error handler — ensures full stack trace on the root span ─────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    for span in [tracer.current_span(), tracer.current_root_span()]:
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
    logger.info(f"Loading product catalog — {len(products)} products from database", extra={
        "catalog": {"product_count": len(products), "source": "database"},
    })

    result = []
    serialization_errors = 0
    for p in products:
        try:
            result.append(p.to_dict_with_category())
        except AttributeError as e:
            serialization_errors += 1
            logger.error(f"Product #{p.id} ({p.name}) has corrupt data — description is NULL, .upper() failed", extra={
                "product": {"id": p.id, "name": p.name, "category_id": p.category_id},
                "error_type": "NullDescriptionBug",
            })
            emit("ddstore.error", tags=["type:serialization", f"product_id:{p.id}"])
            result.append({**p.to_dict(), "category": "Unknown", "description_preview": ""})

    if serialization_errors:
        logger.warning(f"Catalog loaded with {serialization_errors} serialization error(s) — products served with fallback data", extra={
            "catalog": {"total": len(result), "errors": serialization_errors},
        })

    logger.info(f"Catalog response ready — {len(result)} products, {len(products)} individual DB queries (N+1 detected)", extra={
        "catalog": {"total": len(result), "db_queries": len(products) + 1},
        "performance": {"pattern": "N+1", "expected_queries": 1, "actual_queries": len(products) + 1},
    })

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
        logger.error(f"Cursed product ID {product_id} triggered discount calculation bug — dividing by zero", extra={
            "product": {"id": product_id}, "bug": "ZeroDivisionError",
        })
        discount = 100 / (product_id - product_id)  # ZeroDivisionError

    product = Product.query.get_or_404(product_id)
    logger.info(f"Product lookup: \"{product.name}\" (${product.price:.2f}, {product.stock} in stock)", extra={
        "product": {"id": product.id, "name": product.name, "price": product.price, "stock": product.stock, "category_id": product.category_id},
    })
    return jsonify(product.to_dict_with_category())


@app.route("/api/search")
def search_products():
    """
    BUG (slow query): Uses LIKE '%term%' with no index — full table scan.
    Also has an artificial sleep to simulate DB connection wait.
    BUG: 8% chance of SearchIndexCorruptionError — simulates Elasticsearch index corruption.
    """
    q = request.args.get("q", "")
    if not q:
        return jsonify([])

    span = tracer.current_span()
    if span:
        span.set_tag("search.query", q)
        span.set_tag("db.statement", f"SELECT * FROM products WHERE name LIKE '%{q}%'")

    logger.info(f"Search initiated for \"{q}\" — using unindexed LIKE query (full table scan)", extra={
        "search": {"query": q, "strategy": "LIKE_unindexed", "index_used": False},
    })

    # BUG: intermittent search index corruption
    if random.random() < 0.08:
        def _rebuild_index(query):
            """Attempt to rebuild corrupted search index shard."""
            shard_id = hash(query) % 5
            raise RuntimeError(f"Search index shard {shard_id} is corrupted — rebuild failed for query '{query}'")

        def _execute_search(query):
            """Execute search against index, falling back to rebuild on corruption."""
            _rebuild_index(query)

        _execute_search(q)  # raises SearchIndexCorruptionError with deep stack

    # BUG: artificial connection pool wait
    pool_wait = random.uniform(0.2, 0.8)
    time.sleep(pool_wait)
    logger.warning(f"Connection pool starved — waited {pool_wait*1000:.0f}ms for available connection", extra={
        "search": {"query": q},
        "db": {"pool_wait_ms": round(pool_wait * 1000, 1), "pool_exhausted": pool_wait > 0.5},
    })

    # BUG: unindexed LIKE query
    products = Product.query.filter(
        Product.name.ilike(f"%{q}%") | Product.description.ilike(f"%{q}%")
    ).all()

    logger.info(f"Search for \"{q}\" returned {len(products)} result(s)", extra={
        "search": {"query": q, "results": len(products), "pool_wait_ms": round(pool_wait * 1000, 1)},
    })

    emit("ddstore.search.count", tags=[f"results:{len(products)}"])
    return jsonify([p.to_dict() for p in products])


@app.route("/api/recommendations")
def recommendations():
    """
    BUG (slow): Simulates a recommendation engine that takes too long.
    BUG: 5% chance of TimeoutError from ML model inference.
    """
    span = tracer.current_span()

    # BUG: slow — 1-3 second artificial delay every time
    delay = random.uniform(1.0, 3.0)
    if span:
        span.set_tag("recommendation.delay_ms", int(delay * 1000))

    logger.warning(f"Recommendation engine starting — estimated {delay*1000:.0f}ms inference time", extra={
        "recommendations": {"estimated_delay_ms": round(delay * 1000)},
    })

    time.sleep(delay)

    # BUG: ML model inference timeout
    if random.random() < 0.05:
        def _load_model_weights(model_version):
            """Load recommendation model weights from disk."""
            raise MemoryError(f"Cannot allocate tensor for model v{model_version} — OOM during inference (requires 2.1GB, available 1.8GB)")

        def _run_inference(product_ids):
            """Run recommendation model inference on product embeddings."""
            _load_model_weights("3.2.1")

        _run_inference([1, 2, 3])

    # BUG: inefficient — loads ALL products into memory, shuffles, slices in Python
    all_products = Product.query.all()
    random.shuffle(all_products)
    recommended = all_products[:4]

    rec_names = [p.name for p in recommended]
    logger.info(f"Recommendations ready — loaded all {len(all_products)} products into memory, shuffled, picked 4 (took {delay*1000:.0f}ms)", extra={
        "recommendations": {
            "delay_ms": round(delay * 1000),
            "products_loaded": len(all_products),
            "results": rec_names,
            "strategy": "random_shuffle_in_memory",
        },
    })

    return jsonify([p.to_dict() for p in recommended])


@app.route("/api/categories")
def list_categories():
    cats = Category.query.all()
    logger.info(f"Categories loaded: {', '.join(c.name for c in cats)}", extra={
        "categories": {"count": len(cats), "names": [c.name for c in cats]},
    })
    return jsonify([{"id": c.id, "name": c.name} for c in cats])


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8081, debug=False)
