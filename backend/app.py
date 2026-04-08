"""
Datadog Marketplace — Flask API
Intentional bugs & performance issues for Datadog demo purposes.
"""
import os
import time
import random
import threading
import logging
import json
from datetime import datetime

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv

# ── Datadog APM — must be first ──────────────────────────────────────────────
from ddtrace import tracer, patch_all

patch_all()  # auto-instruments Flask, SQLAlchemy, requests, etc.

# ── App setup ─────────────────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://localhost:3000"])
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL environment variable is not set. Copy backend/.env.example to backend/.env and fill in your values.")
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False

from models import db, Category, Product, User, Order, OrderItem
db.init_app(app)

# ── Structured logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "dd.trace_id": "%(dd.trace_id)s", "dd.span_id": "%(dd.span_id)s"}',
)
logger = logging.getLogger("ddstore")

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
        # Each iteration appends ~10KB of data and never clears it
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
    g.start = time.time()

@app.after_request
def log_request(response):
    duration_ms = (time.time() - g.start) * 1000
    logger.info(
        f"{request.method} {request.path} {response.status_code} {duration_ms:.1f}ms"
    )
    emit("ddstore.request.count", tags=[
        f"method:{request.method}",
        f"path:{request.path}",
        f"status:{response.status_code}",
    ])
    emit("ddstore.request.duration", duration_ms, tags=[f"path:{request.path}"])
    return response

# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "ddstore-api", "time": datetime.utcnow().isoformat()})


@app.route("/api/products")
def list_products():
    """
    BUG (N+1): iterates products and calls .to_dict_with_category() on each,
    which triggers a separate SQL query per product to load category + causes
    AttributeError when description is None (product id=6).
    """
    span = tracer.current_span()
    if span:
        span.set_tag("products.source", "database")

    products = Product.query.all()  # 1 query

    result = []
    for p in products:
        # N+1: each iteration fires a SELECT on categories + a potential error
        try:
            result.append(p.to_dict_with_category())  # fires extra query + potential NoneType
        except AttributeError as e:
            # BUG: silently swallowed — but the error still shows in Datadog Error Tracking
            logger.error(f"Failed to serialize product {p.id}: {e}")
            emit("ddstore.error", tags=["type:serialization", f"product_id:{p.id}"])
            result.append({**p.to_dict(), "category": "Unknown", "description_preview": ""})

    emit("ddstore.products.listed", len(result))
    return jsonify(result)


@app.route("/api/products/<int:product_id>")
def get_product(product_id):
    """
    BUG: product_id=13 is a 'cursed' ID — throws a deliberate unhandled division error
    to simulate a real application bug that slips past review.
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
    In production this might be an ML inference call or a complex join.
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


@app.route("/api/cart", methods=["GET", "POST", "DELETE"])
def cart():
    """In-memory cart (keyed by session header). Not persistent — intentional simplification."""
    session_id = request.headers.get("X-Session-Id", "anonymous")

    if request.method == "GET":
        items = _carts.get(session_id, [])
        total = sum(i["price"] * i["quantity"] for i in items)
        return jsonify({"items": items, "total": round(total, 2), "count": len(items)})

    if request.method == "POST":
        data = request.json or {}
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)

        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404

        cart = _carts.setdefault(session_id, [])
        # Check if already in cart
        for item in cart:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                return jsonify({"message": "Updated", "cart": cart})

        cart.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": quantity,
            "image_url": product.image_url,
        })
        emit("ddstore.cart.add", tags=[f"product:{product_id}"])
        return jsonify({"message": "Added", "cart": cart})

    if request.method == "DELETE":
        _carts.pop(request.headers.get("X-Session-Id", "anonymous"), None)
        return jsonify({"message": "Cart cleared"})

# In-memory cart store (intentionally not Redis — another "bug" for the demo)
_carts = {}


@app.route("/api/checkout", methods=["POST"])
def checkout():
    """
    BUG: 15% random failure rate simulating downstream payment service flakiness.
    BUG: On failure it retries internally 3x — causing 4x the DB load on error paths.
    BUG: Does not validate stock levels before decrementing.
    """
    session_id = request.headers.get("X-Session-Id", "anonymous")
    data = request.json or {}
    user_email = data.get("email", "guest@example.com")

    span = tracer.current_span()
    if span:
        span.set_tag("checkout.user", user_email)

    cart_items = _carts.get(session_id, [])
    if not cart_items:
        return jsonify({"error": "Cart is empty"}), 400

    # BUG: simulate flaky payment gateway with retry storm
    payment_success = False
    attempts = 0
    for attempt in range(3):  # BUG: retries silently
        attempts += 1
        if random.random() > 0.15:  # 85% success per attempt
            payment_success = True
            break
        time.sleep(0.3)  # BUG: blocking retry wait on web thread

    if span:
        span.set_tag("checkout.attempts", attempts)
        span.set_tag("checkout.success", payment_success)

    if not payment_success:
        error_types = [
            "PaymentDeclinedException",
            "GatewayTimeoutError",
            "InsufficientFundsError",
            "FraudDetectionTriggered",
        ]
        err = random.choice(error_types)
        logger.error(f"Checkout failed after {attempts} attempts: {err} for {user_email}")
        emit("ddstore.checkout.failure", tags=[f"error:{err}"])
        return jsonify({"error": err, "message": "Payment failed. Please try again."}), 502

    # Create order
    user = User.query.filter_by(email=user_email).first()
    if not user:
        user = User(email=user_email, name=user_email.split("@")[0].title())
        db.session.add(user)
        db.session.flush()

    total = sum(i["price"] * i["quantity"] for i in cart_items)
    order = Order(user_id=user.id, total=round(total, 2), status="confirmed")
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        # BUG: no stock check — can oversell
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            price=item["price"],
        ))
        # BUG: decrement stock without checking if > 0
        product = Product.query.get(item["product_id"])
        if product:
            product.stock -= item["quantity"]

    db.session.commit()
    _carts.pop(session_id, None)

    emit("ddstore.checkout.success", tags=[f"items:{len(cart_items)}"])
    emit("ddstore.revenue", total)
    logger.info(f"Order {order.id} confirmed for {user_email}, total=${total:.2f}")

    return jsonify({"order_id": order.id, "total": round(total, 2), "status": "confirmed"})


@app.route("/api/orders")
def list_orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    return jsonify([o.to_dict() for o in orders])


@app.route("/api/categories")
def list_categories():
    cats = Category.query.all()
    return jsonify([{"id": c.id, "name": c.name} for c in cats])


@app.route("/api/compute")
def cpu_spike():
    """
    BUG (CPU): Intentional CPU-intensive endpoint — naive prime sieve with no caching.
    Simulates a poorly-optimized computation that should be cached or async.
    """
    n = int(request.args.get("n", 50000))
    n = min(n, 500_000)  # cap to avoid total meltdown

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


@app.route("/api/stats")
def stats():
    """Dashboard stats — runs several unoptimized aggregate queries."""
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8080, debug=False)
