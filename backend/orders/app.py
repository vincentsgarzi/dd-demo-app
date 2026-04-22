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
from shared.logging import setup_logging
logger = setup_logging("orders")

# ── DogStatsD metrics ─────────────────────────────────────────────────────────
try:
    from datadog import initialize, statsd
    initialize(statsd_host=os.getenv("DD_AGENT_HOST", "localhost"), statsd_port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")))
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
    emit("ddstore.request.count", tags=[
        f"method:{request.method}", f"path:{request.path}", f"status:{response.status_code}",
    ])
    emit("ddstore.request.duration", duration_ms, tags=[f"path:{request.path}"])
    return response


# ── Error handler — ensures full stack trace on the root span ─────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled {type(e).__name__}: {e}", extra={
        "error_type": type(e).__name__, "error_message": str(e),
        "error_stack": traceback.format_exc(),
    })
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
        logger.info(f"Cart viewed — {len(items)} item(s), ${total:.2f} total", extra={
            "cart": {"session_id": session_id, "items": len(items), "total": round(total, 2)},
            "action": "cart_viewed",
        })
        return jsonify({"items": items, "total": round(total, 2), "count": len(items)})

    if request.method == "POST":
        data = request.json or {}
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)

        product = Product.query.get(product_id)
        if not product:
            logger.warning(f"Add to cart failed — product #{product_id} not found", extra={
                "cart": {"session_id": session_id}, "product": {"id": product_id},
                "action": "cart_product_not_found",
            })
            return jsonify({"error": "Product not found"}), 404

        cart_list = _carts.setdefault(session_id, [])
        for item in cart_list:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                new_total = sum(i["price"] * i["quantity"] for i in cart_list)
                logger.info(f"Cart updated — added {quantity} more \"{product.name}\" (now {item['quantity']}x), cart total ${new_total:.2f}", extra={
                    "cart": {"session_id": session_id, "items": len(cart_list), "total": round(new_total, 2)},
                    "product": {"id": product_id, "name": product.name, "price": product.price, "quantity": item["quantity"]},
                    "action": "cart_quantity_increased",
                })
                return jsonify({"message": "Updated", "cart": cart_list})

        cart_list.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": quantity,
            "image_url": product.image_url,
        })
        new_total = sum(i["price"] * i["quantity"] for i in cart_list)
        logger.info(f"Item added to cart — \"{product.name}\" x{quantity} (${product.price:.2f} each), cart now {len(cart_list)} item(s), ${new_total:.2f} total", extra={
            "cart": {"session_id": session_id, "items": len(cart_list), "total": round(new_total, 2)},
            "product": {"id": product.id, "name": product.name, "price": product.price, "quantity": quantity},
            "action": "cart_item_added",
        })
        emit("ddstore.cart.add", tags=[f"product:{product_id}"])
        return jsonify({"message": "Added", "cart": cart_list})

    if request.method == "DELETE":
        old_cart = _carts.pop(session_id, [])
        old_total = sum(i["price"] * i["quantity"] for i in old_cart)
        logger.info(f"Cart cleared — {len(old_cart)} item(s) removed, ${old_total:.2f} abandoned", extra={
            "cart": {"session_id": session_id, "items_removed": len(old_cart), "value_abandoned": round(old_total, 2)},
            "action": "cart_cleared",
        })
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
        logger.warning(f"Checkout attempted with empty cart by {user_email}", extra={
            "usr": {"email": user_email}, "action": "checkout_empty_cart",
        })
        return jsonify({"error": "Cart is empty"}), 400

    cart_total = sum(i["price"] * i["quantity"] for i in cart_items)
    item_names = [f"{i['name']} x{i['quantity']}" for i in cart_items]
    logger.info(f"Checkout started for {user_email} — {len(cart_items)} item(s), ${cart_total:.2f}: {', '.join(item_names)}", extra={
        "usr": {"email": user_email},
        "checkout": {"items": len(cart_items), "total": round(cart_total, 2), "product_names": item_names},
        "action": "checkout_started",
    })

    # ── Cross-service call: validate products via product service ─────────
    for item in cart_items:
        try:
            resp = http_client.get(
                f"{PRODUCT_SERVICE}/api/products/{item['product_id']}",
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"Product validation OK — \"{item['name']}\" (#{item['product_id']}) exists in catalog", extra={
                    "product": {"id": item["product_id"], "name": item["name"]},
                    "action": "product_validated",
                    "cross_service": {"target": "ddstore-products", "status": "ok"},
                })
            else:
                logger.warning(f"Product validation returned {resp.status_code} for \"{item['name']}\" — proceeding anyway (no validation)", extra={
                    "product": {"id": item["product_id"], "name": item["name"]},
                    "action": "product_validation_ignored",
                    "cross_service": {"target": "ddstore-products", "status_code": resp.status_code},
                })
        except Exception:
            pass  # BUG: intentionally ignores validation failures

    # BUG: simulate flaky payment gateway with retry storm
    payment_success = False
    attempts = 0
    for attempt in range(3):
        attempts += 1
        if random.random() > 0.15:
            payment_success = True
            logger.info(f"Payment authorized on attempt {attempts} for {user_email} — ${cart_total:.2f}", extra={
                "usr": {"email": user_email},
                "payment": {"attempt": attempts, "status": "authorized", "amount": round(cart_total, 2), "gateway": "stripe_sim"},
                "action": "payment_authorized",
            })
            break
        logger.warning(f"Payment attempt {attempts} DECLINED for {user_email} — retrying in 300ms (attempt {attempts}/3)", extra={
            "usr": {"email": user_email},
            "payment": {"attempt": attempts, "status": "declined", "amount": round(cart_total, 2), "gateway": "stripe_sim", "retry": True},
            "action": "payment_declined",
        })
        time.sleep(0.3)

    if span:
        span.set_tag("checkout.attempts", attempts)
        span.set_tag("checkout.success", payment_success)

    if not payment_success:
        # BUG: raises realistic payment processing exceptions
        error_scenario = random.choice(["pci", "idempotency", "fraud", "gateway"])

        def _submit_to_payment_processor(order_ref, amount, email):
            """Submit charge to payment processor via PCI-compliant tokenized flow."""

            if error_scenario == "pci":
                def _tokenize_card(vault_id, card_hash):
                    """Exchange card hash for single-use PCI token via Vault API."""
                    raise ConnectionError(
                        f"PCI Vault connection refused — vault.payments.internal:8443 "
                        f"returned TLS handshake failure (certificate expired 2h ago). "
                        f"Affected: all payment processing. Order ref: {order_ref}. "
                        f"Oncall paged at 14:32 UTC. Cert auto-renewal failed — "
                        f"ACME challenge DNS record was deleted during infra migration."
                    )
                _tokenize_card("vault-prod-us1", f"card_{hash(email) % 9999:04d}")

            elif error_scenario == "idempotency":
                def _check_idempotency(idempotency_key, amount):
                    """Verify this isn't a duplicate charge using idempotency store."""
                    raise ValueError(
                        f"IdempotencyConflict: key '{idempotency_key}' already exists "
                        f"with amount=${amount - random.uniform(5, 50):.2f} but current request "
                        f"has amount=${amount:.2f}. This indicates the cart was modified between "
                        f"payment attempts. Customer: {email}. First attempt was {random.randint(2, 8)}s ago. "
                        f"Request was rejected to prevent double-charging."
                    )
                _check_idempotency(f"idem_{hash(email) % 99999:05d}", amount)

            elif error_scenario == "fraud":
                def _evaluate_risk(transaction, model_version="fraud-rf-v7"):
                    """Score transaction against real-time fraud detection model."""
                    risk = random.uniform(0.82, 0.98)
                    raise PermissionError(
                        f"FraudDetection: transaction blocked — risk score {risk:.2f} exceeds "
                        f"threshold 0.80 (model: {model_version}). "
                        f"Signals: new email domain ({email.split('@')[1]}), "
                        f"cart value ${amount:.2f} is {random.uniform(2, 5):.1f}x above user's "
                        f"historical average, {random.randint(3, 7)} failed attempts in last hour. "
                        f"Customer has been added to review queue (case #FR-{random.randint(10000, 99999)})."
                    )
                _evaluate_risk({"email": email, "amount": amount})

            else:
                def _charge_via_gateway(provider, amount):
                    """Execute charge through payment gateway."""
                    raise TimeoutError(
                        f"Stripe API timeout after 5000ms on POST /v1/charges "
                        f"(amount=${amount:.2f}, currency=usd). "
                        f"Stripe status page reports degraded performance in us-east-1. "
                        f"Circuit breaker state: OPEN (failures: 23/25 in last 60s). "
                        f"Retry budget exhausted — 0 of 3 retries remaining."
                    )
                _charge_via_gateway("stripe", amount)

        _submit_to_payment_processor(f"ORD-{random.randint(10000, 99999)}", cart_total, user_email)

    # BUG: 6% chance of distributed lock contention during checkout
    if random.random() < 0.06:
        def _reserve_inventory(items, lock_ttl_ms=5000):
            """Acquire distributed lock on inventory rows to prevent oversell."""
            def _acquire_redis_lock(lock_key, ttl_ms):
                """Acquire Redlock across 3 Redis nodes for distributed consensus."""
                product_name = random.choice([i["name"] for i in cart_items]) if cart_items else "Unknown"
                holder = f"checkout-worker-{random.randint(1, 8)}"
                raise TimeoutError(
                    f"DistributedLockTimeout: failed to acquire lock '{lock_key}' "
                    f"within {ttl_ms}ms — held by '{holder}' for {random.randint(6, 30)}s "
                    f"(expected max hold time: 5s). Product '{product_name}' has "
                    f"{random.randint(12, 50)} concurrent checkout attempts. "
                    f"Redis cluster latency p99={random.randint(80, 400)}ms (normal: <10ms). "
                    f"Lock queue depth: {random.randint(8, 25)} waiters. "
                    f"Possible cause: Redis primary failover in progress."
                )
            product_id = items[0]["product_id"] if items else 0
            _acquire_redis_lock(f"inventory:lock:product:{product_id}", lock_ttl_ms)

        _reserve_inventory(cart_items)

    # Create order
    user = User.query.filter_by(email=user_email).first()
    if not user:
        user = User(email=user_email, name=user_email.split("@")[0].title())
        db.session.add(user)
        db.session.flush()
        logger.info(f"New customer created — {user.name} ({user_email})", extra={
            "usr": {"id": user.id, "email": user_email, "name": user.name},
            "action": "user_created",
        })

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
            old_stock = product.stock
            product.stock -= item["quantity"]
            if product.stock < 0:
                logger.error(f"OVERSOLD \"{product.name}\" — stock went from {old_stock} to {product.stock} (negative!)", extra={
                    "product": {"id": product.id, "name": product.name, "old_stock": old_stock, "new_stock": product.stock},
                    "order": {"id": order.id},
                    "action": "stock_oversold",
                    "bug": "no_stock_validation",
                })
            elif old_stock <= 10:
                logger.warning(f"Low stock alert — \"{product.name}\" now at {product.stock} units (was {old_stock})", extra={
                    "product": {"id": product.id, "name": product.name, "old_stock": old_stock, "new_stock": product.stock},
                    "action": "low_stock_warning",
                })

    db.session.commit()
    _carts.pop(session_id, None)

    emit("ddstore.checkout.success", tags=[f"items:{len(cart_items)}"])
    emit("ddstore.revenue", total)
    logger.info(f"Order #{order.id} CONFIRMED for {user_email} — ${total:.2f}, {len(cart_items)} item(s), paid on attempt {attempts}", extra={
        "usr": {"email": user_email, "name": user.name},
        "order": {"id": order.id, "total": round(total, 2), "items": len(cart_items), "status": "confirmed"},
        "checkout": {"attempts": attempts, "success": True},
        "payment": {"final_status": "authorized", "gateway": "stripe_sim"},
        "action": "order_confirmed",
    })

    return jsonify({"order_id": order.id, "total": round(total, 2), "status": "confirmed"})


@app.route("/api/orders")
def list_orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    logger.info(f"Order history loaded — {len(orders)} recent orders", extra={
        "orders": {"count": len(orders), "limit": 50},
        "action": "orders_listed",
    })
    return jsonify([o.to_dict() for o in orders])


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8082, debug=False)
