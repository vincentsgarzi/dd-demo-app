"""
Datadog Marketplace — API Gateway
Thin routing proxy that forwards requests to downstream microservices.
Creates a gateway node in the Datadog Service Map with distributed traces.
"""
import os
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
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = Flask(__name__)
CORS(
    app,
    origins=["http://localhost:5173", "http://localhost:3000"],
    allow_headers=["Content-Type", "X-Session-Id", "x-datadog-trace-id", "x-datadog-parent-id",
                    "x-datadog-origin", "x-datadog-sampling-priority", "traceparent", "tracestate"],
    expose_headers=["x-datadog-trace-id", "x-datadog-parent-id", "traceparent", "tracestate"],
)

# ── Service URLs ──────────────────────────────────────────────────────────────
PRODUCT_SVC = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8081")
ORDER_SVC = os.getenv("ORDER_SERVICE_URL", "http://localhost:8082")
ANALYTICS_SVC = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8083")

# ── Structured logging ────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logging import setup_logging
logger = setup_logging("gateway")

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
    # Map paths to service names for log context
    svc = "unknown"
    if request.path.startswith(("/api/products", "/api/search", "/api/recommendations", "/api/categories")):
        svc = "ddstore-products"
    elif request.path.startswith(("/api/cart", "/api/checkout", "/api/orders")):
        svc = "ddstore-orders"
    elif request.path.startswith(("/api/stats", "/api/compute")):
        svc = "ddstore-analytics"

    logger.info(f"Routed {request.method} {request.path} → {svc} — {response.status_code} in {duration_ms:.1f}ms", extra={
        "http": {"method": request.method, "url": request.path, "status_code": response.status_code},
        "duration_ms": round(duration_ms, 1),
        "routing": {"target_service": svc},
        "action": "request_routed",
    })
    emit("ddstore.gateway.request.count", tags=[
        f"method:{request.method}", f"path:{request.path}", f"status:{response.status_code}",
    ])
    return response


# ── Error handler — ensures full stack trace on the root span ─────────────
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled {type(e).__name__}: {e}", extra={
        "error_type": type(e).__name__, "error_message": str(e),
        "error_stack": traceback.format_exc(),
    })
    return jsonify({"error": type(e).__name__, "message": str(e)}), 500


# ── Proxy helper ──────────────────────────────────────────────────────────────
def _forward_headers():
    """Forward relevant headers from the incoming request to the downstream service."""
    headers = {"Content-Type": request.content_type or "application/json"}
    session_id = request.headers.get("X-Session-Id")
    if session_id:
        headers["X-Session-Id"] = session_id
    return headers


_request_counts = {}

def _proxy(service_base, path):
    """Proxy the current request to a downstream service. ddtrace auto-instruments
    the outgoing requests call, propagating trace context."""
    url = f"{service_base}{path}"

    # BUG: 3% chance of request validation error on POST/PUT
    if request.method in ("POST", "PUT") and random.random() < 0.03:
        def _validate_request_schema(method, path, body):
            """Validate incoming request against OpenAPI schema."""
            def _check_content_type(headers):
                """Ensure Content-Type matches expected schema."""
                raise TypeError(f"Request body validation failed: expected 'application/json; charset=utf-8' but got '{headers.get('Content-Type', 'None')}' for {method} {path}")
            _check_content_type(request.headers)
        _validate_request_schema(request.method, path, request.get_data())
    try:
        resp = http_client.request(
            method=request.method,
            url=url,
            params=request.args,
            data=request.get_data(),
            headers=_forward_headers(),
            timeout=60,
        )

        # Don't manually tag spans with downstream errors — the downstream service's
        # trace already has the error on the correct span. ddtrace propagates error
        # status automatically. Manual tagging creates confusing duplicates.

        return (resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except http_client.exceptions.ConnectionError:
        # ddtrace auto-tags the requests span with the ConnectionError
        logger.error(f"Downstream service unavailable: {url}", extra={
            "downstream": {"url": url, "error": "ConnectionError"},
        })
        return jsonify({"error": "ConnectionError", "message": f"Service unavailable: {url}"}), 503
    except http_client.exceptions.Timeout:
        # ddtrace auto-tags the requests span with the Timeout
        logger.error(f"Downstream service timeout: {url}", extra={
            "downstream": {"url": url, "error": "Timeout"},
        })
        return jsonify({"error": "TimeoutError", "message": f"Service timeout: {url}"}), 504


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Product Service
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/products")
def proxy_products():
    return _proxy(PRODUCT_SVC, "/api/products")


@app.route("/api/products/<int:product_id>")
def proxy_product(product_id):
    return _proxy(PRODUCT_SVC, f"/api/products/{product_id}")


@app.route("/api/search")
def proxy_search():
    return _proxy(PRODUCT_SVC, "/api/search")


@app.route("/api/recommendations")
def proxy_recommendations():
    return _proxy(PRODUCT_SVC, "/api/recommendations")


@app.route("/api/categories")
def proxy_categories():
    return _proxy(PRODUCT_SVC, "/api/categories")


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Order Service
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/cart", methods=["GET", "POST", "DELETE"])
def proxy_cart():
    return _proxy(ORDER_SVC, "/api/cart")


@app.route("/api/checkout", methods=["POST"])
def proxy_checkout():
    return _proxy(ORDER_SVC, "/api/checkout")


@app.route("/api/orders")
def proxy_orders():
    return _proxy(ORDER_SVC, "/api/orders")


# ─────────────────────────────────────────────────────────────────────────────
# Routes — Analytics Service
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def proxy_stats():
    return _proxy(ANALYTICS_SVC, "/api/stats")


@app.route("/api/compute")
def proxy_compute():
    return _proxy(ANALYTICS_SVC, "/api/compute")


# ─────────────────────────────────────────────────────────────────────────────
# Health — composite check across all downstream services
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    services = {
        "ddstore-products": PRODUCT_SVC,
        "ddstore-orders": ORDER_SVC,
        "ddstore-analytics": ANALYTICS_SVC,
    }
    results = {"gateway": "ok"}
    all_ok = True
    for name, url in services.items():
        try:
            resp = http_client.get(f"{url}/api/health", timeout=3)
            results[name] = "ok" if resp.status_code == 200 else "degraded"
        except Exception:
            results[name] = "down"
            all_ok = False

    status = "ok" if all_ok else "degraded"
    return jsonify({"status": status, "services": results}), 200 if all_ok else 207


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
