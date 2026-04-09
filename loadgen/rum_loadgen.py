#!/usr/bin/env python3
"""
RUM Load Generator — Playwright headless browsers simulating real user sessions.

Each user persona has different behaviors, speeds, devices, and error propensity.
Generates real RUM sessions with views, actions, errors, long tasks, resources,
frustration signals, custom actions, and varied session lengths.

Usage:
    python rum_loadgen.py                  # default: 3 concurrent users
    python rum_loadgen.py --users 5        # 5 concurrent browsers
    python rum_loadgen.py --users 2 --headful  # visible browsers for debugging
"""

import asyncio
import random
import argparse
import signal
import sys
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"

# ─── User Personas ───────────────────────────────────────────────────────────
# Each persona represents a distinct user archetype with unique behavior patterns.
# RUM will show these as separate users with tagged attributes.

PERSONAS = [
    {
        "name": "Alice Chen",
        "email": "alice.chen@acme.com",
        "role": "power_user",
        "plan": "enterprise",
        "company": "Acme Corp",
        "company_size": "10000+",
        "speed": "fast",
        "patience": 0.95,
        "error_prone": False,
        "viewport": {"width": 1440, "height": 900},
        "device": "MacBook Pro",
        "journeys": ["full_purchase", "search_and_buy", "full_purchase", "compare_products", "deep_browse"],
        "user_agent": None,
    },
    {
        "name": "Bob Martinez",
        "email": "bob.martinez@globex.com",
        "role": "admin",
        "plan": "enterprise",
        "company": "Globex Corp",
        "company_size": "5000+",
        "speed": "fast",
        "patience": 0.95,
        "error_prone": False,
        "viewport": {"width": 1920, "height": 1080},
        "device": "Desktop Windows",
        "journeys": ["full_purchase", "admin_deep_dive", "search_and_buy", "full_purchase", "orders_review"],
        "user_agent": None,
    },
    {
        "name": "Charlie Kim",
        "email": "charlie.kim@initech.com",
        "role": "casual_browser",
        "plan": "free",
        "company": "Initech",
        "company_size": "50-200",
        "speed": "slow",
        "patience": 0.4,
        "error_prone": False,
        "viewport": {"width": 1366, "height": 768},
        "device": "Chromebook",
        "journeys": ["window_shop", "search_browse", "abandon_cart", "window_shop", "bounce"],
        "user_agent": None,
    },
    {
        "name": "Dana Park",
        "email": "dana.park@waynetech.com",
        "role": "qa_tester",
        "plan": "pro",
        "company": "Wayne Technologies",
        "company_size": "1000+",
        "speed": "medium",
        "patience": 0.7,
        "error_prone": True,
        "viewport": {"width": 1280, "height": 800},
        "device": "ThinkPad",
        "journeys": ["trigger_errors", "rage_click_session", "trigger_errors", "search_edge_cases", "error_recovery_flow"],
        "user_agent": None,
    },
    {
        "name": "Mo Hassan",
        "email": "mo@startup.io",
        "role": "mobile_user",
        "plan": "pro",
        "company": "StartupIO",
        "company_size": "10-50",
        "speed": "medium",
        "patience": 0.3,
        "error_prone": False,
        "viewport": {"width": 390, "height": 844},
        "device": "iPhone 15 Pro",
        "journeys": ["mobile_quick_buy", "mobile_browse_and_bounce", "mobile_quick_buy", "mobile_scroll_heavy"],
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    },
    {
        "name": "Tina Tabsworth",
        "email": "tina.tabs@megacorp.com",
        "role": "power_user",
        "plan": "enterprise",
        "company": "MegaCorp",
        "company_size": "50000+",
        "speed": "fast",
        "patience": 0.85,
        "error_prone": False,
        "viewport": {"width": 2560, "height": 1440},
        "device": "iMac 27in",
        "journeys": ["multi_tab_browse", "full_purchase", "compare_products", "deep_browse"],
        "user_agent": None,
    },
    {
        "name": "Priya Sharma",
        "email": "priya.sharma@techflow.dev",
        "role": "developer",
        "plan": "pro",
        "company": "TechFlow",
        "company_size": "200-500",
        "speed": "fast",
        "patience": 0.8,
        "error_prone": False,
        "viewport": {"width": 1440, "height": 900},
        "device": "MacBook Air M2",
        "journeys": ["search_and_buy", "admin_deep_dive", "full_purchase", "search_browse"],
        "user_agent": None,
    },
    {
        "name": "Raj Patel",
        "email": "raj@bigsales.io",
        "role": "sales_rep",
        "plan": "enterprise",
        "company": "BigSales",
        "company_size": "500-1000",
        "speed": "fast",
        "patience": 0.6,
        "error_prone": False,
        "viewport": {"width": 1536, "height": 864},
        "device": "Surface Pro",
        "journeys": ["full_purchase", "full_purchase", "full_purchase", "compare_products", "orders_review"],
        "user_agent": None,
    },
    {
        "name": "Sam Rivera",
        "email": "sam.rivera@tablet.user",
        "role": "casual_browser",
        "plan": "free",
        "company": "Personal",
        "company_size": "1",
        "speed": "slow",
        "patience": 0.35,
        "error_prone": False,
        "viewport": {"width": 768, "height": 1024},
        "device": "iPad Air",
        "journeys": ["window_shop", "bounce", "mobile_scroll_heavy", "abandon_cart"],
        "user_agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    },
    {
        "name": "Eve Nakamura",
        "email": "eve.n@securecorp.net",
        "role": "security_analyst",
        "plan": "enterprise",
        "company": "SecureCorp",
        "company_size": "2000+",
        "speed": "medium",
        "patience": 0.9,
        "error_prone": True,
        "viewport": {"width": 1920, "height": 1200},
        "device": "Dell Precision",
        "journeys": ["search_edge_cases", "trigger_errors", "admin_deep_dive", "error_recovery_flow"],
        "user_agent": None,
    },
]

# ─── Timing helpers ──────────────────────────────────────────────────────────

def delay_for(speed):
    """Return a random delay based on user speed."""
    ranges = {"fast": (0.5, 1.5), "medium": (1.5, 3.0), "slow": (2.5, 5.0)}
    lo, hi = ranges.get(speed, (1.0, 2.5))
    return random.uniform(lo, hi)


def ts():
    return datetime.now().strftime("%H:%M:%S")


# ─── Custom RUM action helper ───────────────────────────────────────────────

async def track_action(page, name, context=None):
    """Send a custom RUM action with optional context attributes."""
    ctx_js = ""
    if context:
        import json
        ctx_js = f", {json.dumps(context)}"
    try:
        await page.evaluate(f"""() => {{
            if (window.DD_RUM) {{
                window.DD_RUM.addAction("{name}"{ctx_js});
            }}
        }}""")
    except Exception:
        pass


async def track_error(page, message, source="custom"):
    """Send a custom RUM error."""
    try:
        await page.evaluate(f"""() => {{
            if (window.DD_RUM) {{
                window.DD_RUM.addError(new Error("{message}"), {{ source: "{source}" }});
            }}
        }}""")
    except Exception:
        pass


# ─── Journey Implementations ────────────────────────────────────────────────

async def journey_window_shop(page, persona):
    """Casual browsing — look but don't touch. Short session, low engagement."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    # Scroll the homepage slowly
    for scroll_pct in [25, 50, 75]:
        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pct / 100})")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.6)

    # Click 1-2 products, glance, go back
    for _ in range(random.randint(1, 2)):
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await track_action(page, "product_viewed", {"source": "window_shopping"})
        await asyncio.sleep(delay_for(persona["speed"]) * 0.5)
        await page.go_back()
        await page.wait_for_load_state("networkidle")


async def journey_bounce(page, persona):
    """Ultra-short session — land on homepage and leave immediately."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    # Look at page for 1-3 seconds then bail
    await asyncio.sleep(random.uniform(1.0, 3.0))
    await track_action(page, "session_bounced", {"time_on_page_ms": random.randint(1000, 3000)})


async def journey_full_purchase(page, persona):
    """Complete purchase flow: browse → add items → cart → checkout → order."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "shopping_session_started")

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    items_added = 0
    for _ in range(random.randint(1, 4)):
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Read product details (scroll down)
        await page.evaluate("window.scrollTo(0, 300)")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.4)

        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            items_added += 1
            await track_action(page, "add_to_cart", {"item_number": items_added})
            await asyncio.sleep(0.5)

        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.4)

    if items_added == 0:
        return

    # Go to cart
    cart_link = page.locator("a[href='/cart']")
    if await cart_link.count() > 0:
        await cart_link.first.click()
    else:
        await page.goto(f"{BASE_URL}/cart")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "cart_viewed", {"items_count": items_added})

    # Proceed to checkout
    subscribe_btn = page.locator("button", has_text="Subscribe")
    checkout_btn = page.locator("button", has_text="Checkout")
    if await subscribe_btn.count() > 0:
        await subscribe_btn.first.click()
    elif await checkout_btn.count() > 0:
        await checkout_btn.first.click()
    else:
        await page.goto(f"{BASE_URL}/checkout")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Fill email and submit
    email_input = page.locator("input[type='email']")
    if await email_input.count() > 0:
        # Type email character by character for realistic RUM keystroke tracking
        await email_input.click()
        for char in persona["email"]:
            await email_input.press(char)
            await asyncio.sleep(random.uniform(0.03, 0.12))
        await asyncio.sleep(0.5)

        submit_btn = page.locator("button[type='submit']")
        if await submit_btn.count() > 0:
            await track_action(page, "checkout_submitted", {"email": persona["email"]})
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))


async def journey_search_and_buy(page, persona):
    """Search for something specific, find it, buy it. Goal-oriented session."""
    queries = ["APM", "monitoring", "security", "logs", "profiler", "RUM",
               "cloud", "database", "incident", "synthetics"]

    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    q = random.choice(queries)
    search_input = page.locator("input[placeholder*='Search']")
    if await search_input.count() > 0:
        await search_input.click()
        # Type search query with realistic typing speed
        for char in q:
            await search_input.press(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        await asyncio.sleep(0.8)  # Wait for search results
        await track_action(page, "search_executed", {"query": q})
    else:
        await page.goto(f"{BASE_URL}/?q={q}")
        await page.wait_for_load_state("networkidle")

    await asyncio.sleep(delay_for(persona["speed"]))

    # Click first result
    cards = page.locator("a[href^='/product/']")
    if await cards.count() > 0:
        await cards.first.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Add to cart and buy
        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            await track_action(page, "search_result_added_to_cart", {"query": q})
            await asyncio.sleep(0.5)

            await page.goto(f"{BASE_URL}/cart")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))

            # Try to checkout
            subscribe_btn = page.locator("button", has_text="Subscribe")
            checkout_btn = page.locator("button", has_text="Checkout")
            if await subscribe_btn.count() > 0:
                await subscribe_btn.first.click()
            elif await checkout_btn.count() > 0:
                await checkout_btn.first.click()
            else:
                await page.goto(f"{BASE_URL}/checkout")
            await page.wait_for_load_state("networkidle")

            email_input = page.locator("input[type='email']")
            if await email_input.count() > 0:
                await email_input.fill(persona["email"])
                await asyncio.sleep(0.5)
                submit_btn = page.locator("button[type='submit']")
                if await submit_btn.count() > 0:
                    await submit_btn.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(delay_for(persona["speed"]))


async def journey_search_browse(page, persona):
    """Exploratory searching — multiple queries, browsing results."""
    queries = ["APM", "monitoring", "security", "logs", "profiler", "rum",
               "cloud", "database", "incident", "synthetics", "nonexistent_xyz"]

    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    for q in random.sample(queries, random.randint(2, 5)):
        await page.goto(f"{BASE_URL}/?q={q}")
        await page.wait_for_load_state("networkidle")
        await track_action(page, "search_executed", {"query": q})
        await asyncio.sleep(delay_for(persona["speed"]))

        cards = page.locator("a[href^='/product/']")
        if await cards.count() > 0 and random.random() > 0.3:
            await cards.first.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))
            await page.go_back()
            await page.wait_for_load_state("networkidle")


async def journey_trigger_errors(page, persona):
    """Deliberately visit broken pages and trigger JS errors."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Visit products that trigger backend errors (stale cache: %3, feature flag: %7)
    error_products = [3, 7, 13, 17]
    for pid in random.sample(error_products, random.randint(2, len(error_products))):
        try:
            await page.goto(f"{BASE_URL}/product/{pid}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))
        except Exception:
            pass

    # Visit products that trigger frontend errors (price feed: %5, long task: %7)
    frontend_error_products = [5, 10, 14, 15]
    for pid in random.sample(frontend_error_products, random.randint(2, len(frontend_error_products))):
        try:
            await page.goto(f"{BASE_URL}/product/{pid}")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))
        except Exception:
            pass

    # Visit non-existent product
    try:
        await page.goto(f"{BASE_URL}/product/99999")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
    except Exception:
        pass

    # Inject realistic third-party SDK errors
    third_party_errors = [
        "ChunkLoadError: Loading chunk vendors-analytics failed (timeout after 30s). Check CDN availability.",
        "SecurityError: Blocked a frame with origin 'https://ads.tracker.com' from accessing a cross-origin frame.",
        "ResizeObserver loop completed with undelivered notifications — third-party widget overflow",
        "AbortError: The play() request was interrupted by a call to pause() — video ad conflict",
        "NotAllowedError: Permission denied to access property 'localStorage' — private browsing mode",
    ]
    for err_msg in random.sample(third_party_errors, random.randint(1, 3)):
        await page.evaluate(f"""() => {{
            setTimeout(() => {{ throw new Error("{err_msg}"); }}, {random.randint(200, 1000)});
        }}""")
        await asyncio.sleep(1.5)


