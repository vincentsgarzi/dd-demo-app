"""
Datadog Marketplace — Order Service
Handles cart, checkout, and order history.
Intentional bugs preserved for Datadog demo purposes.
"""
import os
import sys
import time
import random
import logging
import traceback
import requests as http_client

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

from shared.models import db, Product, User, Order, OrderItem

db.init_app(app)

# ── Service URLs ──────────────────────────────────────────────────────────────
PRODUCT_SERVICE = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8081")

# ── Structured logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "dd.trace_id": "%(dd.trace_id)s", "dd.span_id": "%(dd.span_id)s"}',
)
logger = logging.getLogger("ddstore.orders")

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


# In-memory cart store (intentionally not Redis — another "bug" for the demo)
_carts = {}

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
    return jsonify({"status": "ok", "service": "ddstore-orders"})


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

    # ── Cross-service call: validate products via product service ─────────
    # Creates distributed trace: orders → products
    for item in cart_items:
        try:
            http_client.get(
                f"{PRODUCT_SERVICE}/api/products/{item['product_id']}",
                timeout=5,
            )
        except Exception:
            pass  # BUG: intentionally ignores validation failures

    # BUG: simulate flaky payment gateway with retry storm
    payment_success = False
    attempts = 0
    for attempt in range(3):
        attempts += 1
        if random.random() > 0.15:
            payment_success = True
            break
        time.sleep(0.3)

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
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            price=item["price"],
        ))
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


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8082, debug=False)
