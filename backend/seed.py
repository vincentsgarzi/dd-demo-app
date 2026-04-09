"""Seed the Datadog Marketplace database."""
from app import app
from models import db, Category, Product, User, Order, OrderItem
from datetime import datetime, timedelta
import random

CATEGORIES = [
    "Observability",
    "Infrastructure",
    "Security",
    "Log Management",
    "Synthetics & Testing",
    "Platform",
]

# Pricing is modeled as $/host/month to look like real SaaS subscription pricing.
# image_url stores a color hex used for the product card gradient background.
PRODUCTS = [
    # Observability
    ("APM & Distributed Tracing",         31.00, 1, "#7B61FF", "End-to-end distributed tracing with flame graphs, service maps, and automatic instrumentation for 200+ frameworks."),
    ("Continuous Profiler",               12.00, 1, "#9B7BFF", "Always-on, low-overhead code profiling in production. Pinpoint CPU, memory, and I/O hotspots down to the line of code."),
    ("Error Tracking",                    15.00, 1, "#6C4FDB", None),  # BUG: NULL description triggers NoneType error
    ("Watchdog",                           0.00, 1, "#8B6BFF", "AI-powered anomaly detection that automatically surfaces issues across metrics, traces, and logs — no configuration required."),
    # Infrastructure
    ("Infrastructure Monitoring",         23.00, 2, "#FF6B6B", "Real-time metrics from 750+ integrations. Auto-discovery, tagging, and correlation with application performance data."),
    ("Network Performance Monitoring",    10.00, 2, "#FF8787", "Map every network flow between services, hosts, and cloud regions. Detect retransmits, latency, and DNS issues."),
    ("Database Monitoring",               70.00, 2, "#E85D5D", "Query-level performance metrics, explain plans, blocking queries, and active session monitoring for Postgres, MySQL, SQL Server, and more."),
    ("Container Monitoring",              15.00, 2, "#FF7B7B", "Full visibility into Kubernetes clusters, Docker containers, and orchestration. Live container map and resource utilization."),
    # Security
    ("Cloud Security Management",         12.00, 3, "#4ECDC4", "Continuous posture management and threat detection across AWS, Azure, and GCP. 500+ out-of-the-box compliance rules."),
    ("Application Security Management",   31.00, 3, "#45B7AA", "Runtime threat detection and blocking for OWASP Top 10 — SQL injection, XSS, SSRF, and more. No WAF rules to write."),
    ("Sensitive Data Scanner",            18.00, 3, "#38A89D", "Automatically detect and redact PII, API keys, and secrets flowing through logs, traces, and events before they're stored."),
    # Log Management
    ("Log Management",                     1.70, 4, "#F7B731", "Ingest, process, archive, and rehydrate logs at any scale. Full correlation with APM traces and infrastructure metrics."),
    ("Audit Trail",                       10.00, 4, "#F5A623", "Immutable, tamper-proof record of every action in your Datadog organization. SOC 2, HIPAA, and FedRAMP ready."),
    # Synthetics & Testing
    ("Synthetic Monitoring",               5.00, 5, "#26DE81", "Proactive uptime monitoring from 30+ global locations. API tests, browser tests, and multi-step transaction recording."),
    ("Real User Monitoring",               1.50, 5, "#2BCB71", "Capture every user session — page loads, clicks, errors, and Core Web Vitals. Session Replay included at no extra cost."),
    ("Mobile RUM",                         1.50, 5, "#20BF6B", "End-to-end mobile monitoring for iOS and Android. Crash reporting, ANR tracking, and mobile-specific session replay."),
    # Platform
    ("Incident Management",                0.00, 6, "#4B7BEC", "Declare, manage, and resolve incidents from a single pane. Integrates with PagerDuty, Slack, Jira, and 40+ tools."),
    ("CI Visibility",                     20.00, 6, "#3867D6", "Pipeline analytics, flaky test detection, and test impact analysis. See which commits broke the build and why."),
]

USERS = [
    ("alice@acme.com",      "Alice Johnson"),
    ("bob@globex.com",      "Bob Smith"),
    ("carol@initech.com",   "Carol Williams"),
    ("dave@umbrella.com",   "Dave Brown"),
    ("eve@hooli.com",       "Eve Davis"),
]

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        cats = {}
        for name in CATEGORIES:
            c = Category(name=name)
            db.session.add(c)
            db.session.flush()
            cats[name] = c

        cat_list = list(cats.values())

        products = []
        for name, price, cat_idx, color, desc in PRODUCTS:
            p = Product(
                name=name,
                price=price,
                category_id=cat_list[cat_idx - 1].id,
                image_url=color,
                description=desc,
                stock=random.randint(5, 999),
            )
            db.session.add(p)
            products.append(p)

        users = []
        for email, name in USERS:
            u = User(email=email, name=name)
            db.session.add(u)
            users.append(u)

        db.session.flush()

        statuses = ["completed", "completed", "completed", "shipped", "pending"]
        for i in range(30):
            user = random.choice(users)
            num_items = random.randint(1, 3)
            items = random.sample(products, num_items)
            total = sum(p.price * random.randint(1, 5) for p in items)
            order = Order(
                user_id=user.id,
                total=round(total, 2),
                status=random.choice(statuses),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
            )
            db.session.add(order)
            db.session.flush()
            for p in items:
                qty = random.randint(1, 5)
                db.session.add(OrderItem(
                    order_id=order.id,
                    product_id=p.id,
                    quantity=qty,
                    price=p.price,
                ))

        db.session.commit()
        print(f"Seeded {len(PRODUCTS)} products across {len(CATEGORIES)} categories, {len(USERS)} users, 30 orders.")

if __name__ == "__main__":
    seed()