async def journey_rage_click_session(page, persona):
    """Frustrated user rage-clicking on unresponsive elements."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(0.5)

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    # Visit a product and rage-click the add to cart button
    await cards.nth(random.randint(0, count - 1)).click()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(0.5)

    add_btn = page.locator("button", has_text="Add to cart")
    if await add_btn.count() > 0:
        # Rage click: 6-10 rapid clicks (RUM detects frustration signals)
        for _ in range(random.randint(6, 10)):
            await add_btn.first.click()
            await asyncio.sleep(random.uniform(0.04, 0.1))
        await track_action(page, "rage_click_detected", {"element": "add_to_cart_button"})

    await asyncio.sleep(1)

    # Go to checkout and rage-click submit without filling email
    await page.goto(f"{BASE_URL}/checkout")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(0.5)

    submit_btn = page.locator("button[type='submit']")
    if await submit_btn.count() > 0:
        for _ in range(random.randint(4, 8)):
            await submit_btn.first.click()
            await asyncio.sleep(random.uniform(0.05, 0.15))

    # Back-button mashing (frustration signal)
    for _ in range(random.randint(3, 6)):
        await page.go_back()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=2000)
        except Exception:
            break


async def journey_abandon_cart(page, persona):
    """Add items but leave at checkout — classic abandonment with hesitation."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "shopping_session_started")

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    items_added = 0
    for _ in range(random.randint(1, 3)):
        if count == 0:
            break
        idx = random.randint(0, count - 1)
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        add_btn = page.locator("button", has_text="Add to cart")
        if await add_btn.count() > 0:
            await add_btn.first.click()
            items_added += 1
            await asyncio.sleep(0.5)

        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")

    # Go to cart and stare at it
    await page.goto(f"{BASE_URL}/cart")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]) * 3)  # long hesitation

    # Navigate to checkout
    subscribe_btn = page.locator("button", has_text="Subscribe")
    checkout_btn = page.locator("button", has_text="Checkout")
    if await subscribe_btn.count() > 0:
        await subscribe_btn.first.click()
    elif await checkout_btn.count() > 0:
        await checkout_btn.first.click()
    else:
        await page.goto(f"{BASE_URL}/checkout")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Start typing email but abandon halfway
    email_input = page.locator("input[type='email']")
    if await email_input.count() > 0:
        partial = persona["email"][:random.randint(3, 8)]
        for char in partial:
            await email_input.press(char)
            await asyncio.sleep(random.uniform(0.08, 0.2))
        await asyncio.sleep(delay_for(persona["speed"]) * 2)  # hesitate

    await track_action(page, "cart_abandoned", {"items_count": items_added, "stage": "checkout_email"})
    # Abandon — go back to homepage
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")


