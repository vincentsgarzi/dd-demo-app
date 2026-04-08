"""
Datadog Marketplace Load Generator
Simulates realistic user traffic to generate APM traces, logs, and errors.
Run: python3 loadgen/loadgen.py
"""
import requests
import random
import time
import uuid
import sys

BASE = "http://localhost:8080/api"
USERS = ["alice@acme.com", "bob@globex.com", "carol@initech.com", "dave@umbrella.com", "eve@hooli.com"]
SEARCH_TERMS = ["monitoring", "APM", "logs", "infrastructure", "security", "synthetics", "tracing", "profiling", "RUM", "database"]

def session_headers():
    return {"X-Session-Id": f"loadgen-{uuid.uuid4().hex[:8]}", "Content-Type": "application/json"}

def browse_and_buy():
    """Simulates a user browsing, adding to cart, and checking out."""
    h = session_headers()
    try:
        # Browse products (triggers N+1 + potential AttributeError on product with NULL description)
        r = requests.get(f"{BASE}/products", headers=h, timeout=10)
        products = r.json() if r.ok else []
        print(f"  [browse] {len(products)} products listed | {r.status_code}")

        if not products:
            return

        # View a random product detail (product ending in 3 triggers ZeroDivisionError)
        p = random.choice(products)
        r = requests.get(f"{BASE}/products/{p['id']}", headers=h, timeout=10)
        print(f"  [product] id={p['id']} | {r.status_code}")

        # Sometimes hit the cursed product ID (ends in 3 → ZeroDivisionError)
        if random.random() < 0.2:
            r = requests.get(f"{BASE}/products/3", headers=h, timeout=10)
            print(f"  [cursed] products/3 | {r.status_code}")

        # Fetch recommendations (slow endpoint — 1-3s delay)
        r = requests.get(f"{BASE}/recommendations", headers=h, timeout=15)
        print(f"  [recs] {r.status_code} ({r.elapsed.total_seconds():.2f}s)")

        # Add 1-3 items to cart
        chosen = random.sample(products, min(random.randint(1, 3), len(products)))
        for item in chosen:
            requests.post(f"{BASE}/cart", headers=h, json={"product_id": item["id"], "quantity": 1}, timeout=5)

        # Checkout (15% failure rate baked in)
        email = random.choice(USERS)
        r = requests.post(f"{BASE}/checkout", headers=h, json={"email": email}, timeout=15)
        status = "✓ success" if r.ok else f"✗ {r.json().get('error', 'failed')}"
        print(f"  [checkout] {email} | {r.status_code} {status}")

    except Exception as e:
        print(f"  [error] {type(e).__name__}: {e}")

def search_traffic():
    """Simulates search queries (triggers slow unindexed LIKE queries)."""
    h = session_headers()
    q = random.choice(SEARCH_TERMS)
    try:
        r = requests.get(f"{BASE}/search", params={"q": q}, headers=h, timeout=10)
        print(f"  [search] q={q!r} | {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
    except Exception as e:
        print(f"  [search error] {e}")

def admin_traffic():
    """Occasionally hits the stats endpoint and CPU spike endpoint."""
    h = session_headers()
    try:
        r = requests.get(f"{BASE}/stats", headers=h, timeout=10)
        stats = r.json()
        print(f"  [admin] orders={stats.get('total_orders')} memory_leak_entries={stats.get('memory_leak_entries')}")

        # Occasionally trigger CPU spike
        if random.random() < 0.3:
            n = random.choice([10000, 30000, 50000, 80000])
            r = requests.get(f"{BASE}/compute", params={"n": n}, headers=h, timeout=60)
            print(f"  [cpu] n={n} | {r.elapsed.total_seconds():.2f}s")
    except Exception as e:
        print(f"  [admin error] {e}")

def run():
    print("Datadog Marketplace Load Generator starting... (Ctrl+C to stop)")
    print(f"Target: {BASE}\n")

    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

    iteration = 0
    while True:
        iteration += 1
        print(f"\n── Iteration {iteration} ──")

        action = random.choices(
            ["browse", "search", "admin"],
            weights=[70, 20, 10],
        )[0]

        if action == "browse":
            browse_and_buy()
        elif action == "search":
            search_traffic()
        elif action == "admin":
            admin_traffic()

        time.sleep(interval + random.uniform(-0.5, 1.0))

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped.")
