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

PRODUCTS = [
    # Observability
    ("APM & Distributed Tracing",         150.00, 1, "https://picsum.photos/seed/dd1/400/300",  "End-to-end visibility across your entire distributed system with flame graphs, service maps, and trace search."),
    ("Continuous Profiler",                  4.00, 1, "https://picsum.photos/seed/dd2/400/300",  "Code-level performance insights in production. Pinpoint CPU, memory, and I/O bottlenecks without overhead."),
    ("Error Tracking",                      20.00, 1, "https://picsum.photos/seed/dd3/400/300",  None),  # BUG: NULL description triggers NoneType error
    ("Watchdog",                            10.00, 1, "https://picsum.photos/seed/dd4/400/300",  "AI-powered anomaly detection that surfaces issues before your users notice them."),
    # Infrastructure
    ("Infrastructure Monitoring",           15.00, 2, "https://picsum.photos/seed/dd5/400/300",  "Real-time metrics from 700+ integrations. Correlate infra health with app performance in one view."),
    ("Network Performance Monitoring",       5.00, 2, "https://picsum.photos/seed/dd6/400/300",  "Visualize network flows, latency, and errors between every service, host, and cloud region."),
    ("Database Monitoring",                 70.00, 2, "https://picsum.photos/seed/dd7/400/300",  "Query-level performance metrics, explain plans, and active session tracking for Postgres, MySQL, and more."),
    ("Container Monitoring",                 5.00, 2, "https://picsum.photos/seed/dd8/400/300",  "Full visibility into Docker, Kubernetes, and container orchestration. Live container map included."),
    # Security
    ("Cloud Security Management",            3.00, 3, "https://picsum.photos/seed/dd9/400/300",  "Detect misconfigurations, threats, and compliance violations across your cloud accounts in real time."),
    ("Application Security Management",      2.00, 3, "https://picsum.photos/seed/dd10/400/300", "Runtime protection against OWASP Top 10, injection attacks, and business logic abuse — zero rule writing."),
    ("Sensitive Data Scanner",              25.00, 3, "https://picsum.photos/seed/dd11/400/300", "Automatically detect and redact PII, secrets, and sensitive data flowing through your logs and traces."),
    # Log Management
    ("Log Management",                       0.10, 4, "https://picsum.photos/seed/dd12/400/300", "Ingest, process, and explore logs at any scale. Full correlation with APM traces and infrastructure metrics."),
    ("Audit Trail",                         25.00, 4, "https://picsum.photos/seed/dd13/400/300", "Immutable record of every action taken in your Datadog account. SOC2 and HIPAA compliance-ready."),
    # Synthetics & Testing
    ("Synthetic Monitoring",                 5.00, 5, "https://picsum.photos/seed/dd14/400/300", "Proactively simulate user journeys from 30+ global locations. API, browser, and multistep tests."),
    ("Real User Monitoring",                 1.50, 5, "https://picsum.photos/seed/dd15/400/300", "Capture every user interaction, page load, and frontend error. Session replay included."),
    ("Mobile RUM",                           1.50, 5, "https://picsum.photos/seed/dd16/400/300", "End-to-end monitoring for iOS and Android. Crash reporting, ANR tracking, and mobile session replay."),
    # Platform
    ("Incident Management",                 25.00, 6, "https://picsum.photos/seed/dd17/400/300", "Streamline on-call, incident declaration, and postmortem workflows. Integrates with PagerDuty and Slack."),
    ("CI Visibility",                       20.00, 6, "https://picsum.photos/seed/dd18/400/300", "Monitor CI/CD pipeline performance, flaky test detection, and test impact analysis across every branch."),
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
        for name, price, cat_idx, img, desc in PRODUCTS:
            p = Product(
                name=name,
                price=price,
                category_id=cat_list[cat_idx - 1].id,
                image_url=img,
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