async def journey_mobile_quick_buy(page, persona):
    """Mobile fast-buy: scroll, tap, buy."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Scroll down on mobile to see products
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(0.4)

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count == 0:
        return

    await cards.nth(random.randint(0, min(5, count - 1))).click()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Add to cart
    add_btn = page.locator("button", has_text="Add to cart")
    buy_btn = page.locator("button", has_text="Buy now")
    if await buy_btn.count() > 0:
        await buy_btn.first.click()
    elif await add_btn.count() > 0:
        await add_btn.first.click()
        await asyncio.sleep(0.5)
        await page.goto(f"{BASE_URL}/cart")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Quick checkout
    subscribe_btn = page.locator("button", has_text="Subscribe")
    checkout_btn = page.locator("button", has_text="Checkout")
    if await subscribe_btn.count() > 0:
        await subscribe_btn.first.click()
    elif await checkout_btn.count() > 0:
        await checkout_btn.first.click()
    else:
        await page.goto(f"{BASE_URL}/checkout")
    await page.wait_for_load_state("networkidle")

    email_input = page.locator("input[type='email']")
    if await email_input.count() > 0:
        await email_input.fill(persona["email"])
        await asyncio.sleep(0.3)
        submit_btn = page.locator("button[type='submit']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(delay_for(persona["speed"]))


async def journey_mobile_browse_and_bounce(page, persona):
    """Mobile user browsing casually then bouncing."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Quick scroll through products
    for _ in range(random.randint(2, 5)):
        await page.evaluate(f"window.scrollBy(0, {random.randint(200, 400)})")
        await asyncio.sleep(random.uniform(0.5, 1.5))

    # Maybe click one product
    if random.random() > 0.4:
        cards = page.locator("a[href^='/product/']")
        count = await cards.count()
        if count > 0:
            await cards.nth(random.randint(0, min(3, count - 1))).click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1.0, 3.0))

    await track_action(page, "mobile_bounce", {"scroll_depth": random.randint(20, 80)})


async def journey_mobile_scroll_heavy(page, persona):
    """Mobile user doing lots of scrolling — tests scroll tracking and long sessions."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Scroll up and down multiple times (simulates infinite scroll behavior)
    for _ in range(random.randint(5, 12)):
        direction = random.choice(["down", "down", "down", "up"])
        distance = random.randint(200, 600) if direction == "down" else -random.randint(100, 300)
        await page.evaluate(f"window.scrollBy(0, {distance})")
        await asyncio.sleep(random.uniform(0.3, 1.0))

    # Click a product from scroll position
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count > 0:
        await cards.nth(random.randint(0, count - 1)).click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

        # Scroll through product details
        for _ in range(4):
            await page.evaluate(f"window.scrollBy(0, {random.randint(100, 300)})")
            await asyncio.sleep(random.uniform(0.5, 1.2))


async def journey_admin_deep_dive(page, persona):
    """Power user exploring admin dashboard, running compute, reviewing stats."""
    await page.goto(f"{BASE_URL}/admin")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]) * 2)
    await track_action(page, "admin_dashboard_viewed")

    # Trigger compute endpoint (CPU spike)
    compute_btn = page.locator("button", has_text="Run")
    if await compute_btn.count() > 0:
        await compute_btn.first.click()
        await track_action(page, "admin_compute_triggered")
        await asyncio.sleep(delay_for(persona["speed"]) * 3)  # Wait for compute

    # Check orders page
    await page.goto(f"{BASE_URL}/orders")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]) * 1.5)
    await track_action(page, "orders_page_viewed")

    # Scroll through orders
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.5)

    # Back to admin for another look
    await page.goto(f"{BASE_URL}/admin")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))


async def journey_orders_review(page, persona):
    """User reviewing their order history."""
    await page.goto(f"{BASE_URL}/orders")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "orders_reviewed")

    # Scroll through order list
    for _ in range(random.randint(2, 5)):
        await page.evaluate("window.scrollBy(0, 200)")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.6)

    # Click on an order if there are links
    order_links = page.locator("a[href*='order']")
    if await order_links.count() > 0:
        await order_links.first.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))


async def journey_compare_products(page, persona):
    """Click through multiple products rapidly for comparison."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "comparison_started")

    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count < 2:
        return

    products_viewed = 0
    indices = random.sample(range(count), min(random.randint(4, 8), count))
    for idx in indices:
        await cards.nth(idx).click()
        await page.wait_for_load_state("networkidle")
        products_viewed += 1
        await asyncio.sleep(delay_for(persona["speed"]) * 0.5)
        await page.go_back()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(0.2)

    await track_action(page, "comparison_complete", {"products_compared": products_viewed})


async def journey_deep_browse(page, persona):
    """Extended session — browse homepage, search, view products, check recommendations."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Browse homepage products
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count > 0:
        for _ in range(random.randint(2, 4)):
            idx = random.randint(0, count - 1)
            await cards.nth(idx).click()
            await page.wait_for_load_state("networkidle")
            # Scroll through product page
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
            await asyncio.sleep(delay_for(persona["speed"]))
            await page.go_back()
            await page.wait_for_load_state("networkidle")

    # Do a search
    q = random.choice(["monitoring", "security", "logs", "cloud"])
    await page.goto(f"{BASE_URL}/?q={q}")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    # Check a search result
    cards = page.locator("a[href^='/product/']")
    if await cards.count() > 0:
        await cards.first.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))

    # Visit categories or recommendations (scroll to bottom of homepage)
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(delay_for(persona["speed"]))


async def journey_search_edge_cases(page, persona):
    """Search with weird/adversarial inputs."""
    edge_queries = [
        "",
        "a",
        "<script>alert(1)</script>",
        "'; DROP TABLE products;--",
        "x" * 500,
        "🐶💥🔥",
        "monitoring AND security OR logs",
        "price:<10",
        "../../../etc/passwd",
        "{{template_injection}}",
    ]

    for q in random.sample(edge_queries, random.randint(3, 6)):
        try:
            await page.goto(f"{BASE_URL}/?q={q}")
            await page.wait_for_load_state("networkidle")
            await track_action(page, "edge_case_search", {"query": q[:50]})
            await asyncio.sleep(delay_for(persona["speed"]) * 0.4)
        except Exception:
            pass


async def journey_error_recovery_flow(page, persona):
    """Hit an error, then try to recover — realistic user behavior after seeing an error."""
    # Hit a broken product
    pid = random.choice([3, 7, 13, 17])
    try:
        await page.goto(f"{BASE_URL}/product/{pid}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
    except Exception:
        pass

    # User sees error, clicks "Back to shop" or navigates home
    back_btn = page.locator("button", has_text="Back to shop")
    if await back_btn.count() > 0:
        await back_btn.first.click()
    else:
        await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))
    await track_action(page, "error_recovery", {"failed_product_id": pid})

    # Try a different product that works
    cards = page.locator("a[href^='/product/']")
    count = await cards.count()
    if count > 0:
        # Pick a safe product (not ending in 3, 5, or 7)
        safe_ids = [1, 2, 4, 6, 8, 9, 11, 12, 16, 18]
        await page.goto(f"{BASE_URL}/product/{random.choice(safe_ids)}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]))
        await track_action(page, "successful_recovery")

        # Maybe complete purchase after recovery
        if random.random() > 0.5:
            add_btn = page.locator("button", has_text="Add to cart")
            if await add_btn.count() > 0:
                await add_btn.first.click()
                await asyncio.sleep(0.5)


async def journey_multi_tab_browse(page, persona):
    """Open many product pages in rapid succession (tab hoarder behavior)."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(delay_for(persona["speed"]))

    for pid in random.sample(range(1, 19), min(10, 18)):
        await page.goto(f"{BASE_URL}/product/{pid}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(delay_for(persona["speed"]) * 0.3)

    await track_action(page, "tab_hoarding_session", {"pages_visited": 10})


# ─── Journey dispatcher ─────────────────────────────────────────────────────

JOURNEY_MAP = {
    "window_shop": journey_window_shop,
    "bounce": journey_bounce,
    "full_purchase": journey_full_purchase,
    "search_and_buy": journey_search_and_buy,
    "search_browse": journey_search_browse,
    "trigger_errors": journey_trigger_errors,
    "rage_click_session": journey_rage_click_session,
    "abandon_cart": journey_abandon_cart,
    "mobile_quick_buy": journey_mobile_quick_buy,
    "mobile_browse_and_bounce": journey_mobile_browse_and_bounce,
    "mobile_scroll_heavy": journey_mobile_scroll_heavy,
    "admin_deep_dive": journey_admin_deep_dive,
    "orders_review": journey_orders_review,
    "compare_products": journey_compare_products,
    "deep_browse": journey_deep_browse,
    "search_edge_cases": journey_search_edge_cases,
    "error_recovery_flow": journey_error_recovery_flow,
    "multi_tab_browse": journey_multi_tab_browse,
}

# ─── Session Runner ──────────────────────────────────────────────────────────

async def run_persona(playwright, persona, headless=True, loop_count=0):
    """Run a single persona's session in a dedicated browser context."""
    iteration = 0
    browser = await playwright.chromium.launch(headless=headless)

    try:
        while loop_count == 0 or iteration < loop_count:
            iteration += 1
            context = await browser.new_context(
                viewport=persona["viewport"],
                user_agent=persona.get("user_agent"),
            )
            page = await context.new_page()

            # Inject RUM user context with rich attributes
            await page.add_init_script(f"""
                window.__DD_USER__ = {{
                    id: "{persona['email']}",
                    name: "{persona['name']}",
                    email: "{persona['email']}",
                    role: "{persona['role']}",
                    plan: "{persona['plan']}",
                    company: "{persona['company']}",
                    company_size: "{persona['company_size']}",
                    device: "{persona['device']}"
                }};
            """)

            # Pick journey — cycle through persona's journey list with some randomization
            if random.random() < 0.15:
                # 15% chance of picking a random journey for variety
                journey_name = random.choice(list(JOURNEY_MAP.keys()))
            else:
                journey_name = persona["journeys"][iteration % len(persona["journeys"])]

            journey_fn = JOURNEY_MAP.get(journey_name, journey_window_shop)

            print(f"  [{ts()}] 🧑 {persona['name']:22s} | {journey_name:28s} | {persona['device']}")

            try:
                await journey_fn(page, persona)
            except Exception as e:
                print(f"  [{ts()}] ⚠️  {persona['name']:22s} | {journey_name} error: {type(e).__name__}: {str(e)[:80]}")

            await context.close()

            # Pause between sessions — varies by persona patience
            base_pause = random.uniform(3, 10)
            pause = base_pause * (1.5 - persona["patience"])  # impatient users come back faster
            await asyncio.sleep(max(2, pause))

    except asyncio.CancelledError:
        pass
    finally:
        await browser.close()


# ─── Main ────────────────────────────────────────────────────────────────────

async def main(num_users=3, headless=True, loops=0):
    print(f"\n{'='*70}")
    print(f"  🐕 Datadog RUM Load Generator")
    print(f"  Target:     {BASE_URL}")
    print(f"  Users:      {num_users} concurrent browsers")
    print(f"  Personas:   {len(PERSONAS)} available")
    print(f"  Journeys:   {len(JOURNEY_MAP)} types")
    print(f"  Headless:   {headless}")
    print(f"  Loops:      {'infinite' if loops == 0 else loops}")
    print(f"{'='*70}\n")

    async with async_playwright() as pw:
        selected = random.sample(PERSONAS, min(num_users, len(PERSONAS)))
        if num_users > len(PERSONAS):
            while len(selected) < num_users:
                extra = random.choice(PERSONAS).copy()
                extra["name"] = f"{extra['name']} (clone-{len(selected)})"
                extra["email"] = f"clone{len(selected)}@demo.com"
                selected.append(extra)

        print(f"  Active personas:")
        for p in selected:
            print(f"    • {p['name']:22s} ({p['role']:16s}) — {p['device']}")
        print()

        tasks = [
            asyncio.create_task(run_persona(pw, p, headless, loops))
            for p in selected
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RUM Load Generator")
    parser.add_argument("--users", type=int, default=3, help="Concurrent browser users (default: 3)")
    parser.add_argument("--headful", action="store_true", help="Show browser windows")
    parser.add_argument("--loops", type=int, default=0, help="Loops per user (0=infinite)")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        print(f"\n  🛑 Shutting down ({sig})...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, lambda s, f: shutdown(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: shutdown(s, f))

    try:
        loop.run_until_complete(main(args.users, not args.headful, args.loops))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("  ✅ All browsers closed.\n")
